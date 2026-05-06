from typing import Dict, List, Any, Optional
import polars as pl

from .base_renderer import BaseRenderer


class DualAxisRenderer(BaseRenderer):
    """
    Renders two series on independent Y-axes (left + right).

    Use when series have incompatible scales — e.g., revenue ($M) and
    conversion rate (0–1%). Overlay would make the smaller series invisible.

    Primary series → left Y-axis (yaxis)
    Secondary series → right Y-axis (yaxis2, overlaying='y', side='right')
    Both share the same X-axis.
    If more than 2 series, groups them: first half → left, rest → right.
    """

    async def render(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        self._validate_spec(spec)

        y_roles = spec.y_roles or []
        if not y_roles:
            raise ValueError("DualAxisRenderer requires at least 2 series in y_roles")

        x_col = spec.encoding.get("x") or spec.encoding.get("x_axis", {})
        if isinstance(x_col, dict):
            x_col = x_col.get("column")

        x_values = df[x_col].to_list() if x_col and x_col in df.columns else list(range(len(df)))

        columns = [r["column"] for r in y_roles if "column" in r and r["column"] in df.columns]
        if len(columns) < 2:
            raise ValueError("DualAxisRenderer requires at least 2 valid columns")

        colors = self._assign_colors(len(columns))

        # Split: first series on left axis, rest on right axis
        # If scale_mismatch pattern is present, use its grouping
        left_cols, right_cols = self._split_axes(columns, spec)

        traces = []

        for i, col in enumerate(left_cols):
            y_values = df[col].to_list()
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": col,
                "x": x_values,
                "y": y_values,
                "yaxis": "y",
                "line": {"color": colors[i], "width": 2},
                "marker": {"size": 5, "color": colors[i]},
                "hovertemplate": self._build_hover_template(col, str(x_col), col),
            })

        for j, col in enumerate(right_cols):
            y_values = df[col].to_list()
            color_idx = len(left_cols) + j
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": col,
                "x": x_values,
                "y": y_values,
                "yaxis": "y2",
                "line": {"color": colors[color_idx], "width": 2, "dash": "dot"},
                "marker": {"size": 5, "color": colors[color_idx]},
                "hovertemplate": self._build_hover_template(col, str(x_col), col),
            })

        layout = self._build_base_layout(spec)
        layout.update({
            "hovermode": "x unified",
            "xaxis": {
                "title": str(x_col) if x_col else "",
                "showgrid": True,
                "gridcolor": "#f0f0f0",
            },
            "yaxis": {
                "title": " / ".join(left_cols),
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "titlefont": {"color": colors[0]},
                "tickfont": {"color": colors[0]},
            },
            "yaxis2": {
                "title": " / ".join(right_cols),
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "titlefont": {"color": colors[len(left_cols)]},
                "tickfont": {"color": colors[len(left_cols)]},
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

    def _split_axes(
        self,
        columns: List[str],
        spec: "MultiSeriesViewSpec"
    ) -> tuple:
        """
        Split columns into left-axis and right-axis groups.
        Uses scale_mismatch pattern metadata if available, else first vs rest.
        """
        patterns = getattr(spec, "patterns", []) or []

        for p in patterns:
            if p.get("pattern_type") == "scale_mismatch":
                large = p.get("metrics", {}).get("large_scale_col")
                small = p.get("metrics", {}).get("small_scale_col")
                if large and small and large in columns and small in columns:
                    left = [c for c in columns if c != small]
                    right = [small]
                    return left, right

        # Default: first column on left, rest on right
        return [columns[0]], columns[1:]
