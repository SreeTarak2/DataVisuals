"""
VIS Validator
=============
Production-grade validation for Visualization Intent Schema objects.

Validates:
1. Schema compliance — required fields, types, constraints
2. Semantic correctness — valid series types, consistent data lengths
3. Business rules — aggregation compatibility, axis specifications

Designed to catch LLM-generated garbage before it reaches the adapter.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import logging

from .visualization_schema import (
    VIS,
    VISDataSeries,
    VISDataSeriesType,
    VISAxisType,
    VISAxisFormat,
    SeriesStrategyType,
    AnalysisIntentType,
    ValidationSeverity as Sev,
)

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation check with severity and actionable message."""

    def __init__(
        self,
        is_valid: bool,
        severity: Sev = Sev.ERROR,
        message: str = "",
        field: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.severity = severity
        self.message = message
        self.field = field
        self.suggestion = suggestion

    def __repr__(self) -> str:
        return (
            f"[{self.severity.value.upper()}] {self.field or 'global'}: "
            f"{self.message}"
            + (f" → {self.suggestion}" if self.suggestion else "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.is_valid,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "suggestion": self.suggestion,
        }


class VISValidator:
    """
    Multi-stage VIS validator.

    Usage:
        validator = VISValidator()
        results = validator.validate(vis)
        if all(r.is_valid for r in results if r.severity == Sev.ERROR):
            print("VIS is valid")
    """

    # Chart types that require specific data fields
    _REQUIRES_X_Y = {
        VISDataSeriesType.BAR,
        VISDataSeriesType.LINE,
        VISDataSeriesType.AREA,
        VISDataSeriesType.SCATTER,
        VISDataSeriesType.HISTOGRAM,
        VISDataSeriesType.MULTI_LINE,
        VISDataSeriesType.GROUPED_BAR,
        VISDataSeriesType.STACKED_BAR,
        VISDataSeriesType.STACKED_AREA,
        VISDataSeriesType.WATERFALL,
        VISDataSeriesType.BUBBLE,
    }

    _REQUIRES_LABELS_VALUES = {
        VISDataSeriesType.PIE,
    }

    _REQUIRES_2D = {
        VISDataSeriesType.HEATMAP,
        VISDataSeriesType.CORRELATION_MATRIX,
    }

    _REQUIRES_HIERARCHY = {
        VISDataSeriesType.TREEMAP,
        VISDataSeriesType.SUNBURST,
    }

    _REQUIRES_OHLC = {
        VISDataSeriesType.CANDLESTICK,
    }

    _REQUIRES_RAW_Y = {
        VISDataSeriesType.BOX_PLOT,
        VISDataSeriesType.VIOLIN,
    }

    # ECharts-native types requiring nodes + links
    _REQUIRES_NODES_LINKS = {
        VISDataSeriesType.GRAPH,
        VISDataSeriesType.SANKEY,
    }

    _REQUIRES_NODES = {
        VISDataSeriesType.TREE,
    }

    _REQUIRES_COORDS = {
        VISDataSeriesType.LINES,
    }

    _REQUIRES_DIMENSIONS = {
        VISDataSeriesType.PARALLEL,
    }

    _REQUIRES_THEME_DATA = {
        VISDataSeriesType.THEME_RIVER,
    }

    _REQUIRES_SINGLE_VALUE = {
        VISDataSeriesType.GAUGE,
        VISDataSeriesType.BULLET,
    }

    # Series strategies that require multiple series
    # Strategies that ALWAYS require multiple series.
    # OVERLAY is excluded because it can be single-series (e.g. one line chart).
    _MULTI_SERIES_STRATEGIES = {
        SeriesStrategyType.GROUPED,
        SeriesStrategyType.STACKED,
        SeriesStrategyType.DUAL_AXIS,
        SeriesStrategyType.COMBO,
        SeriesStrategyType.FACET,
        SeriesStrategyType.SMALL_MULTIPLES,
    }

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: If True, WARNING severity counts as validation failure.
                    If False, only ERROR counts.
        """
        self.strict = strict

    def is_valid(self, vis: VIS) -> bool:
        """Quick validity check. Returns True if VIS passes all ERROR-level checks."""
        results = self.validate(vis)
        threshold = Sev.WARNING if self.strict else Sev.ERROR
        return all(
            r.is_valid for r in results if r.severity.value >= threshold.value
        )

    def first_error(self, vis: VIS) -> Optional[str]:
        """Return the first error message, or None."""
        for r in self.validate(vis):
            if r.severity == Sev.ERROR:
                return r.message
        return None

    # ── Stage 1: Structural validation ──────────────────────────────

    def _validate_structure(self, vis: VIS) -> List[ValidationResult]:
        results = []

        # Title
        if not vis.title or not vis.title.strip():
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="title", message="Title is empty",
                suggestion="Set a descriptive title"
            ))

        # Series — at least one series or series_collection
        if not vis.series and not vis.series_collection:
            results.append(ValidationResult(
                is_valid=False, severity=Sev.ERROR,
                field="series", message="No data series provided",
                suggestion="Add at least one VISDataSeries to series[]"
            ))

        # Series count vs strategy
        if vis.series_strategy in self._MULTI_SERIES_STRATEGIES and len(vis.series) < 2:
            if not vis.series_collection or len(vis.series_collection.series) < 2:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="series_strategy",
                    message=f"Strategy '{vis.series_strategy}' needs ≥2 series, got {len(vis.series)}",
                    suggestion="Add more series or change strategy to 'none'"
                ))

        # Visualization type must be defined
        if not vis.visualization_type:
            results.append(ValidationResult(
                is_valid=False, severity=Sev.ERROR,
                field="visualization_type", message="Visualization type is required",
                suggestion="Set a valid VISDataSeriesType"
            ))

        return results

    # ── Stage 2: Series semantic validation ─────────────────────────

    def _validate_series(self, vis: VIS) -> List[ValidationResult]:
        results = []
        all_series = list(vis.series)
        if vis.series_collection:
            all_series.extend(vis.series_collection.series)

        for idx, series in enumerate(all_series):
            results.extend(self._validate_single_series(series, idx))

        return results

    def _validate_single_series(
        self, series: VISDataSeries, idx: int
    ) -> List[ValidationResult]:
        results = []
        prefix = f"series[{idx}]"

        st = series.series_type

        # Required fields per type
        if st in self._REQUIRES_X_Y:
            if not series.x or not series.y:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.x/y",
                    message=f"Chart type '{st.value}' requires both x and y arrays",
                    suggestion="Provide both x[] and y[] data"
                ))

        elif st in self._REQUIRES_LABELS_VALUES:
            if not series.labels or not series.values:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.labels/values",
                    message="Pie chart requires both labels and values",
                    suggestion="Provide labels[] and values[]"
                ))

        elif st in self._REQUIRES_2D:
            if not series.z:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.z",
                    message="Heatmap requires z (2D matrix)",
                    suggestion="Provide z[][] with numeric values"
                ))

        elif st in self._REQUIRES_HIERARCHY:
            if not series.ids or not series.parents:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.ids/parents",
                    message="Hierarchical chart requires ids[] and parents[]",
                    suggestion="Provide both ids[] and parents[] arrays"
                ))

        elif st in self._REQUIRES_OHLC:
            missing = []
            for f in ("open", "high", "low", "close"):
                if getattr(series, f) is None:
                    missing.append(f)
            if missing:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.ohlc",
                    message=f"Candlestick missing: {', '.join(missing)}",
                    suggestion="Provide all OHLC arrays"
                ))

        elif st in self._REQUIRES_RAW_Y:
            if not series.y_raw:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field=f"{prefix}.y_raw",
                    message="Box/violin chart should have y_raw values",
                    suggestion="Provide y_raw[] for distribution rendering"
                ))

        # ECharts-native: nodes + links (graph, sankey)
        elif st in self._REQUIRES_NODES_LINKS:
            if not series.nodes:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.nodes",
                    message=f"'{st.value}' requires nodes[]",
                    suggestion="Provide nodes[] with name and optional value"
                ))
            if not series.links:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.links",
                    message=f"'{st.value}' requires links[]",
                    suggestion="Provide links[] with source, target, and optional value"
                ))

        # ECharts-native: tree (nested children)
        elif st in self._REQUIRES_NODES:
            if not series.children:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.children",
                    message="Tree requires children[] with nested nodes",
                    suggestion="Provide children[] with hierarchical VISNode objects"
                ))

        # ECharts-native: lines (coordinate pairs)
        elif st in self._REQUIRES_COORDS:
            if not series.coords:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.coords",
                    message="Lines chart requires coords (coordinate paths)",
                    suggestion="Provide coords as [[[x1,y1],[x2,y2]], ...]"
                ))

        # ECharts-native: parallel (dimensions + data_rows)
        elif st in self._REQUIRES_DIMENSIONS:
            if not series.dimensions:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.dimensions",
                    message="Parallel chart requires dimensions[]",
                    suggestion="Provide dimensions[] with VISAxis objects"
                ))
            if not series.data_rows:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field=f"{prefix}.data_rows",
                    message="Parallel chart should have data_rows",
                    suggestion="Provide data_rows as multi-dimensional array"
                ))

        # ECharts-native: theme_river
        elif st in self._REQUIRES_THEME_DATA:
            if not series.theme_data:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.theme_data",
                    message="ThemeRiver requires theme_data",
                    suggestion="Provide theme_data as [[date, value, category], ...]"
                ))

        # Single-value types (gauge, bullet)
        elif st in self._REQUIRES_SINGLE_VALUE:
            if series.value is None:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field=f"{prefix}.value",
                    message=f"'{st.value}' should have a value field",
                    suggestion="Set series.value to a numeric value"
                ))

        # Pictorial bar: same as bar, reuses x/y

        # Effect scatter: same as scatter, reuses x/y

        # Map: uses locations + z_geo (same as choropleth)

        # Donut: same as pie, variant_config.donut_hole controls the hole

        # Length consistency checks
        if series.x is not None and series.y is not None:
            if len(series.x) != len(series.y):
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.length_mismatch",
                    message=f"x ({len(series.x)}) and y ({len(series.y)}) length mismatch",
                    suggestion="Ensure x[] and y[] have the same length"
                ))

        if series.labels is not None and series.values is not None:
            if len(series.labels) != len(series.values):
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.ERROR,
                    field=f"{prefix}.length_mismatch",
                    message=f"labels ({len(series.labels)}) and values ({len(series.values)}) mismatch"
                ))

        return results

    # ── Stage 3: Axis validation ────────────────────────────────────

    def _validate_axes(self, vis: VIS) -> List[ValidationResult]:
        results = []

        for role, axis in vis.axes.items():
            if axis.axis_type == VISAxisType.DATE and axis.format == VISAxisFormat.AUTO:
                results.append(ValidationResult(
                    is_valid=True, severity=Sev.INFO,
                    field=f"axes.{role}.format",
                    message="Date axis with AUTO format — adapter will auto-detect"
                ))

        if "y2" in vis.axes and vis.series_strategy not in (
            SeriesStrategyType.DUAL_AXIS,
            SeriesStrategyType.COMBO,
        ):
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="axes.y2",
                message="Secondary y-axis defined but strategy is not dual_axis or combo",
                suggestion="Set series_strategy to 'dual_axis' or 'combo'"
            ))

        return results

    # ── Stage 4: Multi-series validation ────────────────────────────

    def _validate_multi_series(self, vis: VIS) -> List[ValidationResult]:
        results = []

        if vis.series_strategy == SeriesStrategyType.DUAL_AXIS:
            if "y2" not in vis.axes:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="axes.y2",
                    message="Dual-axis strategy requires a 'y2' axis definition",
                    suggestion="Add axes.y2 with the secondary metric specification"
                ))

        if vis.series_strategy in (SeriesStrategyType.FACET, SeriesStrategyType.SMALL_MULTIPLES):
            if not vis.facet_config:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="facet_config",
                    message=f"Strategy '{vis.series_strategy}' needs facet_config",
                    suggestion="Add facet_config with facet_column"
                ))
            elif vis.facet_config and vis.facet_config.facet_count > vis.facet_config.max_facets:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="facet_config.facet_count",
                    message=f"Facet count ({vis.facet_config.facet_count}) exceeds max ({vis.facet_config.max_facets})",
                    suggestion="Reduce facet_count or increase max_facets"
                ))

        return results

    # ── Stage 5: Business rule validation ───────────────────────────

    def _validate_business_rules(self, vis: VIS) -> List[ValidationResult]:
        results = []

        # Pie charts should have limited slices
        if vis.visualization_type == VISDataSeriesType.PIE:
            primary = vis.get_primary_series()
            if primary and primary.labels and len(primary.labels) > 10:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="series[0].labels",
                    message=f"Pie chart has {len(primary.labels)} slices (>10 recommended max)",
                    suggestion="Limit to 10 or fewer slices, aggregate rest as 'Other'"
                ))

        # Bar charts with many categories should be capped
        if vis.visualization_type in (VISDataSeriesType.BAR, VISDataSeriesType.GROUPED_BAR):
            primary = vis.get_primary_series()
            if primary and primary.x and len(primary.x) > 25:
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.WARNING,
                    field="series[0].x",
                    message=f"Bar chart has {len(primary.x)} categories (>25 recommended max)",
                    suggestion="Cap at 25 categories, aggregate rest as 'Other'"
                ))

        # Scatter and heatmap should not have aggregation
        if vis.visualization_type in (VISDataSeriesType.SCATTER, VISDataSeriesType.HEATMAP):
            if vis.aggregation and vis.aggregation not in ("none", ""):
                results.append(ValidationResult(
                    is_valid=False, severity=Sev.INFO,
                    field="aggregation",
                    message=f"Scatter/heatmap with aggregation='{vis.aggregation}'",
                    suggestion="Consider setting aggregation to 'none' for raw data display"
                ))

        return results

    # ── Stage 6: Variant config validation ──────────────────────────

    def _validate_variant_config(self, vis: VIS) -> List[ValidationResult]:
        results = []
        vc = vis.variant_config
        if vc is None:
            return results

        # Step lines require line chart
        if vc.step is not None and vis.visualization_type not in (
            VISDataSeriesType.LINE, VISDataSeriesType.MULTI_LINE, VISDataSeriesType.AREA
        ):
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.step",
                message="'step' variant only applies to line charts",
                suggestion="Set visualization_type to 'line' or remove step"
            ))

        # Smooth lines require line chart
        if vc.smooth is not None and vc.smooth and vis.visualization_type not in (
            VISDataSeriesType.LINE, VISDataSeriesType.MULTI_LINE, VISDataSeriesType.AREA
        ):
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.smooth",
                message="'smooth' variant only applies to line charts"
            ))

        # Donut hole requires pie or donut type
        if vc.donut_hole is not None and vis.visualization_type not in (
            VISDataSeriesType.PIE, VISDataSeriesType.DONUT
        ):
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.donut_hole",
                message="'donut_hole' variant only applies to pie/donut charts",
                suggestion="Set visualization_type to 'pie' or 'donut'"
            ))

        # Rose type requires pie chart
        if vc.rose_type is not None and vis.visualization_type != VISDataSeriesType.PIE:
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.rose_type",
                message="'rose_type' variant only applies to pie charts",
                suggestion="Set visualization_type to 'pie'"
            ))

        # Bar race requires bar chart
        if vc.realtime_sort is not None and vc.realtime_sort and vis.visualization_type not in (
            VISDataSeriesType.BAR, VISDataSeriesType.GROUPED_BAR, VISDataSeriesType.STACKED_BAR
        ):
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.realtime_sort",
                message="'realtime_sort' variant only applies to bar charts"
            ))

        # Pictorial symbol requires pictorial_bar type
        if vc.symbol_path is not None and vis.visualization_type != VISDataSeriesType.PICTORIAL_BAR:
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.symbol_path",
                message="'symbol_path' variant only applies to pictorial_bar charts",
                suggestion="Set visualization_type to 'pictorial_bar'"
            ))

        # Graph layout requires graph type
        if vc.graph_layout is not None and vis.visualization_type != VISDataSeriesType.GRAPH:
            results.append(ValidationResult(
                is_valid=False, severity=Sev.WARNING,
                field="variant_config.graph_layout",
                message="'graph_layout' variant only applies to graph charts"
            ))

        return results

    def validate(self, vis: VIS) -> List[ValidationResult]:
        """Run all validation stages. Returns list of results."""
        results = []
        results.extend(self._validate_structure(vis))

        if not any(r.severity == Sev.ERROR for r in results):
            results.extend(self._validate_series(vis))
            results.extend(self._validate_axes(vis))
            results.extend(self._validate_multi_series(vis))
            results.extend(self._validate_variant_config(vis))
            results.extend(self._validate_business_rules(vis))

        # Log results
        errors = [r for r in results if r.severity == Sev.ERROR]
        warnings = [r for r in results if r.severity == Sev.WARNING]
        if errors:
            logger.warning(
                f"VIS validation failed: {len(errors)} error(s), {len(warnings)} warning(s)"
            )
            for err in errors[:5]:
                logger.warning(f"  {err}")
        elif warnings:
            logger.info(f"VIS validation passed with {len(warnings)} warning(s)")

        return results


__all__ = ["VISValidator", "ValidationResult"]
