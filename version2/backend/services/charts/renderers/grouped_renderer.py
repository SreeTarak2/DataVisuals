from typing import Dict, List, Any, Optional
import polars as pl

from .base_renderer import BaseRenderer


class GroupedBarRenderer(BaseRenderer):
    """
    Renders multiple series as side-by-side (grouped) bars.

    Use when: comparing multiple metrics across categories where each
    metric is independent and seeing absolute values matters more than composition.
    e.g., Q1 vs Q2 vs Q3 revenue, units, margin — side by side per region.

    All series share the same Y-axis (same unit implied).
    If units differ, DualAxisRenderer or ComboRenderer is more appropriate.
    """

    async def render(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        self._validate_spec(spec)

        y_roles = spec.y_roles or []
        columns = [r["column"] for r in y_roles if "column" in r and r["column"] in df.columns]

        if not columns:
            raise ValueError("GroupedBarRenderer: no valid columns in y_roles")

        x_col = spec.encoding.get("x") or spec.encoding.get("x_axis", {})
        if isinstance(x_col, dict):
            x_col = x_col.get("column")

        x_values = df[x_col].to_list() if x_col and x_col in df.columns else list(range(len(df)))
        colors = self._assign_colors(len(columns))

        traces = []
        for i, col in enumerate(columns):
            traces.append({
                "type": "bar",
                "name": col,
                "x": x_values,
                "y": df[col].to_list(),
                "marker": {
                    "color": colors[i],
                    "opacity": 0.85,
                },
                "hovertemplate": (
                    f"<b>{col}</b><br>"
                    f"{x_col}: %{{x}}<br>"
                    f"Value: %{{y:,.1f}}<extra></extra>"
                ),
            })

        layout = self._build_base_layout(spec)
        layout.update({
            "barmode": "group",
            "bargap": 0.2,
            "bargroupgap": 0.05,
            "hovermode": "x unified",
            "xaxis": {
                "title": str(x_col) if x_col else "",
                "showgrid": False,
                "type": "category",
            },
            "yaxis": {
                "title": self._infer_y_label(spec, columns),
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "zeroline": True,
                "zerolinecolor": "#e0e0e0",
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        })

        chart = {"data": traces, "layout": layout}
        return await self._post_process(chart, spec)

    def _infer_y_label(self, spec: "MultiSeriesViewSpec", columns: List[str]) -> str:
        """Use unit metadata if available, else join column names."""
        y_roles = spec.y_roles or []
        units = list({r.get("unit") for r in y_roles if r.get("unit")})
        if len(units) == 1:
            return units[0]
        if len(columns) <= 3:
            return " / ".join(columns)
        return "Value"
