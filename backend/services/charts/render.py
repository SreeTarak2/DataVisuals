# services/charts/render.py
"""
Chart Renderer (Production-Grade v2.0)
-------------------------------------
Responsibility:
- Accept hydrated traces
- Apply consistent Plotly layout
- Apply theme
- Do minimal chart-type-specific adjustments
- Return unified JSON payload for frontend
"""

from typing import Dict, Any, List, Optional
import logging
import time

logger = logging.getLogger(__name__)


class ChartRenderer:
    def __init__(self):
        self.default_margin = {"l": 30, "r": 20, "t": 40, "b": 40}

    # -----------------------------------------------------
    # PUBLIC API
    # -----------------------------------------------------
    def render(
        self,
        chart_type: str,
        title: str,
        traces: List[Dict[str, Any]],
        rows_used: int,
        theme: str = "light",
        colorscale: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convert hydrated traces into final Plotly payload."""
        start = time.time()
        warnings = []

        if not traces:
            warnings.append("No traces generated")

        # Apply trace-level adjustments (heatmap area colorscale)
        self._patch_traces(chart_type, traces, colorscale)

        layout = self._build_layout(chart_type, title, theme)

        payload = {
            "type": "chart",
            "chart_type": chart_type,
            "title": title,
            "layout": layout,
            "traces": traces or [],
            "meta": {
                "success": bool(traces),
                "rows_used": rows_used,
                "warnings": warnings,
                "render_ms": round((time.time() - start) * 1000, 2)
            }
        }

        logger.info(f"Rendered {chart_type}: {len(traces)} traces, {rows_used} rows")
        return payload

    # -----------------------------------------------------
    # INTERNAL: TRACE PATCHING
    # -----------------------------------------------------
    def _patch_traces(self, chart_type: str, traces: List[Dict[str, Any]], colorscale: Optional[str]):
        """Patch traces for type-specific overrides."""

        if chart_type in ["pie", "donut"]:
            for tr in traces:
                tr.pop("x", None)
                tr.pop("y", None)

        if chart_type == "heatmap" and colorscale:
            for tr in traces:
                tr["colorscale"] = colorscale

        if chart_type == "area":
            for tr in traces:
                tr.setdefault("fill", "tozeroy")

    # -----------------------------------------------------
    # INTERNAL: LAYOUT GENERATION
    # -----------------------------------------------------
    def _build_layout(self, chart_type: str, title: str, theme: str) -> Dict[str, Any]:
        """Minimal Plotly layout with theme + type-specific rules."""

        if theme == "dark":
            bg = "#111827"
            fg = "#E5E7EB"
            grid_color = "#1F2937"
        else:
            bg = "white"
            fg = "#1F2937"
            grid_color = "#E5E7EB"

        layout = {
            "title": {"text": title, "font": {"size": 18, "color": fg}},
            "paper_bgcolor": bg,
            "plot_bgcolor": bg,
            "margin": self.default_margin,
            "legend": {"font": {"color": fg}},
            "xaxis": {
                "showgrid": True,
                "gridcolor": grid_color,
                "tickfont": {"color": fg}
            },
            "yaxis": {
                "showgrid": True,
                "gridcolor": grid_color,
                "tickfont": {"color": fg}
            },
        }

        # ---- Chart-specific overrides ----

        # ✦ Pie / Donut: Remove axes entirely
        if chart_type in ["pie", "donut"]:
            layout["xaxis"].update({
                "showticklabels": False,
                "showgrid": False
            })
            layout["yaxis"].update({
                "showticklabels": False,
                "showgrid": False
            })

        # ✦ Heatmap: Grid off
        elif chart_type == "heatmap":
            layout["xaxis"]["showgrid"] = False
            layout["yaxis"]["showgrid"] = False

        # ✦ Area chart
        elif chart_type == "area":
            layout["xaxis"]["type"] = "category"

        return layout


chart_renderer = ChartRenderer()
