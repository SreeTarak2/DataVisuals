"""
Base Renderer
=============
Parent class for all strategy-specific chart renderers.

Provides:
- Common layout building
- Color assignment
- Hover template generation
- Data extraction utilities
- Post-processing hooks
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import polars as pl


class BaseRenderer(ABC):
    """Abstract base class for all chart renderers"""

    def __init__(self):
        """Initialize with default colors and settings"""
        self.default_colors = [
            "#1f77b4",  # Blue
            "#ff7f0e",  # Orange
            "#2ca02c",  # Green
            "#d62728",  # Red
            "#9467bd",  # Purple
            "#8c564b",  # Brown
            "#e377c2",  # Pink
            "#7f7f7f",  # Gray
            "#bcbd22",  # Yellow-green
            "#17becf",  # Cyan
        ]

    @abstractmethod
    async def render(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Main render method (must be implemented by subclass).

        Args:
            spec: MultiSeriesViewSpec with chart configuration
            df: Polars DataFrame with data

        Returns:
            Dict with structure:
            {
                "data": [trace1, trace2, ...],  # Plotly traces
                "layout": {...},                 # Plotly layout
                "metadata": {...}                # Custom metadata
            }
        """
        pass

    # ========================================
    # COMMON UTILITIES
    # ========================================

    def _build_base_layout(self, spec: "MultiSeriesViewSpec") -> Dict[str, Any]:
        """
        Build common layout properties for all renderers.

        All renderers should call this and then add strategy-specific props.
        """
        return {
            "title": spec.title or "Chart",
            "template": "plotly_white",
            "hovermode": "x unified",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "paper_bgcolor": "rgba(255,255,255,1)",
            "font": {
                "family": "Arial, sans-serif",
                "size": 12,
                "color": "#333"
            },
            "margin": {
                "l": 60,
                "r": 60,
                "t": 60,
                "b": 60
            }
        }

    def _assign_colors(self, num_series: int) -> List[str]:
        """
        Assign distinct colors to series.

        Args:
            num_series: Number of series needing colors

        Returns:
            List of color strings (cycles through default_colors)
        """
        colors = []
        for i in range(num_series):
            colors.append(self.default_colors[i % len(self.default_colors)])
        return colors

    def _extract_x_axis_data(
        self,
        df: pl.DataFrame,
        spec: "MultiSeriesViewSpec"
    ) -> List[str]:
        """
        Extract x-axis values from DataFrame.

        Args:
            df: Polars DataFrame
            spec: Chart spec with encoding info

        Returns:
            List of x-axis values
        """
        x_col = spec.encoding.get("x_axis", {}).get("column")
        if not x_col or x_col not in df.columns:
            return list(range(len(df)))

        return df[x_col].to_list()

    def _build_hover_template(
        self,
        series_name: str,
        x_label: str,
        y_label: str
    ) -> str:
        """
        Build standard hover template for traces.

        Args:
            series_name: Name of the series
            x_label: Label for x-axis
            y_label: Label for y-axis

        Returns:
            Plotly hover template string
        """
        return (
            f"<b>{series_name}</b><br>"
            f"{x_label}: %{{x}}<br>"
            f"{y_label}: %{{y:,.2f}}<br>"
            "<extra></extra>"
        )

    def _validate_spec(self, spec: "MultiSeriesViewSpec") -> bool:
        """
        Validate spec has required fields for rendering.

        Args:
            spec: Chart spec to validate

        Raises:
            ValueError if required fields missing

        Returns:
            True if valid
        """
        required = ["title", "encoding", "y_roles", "chart_type_primary"]

        for field in required:
            if not hasattr(spec, field) or not getattr(spec, field):
                raise ValueError(f"Missing required field in spec: {field}")

        return True

    async def _post_process(
        self,
        chart_dict: Dict[str, Any],
        spec: "MultiSeriesViewSpec"
    ) -> Dict[str, Any]:
        """
        Common post-processing for all renderers.

        - Add standard metadata
        - Ensure required keys exist
        - Validate structure

        Args:
            chart_dict: Chart output from render method
            spec: Original chart spec

        Returns:
            Processed chart dict
        """
        if "metadata" not in chart_dict:
            chart_dict["metadata"] = {}

        chart_dict["metadata"].update({
            "series_strategy": spec.series_strategy,
            "chart_type": spec.chart_type_primary,
            "y_roles": spec.y_roles,
            "analysis_intent": spec.analysis_intent,
            "readability_score": getattr(spec, "readability_score", 0.8),
            "rendered_at": None  # Can be set by caller
        })

        return chart_dict

    # ========================================
    # HELPER FUNCTIONS
    # ========================================

    @staticmethod
    def _normalize_values(values: List[float], target_min: float = 0.0, target_max: float = 1.0) -> List[float]:
        """
        Normalize values to range [target_min, target_max].

        Useful for comparing series with different units/scales.

        Args:
            values: Input values
            target_min: Minimum of output range
            target_max: Maximum of output range

        Returns:
            Normalized values
        """
        if len(values) < 2:
            return values

        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            return [0.5 * (target_max + target_min)] * len(values)

        normalized = []
        for v in values:
            norm = (v - min_val) / (max_val - min_val)
            scaled = norm * (target_max - target_min) + target_min
            normalized.append(scaled)

        return normalized

    @staticmethod
    def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
        """
        Safely divide two numbers, return default if denominator is zero.

        Args:
            numerator: Top value
            denominator: Bottom value
            default: Value to return if denominator is 0

        Returns:
            Division result or default
        """
        try:
            return numerator / denominator if denominator != 0 else default
        except (TypeError, ZeroDivisionError):
            return default

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """
        Clamp value to range [min_val, max_val].

        Args:
            value: Value to clamp
            min_val: Minimum allowed
            max_val: Maximum allowed

        Returns:
            Clamped value
        """
        return max(min_val, min(max_val, value))
