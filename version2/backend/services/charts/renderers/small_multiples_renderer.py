from typing import Dict, List, Any, Optional
import math
import polars as pl

from .base_renderer import BaseRenderer


class SmallMultiplesRenderer(BaseRenderer):
    """
    Renders each series in its own panel (small multiples / faceted grid).

    Use when: >4 series, independent series, or high-cardinality x-axis.
    Each panel shares the same x-axis scale but has an independent y-axis.
    Grid is auto-sized: up to 3 columns, rows calculated from series count.

    Uses Plotly subplots via layout.grid and axis references (xaxis1..N, yaxis1..N).
    """

    MAX_COLS = 3

    async def render(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        self._validate_spec(spec)

        y_roles = spec.y_roles or []
        columns = [r["column"] for r in y_roles if "column" in r and r["column"] in df.columns]

        if not columns:
            raise ValueError("SmallMultiplesRenderer: no valid columns in y_roles")

        x_col = spec.encoding.get("x") or spec.encoding.get("x_axis", {})
        if isinstance(x_col, dict):
            x_col = x_col.get("column")

        x_values = df[x_col].to_list() if x_col and x_col in df.columns else list(range(len(df)))

        n = len(columns)
        n_cols = min(n, self.MAX_COLS)
        n_rows = math.ceil(n / n_cols)
        colors = self._assign_colors(n)

        traces = []
        # Plotly subplot axes: panel i → xaxis(i+1), yaxis(i+1)
        # Panel 1 is special: xaxis / yaxis (no number suffix)
        for i, col in enumerate(columns):
            panel = i + 1
            x_ref = "x" if panel == 1 else f"x{panel}"
            y_ref = "y" if panel == 1 else f"y{panel}"

            y_values = df[col].to_list()
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": col,
                "x": x_values,
                "y": y_values,
                "xaxis": x_ref,
                "yaxis": y_ref,
                "line": {"color": colors[i], "width": 2},
                "marker": {"size": 4, "color": colors[i]},
                "hovertemplate": (
                    f"<b>{col}</b><br>"
                    f"{x_col}: %{{x}}<br>"
                    f"Value: %{{y:,.2f}}<extra></extra>"
                ),
                "showlegend": True,
            })

        layout = self._build_base_layout(spec)
        layout.update({
            "grid": {
                "rows": n_rows,
                "columns": n_cols,
                "pattern": "independent",
                "roworder": "top to bottom",
            },
            "height": max(300, n_rows * 280),
        })

        # Add per-panel axis definitions
        for i, col in enumerate(columns):
            panel = i + 1
            row = i // n_cols + 1
            col_pos = i % n_cols + 1

            x_key = "xaxis" if panel == 1 else f"xaxis{panel}"
            y_key = "yaxis" if panel == 1 else f"yaxis{panel}"

            layout[x_key] = {
                "title": str(x_col) if x_col and row == n_rows else "",
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "matches": "x" if panel > 1 else None,  # share x scale
            }
            layout[y_key] = {
                "title": col,
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "titlefont": {"color": colors[i], "size": 11},
            }

            # Remove None values
            layout[x_key] = {k: v for k, v in layout[x_key].items() if v is not None}

        # Panel titles via annotations
        annotations = []
        for i, col in enumerate(columns):
            panel = i + 1
            row = i // n_cols + 1
            col_pos = i % n_cols + 1

            # Position annotation in normalized paper coords
            x_frac = (col_pos - 0.5) / n_cols
            y_frac = 1.0 - (row - 1) / n_rows - (0.5 / n_rows) * 0.3

            annotations.append({
                "text": f"<b>{col}</b>",
                "xref": "paper",
                "yref": "paper",
                "x": x_frac,
                "y": y_frac + 0.02,
                "showarrow": False,
                "font": {"size": 12, "color": colors[i]},
                "xanchor": "center",
            })

        layout["annotations"] = annotations
        layout["showlegend"] = False  # Panel titles replace legend

        chart = {"data": traces, "layout": layout}
        return await self._post_process(chart, spec)
