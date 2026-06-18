"""
Multi-Series Chart Generation Service
======================================
Main orchestrator for Phase 2 multi-series chart generation.

Pipeline:
    1. Ingest: Accept data + minimal user intent
    2. Recommend: Strategy router suggests best visualization
    3. Detect: Pattern detection router finds insights
    4. Render: Series strategy router creates chart
    5. Validate: Quality metrics + narrative grounding
    6. Return: Chart + insights + why explanation

Entry point for API layer and internal analyst workflows.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
import polars as pl
from datetime import datetime

logger = logging.getLogger(__name__)


class MultiSeriesChartService:
    """
    Main service for multi-series chart generation.

    Orchestrates:
    - Pattern detection
    - Strategy recommendation
    - Rendering
    - Validation
    - Narrative generation
    """

    def __init__(self):
        """Initialize sub-service routers."""
        self.pattern_router = None  # Initialized lazily
        self.series_router = None
        self.insights_service = None

    async def generate_chart(
        self,
        df: pl.DataFrame,
        metric_columns: List[str],
        x_column: str,
        title: str,
        analysis_intent: Optional[str] = None,
        time_indexed: bool = False,
        auto_strategy: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate multi-series chart end-to-end.

        Args:
            df: Input DataFrame
            metric_columns: List of metrics to visualize
            x_column: X-axis (time/category) column
            title: Chart title
            analysis_intent: Optional intent (trend, comparison, composition, etc.)
            time_indexed: If True, treat x_column as time series
            auto_strategy: If True, auto-select best strategy

        Returns:
            {
                "chart": {"data": [...], "layout": {...}},
                "spec": MultiSeriesViewSpec object,
                "patterns": [CrossSeriesPattern objects],
                "insights": [InsightObject],
                "quality_score": 0.85,
                "narrative": "Why we chose this visualization...",
                "timestamp": "2025-01-10T14:32:00"
            }

        Raises:
            ValueError: If data invalid or generation fails
        """
        from .series_strategy_router import series_strategy_router
        from .pattern_detection_router import pattern_detection_router
        from db.schemas_charts import MultiSeriesViewSpec, SeriesStrategy, AnalysisIntent

        logger.info(
            f"Generate chart: {title}, {len(metric_columns)} series, intent={analysis_intent}"
        )

        start_time = datetime.utcnow()

        try:
            # Step 1: Validate input
            self._validate_generation_input(df, metric_columns, x_column)

            # Step 2: Run pattern detection (parallel to prep)
            patterns = await pattern_detection_router.run_detection(
                df, metric_columns, x_column, time_indexed=time_indexed
            )

            # Step 3: Determine strategy
            if auto_strategy:
                strategy = await self._recommend_strategy(
                    df, metric_columns, analysis_intent, patterns
                )
            else:
                strategy = "overlay"  # Default fallback

            # Step 4: Build spec object
            spec = MultiSeriesViewSpec(
                title=title,
                chart_type_primary="scatter",  # Multi-series base
                chart_type_secondary=None,
                series_strategy=strategy,
                encoding={"x": x_column},
                y_roles=[{"column": col, "role": "series"} for col in metric_columns],
                analysis_intent=analysis_intent or "comparison",
                patterns=patterns,
                quality_score=0.5,  # Placeholder, will update after render
            )

            # Step 5: Render using strategy router
            chart_dict = await series_strategy_router.route_rendering(spec, df)

            # Step 6: Run validation & generate insights
            quality_score = await self._validate_quality(chart_dict, spec, df, metric_columns)

            narrative = await self._generate_narrative(spec, patterns, quality_score, strategy)

            # Step 7: Aggregate and return
            result = {
                "chart": chart_dict,
                "spec": spec,
                "patterns": patterns,
                "quality_score": quality_score,
                "narrative": narrative,
                "strategy_used": strategy,
                "render_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "timestamp": start_time.isoformat(),
            }

            logger.info(f"Chart generation complete: {quality_score:.2f} quality")
            return result

        except Exception as e:
            logger.error(f"Chart generation failed: {e}", exc_info=True)
            raise

    def _validate_generation_input(
        self, df: pl.DataFrame, metric_columns: List[str], x_column: str
    ) -> None:
        """Validate inputs before chart generation."""
        if df.is_empty():
            raise ValueError("DataFrame is empty")

        if len(metric_columns) < 2:
            raise ValueError("Multi-series requires at least 2 metrics")

        if not all(col in df.columns for col in metric_columns):
            missing = [c for c in metric_columns if c not in df.columns]
            raise ValueError(f"Metric columns not found: {missing}")

        if x_column not in df.columns:
            raise ValueError(f"X column not found: {x_column}")

        # Check numeric types
        for col in metric_columns:
            dtype = df.schema[col]
            if dtype not in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]:
                raise ValueError(f"Column {col} not numeric: {dtype}")

    async def _recommend_strategy(
        self,
        df: pl.DataFrame,
        metric_columns: List[str],
        analysis_intent: Optional[str],
        patterns: List[Dict[str, Any]],
    ) -> str:
        """
        Recommend best visualization strategy driven by detected patterns.

        Priority order:
        1. Panel suggestion (too many series / high cardinality) → facet/small_multiples
        2. Scale mismatch detected → dual_axis
        3. Explicit composition intent → stacked
        4. Explicit comparison of categories with 2+ cat dims → grouped
        5. One dominant series + rate/ratio series → combo
        6. Default → overlay
        """
        num_series = len(metric_columns)
        pattern_types = {p.get("pattern_type") for p in patterns}

        # 1. Faceting signal from PanelPatternDetector
        if "panel_suggestion" in pattern_types:
            for p in patterns:
                if p.get("pattern_type") == "panel_suggestion":
                    if p.get("metrics", {}).get("suggests_facet"):
                        # Use small_multiples for cleaner layout
                        return "small_multiples"

        # Fallback: too many series regardless of detector
        if num_series > 6:
            return "small_multiples"
        if num_series > 4:
            return "facet"

        # 2. Scale mismatch → dual axis
        if "scale_mismatch" in pattern_types:
            return "dual_axis"

        # Auto-detect scale mismatch: check if metrics have vastly different ranges
        if num_series >= 2:
            ranges = []
            for col in metric_columns:
                if col in df.columns and df[col].dtype in [
                    pl.Int32,
                    pl.Int64,
                    pl.Float32,
                    pl.Float64,
                ]:
                    col_min = df[col].min()
                    col_max = df[col].max()
                    if col_min is not None and col_max is not None and col_min != 0:
                        ranges.append(abs(col_max / col_min))
            if len(ranges) >= 2:
                max_range_ratio = max(ranges) / min(ranges) if min(ranges) > 0 else float("inf")
                if max_range_ratio > 100:
                    return "dual_axis"

        # 3. Composition intent → stacked
        if analysis_intent == "composition":
            return "stacked"

        # 4. Comparison across multiple categories → grouped bars
        if analysis_intent == "comparison":
            # Check if x-axis is categorical (non-numeric, non-date)
            if df.schema.get(df.columns[0]) in [pl.Utf8, pl.Categorical]:
                return "grouped"
            return "overlay"

        # 5. Combo: if intent is to show volume + rate together
        if analysis_intent == "diagnosis" and num_series == 2:
            return "combo"

        # 6. Default: overlay (same scale, few series, trend comparison)
        return "overlay"

    async def _validate_quality(
        self, chart_dict: Dict[str, Any], spec, df: pl.DataFrame, metric_columns: List[str]
    ) -> float:
        """
        Calculate quality score (0-1).

        Metrics:
        - Data mapped (0.2)
        - Readability (0.3)
        - Pattern clarity (0.3)
        - Performance (0.2)
        """
        score = 0.0

        try:
            # Data mapped
            data_traces = chart_dict.get("data", [])
            if len(data_traces) >= len(metric_columns) * 0.8:
                score += 0.2

            # Readability
            if len(data_traces) <= 5:
                score += 0.3
            elif len(data_traces) <= 10:
                score += 0.15

            # Pattern clarity
            if len(spec.patterns) > 0:
                score += 0.3

            # Performance (rows)
            if len(df) <= 5000:
                score += 0.2
            elif len(df) <= 10000:
                score += 0.1

            return min(score, 1.0)  # Cap at 1.0

        except Exception as e:
            logger.warning(f"Quality validation error: {e}")
            return 0.5

    async def _generate_narrative(
        self, spec, patterns: List[Dict[str, Any]], quality_score: float, strategy: str
    ) -> str:
        """
        Generate narrative explaining chart choice.

        Format:
        "We chose [STRATEGY] to show [INTENT].
         [PATTERN INSIGHTS].
         Quality: [SCORE]"
        """
        intent = spec.analysis_intent or "comparison"

        intent_text = {
            "trend": "track trends over time",
            "comparison": "compare metrics directly",
            "composition": "show part-to-whole relationships",
            "relationship": "reveal correlations",
            "distribution": "examine distributions",
            "ranking": "rank performance",
            "diagnosis": "diagnose anomalies",
        }.get(intent, "analyze data")

        narrative = f"We chose {strategy.upper()} visualization to {intent_text}. "

        if patterns:
            pattern_types = set(p.get("pattern_type", "unknown") for p in patterns)
            narrative += f"Detected patterns: {', '.join(pattern_types)}. "

        narrative += f"Quality: {quality_score:.0%}."

        return narrative


# Singleton instance for use in API
multi_series_chart_service = MultiSeriesChartService()
