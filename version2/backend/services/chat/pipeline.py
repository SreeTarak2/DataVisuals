"""
Chat Pipeline — Unified Orchestrator
======================================

Single pipeline that replaces:
  - services/ai/ai_service.py (process_chat_message, process_chat_message_streaming)
  - services/ai/copilot_service.py (process_streaming)
  - services/copilot/orchestrator.py (partial)

Flow:
  1. Guards — off-topic detection (no LLM call)
  2. Context — load dataset, RAG, memory, privacy (parallel)
  3. Understand — query rewriting + intent detection
  4. Route — check routing (sql | metadata | conversational)
  5. Agent — ReAct loop via ChatAgent (tools: sql, stats, rag, memory)
  6. Synthesize — strong prompt + LLM call + quality gate
  7. Persist — save conversation + background tasks
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from agents.agent_utils import build_synthesis_snippets
from core.config import settings
from services.chat.context_loader import (
    load_context,
    context_manager,
)
from prompts.guards import check_off_topic, check_scope
from services.chat.cleaning_guard import (
    build_block_message,
    build_warning_note,
    classify_cleaning_state,
)
from services.chat.models import ChatResult, ContextPackage, GuardResult, QueryContext
from prompts.chat import (
    build_synthesis_prompt,
    check_response_quality,
    normalize_response_style,
    humanize_text,
)

logger = logging.getLogger(__name__)


class ChatPipeline:
    """
    Unified orchestrator for chat processing.

    Usage:
        pipeline = ChatPipeline()
        result = await pipeline.process(query, dataset_id, user_id)
        async for chunk in pipeline.process_streaming(query, dataset_id, user_id):
            ...
    """

    def __init__(self):
        self._agent = None
        self._initialized = False

    async def _ensure_agent(self):
        """Lazily initialize the ReAct agent."""
        if self._agent is None:
            from agents.chat.chat_agent import ChatAgent

            self._agent = ChatAgent()
        return self._agent

    # ── Non-Streaming Path ─────────────────────────────────────────

    async def process(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        archetype: Optional[str] = None,
        mode: str = "analyst",
        workspace_id: Optional[str] = None,
    ) -> ChatResult:
        """
        Process a non-streaming chat message end-to-end.

        Pipeline:
          1. Off-topic guard (no LLM call)
          2. Load context (dataset + RAG + memory + privacy, parallel)
          3. Scope guard (no LLM cost — query must reference data terms or known columns)
          4. Query understanding (intent + enrichment)
          5. Routing check (off-topic from semantic routing)
          6. Run ReAct agent (sql, stats, rag, memory)
          7. Build synthesis prompt → LLM call
          8. Quality gate → retry if needed
          9. Save conversation + background tasks
        """
        start_time = time.monotonic()
        original_query = query.strip()
        query = query.strip()

        # ── Step 1: Off-topic guard ──
        guard = check_off_topic(query)
        if guard.should_redirect:
            logger.info(f"[ChatPipeline] Guard blocked query: {guard.reason}")
            return ChatResult(
                response_text=guard.redirect_message,
                conversation_id=conversation_id,
            )

        # ── Step 2: Load context ──
        try:
            context_pkg = await load_context(
                query, dataset_id, user_id, conversation_id, workspace_id=workspace_id
            )
        except ValueError as e:
            return ChatResult(response_text=str(e), conversation_id=conversation_id)
        except Exception as e:
            logger.error(f"[ChatPipeline] Context load failed: {e}", exc_info=True)
            return ChatResult(
                response_text="I'm having trouble accessing your dataset. Please try again.",
                conversation_id=conversation_id,
            )

        # ── Step 3: Cleaning guard (Principle #0 — no analysis on dirty data) ──
        # Number-changing cleaning actions (drop/remove/merge) still pending
        # review → block and redirect to the Data Briefing. Label-only renames
        # pending → answer but append a note.
        cleaning = classify_cleaning_state(context_pkg.cleaning_manifest)
        if cleaning.block:
            logger.info(
                "[ChatPipeline] Cleaning guard blocked query: %d critical "
                "action(s) pending (cid=%s)",
                cleaning.pending_critical,
                context_pkg.conversation_id,
            )
            return ChatResult(
                response_text=build_block_message(cleaning),
                conversation_id=context_pkg.conversation_id,
                redirect_to="briefing",
                cleaning_pending_critical=cleaning.pending_critical,
            )

        # ── Step 3a: Scope guard (catches off-topic queries that slip past off-topic guard) ──
        scope = check_scope(query, dataset_id, column_names=context_pkg.columns)
        if scope.should_redirect:
            logger.info(f"[ChatPipeline] Scope guard blocked query: {scope.reason}")
            return ChatResult(
                response_text=scope.redirect_message,
                conversation_id=context_pkg.conversation_id,
            )

        # ── Step 3b: Apply stored correction rules (cross-session learning) ──
        # Rewrites "revenue" → "recognized revenue" per workspace-scoped rules
        # learned from past corrections, BEFORE query understanding so the
        # enriched query, agent, and synthesis all inherit the correction.
        corrections_applied: List[Dict[str, Any]] = []
        if workspace_id or user_id:
            try:
                from services.feedback.correction_rewriter import correction_rewriter

                rewritten, corrections_applied = await correction_rewriter.apply_corrections(
                    query, workspace_id or user_id
                )
                if corrections_applied:
                    logger.info(
                        f"[ChatPipeline] Applied {len(corrections_applied)} stored "
                        f"correction rule(s) to query"
                    )
                    query = rewritten
            except Exception as e:
                logger.warning(f"[ChatPipeline] Correction rewrite failed (non-critical): {e}")

        # ── Step 4: Query understanding ──
        query_ctx = await self._understand_query(query, context_pkg)

        # ── Step 4b: Upgrade RAG context with enriched query ──
        await self._upgrade_rag_with_enriched_query(query_ctx, context_pkg, dataset_id, user_id)

        # ── Step 5: Routing check (semantic) ──
        if query_ctx.routing == "conversational":
            logger.info(f"[ChatPipeline] Semantic routing blocked as conversational")
            return ChatResult(
                response_text=(
                    "I'm a specialized data analytics assistant. I can help with trends, "
                    "charts, forecasts, correlations, or insights from your dataset.\n\n"
                    'Try asking: "Show top products by revenue" or '
                    '"What is the sales trend over time?"'
                ),
                conversation_id=context_pkg.conversation_id,
                query_context=query_ctx,
            )

        # ── Step 5: Run ReAct agent ──
        agent = await self._ensure_agent()
        agent_query = query_ctx.enriched_query + self._comparison_agent_hint(query_ctx)
        agent_result = await agent.run(
            query=agent_query,
            dataset_id=dataset_id,
            user_id=user_id,
            schema=context_pkg.dataset_context_str,
        )
        observations = agent_result.get("observations", [])

        if agent_result.get("error"):
            logger.warning(f"[ChatPipeline] Agent error: {agent_result['error']}")

        # ── Step 6: Synthesis ──
        response_text = await self._synthesize(
            query=query_ctx.enriched_query,
            observations=observations,
            context_pkg=context_pkg,
            archetype=query_ctx.archetype,
            conversation_context=self._build_conversation_context(context_pkg.conversation_messages),
            comparison_resolution=query_ctx.comparison_resolution,
        )

        # ── Normalize response ──
        response_text = normalize_response_style(response_text)
        response_text = humanize_text(response_text)

        # ── Cleaning warning (label-only renames pending — answer + flag) ──
        if cleaning.has_warning:
            response_text += build_warning_note(cleaning)

        # ── Step 7: Quality gate (log only) ──
        quality = check_response_quality(response_text)
        if not quality["passed"]:
            logger.warning(
                f"[ChatPipeline] Quality issues: {'; '.join(quality['issues'])}"
            )

        # ── Step 8: Persist + background ──
        asyncio.create_task(
            self._save_and_background(
                conversation_id=context_pkg.conversation_id,
                user_id=user_id,
                dataset_id=dataset_id,
                user_message=original_query,
                ai_response=response_text,
                context_pkg=context_pkg,
                workspace_id=workspace_id,
            )
        )

        duration = (time.monotonic() - start_time) * 1000
        logger.info(
            f"[ChatPipeline] Processed in {duration:.0f}ms | "
            f"routing={query_ctx.routing} | archetype={query_ctx.archetype} | "
            f"quality={quality['passed']} | corrections={len(corrections_applied)}"
        )

        return ChatResult(
            response_text=response_text,
            conversation_id=context_pkg.conversation_id,
            query_context=query_ctx,
            quality_issues=quality["issues"],
            corrections_applied=corrections_applied,
        )

    # ── Streaming Path ─────────────────────────────────────────────

    async def process_streaming(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        archetype: Optional[str] = None,
        mode: str = "analyst",
        skip_persist: bool = False,
        workspace_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a streaming chat message end-to-end.

        Shares steps 1-5 with process(), then streams synthesis output.
        Quality gate runs at the end (log only — can't regenerate streaming).
        """
        original_query = query.strip()
        query = query.strip()

        # ── Step 1: Off-topic guard ──
        guard = check_off_topic(query)
        if guard.should_redirect:
            logger.info(f"[ChatPipeline] Guard blocked streaming query: {guard.reason}")
            yield {"type": "token", "content": guard.redirect_message}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        # ── Step 2: Load context ──
        try:
            context_pkg = await load_context(
                query, dataset_id, user_id, conversation_id, workspace_id=workspace_id
            )
        except ValueError as e:
            yield {"type": "token", "content": str(e)}
            yield {"type": "done", "conversation_id": conversation_id}
            return
        except Exception as e:
            logger.error(f"[ChatPipeline] Context load failed: {e}", exc_info=True)
            yield {"type": "token", "content": "I'm having trouble accessing your dataset."}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        # ── Step 3: Cleaning guard (Principle #0 — no analysis on dirty data) ──
        cleaning = classify_cleaning_state(context_pkg.cleaning_manifest)
        if cleaning.block:
            logger.info(
                "[ChatPipeline] Cleaning guard blocked streaming query: %d "
                "critical action(s) pending",
                cleaning.pending_critical,
            )
            yield {"type": "token", "content": build_block_message(cleaning)}
            yield {
                "type": "cleaning_redirect",
                "redirect_to": "briefing",
                "pending_critical": cleaning.pending_critical,
            }
            yield {"type": "done", "conversation_id": context_pkg.conversation_id}
            return

        # ── Step 3a: Scope guard (catches off-topic queries that slip past off-topic guard) ──
        scope = check_scope(query, dataset_id, column_names=context_pkg.columns)
        if scope.should_redirect:
            logger.info(f"[ChatPipeline] Scope guard blocked streaming query: {scope.reason}")
            yield {"type": "token", "content": scope.redirect_message}
            yield {"type": "done", "conversation_id": context_pkg.conversation_id}
            return

        # ── Step 3b: Apply stored correction rules (cross-session learning) ──
        if workspace_id or user_id:
            try:
                from services.feedback.correction_rewriter import correction_rewriter

                rewritten, applied = await correction_rewriter.apply_corrections(
                    query, workspace_id or user_id
                )
                if applied:
                    logger.info(
                        f"[ChatPipeline][Stream] Applied {len(applied)} stored "
                        f"correction rule(s) to query"
                    )
                    query = rewritten
            except Exception as e:
                logger.warning(f"[ChatPipeline] Correction rewrite failed (non-critical): {e}")

        yield {"type": "thinking_step", "label": "Understanding your question", "step": 1}

        # ── Step 4: Query understanding ──
        query_ctx = await self._understand_query(query, context_pkg)

        # ── Step 4b: Upgrade RAG context with enriched query ──
        await self._upgrade_rag_with_enriched_query(query_ctx, context_pkg, dataset_id, user_id)

        # ── Step 5: Routing check ──
        if query_ctx.routing == "conversational":
            yield {"type": "token", "content": (
                "I'm a specialized data analytics assistant. I can help with trends, "
                "charts, forecasts, correlations, or insights from your dataset.\n\n"
                'Try asking: "Show top products by revenue" or '
                '"What is the sales trend over time?"'
            )}
            yield {"type": "done", "conversation_id": context_pkg.conversation_id}
            return

        # ── Step 6: Run ReAct agent (streaming-aware) ──
        yield {"type": "thinking_step", "label": "Analyzing your data", "step": 2}

        agent = await self._ensure_agent()
        agent_query = query_ctx.enriched_query + self._comparison_agent_hint(query_ctx)
        agent_result = await agent.run(
            query=agent_query,
            dataset_id=dataset_id,
            user_id=user_id,
            schema=context_pkg.dataset_context_str,
        )
        observations = agent_result.get("observations", [])

        tools_used = agent_result.get("tools_used", [])
        if tools_used:
            yield {
                "type": "thinking_step",
                "label": f"Used: {', '.join(tools_used)}",
                "step": 3,
            }

        # ── Step 7: Stream synthesis ──
        response_text = ""
        async for chunk in self._synthesize_streaming(
            query=query_ctx.enriched_query,
            observations=observations,
            context_pkg=context_pkg,
            archetype=query_ctx.archetype,
            conversation_context=self._build_conversation_context(context_pkg.conversation_messages),
            comparison_resolution=query_ctx.comparison_resolution,
        ):
            if chunk.get("type") == "token":
                response_text += chunk.get("content", "")
            yield chunk

        # ── Normalize response (apply to full response) ──
        if response_text:
            response_text = normalize_response_style(response_text)
            response_text = humanize_text(response_text)

        # ── Cleaning warning (label-only renames pending — answer + flag) ──
        if cleaning.has_warning:
            note = build_warning_note(cleaning)
            response_text += note
            yield {"type": "token", "content": note}

        # ── Quality gate (log only — can't regen streaming) ──
        quality = check_response_quality(response_text)
        if not quality["passed"]:
            logger.warning(
                f"[ChatPipeline][Stream] Quality issues: {'; '.join(quality['issues'])}"
            )

        # ── Persist + background (unless skip_persist is True) ──
        if not skip_persist:
            asyncio.create_task(
                self._save_and_background(
                    conversation_id=context_pkg.conversation_id,
                    user_id=user_id,
                    dataset_id=dataset_id,
                    user_message=original_query,
                    ai_response=response_text,
                    context_pkg=context_pkg,
                    workspace_id=workspace_id,
                )
            )

        yield {"type": "done", "conversation_id": context_pkg.conversation_id}

    # ── Internal Pipeline Steps ────────────────────────────────────

    async def _upgrade_rag_with_enriched_query(
        self,
        query_ctx: QueryContext,
        context_pkg: ContextPackage,
        dataset_id: str,
        user_id: str,
    ) -> None:
        """
        After query understanding, re-run RAG retrieval with the enriched
        query for better chunk relevance. Runs synchronously (~20-50ms)
        before the agent starts, so both the agent and synthesis benefit
        from the improved context.
        """
        if not query_ctx.was_enriched:
            return
        if not context_pkg.dataset_metadata:
            return

        try:
            from services.chat.context_loader import get_rag_context

            enriched_rag = await get_rag_context(
                query=query_ctx.enriched_query,
                dataset_id=dataset_id,
                user_id=user_id,
                metadata=context_pkg.dataset_metadata,
            )
            if enriched_rag:
                context_pkg.rag_context = enriched_rag
                context_pkg.dataset_context_str = enriched_rag
                logger.debug(
                    "[ChatPipeline] Upgraded RAG context with enriched query "
                    f"({len(enriched_rag)} chars)"
                )
        except Exception as e:
            logger.warning(f"[ChatPipeline] Enriched RAG upgrade failed (non-critical): {e}")

    @staticmethod
    def _extract_date_range_days(context_pkg: ContextPackage) -> Optional[int]:
        """Best-effort date span from the loaded dataset metadata (for the
        comparison resolver's data-driven default)."""
        md = context_pkg.dataset_metadata or {}
        if md.get("date_range_days") is not None:
            return md.get("date_range_days")
        profile = md.get("profile")
        if isinstance(profile, dict) and profile.get("date_range_days") is not None:
            return profile.get("date_range_days")
        return None

    @staticmethod
    def _comparison_agent_hint(query_ctx: QueryContext) -> str:
        """
        A compact instruction appended to the agent's query when the user
        explicitly named a comparison ("vs last year" → the agent's SQL/stats
        must compute that baseline, not guess).
        """
        res = query_ctx.comparison_resolution or {}
        if res.get("source") == "explicit" and res.get("label"):
            return (
                f"\n\n[Comparison baseline: {res['label']} — "
                "ground your calculations in THIS comparison. "
                "Show the delta against it explicitly.]"
            )
        return ""

    async def _understand_query(
        self,
        query: str,
        context_pkg: ContextPackage,
    ) -> QueryContext:
        """Run query understanding with timeout and fallback."""
        try:
            from services.ai.query_rewrite import understand_query

            uq = await asyncio.wait_for(
                understand_query(
                    query,
                    dataset_context=context_pkg.dataset_context_str,
                    available_columns=context_pkg.columns,
                ),
                timeout=settings.UNDERSTAND_QUERY_TIMEOUT,
            )
            qc = QueryContext(
                original_query=uq.original_query,
                enriched_query=uq.enriched_query,
                what_i_understood=uq.what_i_understood,
                archetype=uq.archetype,
                routing=uq.routing,
                failure_mode=uq.failure_mode,
                needs_clarification=uq.needs_clarification,
                decision_at_stake=uq.decision_at_stake,
                was_enriched=uq.was_enriched,
            )
            # Resolve the comparison baseline the question asks for
            # (deterministic — see services/ai/comparison_resolver.py).
            from services.ai.comparison_resolver import resolve_comparison_period

            resolution = resolve_comparison_period(
                qc.original_query or query,
                self._extract_date_range_days(context_pkg),
            )
            qc.comparison_period = (
                resolution.comparison if resolution.source == "explicit" else None
            )
            qc.comparison_resolution = {
                "comparison": resolution.comparison,
                "source": resolution.source,
                "needs_clarification": resolution.needs_clarification,
                "label": resolution.label,
                "matched_phrase": resolution.matched_phrase,
            }
            return qc
        except asyncio.TimeoutError:
            logger.warning(f"Query understanding timed out — using raw query")
            return QueryContext(
                original_query=query,
                enriched_query=query,
                what_i_understood="",
                routing="sql",
            )
        except Exception as e:
            logger.warning(f"Query understanding failed: {e} — using raw query")
            return QueryContext(
                original_query=query,
                enriched_query=query,
                what_i_understood="",
                routing="sql",
            )

    def _build_conversation_context(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Build a compact conversation history string for context continuity.
        Shows the last 2 turns to avoid repetition without bloating the prompt.
        """
        if not messages or len(messages) < 2:
            return None
        recent = messages[-4:]  # Last 2 user+ai pairs
        parts = []
        for m in recent:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "ai") and content:
                prefix = "User asked:" if role == "user" else "You answered:"
                parts.append(f"{prefix} {content[:200]}")
        return "\n".join(parts) if parts else None

    async def _synthesize(
        self,
        query: str,
        observations: List[Any],
        context_pkg: ContextPackage,
        archetype: str = "analyst",
        conversation_context: Optional[str] = None,
        comparison_resolution: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt, call LLM, check quality, retry if needed."""
        if not observations:
            return "No data available to answer your question."

        snippets = build_synthesis_snippets(observations, max_chars=300)
        prompt = build_synthesis_prompt(
            query, snippets, archetype,
            conversation_context=conversation_context,
            comparison_resolution=comparison_resolution,
        )

        from llm.router import llm_router

        try:
            resp = await llm_router.call(
                prompt=prompt,
                model_role="narrative_story",
                user_id=context_pkg.conversation_id,
                expect_json=False,
                max_tokens=768,
            )
        except Exception as e:
            logger.error(f"[ChatPipeline] Synthesis LLM call failed: {e}", exc_info=True)
            return "I couldn't generate a summary for your data."

        response = resp.get("text") if isinstance(resp, dict) else str(resp)

        # ── Quality gate with retry ──
        quality = check_response_quality(response)
        if not quality["passed"]:
            logger.warning(
                f"[ChatPipeline] Quality failed: {'; '.join(quality['issues'])}"
            )
            # Retry once with fix instruction
            fix_prompt = prompt + (
                "\n\n## Quality Check Failed — Fix These Issues Before Responding\n"
                + "\n".join(f"- {issue}" for issue in quality["issues"])
                + "\n\nRewrite your response fixing ALL of the above issues. "
                "Follow the response rules strictly this time."
            )
            try:
                resp2 = await llm_router.call(
                    prompt=fix_prompt,
                    model_role="narrative_story",
                    user_id=context_pkg.conversation_id,
                    expect_json=False,
                    max_tokens=768,
                )
                response = resp2.get("text") if isinstance(resp2, dict) else str(resp2)
            except Exception:
                pass  # Use original response if retry fails

        return response

    async def _synthesize_streaming(
        self,
        query: str,
        observations: List[Any],
        context_pkg: ContextPackage,
        archetype: str = "analyst",
        conversation_context: Optional[str] = None,
        comparison_resolution: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream synthesis output. Quality gate logged at end."""
        if not observations:
            yield {"type": "token", "content": "No data available to answer your question."}
            return

        snippets = build_synthesis_snippets(observations, max_chars=300)
        prompt = build_synthesis_prompt(
            query, snippets, archetype,
            conversation_context=conversation_context,
            comparison_resolution=comparison_resolution,
        )

        from llm.router import llm_router
        from services.retries.async_utils import retry_async

        async def call_stream():
            return llm_router.call_streaming(
                prompt=prompt,
                model_role="narrative_story",
                is_conversational=False,
                user_id=context_pkg.conversation_id,
            )

        try:
            stream_gen = await retry_async(call_stream, attempts=3, base_delay=0.5)
            full = ""
            async for chunk in stream_gen:
                if chunk.get("type") == "token":
                    token = chunk.get("content", "")
                    full += token
                    yield {"type": "token", "content": token}
                elif chunk.get("type") == "error":
                    yield {"type": "error", "content": chunk.get("content", "")}
                    return
                elif chunk.get("type") == "done":
                    quality = check_response_quality(full)
                    if not quality["passed"]:
                        logger.warning(
                            f"[ChatPipeline][Stream] Quality: {'; '.join(quality['issues'])}"
                        )
                    yield {"type": "response_complete", "full_response": full}
                    return
        except Exception as e:
            logger.error(f"[ChatPipeline] Stream synthesis failed: {e}", exc_info=True)
            yield {"type": "error", "content": "Failed to generate streaming response."}

    # ── Persistence + Background Tasks ─────────────────────────────

    async def _save_and_background(
        self,
        conversation_id: str,
        user_id: str,
        dataset_id: str,
        user_message: str,
        ai_response: str,
        context_pkg: ContextPackage,
        workspace_id: Optional[str] = None,
    ) -> None:
        """
        Save conversation + run background tasks (fire-and-forget).

        Background tasks:
        - Memory extraction
        - Passive belief update
        - Response reflection (self-improvement loop)
        - Correction capture (implicit corrections → persistent rules)
        """
        try:
            from services.conversations.conversation_service import (
                load_or_create_conversation,
                save_conversation,
            )

            # Save conversation
            conv = await load_or_create_conversation(conversation_id, user_id, dataset_id)
            messages = conv.get("messages", [])

            # The user's message may be correcting the PREVIOUS AI answer —
            # capture it before appending the current turn.
            previous_ai_response = ""
            for m in reversed(messages):
                if m.get("role") == "ai" and m.get("content"):
                    previous_ai_response = m["content"]
                    break

            messages.append({"role": "user", "content": user_message})
            ai_message = {
                "role": "ai",
                "content": ai_response,
                "confidence": "ai_analysis",
            }
            messages.append(ai_message)
            await save_conversation(conv["_id"], messages)

            # Auto-name new conversations (fire-and-forget)
            if not conv.get("title") and len(conv.get("messages", [])) <= 2:
                asyncio.create_task(self._auto_name(str(conv["_id"]), user_id, user_message))

            # Run background tasks in parallel with 30s timeout each
            await self._run_background_tasks(
                user_id=user_id,
                dataset_id=dataset_id,
                query=user_message,
                ai_response=ai_response,
                conversation_id=str(conv["_id"]),
                workspace_id=workspace_id,
                previous_ai_response=previous_ai_response,
            )
        except Exception as e:
            logger.warning(f"[ChatPipeline] Save + background failed: {e}")

    async def _auto_name(self, conversation_id: str, user_id: str, query: str) -> None:
        """Auto-name a new conversation based on the first query."""
        try:
            from services.conversations.conversation_service import auto_name_conversation

            await auto_name_conversation(conversation_id, user_id, query)
        except Exception as e:
            logger.debug(f"[ChatPipeline] Auto-name failed (non-critical): {e}")

    async def _run_background_tasks(
        self,
        user_id: str,
        dataset_id: str,
        query: str,
        ai_response: str,
        conversation_id: str,
        workspace_id: Optional[str] = None,
        previous_ai_response: str = "",
    ) -> None:
        """Run background tasks: memory, belief update, reflection, correction capture."""
        if not ai_response or len(ai_response.strip()) < 20:
            return

        async def _task(name: str, coro):
            try:
                await asyncio.wait_for(coro, timeout=30.0)
                logger.debug(f"[ChatPipeline] Background task '{name}' completed")
            except asyncio.TimeoutError:
                logger.debug(f"[ChatPipeline] Background task '{name}' timed out")
            except Exception as e:
                logger.debug(f"[ChatPipeline] Background task '{name}' failed: {e}")

        tasks = []

        try:
            # Memory extraction
            from services.memory.memory_service import memory_service

            tasks.append(
                _task(
                    "memory_extraction",
                    memory_service.extract_and_store(query, ai_response, user_id, dataset_id),
                )
            )

            # Passive belief update
            tasks.append(
                _task(
                    "belief_update",
                    self._passive_belief_update(user_id, query, ai_response, dataset_id),
                )
            )

            # Response reflection
            tasks.append(
                _task(
                    "response_reflection",
                    self._reflect_on_response(
                        query=query,
                        ai_response=ai_response,
                        dataset_context="",
                        dataset_type="general",
                        user_id=user_id,
                        conversation_id=conversation_id,
                    ),
                )
            )

            # Correction capture — the previously-dead implicit correction path.
            # Detects "no, revenue is recognized revenue"-style messages and
            # persists them so future answers are corrected (cross-session).
            tasks.append(
                _task(
                    "correction_capture",
                    self._capture_correction_signals(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        dataset_id=dataset_id,
                        query=query,
                        previous_ai_response=previous_ai_response,
                        conversation_id=conversation_id,
                    ),
                )
            )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning(f"[ChatPipeline] Background task setup failed: {e}")

    async def _capture_correction_signals(
        self,
        user_id: str,
        workspace_id: Optional[str],
        dataset_id: str,
        query: str,
        previous_ai_response: str,
        conversation_id: str,
    ) -> None:
        """
        Background task: detect implicit corrections and persist them so they
        improve future answers (cross-session learning).

        Two persistence substrates are written:
          1. ``correction_rules`` (MongoDB)  → CorrectionRewriter rewrites
             future queries before understanding.
          2. ``beliefs`` (MongoDB)           → injected into QUIS prompts and
             metric definitions on future runs.
        Plus a ``signal_collector`` event for the analytics layer.

        Every step is guarded — a failure here must never affect the chat.
        """
        try:
            from services.feedback.event_logger import event_logger
            from services.feedback.signal_classifier import signal_classifier
            from services.feedback.context_store import context_store
            from services.learning.signal_collector import signal_collector
            from db.schemas_context import CorrectionScope

            ws = workspace_id or user_id
            text = (query or "").strip()
            if not text or not ws:
                return

            # ── Cheap gate: does this message look like a correction? ──
            is_correction_like = event_logger.detect_correction_phrase(text)
            has_semantic_pattern = bool(
                re.search(r"\b(means?|refers to|is defined as|should be)\b", text, re.I)
                or re.search(r"\b[a-z][a-z0-9_ ]+\s*=\s*[a-z]", text, re.I)
            )
            if not (is_correction_like or has_semantic_pattern):
                return

            # ── Path 1: deterministic term extraction → correction_rules ──
            extracted = await signal_classifier.detect_reusable_correction(
                user_id=user_id,
                workspace_id=ws,
                correction_text=text,
                original_response=previous_ai_response,
            )
            if extracted:
                scope = (
                    CorrectionScope.WORKSPACE
                    if extracted.get("is_metric_term") is True
                    else CorrectionScope.CONVERSATION
                )
                rule = await context_store.upsert_correction_rule(
                    original_term=extracted["original_term"],
                    corrected_term=extracted["corrected_term"],
                    interpretation=extracted["interpretation"],
                    scope=scope,
                    workspace_id=ws,
                    user_id=user_id,
                )
                if rule and rule.id:
                    try:
                        await context_store.increment_correction_count(ws, user_id)
                    except Exception:
                        pass
                    logger.info(
                        f"[CorrectionCapture] Stored rule: "
                        f"{extracted['original_term']} -> {extracted['corrected_term']} "
                        f"(scope={scope.value})"
                    )
                    # Enrich with metric semantic when the correction is a
                    # definition ("X means Y") → feeds metric_definition_store.
                    try:
                        semantic = await context_store.capture_semantic_from_correction(
                            rule_id=rule.id, query_context=text
                        )
                        if semantic:
                            logger.info(
                                f"[CorrectionCapture] Captured semantic for "
                                f"{semantic.metric_name}"
                            )
                    except Exception as e:
                        logger.debug(
                            f"[CorrectionCapture] Semantic capture failed (non-critical): {e}"
                        )

            # ── Path 2: LLM-based rule extraction → beliefs ──
            # Reliable for free-form corrections ("revenue should exclude refunds");
            # beliefs are already read back by QUIS + metric_definition_store.
            if dataset_id:
                try:
                    from db.database import get_database
                    from services.memory.belief_service import BeliefService

                    belief_service = BeliefService(get_database())
                    saved = await belief_service.extract_and_save(
                        user_id=user_id,
                        dataset_id=dataset_id,
                        user_message=text,
                        previous_ai_response=previous_ai_response,
                    )
                    if saved:
                        content = str(saved.get("content", ""))[:80]
                        logger.info(f"[CorrectionCapture] Saved belief rule: {content}")
                except Exception as e:
                    logger.debug(
                        f"[CorrectionCapture] Belief extraction failed (non-critical): {e}"
                    )

            # ── Analytics signal ──
            try:
                await signal_collector.record_correction(
                    user_id=user_id,
                    workspace_id=ws,
                    dataset_id=dataset_id or "",
                    original_query=(previous_ai_response or text)[:200],
                    correction_text=text,
                    source="chat_pipeline",
                )
            except Exception as e:
                logger.debug(f"[CorrectionCapture] Signal record failed (non-critical): {e}")

        except Exception as e:
            logger.debug(f"[CorrectionCapture] Correction capture failed (non-critical): {e}")

    async def _passive_belief_update(
        self, user_id: str, query: str, ai_response: str, dataset_id: str = None
    ):
        """Background task: passively update belief store from a chat interaction."""
        try:
            from agents.belief.belief_store import (
                get_belief_store,
                PassiveBeliefIngestion,
            )

            belief_store = get_belief_store()
            await PassiveBeliefIngestion.boost_related_beliefs(belief_store, user_id, query)
            await PassiveBeliefIngestion.auto_ingest_from_response(
                belief_store, user_id, ai_response, dataset_id
            )
        except Exception as e:
            logger.debug(f"[ChatPipeline] Belief update failed: {e}")

    async def _reflect_on_response(
        self,
        query: str,
        ai_response: str,
        dataset_context: str,
        dataset_type: str,
        user_id: str,
        conversation_id: str,
    ) -> None:
        """Fire-and-forget reflection for self-improvement loop."""
        try:
            from services.insight_reflection.reflector import insight_reflection_agent

            score = await insight_reflection_agent.reflect(
                user_query=query,
                ai_output=ai_response[:2000],
                schema_context=dataset_context[:800],
                dataset_type=dataset_type or "general",
                output_type="insight",
                user_id=user_id,
            )

            if score.overall_score < insight_reflection_agent.GOOD_THRESHOLD:
                adjustments = score.prompt_adjustments
                instruction = adjustments.get("instruction_add", "").strip()
                if instruction:
                    from services.insight_reflection.conversation_learner import (
                        conversation_learner,
                    )

                    await conversation_learner.add_adjustment(
                        conversation_id,
                        {
                            "instruction": instruction,
                            "temperature_change": adjustments.get("temperature_change", 0.0),
                            "add_examples": adjustments.get("add_examples", False),
                            "failure_modes": score.failure_modes,
                        },
                    )
        except Exception as e:
            logger.debug(f"[ChatPipeline] Reflection failed (non-critical): {e}")

    # ── Save Conversation (public, used by external routes) ────────

    async def save_conversation_message(
        self,
        conversation_id: str,
        user_id: str,
        dataset_id: str,
        user_message: str,
        ai_response: str,
        chart_config: Optional[Dict] = None,
        sql: Optional[str] = None,
        result_table: Optional[Dict] = None,
        follow_up_suggestions: Optional[List[str]] = None,
        show_follow_up_suggestions: bool = False,
        confidence: str = "ai_analysis",
        reasoning_trace: Optional[List[Dict]] = None,
    ):
        """Save a chat message to the conversation history manually."""
        try:
            from services.conversations.conversation_service import (
                load_or_create_conversation,
                save_conversation,
            )

            conv = await load_or_create_conversation(conversation_id, user_id, dataset_id)
            messages = conv.get("messages", [])

            messages.append({"role": "user", "content": user_message})

            ai_message = {
                "role": "ai",
                "content": ai_response,
                "confidence": confidence,
            }
            if chart_config:
                ai_message["chart_config"] = chart_config
            if sql:
                ai_message["sql"] = sql
            if result_table:
                ai_message["result_table"] = result_table
            if follow_up_suggestions:
                ai_message["follow_up_suggestions"] = follow_up_suggestions
                ai_message["show_follow_up_suggestions"] = show_follow_up_suggestions
            if reasoning_trace:
                ai_message["reasoning_trace"] = reasoning_trace

            messages.append(ai_message)
            await save_conversation(conv["_id"], messages)

            asyncio.create_task(
                self._run_background_tasks(
                    user_id=user_id,
                    dataset_id=dataset_id,
                    query=user_message,
                    ai_response=ai_response,
                    conversation_id=str(conv["_id"]),
                )
            )
        except Exception as e:
            logger.error(f"[ChatPipeline] Save conversation failed: {e}")


# Singleton
chat_pipeline = ChatPipeline()
