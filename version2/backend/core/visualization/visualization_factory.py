"""
VIS Factory
===========
Factory for creating VIS objects from various input types.

Sources:
- ChartConfig (dashboard config) → VIS
- ChartItemV2 (LLM-optimized config from prompts.py) → VIS
- chart_recommender output → VIS
- chart_intelligence_service output → VIS
- Raw dict (from LLM or API) → VIS (with validation)

Single source of truth for VIS creation — ensures all VIS objects
are consistent, validated, and carry proper metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import logging
import uuid

from .visualization_schema import (
    VIS,
    VISDataSeries,
    VISDataSeriesType,
    VISAxis,
    VISAxisType,
    VISAxisFormat,
    VISInteraction,
    VISAnalytics,
    VISNarrative,
    VISSeriesCollection,
    VIFacetConfig,
    VISVariantConfig,
    SeriesStrategyType,
    AnalysisIntentType,
)
from .visualization_validator import VISValidator

logger = logging.getLogger(__name__)


class VISFactory:
    """
    Factory for creating VIS objects.

    Centralizes VIS creation logic so every producer follows the same pattern.
    """

    def __init__(self, strict: bool = True):
        self.validator = VISValidator(strict=strict)

    # ── Primary factory method ──────────────────────────────────────

    def create(
        self,
        visualization_type: Union[str, VISDataSeriesType],
        title: str,
        series: List[VISDataSeries],
        *,
        source: str = "factory",
        analysis_intent: Optional[Union[str, AnalysisIntentType]] = None,
        data_mapping: Optional[Dict[str, Any]] = None,
        aggregation: str = "sum",
        axes: Optional[Dict[str, Union[Dict, VISAxis]]] = None,
        interaction: Optional[Union[Dict, VISInteraction]] = None,
        analytics: Optional[Union[Dict, VISAnalytics]] = None,
        narrative: Optional[Union[Dict, VISNarrative]] = None,
        series_strategy: Optional[Union[str, SeriesStrategyType]] = None,
        series_collection: Optional[Union[Dict, VISSeriesCollection]] = None,
        facet_config: Optional[Union[Dict, VIFacetConfig]] = None,
        point_intelligence: Optional[Dict] = None,
        variant_config: Optional[Union[Dict, VISVariantConfig]] = None,
        color_hint: Optional[str] = None,
        theme: str = "dark",
        metadata: Optional[Dict[str, Any]] = None,
        description: str = "",
        vis_id: Optional[str] = None,
        validate: bool = True,
    ) -> VIS:
        """
        Create a validated VIS object.

        Args:
            visualization_type: Primary chart type
            title: Chart title
            series: List of data series
            source: Producer identifier for debugging
            analysis_intent: What analytical question this answers
            data_mapping: Column-to-role mapping
            aggregation: Aggregation function applied
            axes: Axis specifications by role
            interaction: Interaction settings
            analytics: Statistical overlay config
            narrative: Natural language explanation
            series_strategy: Multi-series composition strategy
            series_collection: Grouped series representation
            facet_config: Faceted layout config
            point_intelligence: Per-point statistics
            color_hint: Color strategy hint
            theme: Visual theme hint
            metadata: Free-form metadata
            description: Chart description
            vis_id: Optional ID (auto-generated if not provided)
            validate: If True, validate before returning

        Returns:
            Validated VIS object

        Raises:
            ValueError: If validation fails and strict=True
        """
        # Normalize enum types
        if isinstance(visualization_type, str):
            visualization_type = self._parse_viz_type(visualization_type)

        if isinstance(analysis_intent, str):
            try:
                analysis_intent = AnalysisIntentType(analysis_intent.lower())
            except ValueError:
                analysis_intent = AnalysisIntentType.UNKNOWN

        if isinstance(series_strategy, str):
            try:
                series_strategy = SeriesStrategyType(series_strategy.lower())
            except ValueError:
                series_strategy = SeriesStrategyType.NONE

        # Normalize dicts to models
        if isinstance(interaction, dict):
            interaction = VISInteraction(**interaction)
        if isinstance(analytics, dict):
            analytics = VISAnalytics(**analytics)
        if isinstance(narrative, dict):
            narrative = VISNarrative(**narrative)
        if isinstance(series_collection, dict):
            series_collection = VISSeriesCollection(**series_collection)
        if isinstance(facet_config, dict):
            facet_config = VIFacetConfig(**facet_config)
        if isinstance(variant_config, dict):
            variant_config = VISVariantConfig(**variant_config)

        # Normalize axes
        normalized_axes: Dict[str, VISAxis] = {}
        if axes:
            for role, axis in axes.items():
                if isinstance(axis, dict):
                    normalized_axes[role] = VISAxis(**axis)
                elif isinstance(axis, VISAxis):
                    normalized_axes[role] = axis

        # Ensure interaction/analytics/narrative defaults
        interaction = interaction or VISInteraction()
        analytics = analytics or VISAnalytics()
        narrative = narrative or VISNarrative()

        # Build VIS
        vis = VIS(
            id=vis_id or f"vis_{uuid.uuid4().hex[:12]}",
            version="1.0",
            visualization_type=visualization_type,
            analysis_intent=analysis_intent or AnalysisIntentType.UNKNOWN,
            title=title,
            description=description,
            data_mapping=data_mapping or {},
            aggregation=aggregation,
            series=series,
            series_strategy=series_strategy or SeriesStrategyType.NONE,
            series_collection=series_collection,
            facet_config=facet_config,
            axes=normalized_axes,
            interaction=interaction,
            analytics=analytics,
            narrative=narrative,
            point_intelligence=point_intelligence,
            variant_config=variant_config,
            color_hint=color_hint,
            theme=theme,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            source=source,
        )

        if validate:
            if not self.validator.is_valid(vis):
                error = self.validator.first_error(vis)
                logger.warning(f"VIS validation failed: {error}")
                if self.validator.strict:
                    raise ValueError(f"VIS validation failed: {error}")
                # Non-strict: return with warning

        return vis

    # ── From chart config dict ──────────────────────────────────────

    @classmethod
    def from_chart_config(cls, config: Dict[str, Any], **kwargs) -> VIS:
        """
        Create VIS from a chart configuration dict.

        Handles multiple config formats:
        - ChartConfig-like: {chart_type, columns, aggregation, group_by}
        - ChartItemV2-like: {type, x, y, group_by, aggregation, title_insight, ...}
        - LLM output: {type, x, y, aggregation, group_by, title}
        """
        viz_type = cls._parse_viz_type(
            config.get("type") or config.get("chart_type") or "bar"
        )
        title = (
            config.get("title_insight")
            or config.get("title")
            or f"{viz_type.value} visualization"
        )

        # Extract columns
        columns = config.get("columns", [])
        x_col = config.get("x", columns[0] if columns else None)
        y_col = config.get("y", columns[1] if len(columns) > 1 else None)
        group_by = config.get("group_by")

        # Build data mapping
        data_mapping = {"x": x_col, "y": y_col or []}
        if isinstance(y_col, str):
            data_mapping["y"] = [y_col]
        if group_by:
            data_mapping["group_by"] = group_by

        # Build axes
        axes = {}
        if x_col:
            axes["x"] = VISAxis(field=x_col, axis_type=VISAxisType.CATEGORY)
        if y_col:
            axes["y"] = VISAxis(field=y_col if isinstance(y_col, str) else (y_col[0] if y_col else None))

        # Build narrative from insight fields
        narrative = {}
        for field in ("insight_annotation", "reading_guide", "badge_type"):
            if config.get(field):
                if field == "insight_annotation":
                    narrative["insight_annotation"] = config[field]
                elif field == "reading_guide":
                    narrative["reading_guide"] = config[field]
                elif field == "badge_type":
                    narrative["badge_type"] = config[field]

        # Build analytics
        analytics = {}
        if config.get("show_reference_line"):
            ref_type = config.get("reference_type", "mean")
            analytics["show_average"] = ref_type == "mean"
            analytics["show_median"] = ref_type == "median"
        if config.get("highlight_outliers"):
            analytics["show_anomalies"] = True

        # Build interaction
        interaction = {}
        if config.get("drill_down_column"):
            interaction["drilldown_enabled"] = True
            interaction["drill_path"] = [config["drill_down_column"]]

        return cls().create(
            visualization_type=viz_type,
            title=title,
            series=[],  # No data — caller must hydrate
            source="chart_config",
            analysis_intent=config.get("diversity_role"),
            data_mapping=data_mapping,
            aggregation=config.get("aggregation", "sum"),
            axes=axes,
            interaction=interaction or None,
            analytics=analytics or None,
            narrative=narrative or None,
            series_strategy=cls._detect_strategy(viz_type),
            color_hint=config.get("color_strategy"),
            metadata={
                "source_config": config,
                "span": config.get("span", 1),
                "position": config.get("position", "supporting"),
            },
            **kwargs,
        )

    # ── Factory for error/informational VIS ─────────────────────────

    @classmethod
    def error_vis(
        cls, message: str, title: str = "Chart Error", viz_type: str = "bar"
    ) -> VIS:
        """Create a minimal VIS indicating an error state."""
        return cls().create(
            visualization_type=viz_type,
            title=title,
            series=[],
            source="error",
            narrative={"description": message, "headline": title},
            validate=False,
        )

    @classmethod
    def empty_vis(cls, title: str = "No Data") -> VIS:
        """Create a minimal VIS for empty states."""
        return cls().create(
            visualization_type="bar",
            title=title,
            series=[],
            source="empty",
            description="No data available for this visualization",
            validate=False,
        )

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _parse_viz_type(raw: str) -> VISDataSeriesType:
        """Parse a string to VISDataSeriesType with normalization."""
        if isinstance(raw, VISDataSeriesType):
            return raw
        normalized = raw.lower().replace("_chart", "").replace("_plot", "").strip()
        try:
            return VISDataSeriesType(normalized)
        except ValueError:
            logger.warning(f"Unknown visualization type '{raw}', defaulting to 'bar'")
            return VISDataSeriesType.BAR

    @staticmethod
    def _detect_strategy(viz_type: VISDataSeriesType) -> SeriesStrategyType:
        """Infer series strategy from visualization type."""
        strategy_map = {
            VISDataSeriesType.GROUPED_BAR: SeriesStrategyType.GROUPED,
            VISDataSeriesType.STACKED_BAR: SeriesStrategyType.STACKED,
            VISDataSeriesType.STACKED_AREA: SeriesStrategyType.STACKED,
            VISDataSeriesType.MULTI_LINE: SeriesStrategyType.OVERLAY,
            VISDataSeriesType.DUAL_AXIS: SeriesStrategyType.DUAL_AXIS,
            VISDataSeriesType.COMBO: SeriesStrategyType.COMBO,
            VISDataSeriesType.FACET: SeriesStrategyType.FACET,
            VISDataSeriesType.SMALL_MULTIPLES: SeriesStrategyType.SMALL_MULTIPLES,
            # ECharts-native: single series, no special strategy
            VISDataSeriesType.GRAPH: SeriesStrategyType.NONE,
            VISDataSeriesType.SANKEY: SeriesStrategyType.NONE,
            VISDataSeriesType.PARALLEL: SeriesStrategyType.NONE,
            VISDataSeriesType.LINES: SeriesStrategyType.NONE,
            VISDataSeriesType.TREE: SeriesStrategyType.NONE,
            VISDataSeriesType.THEME_RIVER: SeriesStrategyType.NONE,
            VISDataSeriesType.PICTORIAL_BAR: SeriesStrategyType.NONE,
            VISDataSeriesType.EFFECT_SCATTER: SeriesStrategyType.NONE,
            VISDataSeriesType.MAP: SeriesStrategyType.NONE,
            VISDataSeriesType.DONUT: SeriesStrategyType.NONE,
        }
        return strategy_map.get(viz_type, SeriesStrategyType.NONE)


# Singleton for convenience
vis_factory = VISFactory()

__all__ = ["VISFactory", "vis_factory"]
