"""
ProfileAgent — pure computation agent for dataset profiling and KPI specification.

Handles "What does the data look like?"
- Input: Polars DataFrame, dataset metadata
- Tools: profiler (profile_dataframe), classifier (classify)
- Output: DatasetProfile + PrimitiveSpec list
- No LLM needed — deterministic computation
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from agents.base_agent import AgentContext, BaseAgent, ToolResult

logger = logging.getLogger(__name__)


class ProfileAgent(BaseAgent):
    """
    Computes DatasetProfile and PrimitiveSpec list from a DataFrame.

    This agent uses the ReAct loop structure for consistency and future extensibility,
    but its tools (profiler, classifier) are pure computation — no LLM calls.
    """

    def _select_tools(self) -> list[str]:
        return ["profiler", "classifier"]

    async def _process_result(
        self, observations: list[ToolResult], context: AgentContext
    ) -> dict[str, Any]:
        profile_model = None
        specs = []

        for obs in observations:
            if not obs.success:
                continue
            result = obs.result or {}
            if "profile" in result:
                profile_model = result["profile"]
            if "specs" in result:
                specs = result["specs"]

        if profile_model is None:
            logger.warning("ProfileAgent: no profiler result found in observations")
            return {"profile": None, "specs": [], "error": "Profiling failed"}

        return {
            "profile": profile_model,
            "specs": specs,
            "row_count": profile_model.row_count
            if hasattr(profile_model, "row_count")
            else 0,
            "column_count": len(profile_model.columns)
            if hasattr(profile_model, "columns")
            else 0,
        }

    async def _call_tool(
        self,
        tool_name: str,
        tool: Any,
        observations: list[ToolResult],
        context: AgentContext,
    ) -> tuple[dict[str, Any], str]:
        if tool_name == "profiler":
            return await self._handle_profiler(tool, context)
        elif tool_name == "classifier":
            return await self._handle_classifier(tool, observations, context)
        return await super()._call_tool(tool_name, tool, observations, context)

    async def _handle_profiler(
        self, profiler_fn: Any, context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        df = context.df
        if df is None:
            return {"error": "No DataFrame in context"}, "Profiler requires df"

        try:
            if not isinstance(df, pl.DataFrame):
                return {
                    "error": f"Expected Polars DataFrame, got {type(df)}"
                }, "Invalid df type"

            profile = await profiler_fn(
                df=df,
                domain_signal=context.domain_signal,
                domain_confidence=context.domain_confidence,
            )

            return {
                "profile": profile
            }, f"Profiled {len(df)} rows x {len(df.columns)} columns"

        except Exception as e:
            logger.error(f"ProfileAgent profiler failed: {e}", exc_info=True)
            return {"error": str(e)}, f"Profiling failed: {e}"

    async def _handle_classifier(
        self, classifier_fn: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        profile_model = None
        for obs in reversed(observations):
            if obs.tool == "profiler" and obs.success:
                result = obs.result or {}
                profile_model = result.get("profile")
                break

        if profile_model is None:
            return {"specs": []}, "Classifier called without profiler result"

        try:
            specs = classifier_fn(profile_model)
            return {"specs": specs}, f"Generated {len(specs)} PrimitiveSpecs"

        except Exception as e:
            logger.error(f"ProfileAgent classifier failed: {e}", exc_info=True)
            return {"specs": [], "error": str(e)}, f"Classification failed: {e}"
