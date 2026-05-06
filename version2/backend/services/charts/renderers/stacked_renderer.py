from typing import Dict, List, Any, Optional
import polars as pl

from .base_renderer import BaseRenderer


class StackedChartRenderer(BaseRenderer):
    """
    Renders series as stacked bars or stacked area charts.

    Use when: parts-of-whole / composition story.
    e.g., revenue broken down by product line, costs by department.

    Stacked bars → categorical x-axis (composition per category).
    Stacked area → time-series x-axis (composition over time, showing volume + share).

    Automatically picks bar vs area based on x-axis type.
    Also supports percentage-normalized stacking (100% stacked).
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
            raise ValueError("StackedChartRenderer: no valid columns in y_roles")

        x_col = spec.encoding.get("x") or spec.encoding.get("x_axis", {})
        if isinstance(x_col, dict):
            x_col = x_col.get("column")

        x_values = df[x_col].to_list() if x_col and x_col in df.columns else list(range(len(df)))
        colors = self._assign_colors(len(columns))

        use_area = self._should_use_area(df, x_col)
        normalize = getattr(spec, "normalize_stacked", False)

        if normalize:
            column_data = self._normalize_to_100(df, columns)
        else:
            column_data = {col: df[col].to_list() for col in columns}

        traces = []
        for i, col in enumerate(columns):
            y_values = column_data[col]

            if use_area:
                trace = {
                    "type": "scatter",
                    "mode": "lines",
                    "name": col,
                    "x": x_values,
                    "y": y_values,
                    "stackgroup": "one",
                    "line": {"width": 0.5, "color": colors[i]},
                    "fillcolor": colors[i],
                    "opacity": 0.8,
                    "hovertemplate": (
                        f"<b>{col}</b><br>"
                        f"{x_col}: %{{x}}<br>"
                        f"{'Share' if normalize else 'Value'}: %{{y:{',.1f' if not normalize else '.1%'}}}"
                        f"<extra></extra>"
                    ),
                }
                if normalize:
                    trace["groupnorm"] = "percent"
            else:
                trace = {
                    "type": "bar",
                    "name": col,
                    "x": x_values,
                    "y": y_values,
                    "marker": {"color": colors[i], "opacity": 0.85},
                    "hovertemplate": (
                        f"<b>{col}</b><br>"
                        f"{x_col}: %{{x}}<br>"
                        f"Value: %{{y:,.1f}}<extra></extra>"
                    ),
                }

            traces.append(trace)

        layout = self._build_base_layout(spec)
        layout.update({
            "barmode": "stack" if not use_area else None,
            "hovermode": "x unified",
            "xaxis": {
                "title": str(x_col) if x_col else "",
                "showgrid": False,
            },
            "yaxis": {
                "title": "Share (%)" if normalize else self._infer_y_label(columns),
                "showgrid": True,
                "gridcolor": "#f0f0f0",
                "ticksuffix": "%" if normalize else "",
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
                "traceorder": "normal",
            },
        })

        # Clean None values from layout
        layout = {k: v for k, v in layout.items() if v is not None}

        chart = {"data": traces, "layout": layout}
        return await self._post_process(chart, spec)

    def _should_use_area(self, df: pl.DataFrame, x_col: Optional[str]) -> bool:
        """Use area if x-axis looks like a time/date column."""
        if not x_col or x_col not in df.columns:
            return False

        dtype = str(df[x_col].dtype).lower()
        if any(t in dtype for t in ["date", "time", "datetime"]):
            return True

        # Check if values look like dates by sampling
        sample = df[x_col].head(3).to_list()
        for v in sample:
            s = str(v)
            if any(sep in s for sep in ["-", "/"]) and len(s) >= 8:
                return True

        return False

    def _normalize_to_100(
        self,
        df: pl.DataFrame,
        columns: List[str]
    ) -> Dict[str, List[float]]:
        """Convert absolute values to row-wise percentages (100% stacked)."""
        n = len(df)
        result = {col: [] for col in columns}

        for i in range(n):
            row_total = sum(
                float(df[col][i]) if df[col][i] is not None else 0.0
                for col in columns
            )
            for col in columns:
                val = float(df[col][i]) if df[col][i] is not None else 0.0
                result[col].append(round((val / row_total * 100) if row_total > 0 else 0.0, 2))

        return result

    def _infer_y_label(self, columns: List[str]) -> str:
        if len(columns) <= 3:
            return " + ".join(columns)
        return "Total"
