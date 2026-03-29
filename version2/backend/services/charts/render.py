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

        # Smart y-axis range for bar/grouped_bar: zoom in when spread is narrow
        if chart_type in ("bar", "grouped_bar", "stacked_bar") and traces:
            all_y = []
            for tr in traces:
                raw = tr.get("y") or []
                all_y.extend(v for v in raw if isinstance(v, (int, float)))
            if len(all_y) >= 2:
                y_min, y_max = min(all_y), max(all_y)
                span = y_max - y_min
                # Only zoom when values are clustered (spread < 30% of max)
                if y_max > 0 and span / y_max < 0.30:
                    padding = span * 0.25 if span > 0 else y_max * 0.05
                    layout["yaxis"]["range"] = [
                        max(0, y_min - padding),
                        y_max + padding,
                    ]
                    logger.info(
                        f"Smart y-axis range applied: [{layout['yaxis']['range'][0]:.1f}, "
                        f"{layout['yaxis']['range'][1]:.1f}] (span={span:.1f}, max={y_max:.1f})"
                    )

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

        if chart_type in ["pie", "donut", "pie_chart"]:
            for tr in traces:
                tr.pop("x", None)
                tr.pop("y", None)
                # Modern Enhanced Donut Design
                tr["type"] = "pie"
                tr["hole"] = 0.65  # Makes it a donut
                tr["textinfo"] = "label+percent"  # Show label + % on chart
                tr["textposition"] = "outside"
                # Rich hover with label, count, and percentage
                tr["hovertemplate"] = "<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>"
                tr["marker"] = tr.get("marker", {})
                # Enhanced styling: subtle borders for depth
                tr["marker"]["line"] = {
                    "color": "#111827",
                    "width": 1,
                    "opacity": 0.3
                }
                # Professional text styling
                tr["textfont"] = {
                    "size": 12,
                    "color": "#F0F4F8",
                    "family": "IBM Plex Sans, sans-serif"
                }

        if chart_type == "heatmap" and colorscale:
            for tr in traces:
                tr["colorscale"] = colorscale

        if chart_type == "stacked_bar":
            # Remove the internal tag — frontend must never see it
            for tr in traces:
                tr.pop("_stacked", None)

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

        if chart_type in ["pie", "donut", "pie_chart", "gauge"]:
            for ax in ["xaxis", "yaxis"]:
                layout[ax].update({
                    "showticklabels": False,
                    "showgrid": False,
                    "zeroline": False,
                    "showline": False
                })
            # Modern vertical legend for circular charts (better visual hierarchy)
            layout["legend"] = {
                "orientation": "v",
                "yanchor": "middle",
                "y": 0.5,
                "xanchor": "left",
                "x": 1.02,
                "font": {"color": fg, "size": 11, "family": "IBM Plex Sans, sans-serif"},
                "bgcolor": "rgba(0,0,0,0)",
                "bordercolor": "rgba(0,0,0,0)",
                "borderwidth": 0
            }
            # Add bottom margin for better chart spacing
            layout["margin"] = self.default_margin.copy()
            layout["margin"]["b"] = 80

        elif chart_type == "stacked_bar":
            layout["barmode"] = "stack"

        elif chart_type == "heatmap":
            layout["xaxis"]["showgrid"] = False
            layout["yaxis"]["showgrid"] = False

        elif chart_type == "area":
            layout["xaxis"]["type"] = "category"

        elif chart_type == "radar":
            layout["polar"] = {
                "bgcolor": bg,
                "radialaxis": {
                    "visible": True,
                    "gridcolor": grid_color,
                    "tickfont": {"color": fg},
                    "linecolor": grid_color
                },
                "angularaxis": {
                    "tickfont": {"color": fg},
                    "linecolor": grid_color
                }
            }

            layout["xaxis"].update({
                "showgrid": False,
                "showticklabels": False,
                "showline": False
            })

            layout["yaxis"].update({
                "showgrid": False,
                "showticklabels": False,
                "showline": False
            })

        return layout
    
chart_renderer = ChartRenderer()
