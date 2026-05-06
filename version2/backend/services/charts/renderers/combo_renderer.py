from typing import Dict, List, Any, Optional
import polars as pl

from .base_renderer import BaseRenderer


class ComboChartRenderer(BaseRenderer):
    """
    Renders a combination of bars (volume/absolute) and lines (rate/relative).

    Classic use case: monthly revenue (bars) + growth rate % (line on right axis).
    First series → bars on left Y-axis.
    Remaining series → lines. If scale differs significantly, last series gets right Y-axis.

    The combo pattern is the most effective way to show "amount + rate" together
    without the scale problem of pure overlay.
    """

    SCALE_RATIO_THRESHOLD = 5.0  # If line series is Nx smaller, put it on right axis

    async def render(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        self._validate_spec(spec)

        y_roles = spec.y_roles or []
        columns = [r["column"] for r in y_roles if "column" in r and r["column"] in df.columns]

        if len(columns) < 2:
            raise ValueError("ComboChartRenderer requires at least 2 columns")

        x_col = spec.encoding.get("x") or spec.encoding.get("x_axis", {})
        if isinstance(x_col, dict):
            x_col = x_col.get("column")

        x_values = df[x_col].to_list() if x_col and x_col in df.columns else list(range(len(df)))
        colors = self._assign_colors(len(columns))

        bar_col = columns[0]
        line_cols = columns[1:]

        # Determine if any line series needs a right axis
        bar_vals = [v for v in df[bar_col].to_list() if v is not None]
        bar_max = max(abs(v) for v in bar_vals) if bar_vals else 1.0

        traces = []

        # Bar trace (primary series)
        traces.append({
            "type": "bar",
            "name": bar_col,
            "x": x_values,
            "y": df[bar_col].to_list(),
            "yaxis": "y",
            "marker": {
                "color": colors[0],
                "opacity": 0.75,
            },
            "hovertemplate": (
                f"<b>{bar_col}</b><br>"
                f"{x_col}: %{{x}}<br>"
                f"Value: %{{y:,.1f}}<extra></extra>"
            ),
        })

        has_right_axis = False

        for i, col in enumerate(line_cols):
            col_vals = [v for v in df[col].to_list() if v is not None]
            col_max = max(abs(v) for v in col_vals) if col_vals else 1.0

            use_right = bar_max > 0 and (bar_max / max(col_max, 0.001)) > self.SCALE_RATIO_THRESHOLD

            y_axis = "y2" if use_right else "y"
            if use_right:
                has_right_axis = True

            color_idx = i + 1
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": col,
                "x": x_values,
                "y": df[col].to_list(),
                "yaxis": y_axis,
                "line": {"color": colors[color_idx], "width": 2.5},
                "marker": {"size": 6, "color": colors[color_idx], "symbol": "circle"},
                "hovertemplate": (
                    f"<b>{col}</b><br>"
                    f"{x_col}: %{{x}}<br>"
                    f"Value: %{{y:,.2f}}<extra></extra>"
                ),
            })

        layout = self._build_base_layout(spec)
        layout.update({
            "barmode": "group",
            "hovermode": "x unified",
            "xaxis": {
                "title": str(x_col) if x_col else "",
                "showgrid": False,
            },
            "yaxis": {
                "title": bar_col,
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "titlefont": {"color": colors[0]},
                "tickfont": {"color": colors[0]},
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
            "bargap": 0.3,
        })

        if has_right_axis:
            right_col = line_cols[-1]
            right_color = colors[len(line_cols)]
            layout["yaxis2"] = {
                "title": right_col,
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "titlefont": {"color": right_color},
                "tickfont": {"color": right_color},
            }

        chart = {"data": traces, "layout": layout}
        return await self._post_process(chart, spec)
