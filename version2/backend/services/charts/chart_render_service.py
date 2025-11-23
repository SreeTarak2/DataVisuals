"""
Chart Render Service
====================
Production-grade chart rendering service that wraps the render.py module.

Features:
- Async/await support for FastAPI integration
- Error handling and logging
- Chart hydration → rendering pipeline
- Theme support (light/dark)
- Caching support
- Performance monitoring

Author: DataSage AI Team
Version: 2.0 (Production)
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import polars as pl

from services.charts.render import ChartRenderer
from services.charts.hydrate import (
    hydrate_chart,
    validate_config,
    HydrationError
)
from db.schemas_dashboard import ChartConfig, ChartType
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

logger = logging.getLogger(__name__)


class ChartRenderService:
    """
    Production-grade chart rendering service.
    Orchestrates hydration → rendering → output.
    """
    
    def __init__(self):
        self.renderer = ChartRenderer()
        self._cache = {}  # Simple in-memory cache
        self._render_count = 0
        self._error_count = 0
    
    async def render_chart(
        self,
        df: pl.DataFrame,
        chart_config: Dict[str, Any],
        theme: str = "light"
    ) -> Dict[str, Any]:
        """
        Main rendering method: DataFrame + config → Plotly chart.
        
        Args:
            df: Polars DataFrame with data
            chart_config: Chart configuration dict
            theme: Visual theme ("light" or "dark")
        
        Returns:
            Dict with Plotly chart data, layout, and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate inputs
            if df is None or df.is_empty():
                raise ValueError("DataFrame is empty")
            
            if not chart_config:
                raise ValueError("Chart config is required")
            
            # Parse chart config
            config = self._parse_config(chart_config)
            
            # Validate config against DataFrame
            validate_config(df, config)
            
            # Hydrate: DataFrame → Plotly traces
            logger.info(f"Hydrating {config.chart_type.value} chart...")
            traces, rows_used = hydrate_chart(df, config)
            
            if not traces:
                raise HydrationError("No traces generated")
            
            # Render: Traces → Final Plotly payload
            logger.info(f"Rendering chart with {len(traces)} trace(s)...")
            chart_payload = self.renderer.render(
                chart_type=config.chart_type.value,
                title=chart_config.get("title", "Chart"),
                traces=traces,
                rows_used=rows_used,
                theme=theme,
                colorscale=chart_config.get("colorscale")
            )
            
            # Add metadata
            chart_payload["metadata"] = {
                "rows_used": rows_used,
                "total_rows": len(df),
                "columns": config.columns,
                "chart_type": config.chart_type.value,
                "render_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
            
            self._render_count += 1
            logger.info(f"✓ Chart rendered successfully ({chart_payload['metadata']['render_time_ms']:.0f}ms)")
            
            return chart_payload
        
        except HydrationError as e:
            self._error_count += 1
            logger.error(f"✗ Hydration error: {e}")
            raise
        
        except Exception as e:
            self._error_count += 1
            logger.error(f"✗ Chart rendering failed: {e}", exc_info=True)
            raise
    
    async def render_chart_from_config(
        self,
        chart_config: Dict[str, Any],
        dataset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Render chart from config with automatic dataset loading.
        
        Args:
            chart_config: Chart configuration
            dataset_id: Optional dataset ID (if not in config)
        
        Returns:
            Rendered chart payload
        """
        try:
            # Extract dataset_id
            ds_id = chart_config.get("dataset_id") or dataset_id
            if not ds_id:
                raise ValueError("dataset_id is required")
            
            # Load dataset using enhanced_dataset_service
            logger.info(f"Loading dataset {ds_id}...")
            
            # Get user_id from config if provided, otherwise use None (service will handle auth separately)
            user_id = config.get("user_id")
            if not user_id:
                # Try to get from context or raise error
                raise ValueError("user_id is required in config for dataset loading")
            
            # Load the dataset data
            df = await enhanced_dataset_service.load_dataset_data(ds_id, user_id)
            
            # Now render the chart with the loaded dataframe
            return await self.render_chart(df, config)
        
        except Exception as e:
            logger.error(f"✗ Failed to render chart from config: {e}")
            raise
    
    async def render_multiple_charts(
        self,
        df: pl.DataFrame,
        chart_configs: List[Dict[str, Any]],
        theme: str = "light"
    ) -> List[Dict[str, Any]]:
        """
        Render multiple charts in parallel.
        
        Args:
            df: Polars DataFrame
            chart_configs: List of chart configurations
            theme: Visual theme
        
        Returns:
            List of rendered charts
        """
        logger.info(f"Rendering {len(chart_configs)} charts in parallel...")
        
        tasks = [
            self.render_chart(df, config, theme)
            for config in chart_configs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        charts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Chart {i} failed: {result}")
            else:
                charts.append(result)
        
        logger.info(f"✓ Rendered {len(charts)}/{len(chart_configs)} charts successfully")
        return charts
    
    def _parse_config(self, chart_config: Dict[str, Any]) -> ChartConfig:
        """
        Parse chart config dict to ChartConfig object.
        
        Args:
            chart_config: Raw config dict
        
        Returns:
            ChartConfig object
        """
        try:
            # Handle chart_type
            chart_type_str = chart_config.get("chart_type", "bar")
            if isinstance(chart_type_str, str):
                chart_type = ChartType(chart_type_str.lower())
            else:
                chart_type = chart_type_str
            
            # Extract columns
            columns = chart_config.get("columns", [])
            if not columns:
                # Try x_axis, y_axis fallback
                x_axis = chart_config.get("x_axis")
                y_axis = chart_config.get("y_axis")
                if x_axis:
                    columns.append(x_axis)
                if y_axis:
                    columns.append(y_axis)
            
            # Create ChartConfig
            config = ChartConfig(
                chart_type=chart_type,
                columns=columns,
                aggregation=chart_config.get("aggregation", "none"),
                group_by=chart_config.get("group_by"),
                filters=chart_config.get("filters", []),
                sort_by=chart_config.get("sort_by"),
                limit=chart_config.get("limit", 1000)
            )
            
            return config
        
        except Exception as e:
            logger.error(f"Failed to parse chart config: {e}")
            raise ValueError(f"Invalid chart config: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "total_renders": self._render_count,
            "total_errors": self._error_count,
            "success_rate": (
                (self._render_count / (self._render_count + self._error_count))
                if (self._render_count + self._error_count) > 0
                else 1.0
            ),
            "cache_size": len(self._cache)
        }


# Singleton instance
chart_render_service = ChartRenderService()
