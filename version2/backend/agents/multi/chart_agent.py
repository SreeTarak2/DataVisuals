"""
ChartAgent — chart selection and recommendation agent.

Wraps ChartIntelligenceService (deterministic, rule-based) and ChartRecommender
(LLM-guided) into a single agent that implements the PipelineAgent protocol.

Uses ChartIntelligenceService.select_dashboard_charts as the primary path,
with ChartRecommender.recommend_charts as fallback for per-column recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.multi.orchestrator import PipelineContext

logger = logging.getLogger(__name__)


class ChartAgent:
    """
    Chart selection + recommendation agent.

    Implements the PipelineAgent protocol (run_pipeline). Reads profile, specs,
    and compute_results from ctx; writes charts list back to ctx.
    """

    async def run_pipeline(self, ctx: PipelineContext) -> PipelineContext:
        """
        Select charts for the pipeline results.

        Primary path: ChartIntelligenceService.select_dashboard_charts
        Fallback: ChartRecommender.recommend_charts for per-column recommendations.
        """
        if ctx.df is None:
            logger.warning("[ChartAgent] No DataFrame in context — skipping chart generation")
            ctx.errors.append("ChartAgent: no DataFrame provided")
            ctx.partial_failure = True
            return ctx

        try:
            from services.charts.chart_intelligence_service import (
                chart_intelligence_service,
            )
            from services.charts.chart_recommender import ChartRecommender

            column_metadata = self._build_column_metadata(ctx)
            stats = self._build_statistical_findings(ctx)

            cis_result = chart_intelligence_service.select_dashboard_charts(
                df=ctx.df,
                column_metadata=column_metadata,
                domain=ctx.domain_signal,
                domain_confidence=ctx.domain_confidence,
                statistical_findings=stats,
                data_profile={"row_count": len(ctx.df), "column_count": len(ctx.df.columns)},
                context="executive",
                stories=[],
                use_universal=True,
                use_llm_validation=False,
            )

            charts = cis_result.get("charts", [])
            if not charts:
                recommender = ChartRecommender()
                col_recommendations = recommender.recommend_charts(ctx.df)
                charts = self._convert_recommendations(col_recommendations)

            ctx.charts = charts
            logger.info(f"[ChartAgent] Selected {len(charts)} charts")

        except Exception as e:
            logger.warning(f"[ChartAgent] chart selection failed ({e})")
            ctx.errors.append(f"chart: {e}")
            ctx.partial_failure = True

        return ctx

    def _build_column_metadata(self, ctx: PipelineContext) -> list[dict]:
        """Derive column metadata from ctx.profile or ctx.df."""
        meta = []
        if ctx.df is not None:
            for col in ctx.df.columns:
                dtype = str(ctx.df.schema.get(col, "unknown"))
                meta.append({"name": col, "type": dtype})
        return meta

    def _build_statistical_findings(self, ctx: PipelineContext) -> dict[str, Any]:
        """Derive statistical findings from compute_results."""
        findings: dict[str, Any] = {"correlation_strength": 0.0}
        if ctx.compute_results:
            for result in ctx.compute_results:
                if hasattr(result, "current_value") and result.current_value is not None:
                    findings["has_numeric_values"] = True
                if hasattr(result, "time_col") and result.time_col:
                    findings["has_time_column"] = True
        return findings

    def _convert_recommendations(self, recommendations: list[dict]) -> list[dict]:
        """Convert ChartRecommender output to chart dict list."""
        charts = []
        for rec in recommendations:
            charts.append(
                {
                    "type": rec.get("chart_type", "bar"),
                    "columns": rec.get("columns", []),
                    "x_axis": rec.get("x_axis", ""),
                    "y_axis": rec.get("y_axis", ""),
                    "title": rec.get("title", "Chart"),
                    "reason": rec.get("reason", ""),
                }
            )
        return charts
