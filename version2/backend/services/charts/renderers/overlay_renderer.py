"""
Overlay Renderer
================
Renders multiple series on shared axes for direct comparison.

Strategy: All metrics on same (x, y) coordinate system
Use case: Compare metrics with same units, same scale
Visualization: Line plot or scatter with multiple traces

Design:
- Each metric becomes a separate trace
- Shared x-axis, shared y-axis
- Color-coded series for distinction
- Legend shows all series
- Hover shows all values at each x point

Limitations:
- Not suitable for metrics with vastly different scales
- Shouldn't use for >5-7 series (readability drops)
- Not good for composition analysis
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import polars as pl
from datetime import datetime

from .base_renderer import BaseRenderer
from db.schemas_charts import MultiSeriesViewSpec

logger = logging.getLogger(__name__)


class OverlayRenderer(BaseRenderer):
    """
    Render multiple series on shared axes overlay chart.

    Creates Plotly figure with all metrics as separate traces displayed on
    same coordinate system.
    """

    def __init__(self, trace_mode: str = "lines+markers"):
        """
        Initialize Overlay Renderer.

        Args:
            trace_mode: Plotly mode (lines+markers, lines, markers, etc.)
        """
        super().__init__()
        self.trace_mode = trace_mode
        self.max_series = 7  # Readability threshold

    async def render(
        self,
        spec: MultiSeriesViewSpec,
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Render overlay chart.

        Args:
            spec: Chart specification with encoding, y_roles, etc.
            df: Polars DataFrame with data

        Returns:
            Plotly figure dict:
            {
                "data": [
                    {
                        "x": [...],
                        "y": [...],
                        "name": "Revenue",
                        "mode": "lines+markers",
                        "line": {"color": "#1f77b4"},
                        "marker": {"size": 6},
                        "hovertemplate": "...",
                        "visible": true
                    },
                    ...
                ],
                "layout": {
                    "title": "Revenue vs Cost",
                    "xaxis": {...},
                    "yaxis": {...},
                    ...
                },
                "metadata": {
                    "render_engine": "overlay",
                    "series_count": 2,
                    "data_points": 12,
                    "has_nulls": false
                }
            }

        Raises:
            ValueError: If spec invalid, required columns missing, or data malformed
            Exception: Any other rendering error
        """
        logger.info(f"Render overlay chart: {spec.title}")
        render_start = datetime.utcnow()

        try:
            # Step 1: Validate specification
            self._validate_spec(spec)

            # Step 2: Validate data
            self._validate_data(df, spec)

            # Step 3: Check series count
            y_roles = spec.y_roles or []
            series_count = len(y_roles)
            if series_count > self.max_series:
                logger.warning(
                    f"High series count ({series_count}) may reduce readability. "
                    f"Consider faceting instead."
                )

            # Step 4: Extract x-axis data
            x_col = spec.encoding.get("x")
            x_data = self._extract_x_axis_data(df, x_col)

            # Step 5: Build traces (one per metric)
            traces = []
            colors = self._assign_colors(series_count)

            for idx, y_role in enumerate(y_roles):
                column = y_role.get("column")
                if not column or column not in df.columns:
                    logger.warning(f"Column not found: {column}, skipping")
                    continue

                # Extract y values
                y_data = df[column].to_list()

                # Normalize values if needed
                if spec.analysis_intent == "comparison":
                    y_min = min([v for v in y_data if v is not None], default=0)
                    y_max = max([v for v in y_data if v is not None], default=1)
                    # Optional: normalize to 0-1 for comparison
                    # y_data = self._normalize_values(y_data, y_min, y_max)

                # Build trace
                trace = {
                    "x": x_data,
                    "y": y_data,
                    "name": column,
                    "mode": self.trace_mode,
                    "type": "scatter",
                    "line": {
                        "color": colors[idx],
                        "width": 2.5
                    },
                    "marker": {
                        "size": 6,
                        "color": colors[idx],
                        "opacity": 0.8
                    },
                    "hovertemplate": self._build_hover_template(
                        x_col,
                        column,
                        spec.unit_handling or {}
                    ),
                    "visible": True
                }

                traces.append(trace)

            # Step 6: Build layout
            layout = self._build_base_layout(spec)

            # Step 7: Add axis configuration
            layout["xaxis"] = {
                "title": x_col or "X Axis",
                "showgrid": True,
                "gridwidth": 1,
                "gridcolor": "rgba(200, 200, 200, 0.2)",
                "zeroline": False
            }

            layout["yaxis"] = {
                "title": "Value",
                "showgrid": True,
                "gridwidth": 1,
                "gridcolor": "rgba(200, 200, 200, 0.2)",
                "zeroline": False
            }

            # Step 8: Add legend
            layout["showlegend"] = True
            layout["legend"] = {
                "x": 0.01,
                "y": 0.99,
                "bgcolor": "rgba(255, 255, 255, 0.8)",
                "bordercolor": "rgba(0, 0, 0, 0.2)",
                "borderwidth": 1
            }

            # Step 9: Add reference line if present
            if spec.secondary_metric:
                layout["shapes"] = self._add_reference_lines(
                    df,
                    spec.secondary_metric,
                    x_data
                )

            # Step 10: Post-process
            figure = {
                "data": traces,
                "layout": layout
            }
            figure = self._post_process(figure, spec)

            # Step 11: Add metadata
            figure["metadata"] = {
                "renderer": "overlay",
                "series_count": len(traces),
                "data_points_per_series": len(x_data),
                "has_nulls": self._detect_nulls(df, y_roles),
                "render_time_ms": (datetime.utcnow() - render_start).total_seconds() * 1000,
                "mode": self.trace_mode
            }

            logger.info(
                f"Overlay render complete: {len(traces)} series, "
                f"{len(x_data)} points, "
                f"{figure['metadata']['render_time_ms']:.1f}ms"
            )

            return figure

        except Exception as e:
            logger.error(f"Overlay rendering failed: {e}", exc_info=True)
            raise

    def _validate_data(
        self,
        df: pl.DataFrame,
        spec: MultiSeriesViewSpec
    ) -> None:
        """
        Validate DataFrame has required columns and types.

        Args:
            df: Polars DataFrame
            spec: Chart specification

        Raises:
            ValueError: If validation fails
        """
        if df.is_empty():
            raise ValueError("DataFrame is empty")

        x_col = spec.encoding.get("x")
        if not x_col:
            raise ValueError("X column not specified in encoding")

        if x_col not in df.columns:
            raise ValueError(f"X column '{x_col}' not found in DataFrame")

        y_roles = spec.y_roles or []
        if not y_roles:
            raise ValueError("No y_roles specified")

        if len(y_roles) < 2:
            raise ValueError("Overlay requires at least 2 series")

        for y_role in y_roles:
            col = y_role.get("column")
            if not col or col not in df.columns:
                raise ValueError(f"Y column '{col}' not found in DataFrame")

    def _detect_nulls(
        self,
        df: pl.DataFrame,
        y_roles: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if any y column has null values.

        Args:
            df: Polars DataFrame
            y_roles: List of y-axis roles

        Returns:
            True if any nulls detected
        """
        for y_role in y_roles:
            col = y_role.get("column")
            if col and col in df.columns:
                if df[col].is_null().any():
                    return True
        return False

    def _add_reference_lines(
        self,
        df: pl.DataFrame,
        secondary_metric: str,
        x_data: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Add reference lines for secondary metric (if constant).

        Args:
            df: Polars DataFrame
            secondary_metric: Secondary metric column name
            x_data: X-axis data

        Returns:
            List of shape dicts for reference lines
        """
        if secondary_metric not in df.columns:
            return []

        try:
            values = df[secondary_metric].to_list()
            avg_value = sum([v for v in values if v is not None]) / len(
                [v for v in values if v is not None]
            )

            return [
                {
                    "type": "line",
                    "x0": x_data[0],
                    "x1": x_data[-1],
                    "y0": avg_value,
                    "y1": avg_value,
                    "line": {
                        "color": "rgba(200, 0, 0, 0.3)",
                        "width": 2,
                        "dash": "dash"
                    }
                }
            ]
        except Exception as e:
            logger.warning(f"Reference line creation failed: {e}")
            return []


# Singleton instance for use in service layer
overlay_renderer = OverlayRenderer()
