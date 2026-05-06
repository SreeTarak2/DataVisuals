"""
Chart Renderers Package
======================
Strategy-based renderers for multi-series chart generation.

Each renderer handles a specific series_strategy:
- OverlayRenderer: Multiple lines/bars on shared axes
- SmallMultiplesRenderer: Faceted charts (3×3 grid)
- DualAxisRenderer: Dual y-axes for unit mismatch
- ComboChartRenderer: Bars + line mix
- GroupedBarRenderer: Bars grouped side-by-side
- StackedChartRenderer: Bars stacked

All renderers extend BaseRenderer and follow standard interface:
    async def render(spec: MultiSeriesViewSpec, df: pl.DataFrame) -> Dict[str, Any]
"""

from .base_renderer import BaseRenderer
from .overlay_renderer import OverlayRenderer
from .dual_axis_renderer import DualAxisRenderer
from .small_multiples_renderer import SmallMultiplesRenderer
from .combo_renderer import ComboChartRenderer
from .grouped_renderer import GroupedBarRenderer
from .stacked_renderer import StackedChartRenderer

__all__ = [
    "BaseRenderer",
    "OverlayRenderer",
    "DualAxisRenderer",
    "SmallMultiplesRenderer",
    "ComboChartRenderer",
    "GroupedBarRenderer",
    "StackedChartRenderer",
]
