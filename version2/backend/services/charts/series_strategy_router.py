"""
Series Strategy Router
======================
Routes chart rendering requests to the appropriate strategy-specific renderer.

Entry point for multi-series rendering pipeline:
    Data + Spec → Router → Renderer (specific to strategy) → Plotly output

Dispatcher pattern: Maps series_strategy enum to renderer class.
"""

from typing import Dict, Any, Optional
import logging
import polars as pl

logger = logging.getLogger(__name__)


class SeriesStrategyRouter:
    """
    Routes rendering based on series_strategy.

    Each strategy has a dedicated renderer in services/charts/renderers/
    """

    def __init__(self, render_engine=None):
        """
        Initialize router.

        Args:
            render_engine: Optional existing render engine to integrate with
        """
        self.render_engine = render_engine
        self._renderer_cache = {}

    async def route_rendering(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Main entry point: Route to appropriate renderer.

        Args:
            spec: Chart specification with series_strategy field
            df: Polars DataFrame with data

        Returns:
            Plotly chart dict: {"data": [...], "layout": {...}, "metadata": {...}}

        Raises:
            ValueError: If series_strategy not recognized
        """
        strategy = spec.series_strategy

        logger.info(f"Routing {strategy} chart render: {spec.title}")

        try:
            if strategy == "overlay":
                return await self._render_overlay(spec, df)
            elif strategy == "facet":
                return await self._render_faceted(spec, df)
            elif strategy == "dual_axis":
                return await self._render_dual_axis(spec, df)
            elif strategy == "combo":
                return await self._render_combo(spec, df)
            elif strategy == "grouped":
                return await self._render_grouped(spec, df)
            elif strategy == "stacked":
                return await self._render_stacked(spec, df)
            else:
                raise ValueError(f"Unknown series_strategy: {strategy}")
        except Exception as e:
            logger.error(f"Rendering failed for {strategy}: {e}", exc_info=True)
            raise

    async def _render_overlay(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to overlay renderer.

        Strategy: Multiple series on shared axes
        Use case: Compare values directly (same units)
        """
        from .renderers.overlay_renderer import OverlayRenderer

        renderer = OverlayRenderer()
        return await renderer.render(spec, df)

    async def _render_faceted(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to small multiples (faceted) renderer.

        Strategy: One mini-chart per segment in 3×3 grid
        Use case: Compare segments (high cardinality)
        """
        from .renderers.small_multiples_renderer import SmallMultiplesRenderer

        renderer = SmallMultiplesRenderer()
        return await renderer.render(spec, df)

    async def _render_dual_axis(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to dual-axis renderer.

        Strategy: Left y-axis (primary) + Right y-axis (secondary)
        Use case: Compare metrics with different units/scales
        """
        from .renderers.dual_axis_renderer import DualAxisRenderer

        renderer = DualAxisRenderer()
        return await renderer.render(spec, df)

    async def _render_combo(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to combo chart renderer.

        Strategy: Bars + line combination
        Use case: Show absolute amount + rate of change
        """
        from .renderers.combo_renderer import ComboChartRenderer

        renderer = ComboChartRenderer()
        return await renderer.render(spec, df)

    async def _render_grouped(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to grouped bar renderer.

        Strategy: Bars grouped by category
        Use case: Compare multiple metrics at each x value
        """
        from .renderers.grouped_renderer import GroupedBarRenderer

        renderer = GroupedBarRenderer()
        return await renderer.render(spec, df)

    async def _render_stacked(
        self,
        spec: "MultiSeriesViewSpec",
        df: pl.DataFrame
    ) -> Dict[str, Any]:
        """
        Dispatch to stacked chart renderer.

        Strategy: Bars stacked on top of each other
        Use case: Show composition (parts of whole)
        """
        from .renderers.stacked_renderer import StackedChartRenderer

        renderer = StackedChartRenderer()
        return await renderer.render(spec, df)


# Singleton instance for use in services
series_strategy_router = SeriesStrategyRouter()
