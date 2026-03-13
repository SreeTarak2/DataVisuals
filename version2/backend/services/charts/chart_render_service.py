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
- Per-point statistical intelligence

Author: DataSage AI Team
Version: 2.1 (Production + Intelligence)
"""

import logging
import asyncio
import math
from typing import Dict, Any, List, Optional
from datetime import datetime
import polars as pl

from services.charts.render import ChartRenderer
from services.charts.hydrate import (
    hydrate_chart,
    validate_config,
    HydrationError
)
from db.schemas_dashboard import ChartConfig, ChartType, ComponentType
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

    def _compute_point_intelligence(
        self,
        traces: List[Dict[str, Any]],
        df: pl.DataFrame,
        chart_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute per-data-point statistical intelligence from the actual
        DataFrame and rendered traces. Pure math — no LLM, no latency.

        Returns a dict that the frontend can look up by category/x-value
        to show meaningful insights in the tooltip.

        Structure:
        {
            "y_label": "price",
            "x_label": "packaging_type",
            "total_records": 13000,
            "stats": {
                "mean": 120.5,
                "median": 115.0,
                "std": 34.2,
                "min": 10.0,
                "max": 450.0,
                "q1": 95.0,
                "q3": 145.0,
                "iqr": 50.0,
            },
            "points": {
                "Bottle": {
                    "value": 449400,
                    "rank": 1,
                    "percentile": 100,
                    "z_score": 1.82,
                    "vs_avg_pct": 23.5,
                    "is_outlier": false,
                    "record_count": 2100,
                    "insight": "Highest value — 23.5% above average"
                },
                ...
            }
        }
        """
        try:
            columns = chart_config.get("columns", [])
            if len(columns) < 2:
                return {}

            x_col, y_col = columns[0], columns[1]

            # Get trace data (the aggregated values actually shown in the chart)
            trace = traces[0] if traces else {}
            trace_type = trace.get("type", "bar")

            # For pie charts, labels/values instead of x/y
            if trace_type == "pie":
                x_values = trace.get("labels", [])
                y_values = trace.get("values", [])
            else:
                x_values = trace.get("x", [])
                y_values = trace.get("y", [])

            if not x_values or not y_values or len(x_values) != len(y_values):
                return {}

            # Convert to float safely
            numeric_values = []
            for v in y_values:
                try:
                    numeric_values.append(float(v))
                except (TypeError, ValueError):
                    numeric_values.append(0.0)

            n = len(numeric_values)
            if n == 0:
                return {}

            # ── Core statistics ──
            sorted_vals = sorted(numeric_values)
            total = sum(numeric_values)
            mean = total / n
            median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
            variance = sum((v - mean) ** 2 for v in numeric_values) / max(n - 1, 1)
            std = math.sqrt(variance) if variance > 0 else 0.0
            min_val = sorted_vals[0]
            max_val = sorted_vals[-1]
            q1 = sorted_vals[max(n // 4 - 1, 0)]
            q3 = sorted_vals[min(3 * n // 4, n - 1)]
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr

            # ── Per-category record counts (from raw DataFrame) ──
            record_counts = {}
            try:
                if x_col in df.columns:
                    counts = df.group_by(x_col).len()
                    for row in counts.iter_rows():
                        record_counts[str(row[0])] = row[1]
            except Exception:
                pass

            total_records = len(df)

            # ── Rank: sorted descending (1 = highest) ──
            rank_sorted = sorted(range(n), key=lambda i: numeric_values[i], reverse=True)
            rank_map = {}
            for rank_pos, idx in enumerate(rank_sorted):
                rank_map[idx] = rank_pos + 1

            # ── Build per-point intelligence ──
            points = {}
            for i, x_val in enumerate(x_values):
                val = numeric_values[i]
                x_key = str(x_val)
                rank = rank_map.get(i, i + 1)
                z_score = (val - mean) / std if std > 0 else 0.0
                vs_avg_pct = ((val - mean) / mean * 100) if mean != 0 else 0.0
                is_outlier = val < lower_fence or val > upper_fence
                percentile = round((1 - (rank - 1) / max(n - 1, 1)) * 100)
                rec_count = record_counts.get(x_key, None)

                # ── Generate a meaningful insight sentence ──
                insight = self._generate_point_insight(
                    val, mean, std, rank, n, vs_avg_pct, is_outlier, percentile, x_key, y_col
                )

                points[x_key] = {
                    "value": val,
                    "rank": rank,
                    "percentile": percentile,
                    "z_score": round(z_score, 2),
                    "vs_avg_pct": round(vs_avg_pct, 1),
                    "is_outlier": is_outlier,
                    "record_count": rec_count,
                    "insight": insight,
                }

            return {
                "y_label": y_col,
                "x_label": x_col,
                "total_records": total_records,
                "stats": {
                    "mean": round(mean, 2),
                    "median": round(median, 2),
                    "std": round(std, 2),
                    "min": round(min_val, 2),
                    "max": round(max_val, 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2),
                },
                "points": points,
            }

        except Exception as e:
            logger.warning(f"Point intelligence computation failed (non-fatal): {e}")
            return {}

    def _generate_point_insight(
        self, val, mean, std, rank, total, vs_avg_pct, is_outlier, percentile, x_key, y_col
    ) -> str:
        """Generate a concise, meaningful insight sentence for a single data point."""

        parts = []

        # Outlier flag — highest signal
        if is_outlier and val > mean:
            parts.append(f"Statistical outlier — unusually high {y_col}")
        elif is_outlier and val < mean:
            parts.append(f"Statistical outlier — unusually low {y_col}")

        # Rank-based insight
        if rank == 1:
            parts.append(f"Highest {y_col} across all {total} categories")
        elif rank == 2 and total > 3:
            parts.append(f"2nd highest — in the top tier")
        elif rank == total:
            parts.append(f"Lowest {y_col} across all {total} categories")
        elif rank == total - 1 and total > 3:
            parts.append(f"2nd lowest — near the bottom")

        # Deviation-based insight (only if not already covered by outlier/rank)
        if not parts:
            if vs_avg_pct > 40:
                parts.append(f"{vs_avg_pct:+.1f}% above average — a significant leader")
            elif vs_avg_pct > 15:
                parts.append(f"{vs_avg_pct:+.1f}% above average — a solid performer")
            elif vs_avg_pct > 0:
                parts.append(f"Slightly above average ({vs_avg_pct:+.1f}%)")
            elif vs_avg_pct > -15:
                parts.append(f"Slightly below average ({vs_avg_pct:+.1f}%)")
            elif vs_avg_pct > -40:
                parts.append(f"{vs_avg_pct:+.1f}% below average — underperforming")
            else:
                parts.append(f"{vs_avg_pct:+.1f}% below average — significantly trailing")

        # Add std context for outliers
        if is_outlier and std > 0:
            z = abs(val - mean) / std
            parts.append(f"{z:.1f}σ from the mean")

        return " · ".join(parts)
    
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
            
            # Handle both string and enum types for chart_type
            chart_type_str = config.chart_type.value if hasattr(config.chart_type, 'value') else config.chart_type
            
            # Hydrate: DataFrame → Plotly traces
            logger.info(f"Hydrating {chart_type_str} chart...")
            traces, rows_used = hydrate_chart(df, config)
            
            if not traces:
                raise HydrationError("No traces generated")
            
            # Render: Traces → Final Plotly payload
            logger.info(f"Rendering chart with {len(traces)} trace(s)...")
            chart_payload = self.renderer.render(
                chart_type=chart_type_str,
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
                "chart_type": chart_type_str,
                "render_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }

            # ── Compute per-point statistical intelligence ──
            try:
                point_intel = self._compute_point_intelligence(
                    traces=chart_payload.get("traces", traces),
                    df=df,
                    chart_config=chart_config,
                )
                if point_intel:
                    chart_payload["point_intelligence"] = point_intel
            except Exception as e:
                logger.warning(f"Point intelligence skipped: {e}")
            
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
                type=ComponentType.CHART,
                title=chart_config.get("title", "Chart"),
                chart_type=chart_type,
                columns=columns,
                aggregation=chart_config.get("aggregation", "none"),
                group_by=chart_config.get("group_by"),
                span=chart_config.get("span", 1)
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
