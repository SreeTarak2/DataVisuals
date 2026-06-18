import logging
from collections.abc import AsyncGenerator
from typing import Any

import polars as pl

from agents.agent_utils import build_synthesis_snippets
from agents.base_agent import BaseAgent, Observation, ReActContext

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    """
    ReAct Agent for conversational data analysis.

    Initializes with an empty tool set - tools are resolved lazily.
    Maintains full backward compatibility with existing callers.
    """

    def __init__(self) -> None:
        super().__init__(tools={})

    def _select_tools(self) -> list[str]:
        return ["sql", "stats", "rag", "memory"]

    async def _process_result(
        self, observations: list[Observation], context: ReActContext
    ) -> dict[str, Any]:
        return {}

    async def _call_tool(
        self,
        tool_name: str,
        tool: Any,
        observations: list[Observation],
        context: ReActContext,
    ) -> tuple[dict[str, Any], str]:
        if tool_name == "sql":
            return await self._handle_sql(tool, observations, context)
        elif tool_name == "stats":
            return await self._handle_stats(tool, observations, context)
        elif tool_name == "rag":
            return await self._handle_rag(tool, observations, context)
        elif tool_name == "memory":
            return await self._handle_memory(tool, observations, context)
        return await super()._call_tool(tool_name, tool, observations, context)

    async def _handle_sql(
        self, sql_tool: Any, observations: list[Observation], context: ReActContext
    ) -> tuple[dict[str, Any], str]:
        df = context.df
        if df is None:
            return {
                "success": False,
                "error": "No DataFrame in context",
            }, "SQL requires df"

        result = await sql_tool.execute_query(
            query=context.query,
            df=df,
            dataset_id=context.dataset_id,
        )
        row_count = result.get("row_count", 0)
        return result, f"Executed SQL query, returned {row_count} rows"

    async def _handle_stats(
        self, stats_tool: Any, observations: list[Observation], context: ReActContext
    ) -> tuple[dict[str, Any], str]:
        from services.analysis.advanced_stats import (
            anomaly_detector,
            correlation_analyzer,
            effect_size_calculator,
            hypothesis_tester,
        )

        sql_obs = None
        for obs in reversed(observations):
            if obs.tool == "sql" and obs.success:
                sql_obs = obs
                break

        if sql_obs is None:
            return {
                "error": "Stats requires prior SQL observation"
            }, "Stats called without SQL result"

        data = sql_obs.result.get("data", [])
        df = pl.from_dicts(data) if data else pl.DataFrame()

        if df.is_empty():
            return {"error": "No data to analyze"}, "SQL returned empty result"

        stats_results = {
            "hypothesis_test": hypothesis_tester(df),
            "correlations": correlation_analyzer(df),
            "anomalies": anomaly_detector(df),
            "effect_sizes": effect_size_calculator(df),
        }
        return stats_results, f"Stats analysis complete: {len(stats_results)} types"

    async def _handle_rag(
        self, rag_tool: Any, observations: list[Observation], context: ReActContext
    ) -> tuple[dict[str, Any], str]:
        search_text = context.query
        for obs in reversed(observations):
            if obs.success:
                if obs.tool == "stats":
                    search_text = obs.reasoning_summary
                    break
                elif obs.tool == "sql":
                    summary = obs.result.get("summary")
                    if summary:
                        search_text = summary
                        break

        rag_results = await rag_tool.search_similar_queries(
            query=search_text,
            user_id=context.user_id,
            k=5,
        )
        return {
            "documents": rag_results
        }, f"Retrieved {len(rag_results)} similar documents"

    async def _handle_memory(
        self, memory_tool: Any, observations: list[Observation], context: ReActContext
    ) -> tuple[dict[str, Any], str]:
        finding_text = ""
        for obs in reversed(observations):
            if obs.success:
                finding_text = obs.reasoning_summary or ""
                if finding_text:
                    break

        if not finding_text:
            return {"error": "No finding to check"}, "Memory called without findings"

        surprisal, _ = await memory_tool.calculate_semantic_surprisal(
            context.user_id, finding_text
        )
        await memory_tool.add_belief(context.user_id, finding_text, context.dataset_id)

        is_novel = surprisal > 0.7
        return {
            "surprisal_score": surprisal,
            "is_novel": is_novel,
            "finding": finding_text,
        }, f"Novelty: surprisal={surprisal:.2f} ({'novel' if is_novel else 'familiar'})"

    async def _synthesize(
        self, query: str, observations: list[Observation], context: ReActContext
    ) -> str:
        if not observations:
            return "No data available to answer your question."

        snippets = build_synthesis_snippets(observations, max_chars=300)
        prompt = (
            f"You are a narrative assistant. The user asked: {query}\n\n"
            "Below are concise reasoning snippets and brief results from the agent's tools:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, human-facing summary of findings and recommended next steps."
        )

        try:
            from services.llm_router import llm_router

            resp = await llm_router.call(
                prompt=prompt,
                model_role="narrative_story",
                user_id=context.user_id,
                expect_json=False,
                max_tokens=512,
            )
        except Exception as e:
            logger.error(
                f"[SYNTHESIZE] Narrative model call failed: {e}", exc_info=True
            )
            return "Failed to produce a narrative summary."

        return resp.get("text") if isinstance(resp, dict) else str(resp)

    async def _synthesize_streaming(
        self, query: str, observations: list[Observation], context: ReActContext
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not observations:
            yield {"type": "error", "content": "No observations to synthesize."}
            return

        snippets = build_synthesis_snippets(observations, max_chars=300)
        prompt = (
            f"You are a narrative assistant. The user asked: {query}\n\n"
            "Below are concise reasoning snippets and brief results from the agent's tools:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, human-facing summary of findings and recommended next steps."
        )

        full = ""
        from services.llm_router import llm_router
        from services.retries.async_utils import retry_async

        async def call_stream():
            return llm_router.call_streaming(
                prompt=prompt,
                model_role="narrative_story",
                is_conversational=False,
                user_id=context.user_id,
            )

        try:
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
