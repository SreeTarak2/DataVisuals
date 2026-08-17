"""
VIS Compatibility Shim
======================
Bidirectional conversion between VIS and Plotly JSON.

This is the critical backward-compatibility layer for Phase 0.
Allows existing consumers (frontend PlotlyChart, stored chart_data)
to keep working while producers migrate to VIS one by one.

Two converters:
1. `VIS → Plotly JSON`: Used when a VIS producer feeds an old Plotly consumer
2. `Plotly JSON → VIS`: Used when old stored data is read and needs to become VIS
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import logging
import uuid
from datetime import datetime

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
    VISKeyNumber,
    VISPointIntelligence,
    SeriesStrategyType,
    AnalysisIntentType,
)
from .visualization_factory import VISFactory

logger = logging.getLogger(__name__)


class PlotlyConverter:
    """
    Converts VIS to the legacy Plotly JSON format.

    This is the "adapter function" that lets VIS producers feed
    old Plotly consumers without any frontend changes.
    """

    # Plotly trace types mapped from VIS series types
    _TRACE_TYPE_MAP = {
        VISDataSeriesType.BAR: "bar",
        VISDataSeriesType.LINE: "scatter",
        VISDataSeriesType.AREA: "scatter",
        VISDataSeriesType.SCATTER: "scatter",
        VISDataSeriesType.PIE: "pie",
        VISDataSeriesType.HISTOGRAM: "bar",
        VISDataSeriesType.BOX_PLOT: "box",
        VISDataSeriesType.HEATMAP: "heatmap",
        VISDataSeriesType.TREEMAP: "treemap",
        VISDataSeriesType.SUNBURST: "sunburst",
        VISDataSeriesType.RADAR: "scatterpolar",
        VISDataSeriesType.BUBBLE: "scatter",
        VISDataSeriesType.WATERFALL: "waterfall",
        VISDataSeriesType.FUNNEL: "funnel",
        VISDataSeriesType.CANDLESTICK: "candlestick",
        VISDataSeriesType.VIOLIN: "violin",
        VISDataSeriesType.GAUGE: "indicator",
        VISDataSeriesType.BULLET: "indicator",
        VISDataSeriesType.MAP: "choropleth",
        VISDataSeriesType.CORRELATION_MATRIX: "heatmap",
        VISDataSeriesType.MULTI_LINE: "scatter",
        VISDataSeriesType.GROUPED_BAR: "bar",
        VISDataSeriesType.STACKED_BAR: "bar",
        VISDataSeriesType.STACKED_AREA: "scatter",
        VISDataSeriesType.DUAL_AXIS: "scatter",
        VISDataSeriesType.COMBO: "bar",
        VISDataSeriesType.FACET: "scatter",
        VISDataSeriesType.SMALL_MULTIPLES: "scatter",
    }

    def __init__(self, theme: str = "dark"):
        self.theme = theme

    def to_plotly(self, vis: VIS) -> Dict[str, Any]:
        """
        Convert a VIS object to legacy Plotly JSON.

        Returns: {traces: [...], layout: {...}, chart_type: str, title: str, meta: {...}}
        The exact format expected by chart_render_service.py and frontend PlotlyChart.
        """
        traces = self._convert_series_to_traces(vis)
        layout = self._build_plotly_layout(vis)
        meta = self._build_plotly_meta(vis)

        payload = {
            "type": "chart",
            "chart_type": vis.visualization_type.value,
            "title": vis.title,
            "traces": traces,
            "layout": layout,
            "meta": meta,
        }

        # Include point_intelligence if present (renderer-agnostic, pass through)
        if vis.point_intelligence:
            payload["point_intelligence"] = vis.point_intelligence.model_dump()

        # Include narrative fields
        if vis.narrative.headline:
            payload["explanation"] = vis.narrative.headline
        if vis.narrative.confidence:
            payload["confidence"] = vis.narrative.confidence
        if vis.narrative.badge_type:
            payload["badge_type"] = vis.narrative.badge_type

        # Include metadata
        payload["metadata"] = {
            "vis_id": vis.id,
            "vis_version": vis.version,
            "source": vis.source,
            "rows_used": vis.metadata.get("rows_used", 0),
            "total_rows": vis.metadata.get("total_rows", 0),
            "columns": vis.data_mapping,
            "chart_type": vis.visualization_type.value,
            "render_time_ms": vis.metadata.get("render_time_ms", 0),
        }

        return payload

    def _convert_series_to_traces(self, vis: VIS) -> List[Dict[str, Any]]:
        """Convert VISDataSeries list to Plotly trace dicts."""
        traces = []
        all_series = list(vis.series)

        if vis.series_collection:
            all_series.extend(vis.series_collection.series)

        for series in all_series:
            trace = self._series_to_trace(series, vis)
            if trace:
                traces.append(trace)

        # If no series but we have a facet config, return empty
        if not traces and vis.facet_config:
            return []

        return traces

    def _series_to_trace(
        self, series: VISDataSeries, vis: VIS
    ) -> Optional[Dict[str, Any]]:
        """Convert a single VISDataSeries to a Plotly trace dict."""
        plotly_type = self._TRACE_TYPE_MAP.get(series.series_type, "bar")

        trace: Dict[str, Any] = {"type": plotly_type}

        # Name
        if series.name:
            trace["name"] = series.name

        # Map data fields based on type
        if plotly_type == "scatter":
            if series.x is not None:
                trace["x"] = series.x
            if series.y is not None:
                trace["y"] = series.y
            # Default mode for area
            if series.series_type == VISDataSeriesType.AREA:
                trace["mode"] = "lines"
                trace["fill"] = "tozeroy"
            elif series.series_type == VISDataSeriesType.SCATTER:
                trace["mode"] = "markers"
            elif series.series_type == VISDataSeriesType.LINE:
                trace["mode"] = "lines"
            elif series.series_type == VISDataSeriesType.MULTI_LINE:
                trace["mode"] = "lines"
                trace["line"] = {"width": 2}
            elif series.series_type == VISDataSeriesType.STACKED_AREA:
                trace["mode"] = "lines"
                trace["fill"] = "tonexty"

        elif plotly_type == "bar":
            if series.x is not None:
                trace["x"] = series.x
            if series.y is not None:
                trace["y"] = series.y
            if series.group:
                trace["name"] = series.group

        elif plotly_type == "pie":
            if series.labels is not None:
                trace["labels"] = series.labels
            if series.values is not None:
                trace["values"] = series.values
            trace["hole"] = 0.65  # Default donut style
            trace["textinfo"] = "none"

        elif plotly_type == "heatmap":
            if series.z is not None:
                trace["z"] = series.z
            if series.x_labels is not None:
                trace["x"] = series.x_labels
            if series.y_labels is not None:
                trace["y"] = series.y_labels

        elif plotly_type == "box":
            if series.y_raw is not None:
                trace["y"] = series.y_raw
            if series.name:
                trace["name"] = series.name
            trace["boxpoints"] = "outliers"

        elif plotly_type == "violin":
            if series.y_raw is not None:
                trace["y"] = series.y_raw
            if series.name:
                trace["name"] = series.name
            trace["box"] = {"visible": True}
            trace["meanline"] = {"visible": True}

        elif plotly_type == "treemap":
            if series.ids is not None:
                trace["ids"] = series.ids
            if series.parents is not None:
                trace["parents"] = series.parents
            if series.labels_hier is not None:
                trace["labels"] = series.labels_hier

        elif plotly_type == "sunburst":
            if series.ids is not None:
                trace["ids"] = series.ids
            if series.parents is not None:
                trace["parents"] = series.parents
            if series.labels_hier is not None:
                trace["labels"] = series.labels_hier
            trace["branchvalues"] = "total"

        elif plotly_type == "waterfall":
            if series.x is not None:
                trace["x"] = series.x
            if series.y is not None:
                trace["y"] = series.y
            if series.measure is not None:
                trace["measure"] = series.measure
            trace["connector"] = {"line": {"color": "rgb(63, 63, 63)"}}

        elif plotly_type == "funnel":
            if series.y is not None:
                trace["y"] = series.y  # Stage names as y
            if series.x is not None:
                trace["x"] = series.x  # Values as x
            trace["textinfo"] = "value+percent initial"

        elif plotly_type == "candlestick":
            if series.x is not None:
                trace["x"] = series.x
            if series.open is not None:
                trace["open"] = series.open
            if series.high is not None:
                trace["high"] = series.high
            if series.low is not None:
                trace["low"] = series.low
            if series.close is not None:
                trace["close"] = series.close

        elif plotly_type == "indicator":
            if series.value is not None:
                trace["value"] = series.value
                trace["mode"] = "number+gauge" if vis.visualization_type == VISDataSeriesType.GAUGE else "number+gauge+delta"
            if series.target is not None and vis.visualization_type == VISDataSeriesType.BULLET:
                trace["delta"] = {"reference": series.target}

        elif plotly_type == "scatterpolar":
            if series.r is not None:
                trace["r"] = series.r
            if series.theta is not None:
                trace["theta"] = series.theta
            trace["fill"] = "toself"

        elif plotly_type == "choropleth":
            if series.locations is not None:
                trace["locations"] = series.locations
            if series.z_geo is not None:
                trace["z"] = series.z_geo
            trace["colorscale"] = "Viridis"

        # Pass through axis metadata
        if series.axis_hints:
            trace["_axis_metadata"] = series.axis_hints

        # Pass through sampling metadata
        if series.sampled:
            trace["_sampled"] = series.sampled

        return trace

    def _build_plotly_layout(self, vis: VIS) -> Dict[str, Any]:
        """Build minimal Plotly layout from VIS."""
        bg = "#111827" if self.theme == "dark" else "white"
        fg = "#E5E7EB" if self.theme == "dark" else "#1F2937"
        grid = "#1F2937" if self.theme == "dark" else "#E5E7EB"

        layout: Dict[str, Any] = {
            "title": {"text": vis.title, "font": {"size": 18, "color": fg}},
            "paper_bgcolor": bg,
            "plot_bgcolor": bg,
            "margin": {"l": 30, "r": 20, "t": 40, "b": 40},
            "font": {"color": fg},
            "legend": {"font": {"color": fg}},
            "xaxis": {
                "showgrid": True,
                "gridcolor": grid,
                "tickfont": {"color": fg},
            },
            "yaxis": {
                "showgrid": True,
                "gridcolor": grid,
                "tickfont": {"color": fg},
            },
        }

        # Axis titles from VIS axes
        if "x" in vis.axes:
            ax = vis.axes["x"]
            if ax.title:
                layout["xaxis"]["title"] = {"text": ax.title}
        if "y" in vis.axes:
            ax = vis.axes["y"]
            if ax.title:
                layout["yaxis"]["title"] = {"text": ax.title}

        # Secondary y-axis
        if "y2" in vis.axes:
            layout["yaxis2"] = {
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "tickfont": {"color": fg},
            }

        # Barmode for grouped/stacked
        if vis.series_strategy == SeriesStrategyType.GROUPED:
            layout["barmode"] = "group"
        elif vis.series_strategy == SeriesStrategyType.STACKED:
            layout["barmode"] = "stack"

        # Pie/donut layout adjustments
        if vis.visualization_type in (VISDataSeriesType.PIE,):
            layout["xaxis"]["showticklabels"] = False
            layout["xaxis"]["showgrid"] = False
            layout["yaxis"]["showticklabels"] = False
            layout["yaxis"]["showgrid"] = False
            layout["legend"] = {
                "orientation": "v",
                "yanchor": "middle",
                "y": 0.5,
                "xanchor": "left",
                "x": 1.02,
            }

        return layout

    def _build_plotly_meta(self, vis: VIS) -> Dict[str, Any]:
        """Build legacy meta block from VIS metadata."""
        return {
            "success": len(vis.series) > 0 or (vis.series_collection and len(vis.series_collection.series) > 0),
            "rows_used": vis.metadata.get("rows_used", 0),
            "warnings": [],
            "render_ms": vis.metadata.get("render_time_ms", 0),
        }


class VISCompatibilityShim:
    """
    Bidirectional compatibility layer.

    Manages the full lifecycle:
    1. VIS → Plotly JSON (for legacy consumers)
    2. Plotly JSON → VIS (for reading old stored data)
    3. Migration tracking
    """

    def __init__(self, theme: str = "dark"):
        self.plotly_converter = PlotlyConverter(theme=theme)
        self._conversion_count = 0

    # ── VIS → Plotly ────────────────────────────────────────────────

    def vis_to_plotly(self, vis: VIS) -> Dict[str, Any]:
        """Convert VIS to legacy Plotly JSON format."""
        self._conversion_count += 1
        return self.plotly_converter.to_plotly(vis)

    # ── Plotly → VIS ────────────────────────────────────────────────

    def plotly_to_vis(
        self, plotly_data: Dict[str, Any], source: str = "legacy_migration"
    ) -> Optional[VIS]:
        """
        Convert legacy Plotly JSON back to VIS.

        Handles:
        - Full {traces, layout, chart_type} format from chart_render_service
        - {data, layout} format from chat messages
        - Normalized nesting from dashboard components
        """
        try:
            # Extract chart type
            chart_type_str = (
                plotly_data.get("chart_type")
                or plotly_data.get("type", "")
                or "bar"
            )
            if isinstance(chart_type_str, dict):
                chart_type_str = chart_type_str.get("type", "bar")
            viz_type = self._parse_viz_type(chart_type_str)

            # Extract traces
            traces = (
                plotly_data.get("traces")
                or plotly_data.get("data")
                or []
            )

            # Extract layout
            layout = plotly_data.get("layout", {})

            # Extract title
            title = (
                plotly_data.get("title")
                or (layout.get("title", {}).get("text") if isinstance(layout.get("title"), dict) else layout.get("title", ""))
                or "Visualization"
            )

            # Convert traces to VISDataSeries
            series = []
            for trace in traces:
                if not isinstance(trace, dict):
                    continue
                vis_series = self._trace_to_vis_series(trace, viz_type)
                if vis_series:
                    series.append(vis_series)

            # Build narrative
            narrative = VISNarrative(
                headline=plotly_data.get("explanation", ""),
                confidence=plotly_data.get("confidence", 0.0),
                badge_type=plotly_data.get("badge_type"),
            )

            # Build point intelligence if present
            pi = None
            if plotly_data.get("point_intelligence"):
                try:
                    pi = VISPointIntelligence(**plotly_data["point_intelligence"])
                except Exception:
                    pass

            # Build axes from layout
            axes = self._layout_to_axes(layout)

            # Build metadata
            metadata = {
                "rows_used": plotly_data.get("metadata", {}).get("rows_used", 0),
                "total_rows": plotly_data.get("metadata", {}).get("total_rows", 0),
                "render_time_ms": plotly_data.get("metadata", {}).get("render_time_ms", 0),
                "legacy_migrated": True,
            }

            return VISFactory().create(
                visualization_type=viz_type,
                title=str(title),
                series=series,
                source=source,
                axes=axes,
                narrative=narrative,
                point_intelligence=pi.model_dump() if pi else None,
                metadata=metadata,
                validate=False,  # Old data may not validate perfectly
            )

        except Exception as e:
            logger.error(f"Plotly → VIS conversion failed: {e}")
            return None

    def _trace_to_vis_series(
        self, trace: Dict[str, Any], viz_type: VISDataSeriesType
    ) -> Optional[VISDataSeries]:
        """Convert a Plotly trace dict back to VISDataSeries."""
        plotly_type = trace.get("type", "bar")

        series = VISDataSeries(
            name=trace.get("name", ""),
            series_type=viz_type,
        )

        # Common data fields
        if "x" in trace:
            series.x = trace["x"]
        if "y" in trace:
            series.y = trace["y"]

        # Pie
        if "labels" in trace:
            series.labels = trace["labels"]
        if "values" in trace:
            series.values = trace["values"]

        # Heatmap
        if "z" in trace:
            series.z = trace["z"] if isinstance(trace["z"], list) and isinstance(trace["z"][0], list) else None

        # Hierarchy
        if "ids" in trace:
            series.ids = trace["ids"]
        if "parents" in trace:
            series.parents = trace["parents"]
        if "labels" in trace and plotly_type in ("treemap", "sunburst"):
            series.labels_hier = trace["labels"]

        # Box/Violin
        if plotly_type in ("box", "violin") and "y" in trace:
            series.y_raw = trace["y"]
            series.y = None  # Box uses y_raw, not y

        # OHLC
        for field in ("open", "high", "low", "close"):
            if field in trace:
                setattr(series, field, trace[field])

        # Radar
        if "r" in trace:
            series.r = trace["r"]
        if "theta" in trace:
            series.theta = trace["theta"]

        # Axis metadata pass-through
        if "_axis_metadata" in trace:
            series.axis_hints = trace["_axis_metadata"]
        if "_sampled" in trace:
            series.sampled = trace["_sampled"]

        return series

    def _layout_to_axes(self, layout: Dict[str, Any]) -> Dict[str, VISAxis]:
        """Extract VISAxis objects from Plotly layout."""
        axes = {}

        for role, key in [("x", "xaxis"), ("y", "yaxis"), ("y2", "yaxis2")]:
            if key in layout:
                ax_config = layout[key]
                if isinstance(ax_config, dict):
                    axis_type = VISAxisType.CATEGORY
                    if ax_config.get("type") in ("linear", "log"):
                        axis_type = VISAxisType(ax_config["type"])
                    elif ax_config.get("type") == "date":
                        axis_type = VISAxisType.DATE

                    title = None
                    if ax_config.get("title"):
                        t = ax_config["title"]
                        if isinstance(t, dict):
                            title = t.get("text", "")
                        elif isinstance(t, str):
                            title = t

                    axes[role] = VISAxis(
                        title=title or None,
                        axis_type=axis_type,
                    )

        return axes

    @staticmethod
    def _parse_viz_type(raw: str) -> VISDataSeriesType:
        """Parse string to VISDataSeriesType."""
        if isinstance(raw, VISDataSeriesType):
            return raw
        normalized = str(raw).lower().replace("_chart", "").replace("_plot", "").strip()
        try:
            return VISDataSeriesType(normalized)
        except ValueError:
            return VISDataSeriesType.BAR

    # ── Detection helpers ───────────────────────────────────────────

    @staticmethod
    def is_legacy_plotly(data: Dict[str, Any]) -> bool:
        """Check if a dict is legacy Plotly JSON (not VIS)."""
        return bool(
            data.get("traces") or data.get("data")
        ) and not data.get("version", "").startswith("1.")

    @staticmethod
    def is_vis(data: Dict[str, Any]) -> bool:
        """Check if a dict is a VIS object."""
        return data.get("version", "").startswith("1.") or "visualization_type" in data


# Singleton
compat_shim = VISCompatibilityShim()
plotly_converter = PlotlyConverter()

__all__ = ["PlotlyConverter", "VISCompatibilityShim", "compat_shim", "plotly_converter"]
