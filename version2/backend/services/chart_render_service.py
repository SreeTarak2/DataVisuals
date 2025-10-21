# backend/services/chart_render_service.py

import logging
from typing import Dict, List, Any, Optional, Union
import polars as pl
from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import math
import re
from collections import Counter

from database import get_database
from core.chart_definitions import CHART_DEFINITIONS

logger = logging.getLogger(__name__)


class ChartRenderService:
    """
    Deterministic, production-grade chart rendering service.
    Takes validated chart configs and produces Plotly-compatible data traces.
    """

    def __init__(self):
        # Pre-load chart definitions
        self.chart_definitions = {chart['id']: chart for chart in CHART_DEFINITIONS}

        # Map friendly names to internal standardized chart IDs
        self.chart_type_mapping = {
            "bar": "bar_chart",
            "bar_chart": "bar_chart",
            "line": "line_chart",
            "line_chart": "line_chart",
            "pie": "pie_chart",
            "pie_chart": "pie_chart",
            "donut": "donut_chart",
            "donut_chart": "donut_chart",
            "scatter": "scatter_plot",
            "scatter_plot": "scatter_plot",
            "3d scatter": "scatter_3d",
            "3d_scatter": "scatter_3d",
            "histogram": "histogram",
            "box": "box_plot",
            "box_plot": "box_plot",
            "groupedbar": "grouped_bar_chart",
            "grouped_bar": "grouped_bar_chart",
            "grouped_bar_chart": "grouped_bar_chart",
            "stacked_bar": "stacked_bar_chart",
            "stacked_bar_chart": "stacked_bar_chart",
            "heatmap": "heatmap",
            "correlation_matrix": "correlation_matrix",
            "timeseries": "timeseries",
            "candlestick": "candlestick",
            "bubble": "bubble",
            "funnel": "funnel",
            "treemap": "treemap",
            "sunburst": "sunburst",
            "waterfall": "waterfall",
            "radar": "radar",
            "radar_chart": "radar",
            "surface3d": "surface_3d",
            "surface_3d": "surface_3d",
            "violin": "violin",
            "wordcloud": "wordcloud"
        }

    # ---------------------------
    # DB CONNECTION
    # ---------------------------
    @property
    def db(self):
        """Lazily gets the database connection."""
        db_conn = get_database()
        if db_conn is None:
            raise Exception("Database not connected.")
        return db_conn

    # ---------------------------
    # MAIN ENTRYPOINT
    # ---------------------------
    async def render_chart(
        self,
        chart_config: Dict[str, Any],
        dataset_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Renders a chart based on configuration and returns Plotly-ready data.
        """
        try:
            # Validate chart configuration (standardize chart_type)
            self._validate_and_standardize_config(chart_config)

            # Fetch dataset from MongoDB
            try:
                query = {"_id": ObjectId(dataset_id), "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            dataset_doc = await self.db.datasets.find_one(query)
            if not dataset_doc:
                raise HTTPException(status_code=404, detail="Dataset not found")

            if not dataset_doc.get("file_path"):
                raise HTTPException(status_code=404, detail="Dataset file path not found")

            # Generate chart data
            chart_data = await self.render_chart_from_config(chart_config, dataset_doc["file_path"])

            return {
                "chart_data": chart_data,
                "chart_config": chart_config,
                "dataset_id": dataset_id,
                "rendered_at": datetime.now().isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chart rendering error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to render chart: {str(e)}")

    # ---------------------------
    # RENDERER CORE
    # ---------------------------
    async def render_chart_from_config(
        self, chart_config: Dict[str, Any], file_path: str
    ) -> List[Dict]:
        """Primary entry point — loads dataset and routes to correct renderer."""
        try:
            df = self._load_dataset_data(file_path)
            self._validate_and_standardize_config(chart_config)
            return self._render_chart_data(df, chart_config)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chart rendering error: {e}", exc_info=True)
            return []

    def _validate_and_standardize_config(self, config: Dict[str, Any]):
        """Validates the chart config and standardizes chart_type."""
        chart_type = config.get("chart_type")
        if not chart_type:
            raise HTTPException(status_code=400, detail="chart_type is required")
        # Map to internal type if needed
        mapped = self.chart_type_mapping.get(str(chart_type).lower())
        if mapped:
            config["chart_type"] = mapped
        else:
            config["chart_type"] = str(chart_type)

    def _load_dataset_data(self, file_path: str) -> pl.DataFrame:
        """Loads dataset using Polars based on file type."""
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Dataset file not found: {file_path}")

        file_ext = path.suffix.lower()
        try:
            if file_ext == ".csv":
                return pl.read_csv(file_path, infer_schema_length=10000)
            elif file_ext in [".xlsx", ".xls"]:
                return pl.read_excel(file_path)
            elif file_ext == ".json":
                # Polars supports read_jsonlines and read_ndjson; for single JSON try read_json
                try:
                    return pl.read_json(file_path)
                except Exception:
                    # try read_json with lines
                    return pl.read_ndjson(file_path)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to load dataset from {file_path}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Could not load dataset: {str(e)}")

    def _render_chart_data(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Routes to specific renderer based on chart_type."""
        chart_type = config.get("chart_type", "bar_chart")

        # Validate column selection before rendering
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        
        if not columns or not group_by:
            logger.warning("Missing required columns or group_by in config")
            return []

        # Validate that selected columns exist in the dataset
        safe_group_by = self._find_safe_column_name(df, group_by)
        if not safe_group_by:
            logger.warning(f"Group by column '{group_by}' not found in dataset")
            return []

        for col in columns:
            safe_col = self._find_safe_column_name(df, col)
            if not safe_col:
                logger.warning(f"Column '{col}' not found in dataset")
                return []

        router = {
            "bar": self._render_bar_chart,
            "bar_chart": self._render_bar_chart,
            "line": self._render_line_chart,
            "line_chart": self._render_line_chart,
            "area": self._render_area_chart,
            "area_chart": self._render_area_chart,
            "pie": self._render_pie_chart,
            "pie_chart": self._render_pie_chart,
            "donut_chart": self._render_donut_chart,
            "scatter": self._render_scatter_plot,
            "scatter_plot": self._render_scatter_plot,
            "scatter_3d": self._render_scatter_3d,
            "histogram": self._render_histogram,
            "boxplot": self._render_box_plot,
            "box_plot": self._render_box_plot,
            "grouped_bar_chart": self._render_grouped_bar_chart,
            "stacked_bar_chart": self._render_stacked_bar_chart,
            "heatmap": self._render_heatmap,
            "correlation_matrix": self._render_correlation_matrix,
            "timeseries": self._render_timeseries,
            "candlestick": self._render_candlestick,
            "bubble": self._render_bubble,
            "funnel": self._render_funnel,
            "treemap": self._render_treemap,
            "sunburst": self._render_sunburst,
            "waterfall": self._render_waterfall,
            "radar": self._render_radar,
            "surface_3d": self._render_surface_3d,
            "violin": self._render_violin,
            "wordcloud": self._render_wordcloud,
        }

        renderer = router.get(chart_type)
        if renderer:
            try:
                return renderer(df, config)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Renderer {chart_type} failed: {e}", exc_info=True)
                return []
        else:
            logger.warning(f"Unsupported chart type: {chart_type}. Defaulting to bar_chart.")
            return self._render_bar_chart(df, config)

    # ---------------------------
    # UTILITIES
    # ---------------------------
    def _find_safe_column_name(self, df: pl.DataFrame, col_name: Optional[str]) -> Optional[str]:
        """Finds the closest matching column name."""
        if not col_name:
            return None
        if col_name in df.columns:
            return col_name
        # Exact case-insensitive
        for col in df.columns:
            if col.lower() == col_name.lower():
                return col
        # Partial fuzzy match
        matches = [col for col in df.columns if col_name.lower() in col.lower() or col.lower() in col_name.lower()]
        return matches[0] if matches else None

    def _safe_to_numeric(self, v) -> float:
        if v is None:
            return 0.0
        try:
            return float(v)
        except Exception:
            if isinstance(v, str):
                nums = re.findall(r'-?\d+\.?\d*', v)
                if nums:
                    try:
                        return float(nums[0])
                    except Exception:
                        return 0.0
            return 0.0

    def _safe_to_string(self, v) -> str:
        if v is None:
            return "Unknown"
        return str(v)

    def _get_aggregation_function(self, aggregation: str, dtype) -> callable:
        """Returns the appropriate Polars aggregation function based on aggregation type and data type."""
        if aggregation == "sum":
            return lambda col: pl.col(col).sum()
        elif aggregation == "mean":
            return lambda col: pl.col(col).mean()
        elif aggregation == "count":
            return lambda col: pl.col(col).count()
        elif aggregation == "max":
            return lambda col: pl.col(col).max()
        elif aggregation == "min":
            return lambda col: pl.col(col).min()
        elif aggregation == "median":
            return lambda col: pl.col(col).median()
        elif aggregation == "std":
            return lambda col: pl.col(col).std()
        elif aggregation == "var":
            return lambda col: pl.col(col).var()
        else:
            # Default to sum for numeric, count for others
            if dtype in pl.NUMERIC_DTYPES:
                return lambda col: pl.col(col).sum()
            else:
                return lambda col: pl.col(col).count()

    # ---------------------------
    # RENDERERS (Implemented)
    # ---------------------------
    def _render_bar_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a bar chart with proper aggregation support."""
        columns = config.get("columns", [])
        group_by = config.get("group_by") or config.get("category")
        aggregation = config.get("aggregation", "sum")

        if len(columns) < 1 or not group_by:
            return []

        safe_group_by = self._find_safe_column_name(df, group_by)
        if not safe_group_by:
            return []

        value_col = self._find_safe_column_name(df, columns[0])
        if not value_col:
            return []

        try:
            # Apply aggregation based on configuration
            if aggregation == "raw":
                # Use raw data without aggregation
                subset = df.select([safe_group_by, value_col]).drop_nulls()
                unique_data = subset.unique(subset=[safe_group_by], keep="first")
                
                is_numeric = df[value_col].dtype in pl.NUMERIC_DTYPES
                if is_numeric:
                    y_values = [self._safe_to_numeric(v) for v in unique_data[value_col].to_list()]
                else:
                    y_values = list(range(1, len(unique_data) + 1))
            else:
                # Apply aggregation
                agg_func = self._get_aggregation_function(aggregation, df[value_col].dtype)
                aggregated_data = df.group_by(safe_group_by).agg([
                    agg_func(value_col).alias("value")
                ]).sort("value", descending=True)
                
                y_values = [self._safe_to_numeric(v) for v in aggregated_data["value"].to_list()]
                unique_data = aggregated_data
            
            return [{
                "x": unique_data[safe_group_by].to_list(),
                "y": y_values,
                "type": "bar",
                "x_axis_label": group_by,
                "y_axis_label": f"{aggregation.title()} of {columns[0]}" if aggregation != "raw" else columns[0]
            }]
        except Exception as e:
            logger.error(f"Failed to create bar chart: {e}", exc_info=True)
            return []

    def _render_line_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a line chart with aggregation support."""
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        aggregation = config.get("aggregation", "sum")
        
        if len(columns) < 1 or not group_by:
            return []

        value_col = self._find_safe_column_name(df, columns[0])
        safe_group_by = self._find_safe_column_name(df, group_by)
        if not value_col or not safe_group_by:
            return []

        try:
            if aggregation == "raw":
                # Use raw data without aggregation
                subset = df.select([safe_group_by, value_col]).drop_nulls().sort(safe_group_by)
                
                is_numeric = df[value_col].dtype in pl.NUMERIC_DTYPES
                if is_numeric:
                    y_values = [self._safe_to_numeric(v) for v in subset[value_col].to_list()]
                else:
                    y_values = list(range(1, len(subset) + 1))
                
                x_values = subset[safe_group_by].to_list()
            else:
                # Apply aggregation
                agg_func = self._get_aggregation_function(aggregation, df[value_col].dtype)
                aggregated_data = df.group_by(safe_group_by).agg([
                    agg_func(value_col).alias("value")
                ]).sort(safe_group_by)
                
                x_values = aggregated_data[safe_group_by].to_list()
                y_values = [self._safe_to_numeric(v) for v in aggregated_data["value"].to_list()]
            
            return [{
                "x": x_values,
                "y": y_values,
                "type": "scatter",
                "mode": "lines"
            }]
        except Exception as e:
            logger.error(f"Failed to create line chart: {e}", exc_info=True)
            return []

    def _render_area_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for an area chart with aggregation support."""
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        aggregation = config.get("aggregation", "sum")
        
        if len(columns) < 1 or not group_by:
            return []

        value_col = self._find_safe_column_name(df, columns[0])
        safe_group_by = self._find_safe_column_name(df, group_by)
        if not value_col or not safe_group_by:
            return []

        try:
            if aggregation == "raw":
                # Use raw data without aggregation
                subset = df.select([safe_group_by, value_col]).drop_nulls().sort(safe_group_by)
                
                is_numeric = df[value_col].dtype in pl.NUMERIC_DTYPES
                if is_numeric:
                    y_values = [self._safe_to_numeric(v) for v in subset[value_col].to_list()]
                else:
                    y_values = list(range(1, len(subset) + 1))
                
                x_values = subset[safe_group_by].to_list()
            else:
                # Apply aggregation
                agg_func = self._get_aggregation_function(aggregation, df[value_col].dtype)
                aggregated_data = df.group_by(safe_group_by).agg([
                    agg_func(value_col).alias("value")
                ]).sort(safe_group_by)
                
                x_values = aggregated_data[safe_group_by].to_list()
                y_values = [self._safe_to_numeric(v) for v in aggregated_data["value"].to_list()]
            
            return [{
                "x": x_values,
                "y": y_values,
                "type": "scatter",
                "mode": "lines",
                "fill": "tonexty"
            }]
        except Exception as e:
            logger.error(f"Failed to create area chart: {e}", exc_info=True)
            return []

    def _render_pie_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a pie chart with proper aggregation."""
        columns = config.get("columns", [])
        group_by = config.get("group_by") or config.get("category")
        aggregation = config.get("aggregation", "count")

        if len(columns) < 1 or not group_by:
            return []

        safe_group_by = self._find_safe_column_name(df, group_by)
        if not safe_group_by:
            return []

        value_col = self._find_safe_column_name(df, columns[0])
        if not value_col:
            return []

        try:
            # Apply aggregation for pie chart
            agg_func = self._get_aggregation_function(aggregation, df[value_col].dtype)
            aggregated_data = df.group_by(safe_group_by).agg([
                agg_func(value_col).alias("value")
            ]).sort("value", descending=True).limit(10)  # Limit to top 10 for readability
            
            # Convert to pie chart format
            pie_data = []
            for row in aggregated_data.to_dicts():
                pie_data.append({
                    "name": self._safe_to_string(row[safe_group_by]),
                    "value": self._safe_to_numeric(row["value"])
                })
            
            return [{
                "labels": [item["name"] for item in pie_data],
                "values": [item["value"] for item in pie_data],
                "type": "pie"
            }]
        except Exception as e:
            logger.error(f"Failed to create pie chart: {e}", exc_info=True)
            return []

    def _render_donut_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Donut is a pie with a hole. Frontend can set hole property."""
        base = self._render_pie_chart(df, config)
        if not base:
            return []
        # Add a 'hole' parameter (frontend should map this into Plotly's 'hole' attribute)
        base[0].update({"hole": config.get("hole", 0.4)})
        base[0]["type"] = "pie"
        return base

    def _render_scatter_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a scatter plot - X vs Y correlation."""
        columns = config.get("columns", [])
        
        if len(columns) < 2:
            return []

        # For scatter plot: columns[0] = X-axis, columns[1] = Y-axis
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        
        if not x_col or not y_col:
            return []

        try:
            # Get sample of data for scatter plot (limit to 1000 points for performance)
            subset = df.select([x_col, y_col]).drop_nulls().limit(1000)
            
            if len(subset) == 0:
                return []
            
            # Convert to numeric if possible
            x_values = [self._safe_to_numeric(v) for v in subset[x_col].to_list()]
            y_values = [self._safe_to_numeric(v) for v in subset[y_col].to_list()]
            
            # Filter out any None values
            valid_pairs = [(x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None]
            
            if not valid_pairs:
                return []
            
            x_values, y_values = zip(*valid_pairs)
            
            return [{
                "x": list(x_values),
                "y": list(y_values),
                "type": "scatter",
                "mode": "markers",
                "marker": {"size": 6, "opacity": 0.7},
                "insight": self._generate_scatter_insight(list(x_values), list(y_values), x_col, y_col)
            }]
        except Exception as e:
            logger.error(f"Failed to create scatter plot: {e}", exc_info=True)
            return []

    def _render_scatter_3d(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders 3D scatter; expects columns [x,y,z]."""
        columns = config.get("columns", [])
        if len(columns) < 3:
            return []
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        z_col = self._find_safe_column_name(df, columns[2])
        if not x_col or not y_col or not z_col:
            return []

        sample = config.get("sample", 2000)
        try:
            subset = df.select([x_col, y_col, z_col]).drop_nulls()
            n = min(len(subset), sample)
            if len(subset) > n:
                subset = subset.sample(n=n, shuffle=True)
            return [{
                "x": [self._safe_to_numeric(v) for v in subset[x_col].to_list()],
                "y": [self._safe_to_numeric(v) for v in subset[y_col].to_list()],
                "z": [self._safe_to_numeric(v) for v in subset[z_col].to_list()],
                "type": "scatter3d",
                "mode": "markers"
            }]
        except Exception as e:
            logger.error(f"Failed to create 3D scatter: {e}", exc_info=True)
            return []

    def _render_histogram(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a histogram with proper binning."""
        columns = config.get("columns", [])
        
        if len(columns) < 1:
            return []
            
        # Use the value column for histogram data
        col = self._find_safe_column_name(df, columns[0])
        if not col:
            return []
            
        try:
            # Get numeric data
            data = df[col].drop_nulls()
            
            # Convert to numeric if possible
            if df[col].dtype not in pl.NUMERIC_DTYPES:
                data = data.map_elements(lambda x: self._safe_to_numeric(x), return_dtype=pl.Float64)
            
            # Remove nulls after conversion
            data = data.drop_nulls()
            
            if len(data) == 0:
                return []
            
            # Create histogram bins
            values = data.to_list()
            min_val = min(values)
            max_val = max(values)
            
            # Create 20 bins
            num_bins = min(20, len(set(values)))
            bin_width = (max_val - min_val) / num_bins if max_val != min_val else 1
            
            bins = []
            counts = []
            
            for i in range(num_bins):
                bin_start = min_val + i * bin_width
                bin_end = min_val + (i + 1) * bin_width
                
                # Count values in this bin
                count = sum(1 for v in values if bin_start <= v < bin_end)
                if i == num_bins - 1:  # Last bin includes the max value
                    count = sum(1 for v in values if bin_start <= v <= bin_end)
                
                if count > 0:  # Only include non-empty bins
                    bins.append((bin_start + bin_end) / 2)  # Use bin center
                    counts.append(count)
            
            return [{
                "x": bins,
                "y": counts,
                "type": "bar",
                "name": f"Distribution of {col}",
                "marker": {"color": "rgba(55, 128, 191, 0.7)"},
                "insight": self._generate_histogram_insight(values, col)
            }]
        except Exception as e:
            logger.error(f"Failed to create histogram: {e}", exc_info=True)
            return []

    def _render_box_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a box plot grouped by category (columns[0]=category, columns[1]=value)."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        cat_col = self._find_safe_column_name(df, columns[0])
        num_col = self._find_safe_column_name(df, columns[1])
        if not cat_col or not num_col:
            return []
        try:
            cats = df[cat_col].drop_nulls().unique().to_list()
            traces = []
            for cat in cats[:20]:
                slice_df = df.filter(pl.col(cat_col) == cat)[num_col].drop_nulls()
                traces.append({
                    "y": [self._safe_to_numeric(v) for v in slice_df.to_list()],
                    "type": "box",
                    "name": self._safe_to_string(cat)
                })
            return traces
        except Exception as e:
            logger.error(f"Failed to create box plot: {e}", exc_info=True)
            return []

    def _render_grouped_bar_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a grouped bar chart."""
        columns = config.get("columns", [])
        group_by_raw = config.get("group_by")
        # columns typically: [value_col] or [value_col, series_col]
        if not group_by_raw or not columns:
            return []

        # group_by_raw can be single column or [index_col, pivot_col]
        if isinstance(group_by_raw, (list, tuple)):
            index_col = self._find_safe_column_name(df, group_by_raw[0])
            pivot_col = self._find_safe_column_name(df, group_by_raw[1]) if len(group_by_raw) > 1 else None
        else:
            index_col = self._find_safe_column_name(df, group_by_raw)
            pivot_col = self._find_safe_column_name(df, columns[1]) if len(columns) > 1 else None

        value_col = self._find_safe_column_name(df, columns[0])
        if not index_col or not value_col or not pivot_col:
            return []

        try:
            agg_fn = "sum" if df[value_col].dtype in pl.NUMERIC_DTYPES else "count"
            pivot_df = df.pivot(index=index_col, columns=pivot_col, values=value_col, aggregate_function=agg_fn).fill_null(0)
            traces = []
            for col in pivot_df.columns:
                if col != index_col:
                    traces.append({
                        "x": pivot_df[index_col].to_list(),
                        "y": [self._safe_to_numeric(v) for v in pivot_df[col].to_list()],
                        "type": "bar",
                        "name": self._safe_to_string(col)
                    })
            return traces
        except Exception as e:
            logger.error(f"Failed to create grouped bar chart: {e}", exc_info=True)
            return []

    def _render_stacked_bar_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders a stacked bar chart (similar pivot as grouped bar but frontend will use 'stack' mode)."""
        traces = self._render_grouped_bar_chart(df, config)
        # mark stacked mode on each trace
        for t in traces:
            t["stackgroup"] = config.get("stackgroup", "stack")
            t["type"] = "bar"
        return traces

    def _render_heatmap(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Generic heatmap from pivoting x,y,value. Returns single trace dict with x,y,z."""
        x_col = self._find_safe_column_name(df, config.get("x_axis") or (config.get("columns") and config.get("columns")[0]))
        y_col = self._find_safe_column_name(df, config.get("y_axis") or (config.get("columns") and (config.get("columns")[1] if len(config.get("columns")) > 1 else None)))
        z_col = self._find_safe_column_name(df, config.get("z_axis") or (config.get("columns") and (config.get("columns")[2] if len(config.get("columns")) > 2 else None)))

        if not x_col or not y_col or not z_col:
            # Attempt to produce correlation matrix if requested columns only
            return []

        try:
            pivot_df = df.pivot(index=y_col, columns=x_col, values=z_col, aggregate_function="mean").fill_null(0)
            y_vals = pivot_df[y_col].to_list()
            x_vals = [c for c in pivot_df.columns if c != y_col]
            z = pivot_df.select(pl.all().exclude(y_col)).to_numpy().tolist()
            return [{
                "x": x_vals,
                "y": y_vals,
                "z": z,
                "type": "heatmap"
            }]
        except Exception as e:
            logger.error(f"Failed to create heatmap: {e}", exc_info=True)
            return []

    def _render_correlation_matrix(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Creates correlation matrix heatmap for numeric columns provided in config.columns or top numeric columns."""
        cols = config.get("columns")
        if not cols:
            # choose numeric columns automatically
            numeric_cols = [c for c in df.columns if df[c].dtype in pl.NUMERIC_DTYPES]
            cols = numeric_cols[:10]  # limit size
        safe_cols = [self._find_safe_column_name(df, c) for c in cols if self._find_safe_column_name(df, c)]
        if len(safe_cols) < 2:
            return []

        try:
            # compute correlation matrix using Polars -> convert to pandas for corr if easier
            # Polars has pearson_corr for pairs, so compute matrix manually
            matrix = []
            for a in safe_cols:
                row = []
                for b in safe_cols:
                    try:
                        corr = df.select(pl.col(a).cast(pl.Float64)).to_pandas()[a].corr(df.select(pl.col(b).cast(pl.Float64)).to_pandas()[b])
                        row.append(0.0 if math.isnan(corr) else corr)
                    except Exception:
                        row.append(0.0)
                matrix.append(row)
            return [{
                "x": safe_cols,
                "y": safe_cols,
                "z": matrix,
                "type": "heatmap"
            }]
        except Exception as e:
            logger.error(f"Failed to create correlation matrix: {e}", exc_info=True)
            return []

    def _render_timeseries(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Timeseries expects columns: [time_col, value_col]."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        time_col = self._find_safe_column_name(df, columns[0])
        value_col = self._find_safe_column_name(df, columns[1])
        if not time_col or not value_col:
            return []

        try:
            df2 = df.select([time_col, value_col]).drop_nulls()
            # Attempt to parse datetimes
            try:
                df2 = df2.with_columns(pl.col(time_col).str.to_datetime().alias("_t")).sort("_t")
                xs = [t.isoformat() if t else self._safe_to_string(orig) for orig, t in zip(df2[time_col].to_list(), df2["_t"].to_list())]
            except Exception:
                df2 = df2.sort(time_col)
                xs = [self._safe_to_string(v) for v in df2[time_col].to_list()]

            ys = [self._safe_to_numeric(v) for v in df2[value_col].to_list()]
            return [{
                "x": xs,
                "y": ys,
                "type": "scatter",
                "mode": "lines+markers"
            }]
        except Exception as e:
            logger.error(f"Failed to render timeseries: {e}", exc_info=True)
            return []

    def _render_candlestick(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Candlestick uses columns open,high,low,close and time (optional)."""
        time_col = self._find_safe_column_name(df, config.get("x_axis") or config.get("time") or (df.columns[0] if df.columns else None))
        # find OHLC
        col_lookup = {c.lower(): c for c in df.columns}
        o = col_lookup.get("open") or col_lookup.get("o")
        h = col_lookup.get("high") or col_lookup.get("h")
        l = col_lookup.get("low") or col_lookup.get("l")
        ccol = col_lookup.get("close") or col_lookup.get("c")

        if all([o, h, l, ccol]):
            sample = df.select([time_col, o, h, l, ccol]).drop_nulls().limit(200)
            return [{
                "x": [self._safe_to_string(v) for v in sample[time_col].to_list()],
                "open": [self._safe_to_numeric(v) for v in sample[o].to_list()],
                "high": [self._safe_to_numeric(v) for v in sample[h].to_list()],
                "low": [self._safe_to_numeric(v) for v in sample[l].to_list()],
                "close": [self._safe_to_numeric(v) for v in sample[ccol].to_list()],
                "type": "candlestick"
            }]
        else:
            # synthesize OHLC from a single numeric column grouped by time
            columns = config.get("columns", [])
            if len(columns) < 2:
                return []
            idx_col = self._find_safe_column_name(df, columns[0])
            val_col = self._find_safe_column_name(df, columns[1])
            if not idx_col or not val_col:
                return []
            try:
                grouped = df.group_by(idx_col).agg([
                    pl.col(val_col).min().alias("low"),
                    pl.col(val_col).max().alias("high"),
                    pl.col(val_col).first().alias("open"),
                    pl.col(val_col).last().alias("close"),
                ]).sort(idx_col).limit(200)
                return [{
                    "x": grouped[idx_col].to_list(),
                    "open": [self._safe_to_numeric(v) for v in grouped["open"].to_list()],
                    "high": [self._safe_to_numeric(v) for v in grouped["high"].to_list()],
                    "low": [self._safe_to_numeric(v) for v in grouped["low"].to_list()],
                    "close": [self._safe_to_numeric(v) for v in grouped["close"].to_list()],
                    "type": "candlestick"
                }]
            except Exception as e:
                logger.error(f"Failed to create candlestick: {e}", exc_info=True)
                return []

    def _render_bubble(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Bubble chart expects columns [x,y,size, text?]"""
        cols = config.get("columns", [])
        if len(cols) < 3:
            return []
        x_col = self._find_safe_column_name(df, cols[0])
        y_col = self._find_safe_column_name(df, cols[1])
        size_col = self._find_safe_column_name(df, cols[2])
        text_col = self._find_safe_column_name(df, cols[3]) if len(cols) > 3 else None
        if not x_col or not y_col or not size_col:
            return []

        sample = min(len(df), config.get("sample", 500))
        try:
            subset = df.select([x_col, y_col, size_col] + ([text_col] if text_col else [])).drop_nulls()
            if len(subset) > sample:
                subset = subset.sample(n=sample, shuffle=True)
            return [{
                "x": [self._safe_to_numeric(v) for v in subset[x_col].to_list()],
                "y": [self._safe_to_numeric(v) for v in subset[y_col].to_list()],
                "marker": {"size": [self._safe_to_numeric(v) for v in subset[size_col].to_list()]},
                "text": [self._safe_to_string(v) for v in (subset[text_col].to_list() if text_col else [""] * len(subset))],
                "type": "scatter",
                "mode": "markers"
            }]
        except Exception as e:
            logger.error(f"Failed to create bubble chart: {e}", exc_info=True)
            return []

    def _render_funnel(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Simple funnel: group by stage and sum value column."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        stage_col = self._find_safe_column_name(df, columns[0])
        val_col = self._find_safe_column_name(df, columns[1])
        if not stage_col or not val_col:
            return []
        try:
            agg_df = df.group_by(stage_col).agg(pl.col(val_col).sum().alias("value")).sort("value", descending=True)
            return [{
                "stages": [self._safe_to_string(v) for v in agg_df[stage_col].to_list()],
                "values": [self._safe_to_numeric(v) for v in agg_df["value"].to_list()],
                "type": "funnel"
            }]
        except Exception as e:
            logger.error(f"Failed to create funnel: {e}", exc_info=True)
            return []

    def _render_treemap(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Treemap expects columns [name, value, parent?] or a path."""
        cols = config.get("columns", [])
        if not cols:
            return []
        name_col = self._find_safe_column_name(df, cols[0])
        value_col = self._find_safe_column_name(df, cols[1]) if len(cols) > 1 else None
        parent_col = self._find_safe_column_name(df, cols[2]) if len(cols) > 2 else None

        try:
            if parent_col:
                grouped = df.group_by([parent_col, name_col]).agg(pl.col(value_col).sum().alias("value")) if value_col else df.group_by([parent_col, name_col]).agg(pl.col(name_col).count().alias("value"))
                return [{
                    "labels": [self._safe_to_string(r[name_col]) for r in grouped.to_dicts()],
                    "parents": [self._safe_to_string(r[parent_col]) for r in grouped.to_dicts()],
                    "values": [self._safe_to_numeric(r["value"]) for r in grouped.to_dicts()],
                    "type": "treemap"
                }]
            else:
                grouped = df.group_by(name_col).agg(pl.col(value_col).sum().alias("value")) if value_col else df.group_by(name_col).agg(pl.col(name_col).count().alias("value"))
                grouped = grouped.sort("value", descending=True).limit(100)
                return [{
                    "labels": grouped[name_col].to_list(),
                    "parents": ["" for _ in grouped[name_col].to_list()],
                    "values": [self._safe_to_numeric(v) for v in grouped["value"].to_list()],
                    "type": "treemap"
                }]
        except Exception as e:
            logger.error(f"Failed to create treemap: {e}", exc_info=True)
            return []

    def _render_sunburst(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Sunburst expects a path or parent/name/value."""
        # columns: ["path_col"] or ["name", "parent", "value"]
        cols = config.get("columns", [])
        if not cols:
            return []
        if len(cols) == 1:
            path_col = self._find_safe_column_name(df, cols[0])
            if not path_col:
                return []
            # Expect path values as "A/B/C"
            rows = df.select(path_col).drop_nulls().to_series().to_list()
            labels, parents, values = [], [], []
            accumulator = {}
            for path in rows:
                parts = [p.strip() for p in str(path).split("/") if p.strip()]
                parent = ""
                for i, part in enumerate(parts):
                    key = (parent, part)
                    accumulator[key] = accumulator.get(key, 0) + 1
                    parent = part
            # convert accumulator into labels/parents/values
            for (parent, part), val in accumulator.items():
                labels.append(part)
                parents.append(parent if parent else "")
                values.append(val)
            return [{
                "labels": labels,
                "parents": parents,
                "values": values,
                "type": "sunburst"
            }]
        else:
            name_col = self._find_safe_column_name(df, cols[0])
            parent_col = self._find_safe_column_name(df, cols[1]) if len(cols) > 1 else None
            value_col = self._find_safe_column_name(df, cols[2]) if len(cols) > 2 else None
            if not name_col:
                return []
            try:
                if value_col:
                    grouped = df.group_by([parent_col, name_col]).agg(pl.col(value_col).sum().alias("value")) if parent_col else df.group_by(name_col).agg(pl.col(value_col).sum().alias("value"))
                else:
                    grouped = df.group_by([parent_col, name_col]).agg(pl.col(name_col).count().alias("value")) if parent_col else df.group_by(name_col).agg(pl.col(name_col).count().alias("value"))
                d = grouped.to_dicts()
                labels = [self._safe_to_string(r[name_col]) for r in d]
                parents = [self._safe_to_string(r[parent_col]) if parent_col and r.get(parent_col) else "" for r in d]
                values = [self._safe_to_numeric(r["value"]) for r in d]
                return [{
                    "labels": labels,
                    "parents": parents,
                    "values": values,
                    "type": "sunburst"
                }]
            except Exception as e:
                logger.error(f"Failed to create sunburst: {e}", exc_info=True)
                return []

    def _render_waterfall(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Returns a waterfall dataset as stages and values."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        stage_col = self._find_safe_column_name(df, columns[0])
        val_col = self._find_safe_column_name(df, columns[1])
        if not stage_col or not val_col:
            return []
        try:
            agg = df.group_by(stage_col).agg(pl.col(val_col).sum().alias("value")).sort(stage_col)
            stages = [self._safe_to_string(s) for s in agg[stage_col].to_list()]
            values = [self._safe_to_numeric(v) for v in agg["value"].to_list()]
            # add total
            total = sum(values)
            stages.append("Total")
            values.append(total)
            return [{
                "stages": stages,
                "values": values,
                "type": "waterfall"
            }]
        except Exception as e:
            logger.error(f"Failed to create waterfall: {e}", exc_info=True)
            return []

    def _render_radar(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Radar chart expects columns: categories_col (or columns list) and value columns per series."""
        # If config.columns is like ["category", "series1", "series2", ...]
        cols = config.get("columns", [])
        if not cols or len(cols) < 2:
            return []
        category_col = self._find_safe_column_name(df, cols[0])
        series_cols = [self._find_safe_column_name(df, c) for c in cols[1:]]
        series_cols = [c for c in series_cols if c]
        if not category_col or not series_cols:
            return []

        try:
            categories = df[category_col].drop_nulls().unique().to_list()
            traces = []
            for s in series_cols:
                values = []
                for cat in categories:
                    val_row = df.filter(pl.col(category_col) == cat)[s].drop_nulls()
                    if len(val_row) == 0:
                        values.append(0.0)
                    else:
                        # aggregate mean/sum depending on dtype
                        if df[s].dtype in pl.NUMERIC_DTYPES:
                            values.append(self._safe_to_numeric(val_row.mean()))
                        else:
                            values.append(len(val_row))
                traces.append({
                    "r": [self._safe_to_numeric(v) for v in values],
                    "theta": [self._safe_to_string(c) for c in categories],
                    "type": "scatterpolar",
                    "fill": "toself",
                    "name": self._safe_to_string(s)
                })
            return traces
        except Exception as e:
            logger.error(f"Failed to create radar chart: {e}", exc_info=True)
            return []

    def _render_surface_3d(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Create a 3D surface by pivoting x and y into a grid and using z for heights."""
        x_col = self._find_safe_column_name(df, config.get("x_axis") or (config.get("columns") and config.get("columns")[0]))
        y_col = self._find_safe_column_name(df, config.get("y_axis") or (config.get("columns") and (config.get("columns")[1] if len(config.get("columns")) > 1 else None)))
        z_col = self._find_safe_column_name(df, config.get("z_axis") or (config.get("columns") and (config.get("columns")[2] if len(config.get("columns")) > 2 else None)))

        if not x_col or not y_col or not z_col:
            return []

        try:
            pivot_df = df.pivot(index=y_col, columns=x_col, values=z_col, aggregate_function="mean").fill_null(0)
            z = pivot_df.select(pl.all().exclude(y_col)).to_numpy().tolist()
            x_vals = [self._safe_to_string(c) for c in pivot_df.columns if c != y_col]
            y_vals = pivot_df[y_col].to_list()
            return [{
                "x": x_vals,
                "y": y_vals,
                "z": z,
                "type": "surface"
            }]
        except Exception as e:
            logger.error(f"Failed to create 3D surface: {e}", exc_info=True)
            return []

    def _render_violin(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Violin plots grouped by a categorical column."""
        cols = config.get("columns", [])
        if len(cols) < 2:
            return []
        cat_col = self._find_safe_column_name(df, cols[0])
        val_col = self._find_safe_column_name(df, cols[1])
        if not cat_col or not val_col:
            return []
        try:
            cats = df[cat_col].drop_nulls().unique().to_list()
            traces = []
            for cat in cats[:20]:
                vals = df.filter(pl.col(cat_col) == cat)[val_col].drop_nulls().to_list()
                if not vals:
                    continue
                traces.append({
                    "y": [self._safe_to_numeric(v) for v in vals],
                    "type": "violin",
                    "name": self._safe_to_string(cat)
                })
            return traces
        except Exception as e:
            logger.error(f"Failed to create violin plot: {e}", exc_info=True)
            return []

    def _render_wordcloud(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Generates word frequencies for a word cloud. Frontend should render visually."""
        text_col = self._find_safe_column_name(df, config.get("text_column") or (config.get("columns") and config.get("columns")[0]))
        if not text_col:
            return []
        top_n = int(config.get("top_n", 100))
        try:
            all_texts = df[text_col].drop_nulls().to_list()
            words = []
            for t in all_texts:
                # basic tokenization
                toks = re.findall(r"\w{2,}", str(t).lower())
                words.extend(toks)
            freqs = Counter(words).most_common(top_n)
            return [{
                "words": [{"word": w, "count": c} for w, c in freqs],
                "type": "wordcloud"
            }]
        except Exception as e:
            logger.error(f"Failed to create wordcloud data: {e}", exc_info=True)
            return []

    def _generate_histogram_insight(self, values: List[float], column_name: str) -> Dict[str, Any]:
        """Generate insights for histogram data."""
        if not values:
            return {"summary": "No data available for analysis"}
        
        import statistics
        
        mean_val = statistics.mean(values)
        median_val = statistics.median(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 0
        
        # Determine distribution shape
        if abs(mean_val - median_val) < std_val * 0.1:
            shape = "approximately normal"
        elif mean_val > median_val:
            shape = "right-skewed (positive skew)"
        else:
            shape = "left-skewed (negative skew)"
        
        # Find outliers (values beyond 2 standard deviations)
        outliers = [v for v in values if abs(v - mean_val) > 2 * std_val]
        outlier_pct = (len(outliers) / len(values)) * 100
        
        insights = {
            "summary": f"Distribution analysis of {column_name} shows {shape} pattern with mean {mean_val:.1f} and median {median_val:.1f}.",
            "key_findings": [
                f"Average value: {mean_val:.1f}",
                f"Median value: {median_val:.1f}",
                f"Standard deviation: {std_val:.1f}",
                f"Distribution is {shape}",
                f"Outlier rate: {outlier_pct:.1f}% ({len(outliers)} out of {len(values)} values)"
            ],
            "recommendations": [
                f"Focus on the {mean_val:.1f} range for typical values",
                "Investigate outliers if they represent significant business events",
                "Consider segmentation if distribution shows multiple peaks"
            ],
            "business_impact": f"Understanding {column_name} distribution helps identify typical ranges and unusual patterns that may indicate opportunities or risks."
        }
        
        return insights

    def _generate_scatter_insight(self, x_values: List[float], y_values: List[float], x_col: str, y_col: str) -> Dict[str, Any]:
        """Generate insights for scatter plot data."""
        if not x_values or not y_values:
            return {"summary": "No data available for correlation analysis"}
        
        import statistics
        
        # Calculate correlation
        n = len(x_values)
        if n < 2:
            return {"summary": "Insufficient data for correlation analysis"}
        
        mean_x = statistics.mean(x_values)
        mean_y = statistics.mean(y_values)
        
        # Simple correlation calculation
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
        denominator_x = sum((x - mean_x) ** 2 for x in x_values)
        denominator_y = sum((y - mean_y) ** 2 for y in y_values)
        
        if denominator_x == 0 or denominator_y == 0:
            correlation = 0
        else:
            correlation = numerator / (denominator_x * denominator_y) ** 0.5
        
        # Interpret correlation strength
        if abs(correlation) > 0.7:
            strength = "strong"
        elif abs(correlation) > 0.4:
            strength = "moderate"
        elif abs(correlation) > 0.2:
            strength = "weak"
        else:
            strength = "very weak"
        
        direction = "positive" if correlation > 0 else "negative"
        
        insights = {
            "summary": f"Correlation analysis between {x_col} and {y_col} shows {strength} {direction} relationship (r={correlation:.3f}).",
            "key_findings": [
                f"Correlation coefficient: {correlation:.3f}",
                f"Relationship strength: {strength}",
                f"Direction: {direction}",
                f"Sample size: {n} data points"
            ],
            "recommendations": [
                f"Consider {x_col} as a predictor for {y_col}" if abs(correlation) > 0.5 else "Relationship may not be strong enough for prediction",
                "Investigate causal factors if correlation is strong",
                "Look for confounding variables that might explain the relationship"
            ],
            "business_impact": f"Understanding the relationship between {x_col} and {y_col} can help optimize business strategies and identify key performance drivers."
        }
        
        return insights


# Singleton instance for easy import
chart_render_service = ChartRenderService()
