"""
BaseAgent — shared ReAct loop for all domain agents.

Extracts the core Reason → Act → Observe → Loop pattern from ChatAgent
into a generic, injectable base class. Subclasses override _select_tools()
and _process_result() to declare their domain-specific behaviour.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from agents.resilience.concurrency import agent_concurrency_limiter
from agents.resilience.correlation import get_correlation_id, set_correlation_id
from agents.resilience.token_budget import get_run_budget, return_run_budget
from agents.telemetry import tracer
from core.config import settings
from services.audit import audit_service
from services.cache.response_cache import response_cache
from services.prompt_injection_guard import sanitize_and_validate
from services.retries.async_utils import BreakerRegistry

logger = logging.getLogger(__name__)


class AgentContext(BaseModel):
    """Validated request-scoped context — replaces the old TypedDict."""

    query: str
    dataset_id: str
    user_id: str
    correlation_id: str = ""
    df: Any | None = None
    schema_str: str | None = None
    domain_signal: str = "general"
    domain_confidence: float = 0.5
    source_type: str = "file"

    class Config:
        arbitrary_types_allowed = True


class ToolResult(BaseModel):
    """A single tool execution result."""

    tool: str
    success: bool
    timestamp: str = ""
    error: str | None = None
    result: dict[str, Any] = {}
    reasoning_summary: str = ""

    class Config:
        arbitrary_types_allowed = True


class BaseAgent(ABC):
    """
    ReAct Agent: Reason → Act → Observe → Loop

    Provides the shared loop infrastructure. Subclasses must define:
    - _select_tools()  — which tools this agent uses
    - _process_result() — how to combine observations into domain output

    Tools are injected via constructor (not hardcoded singletons), enabling:
    - Multiple instances with different tool configurations
    - Easy mocking in tests
    - Clear dependency boundaries
    """

    MAX_ITERATIONS = 5

    def __init__(self, tools: dict[str, Any]) -> None:
        self._tools = tools
        logger.debug(f"{self.__class__.__name__} initialized with tools: {list(tools.keys())}")

    def _tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @abstractmethod
    def _select_tools(self) -> list[str]:
        """Return the list of tool names this agent uses."""
        raise NotImplementedError

    @abstractmethod
    async def _process_result(
        self, observations: list[ToolResult], context: AgentContext
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _record_audit(
        self,
        user_id: str | None,
        agent_type: str,
        dataset_id: str,
        query: str,
        status: str,
        duration_s: float,
        error: str | None = None,
        tools_used: list[str] | None = None,
        iterations: int = 0,
    ):
        """Fire-and-forget audit log entry for this agent run."""
        if not user_id:
            return
        asyncio.ensure_future(
            audit_service.log_agent_execution(
                user_id=user_id,
                agent_type=agent_type,
                dataset_id=dataset_id,
                query=query,
                status=status,
                duration_ms=duration_s * 1000,
                error=error,
                tools_used=tools_used,
                iterations=iterations,
            )
        )

    async def run(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        df: Any | None = None,
        schema: str | None = None,
    ) -> dict[str, Any]:
        # ── Prompt injection guard ─────────────────────────────────
        is_valid, reason, clean_query = sanitize_and_validate(query)
        if not is_valid:
            logger.warning(
                "[%s] Query rejected by injection guard: %s",
                self.__class__.__name__,
                reason,
            )
            return {
                "response": f"Query rejected: {reason}",
                "error": reason,
                "tools_used": [],
                "iterations": 0,
                "observations": [],
            }
        query = clean_query

        cid = set_correlation_id()
        self._budget = get_run_budget(self.__class__.__name__)
        _run_start = time.monotonic()

        # ── Enforce concurrency limit ──────────────────────────────
        if not await agent_concurrency_limiter.try_acquire(self.__class__.__name__):
            logger.warning(
                "[%s] Concurrency limit reached, rejecting (cid=%s)",
                self.__class__.__name__,
                cid[:8],
            )
            return_run_budget(self.__class__.__name__)
            self._record_audit(
                user_id,
                self.__class__.__name__,
                dataset_id,
                query,
                "rejected",
                time.monotonic() - _run_start,
                error="concurrency limit reached",
            )
            return {
                "response": "System is busy. Please try again shortly.",
                "error": "concurrency limit reached",
                "tools_used": [],
                "iterations": 0,
                "observations": [],
            }

        span_attrs = {
            "agent": self.__class__.__name__,
            "dataset_id": dataset_id,
            "user_id": user_id[:8] if user_id else None,
            "query_length": len(query),
            "correlation_id": cid[:8],
        }
        with tracer.start_as_current_span(
            f"agent.{self.__class__.__name__}.run", attributes=span_attrs
        ):
            context = AgentContext(
                query=query,
                dataset_id=dataset_id,
                user_id=user_id,
                correlation_id=cid,
                df=df,
                schema_str=schema,
            )
            try:
                # ── Total agent execution timeout ──────────────────
                run_timeout = settings.AGENT_RUN_TIMEOUT
                if run_timeout > 0:
                    async with asyncio.timeout(run_timeout):
                        observations = await self._run_loop(context)
                else:
                    observations = await self._run_loop(context)
            except TimeoutError:
                logger.error(
                    "[%s] Agent run timed out after %ds (cid=%s)",
                    self.__class__.__name__,
                    run_timeout,
                    cid[:8],
                )
                _duration = time.monotonic() - _run_start
                self._record_audit(
                    user_id,
                    self.__class__.__name__,
                    dataset_id,
                    query,
                    "timeout",
                    _duration,
                    error=f"timed out after {run_timeout}s",
                )
                return {
                    "response": "The request took too long and was cancelled. Try a simpler query.",
                    "error": f"agent run timed out after {run_timeout}s",
                    "tools_used": [],
                    "iterations": 0,
                    "observations": [],
                }
            finally:
                return_run_budget(self.__class__.__name__)
                agent_concurrency_limiter.release(self.__class__.__name__)

            try:
                domain_output = await self._process_result(observations, context)
            except Exception as e:
                logger.error(
                    f"[{self.__class__.__name__}] _process_result failed: {e}",
                    exc_info=True,
                )
                domain_output = {"error": str(e)}

            try:
                final_answer = await self._synthesize(query, observations, context)
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] _synthesize failed: {e}", exc_info=True)
                final_answer = "I couldn't synthesize a final answer."

            logger.debug(
                "[Budget] %s run complete — tokens=%d, cost=%.4fc",
                self.__class__.__name__,
                self._budget.tokens_used,
                self._budget.cost_cents,
            )

            _duration = time.monotonic() - _run_start
            _tools = [o.tool for o in observations if o.success]
            self._record_audit(
                user_id,
                self.__class__.__name__,
                dataset_id,
                query,
                "success",
                _duration,
                tools_used=_tools,
                iterations=len(observations),
            )

            return {
                "response": final_answer,
                "tools_used": _tools,
                "iterations": len(observations),
                "observations": [o.model_dump() for o in observations],
                **domain_output,
            }

    async def run_streaming(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        df: Any | None = None,
        schema: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        # ── Prompt injection guard ─────────────────────────────────
        is_valid, reason, clean_query = sanitize_and_validate(query)
        if not is_valid:
            logger.warning(
                "[%s] Streaming query rejected by injection guard: %s",
                self.__class__.__name__,
                reason,
            )
            yield {"type": "error", "content": f"Query rejected: {reason}"}
            return
        query = clean_query

        cid = set_correlation_id()
        self._budget = get_run_budget(self.__class__.__name__)

        # ── Enforce concurrency limit ──────────────────────────────
        _stream_acquired = await agent_concurrency_limiter.try_acquire(self.__class__.__name__)
        if not _stream_acquired:
            logger.warning(
                "[%s] Stream concurrency limit reached, rejecting (cid=%s)",
                self.__class__.__name__,
                cid[:8],
            )
            yield {"type": "error", "content": "System is busy. Please try again shortly."}
            return

        try:
            span_attrs = {
                "agent": self.__class__.__name__,
                "dataset_id": dataset_id,
                "user_id": user_id[:8] if user_id else None,
                "query_length": len(query),
                "correlation_id": cid[:8],
            }
            with tracer.start_as_current_span(
                f"agent.{self.__class__.__name__}.stream", attributes=span_attrs
            ):
                context = AgentContext(
                    query=query,
                    dataset_id=dataset_id,
                    user_id=user_id,
                    correlation_id=cid,
                    df=df,
                    schema_str=schema,
                )

                observations: list[ToolResult] = []
                step_timeout = max(settings.AGENT_LLM_TIMEOUT + 10, 60)

                for i in range(self.MAX_ITERATIONS):
                    yield {
                        "type": "thinking_step",
                        "label": f"Deciding next tool (iter {i + 1})",
                        "step": i + 1,
                    }

                    try:
                        async with asyncio.timeout(step_timeout):
                            decision = await self._reason(observations, context)
                    except TimeoutError:
                        logger.error(
                            "[%s] stream _reason timed out at iter %d (cid=%s)",
                            self.__class__.__name__,
                            i + 1,
                            cid[:8],
                        )
                        yield {"type": "error", "content": "Reasoning timed out."}
                        return
                    except Exception as e:
                        logger.error(
                            f"[{self.__class__.__name__} stream] _reason failed: {e}",
                            exc_info=True,
                        )
                        yield {"type": "error", "content": "Reasoning failed."}
                        return

                    if decision == "DONE":
                        break

                    try:
                        async with asyncio.timeout(step_timeout):
                            obs = await self._act(decision, observations, context)
                    except TimeoutError:
                        logger.error(
                            "[%s] stream _act timed out at iter %d (cid=%s)",
                            self.__class__.__name__,
                            i + 1,
                            cid[:8],
                        )
                        yield {"type": "error", "content": "Tool execution timed out."}
                        return
                    observations.append(obs)

                    yield {"type": "thinking_step", "label": f"Ran {obs.tool}", "step": i + 1}

                    if obs.tool == "memory" and obs.success:
                        break

                async for event in self._synthesize_streaming(query, observations, context):
                    yield event

                yield {
                    "type": "done",
                    "trace": {
                        "tools_used": [o.tool for o in observations if o.success],
                        "iterations": len(observations),
                    },
                }
        finally:
            return_run_budget(self.__class__.__name__)
            if _stream_acquired:
                agent_concurrency_limiter.release(self.__class__.__name__)

    async def _run_loop(self, context: AgentContext) -> list[ToolResult]:
        observations: list[ToolResult] = []

        for _ in range(self.MAX_ITERATIONS):
            try:
                decision = await self._reason(observations, context)
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] _reason failed: {e}", exc_info=True)
                break

            if decision == "DONE":
                break

            obs = await self._act(decision, observations, context)
            observations.append(obs)

            if obs.tool == "memory" and obs.success:
                break

        return observations

    async def _reason(self, observations: list[ToolResult], context: AgentContext) -> str:
        with tracer.start_as_current_span(f"agent.{self.__class__.__name__}.reason"):
            selected_tools = self._select_tools()
            schema_ctx = context.schema_str or "Schema not provided"
            tool_list_str = ", ".join(selected_tools)

            if not observations:
                prompt = (
                    "You are a planning model for a ReAct data agent.\n\n"
                    f"User question:\n{context.query}\n\n"
                    f"Dataset schema:\n{schema_ctx}\n\n"
                    f"Task: choose the minimal set of tools needed for the first step.\n"
                    f"Available tools: {tool_list_str}.\n"
                    "Return ONLY valid JSON in this format:\n"
                    '{"tools": ["<tool_name>"], "reason": "short explanation"}\n\n'
                    "Rules:\n"
                    "- Return an empty tools array if the question is unanswerable from data."
                )
                try:
                    response = await self._llm_call(
                        prompt=prompt,
                        model_role="intent_engine",
                        expect_json=True,
                        temperature=0.1,
                        max_tokens=256,
                    )
                except Exception as exc:
                    logger.warning(
                        "[REASON] Intent planner failed (%s); defaulting to first tool.",
                        exc,
                    )
                    return selected_tools[0] if selected_tools else "DONE"

                tools = []
                if isinstance(response, dict):
                    tools = response.get("tools") or response.get("tool") or []
                elif isinstance(response, list):
                    tools = response

                if isinstance(tools, str):
                    tools = [tools]

                for tool_name in tools:
                    if tool_name in selected_tools:
                        logger.debug("[REASON] First-turn planner selected → %s", tool_name)
                        return tool_name

                logger.debug("[REASON] First-turn planner returned no usable tools → DONE")
                return "DONE"

            observation_summary = self._build_observation_summary(observations)

            prompt = (
                "You are a reasoning model for a ReAct data agent.\n\n"
                f"User question:\n{context.query}\n\n"
                f"Dataset schema:\n{schema_ctx}\n\n"
                f"Observations so far:\n{observation_summary}\n\n"
                f"Task: decide the next single tool to call, or DONE if enough evidence exists.\n"
                f"Available tools: {tool_list_str}, DONE.\n"
                "Return ONLY one token.\n"
            )

            try:
                response = await self._llm_call(
                    prompt=prompt,
                    model_role="complex_analysis",
                    expect_json=False,
                    temperature=0.1,
                    max_tokens=32,
                )
            except Exception as exc:
                logger.warning("[REASON] Reasoning model failed (%s); defaulting to DONE.", exc)
                return "DONE"

            choice = str(response).strip().upper()
            for t in selected_tools + ["DONE"]:
                if choice == t.upper():
                    logger.debug("[REASON] Reasoning model selected → %s", t)
                    return t if t != "DONE" else "DONE"

            logger.debug("[REASON] Unrecognized response '%s' → DONE", choice)
            return "DONE"

    async def _act(
        self,
        tool_name: str,
        observations: list[ToolResult],
        context: AgentContext,
    ) -> ToolResult:
        span_attrs = {"tool": tool_name, "agent": self.__class__.__name__}
        with tracer.start_as_current_span(
            f"agent.{self.__class__.__name__}.act", attributes=span_attrs
        ):
            timestamp = datetime.now(UTC).replace(tzinfo=None).isoformat()

            breaker = None
            try:
                # ── Circuit breaker gate ────────────────────────────
                breaker = BreakerRegistry.get(f"tool:{tool_name}")
                if breaker and not breaker.is_allowed():
                    logger.warning(
                        "[ACT] %s/%s blocked by circuit breaker (%s)",
                        self.__class__.__name__,
                        tool_name,
                        breaker.state_name,
                    )
                    return ToolResult(
                        tool=tool_name,
                        success=False,
                        timestamp=timestamp,
                        error=f"circuit breaker open for {tool_name}",
                        result={},
                        reasoning_summary=f"Tool '{tool_name}' unavailable (circuit breaker open)",
                    )

                tool = self._tools.get(tool_name)
                if tool is None:
                    if breaker:
                        breaker.record_failure()
                    return ToolResult(
                        tool=tool_name,
                        success=False,
                        timestamp=timestamp,
                        error=f"Unknown tool: {tool_name}",
                        result={},
                        reasoning_summary=f"Tool '{tool_name}' not found in registry",
                    )

                result, reasoning_summary = await self._call_tool(
                    tool_name, tool, observations, context
                )

                if breaker:
                    breaker.record_success()
                return ToolResult(
                    tool=tool_name,
                    success=True,
                    timestamp=timestamp,
                    error=None,
                    result=result,
                    reasoning_summary=reasoning_summary,
                )

            except Exception as e:
                if breaker:
                    breaker.record_failure()
                logger.error(
                    f"[ACT] {self.__class__.__name__}/{tool_name} failed: {e}",
                    exc_info=True,
                )
                return ToolResult(
                    tool=tool_name,
                    success=False,
                    timestamp=timestamp,
                    error=str(e),
                    result={},
                    reasoning_summary=f"Tool '{tool_name}' execution exception: {str(e)[:100]}",
                )

    async def _call_tool(
        self,
        tool_name: str,
        tool: Any,
        observations: list[ToolResult],
        context: AgentContext,
    ) -> tuple[dict[str, Any], str]:
        handler_name = f"_handle_{tool_name}"
        handler = getattr(self, handler_name, None)
        if handler is not None:
            sig_params = handler.__code__.co_varnames[: handler.__code__.co_argcount]
            if "observations" in sig_params:
                return await handler(tool, observations, context)
            else:
                return await handler(tool, context)

        if callable(tool):
            result = await tool(context=context, observations=observations)
            return result, f"{tool_name} executed"

        return {"result": tool}, f"{tool_name} tool returned"

    async def _synthesize(
        self, query: str, observations: list[ToolResult], context: AgentContext
    ) -> str:
        with tracer.start_as_current_span(f"agent.{self.__class__.__name__}.synthesize"):
            if not observations:
                return "No data available to answer your question."

            snippets = self._build_synthesis_snippets(observations)
            prompt = (
                f"You are a narrative assistant. The user asked: {query}\n\n"
                "Below are concise reasoning snippets and brief results from the agent's tools:\n"
                + "\n".join(snippets)
                + "\n\nProvide a concise, human-facing summary of findings."
            )

            try:
                resp = await self._llm_call(
                    prompt=prompt,
                    model_role="narrative_story",
                    expect_json=False,
                    max_tokens=512,
                )
            except Exception as e:
                logger.error(f"[SYNTHESIZE] Narrative model call failed: {e}", exc_info=True)
                return "Failed to produce a narrative summary."

            if isinstance(resp, dict):
                return resp.get("text", "")
            return str(resp) if resp else ""

    async def _synthesize_streaming(
        self, query: str, observations: list[ToolResult], context: AgentContext
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not observations:
            yield {"type": "error", "content": "No observations to synthesize."}
            return

        snippets = self._build_synthesis_snippets(observations)
        prompt = (
            f"You are a narrative assistant. The user asked: {query}\n\n"
            "Below are concise reasoning snippets and brief results from the agent's tools:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, human-facing summary of findings."
        )

        full = ""

        async def call_stream():
            return self._llm_stream(
                prompt=prompt, model_role="narrative_story", user_id=context.user_id
            )

        try:
            from services.retries.async_utils import retry_async

            stream_gen = await retry_async(call_stream, attempts=3, base_delay=0.5)
            async for chunk in stream_gen:
                if chunk.get("type") == "token":
                    token = chunk.get("content", "")
                    full += token
                    yield {"type": "token", "content": token}
                elif chunk.get("type") == "error":
                    yield {"type": "error", "content": chunk.get("content", "")}
                    return
                elif chunk.get("type") == "done":
                    yield {"type": "response_complete", "full_response": full}
                    return
        except Exception as e:
            logger.error(f"[SYNTH_STREAM] streaming failed: {e}", exc_info=True)
            yield {"type": "error", "content": "Narrative streaming failed."}
            return

    async def _llm_call(
        self,
        prompt: str,
        model_role: str,
        expect_json: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs,
    ) -> Any:
        cache_key = prompt[:100]
        dataset_id = kwargs.get("dataset_id") or getattr(
            getattr(self, "_ctx", None), "dataset_id", None
        )

        # ── Semantic cache check ──────────────────────────────────────
        if dataset_id and model_role in ("narrative_story", "complex_analysis"):
            cached = response_cache.get(query=cache_key, dataset_id=dataset_id, mode=model_role)
            if cached is not None:
                logger.debug("[Cache] HIT for model_role=%s (dataset=%s)", model_role, dataset_id)
                return cached.get("response") if isinstance(cached, dict) else cached

        # ── Per-run token budget check ─────────────────────────────────
        budget = getattr(self, "_budget", None)
        if budget and not budget.can_proceed(estimated_tokens=max_tokens):
            logger.warning(
                "[Budget] %s run budget exhausted for %s (tokens_used=%d, max=%d)",
                self.__class__.__name__,
                model_role,
                budget.tokens_used,
                budget.max_tokens,
            )
            return {"error": "Agent run budget exhausted", "budget_exhausted": True}

        span_attrs = {
            "model_role": model_role,
            "expect_json": expect_json,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with tracer.start_as_current_span(f"llm.call.{model_role}", attributes=span_attrs):
            from llm.router import llm_router
            from services.retries.async_utils import retry_async

            cid_llm = get_correlation_id()

            async def _do_call():
                return await asyncio.wait_for(
                    llm_router.call(
                        prompt=prompt,
                        model_role=model_role,
                        expect_json=expect_json,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        correlation_id=cid_llm,
                        **kwargs,
                    ),
                    timeout=settings.AGENT_LLM_TIMEOUT,
                )

            result = await retry_async(_do_call, attempts=2, base_delay=1.0)

            if budget and isinstance(result, dict) and "error" not in result:
                budget.deduct(tokens=max_tokens, cost_cents=0.01)
            elif budget:
                budget.deduct(tokens=max_tokens // 2, cost_cents=0.005)

            # ── Store in cache on success ─────────────────────────────
            if dataset_id and model_role in ("narrative_story", "complex_analysis"):
                if isinstance(result, dict) and "error" not in result:
                    response_cache.set(
                        query=cache_key,
                        dataset_id=dataset_id,
                        response=result,
                        mode=model_role,
                    )
                    logger.debug("[Cache] SET for model_role=%s", model_role)

            return result

    async def _llm_stream(
        self,
        prompt: str,
        model_role: str,
        user_id: str = None,
        **kwargs,
    ) -> AsyncGenerator[dict[str, Any], None]:
        from agents.resilience.correlation import get_correlation_id
        from llm.router import llm_router

        async for chunk in llm_router.call_streaming(
            prompt=prompt,
            model_role=model_role,
            is_conversational=False,
            user_id=user_id,
            correlation_id=get_correlation_id(),
        ):
            yield chunk

    def _build_observation_summary(self, observations: list[ToolResult], max_items: int = 5) -> str:
        if not observations:
            return "No observations yet."
        lines = []
        for obs in observations[-max_items:]:
            status = "ok" if obs.success else "fail"
            detail = obs.error if (not obs.success and obs.error) else obs.reasoning_summary
            text = str(detail or "").replace("\n", " ").strip()
            line = f"- {obs.tool}: {status} - {text}"
            if len(line) > 120:
                line = line[:117] + "..."
            lines.append(line)
        return "\n".join(lines)

    def _build_synthesis_snippets(
        self, observations: list[ToolResult], max_chars: int = 300
    ) -> list[str]:
        snippets = []
        for obs in observations:
            if not obs.success:
                continue
            tool = str(obs.tool or "").upper()
            summary = str(obs.reasoning_summary or "").replace("\n", " ").strip()
            snippet = f"{tool}: {summary}" if summary else f"{tool}:"
            if len(snippet) > max_chars:
                snippet = snippet[: max_chars - 3] + "..."
            snippets.append(snippet)
        return snippets


# ── Backward-compatible aliases ─────────────────────────────────────────────────

Observation = ToolResult
ReActContext = AgentContext

AgentContext.model_rebuild()
