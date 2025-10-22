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

        # Default aggregations by data type for type-aware chart generation
        self.default_aggregations = {
            'Utf8': 'count',        # Categorical strings
            'Categorical': 'count', # Categorical data
            'Int64': 'sum',         # Numeric integers
            'Float64': 'sum',       # Numeric floats
            'Datetime': 'first',    # Temporal data
            'Boolean': 'count',     # Boolean data
        }

        # Map friendly names to internal standardized chart IDs
        self.chart_type_mapping = {
            # Basic Charts
            "bar": "bar",
            "bar_chart": "bar",
            "line": "line",
            "line_chart": "line",
            "area": "area",
            "area_chart": "area",
            "pie": "pie",
            "pie_chart": "pie",
            "donut": "donut",
            "donut_chart": "donut",
            "scatter": "scatter",
            "scatter_plot": "scatter",
            "histogram": "histogram",
            "boxplot": "boxplot",
            "box_plot": "boxplot",
            "box": "boxplot",
            
            # Advanced Charts
            "heatmap": "heatmap",
            "timeseries": "timeseries",
            "time_series": "timeseries",
            "candlestick": "candlestick",
            "bubble": "bubble",
            "bubble_chart": "bubble",
            "funnel": "funnel",
            "funnel_chart": "funnel",
            "treemap": "treemap",
            "tree_map": "treemap",
            "sunburst": "sunburst",
            "waterfall": "waterfall",
            "radar": "radar",
            "radar_chart": "radar",
            "violin": "violin",
            "violin_plot": "violin",
            "wordcloud": "wordcloud",
            "word_cloud": "wordcloud",
            
            # 3D Charts
            "scatter_3d": "scatter_3d",
            "3d_scatter": "scatter_3d",
            "3d scatter": "scatter_3d",
            "surface_3d": "surface_3d",
            "surface3d": "surface_3d",
            "3d_surface": "surface_3d",
            "3d surface": "surface_3d",
            
            # Specialized Charts
            "contour": "contour",
            "contour_plot": "contour",
            "parallel_coordinate": "parallel_coordinate",
            "parallel": "parallel_coordinate",
            "ternary": "ternary",
            "ternary_plot": "ternary",
            "log_chart": "log_chart",
            "log": "log_chart",
            "continuous_error_plot": "continuous_error_plot",
            "error_plot": "continuous_error_plot",
            
            # Statistical Charts
            "correlation_matrix": "correlation_matrix",
            "correlation": "correlation_matrix",
            
            # Grouped/Stacked Charts
            "grouped_bar": "grouped_bar",
            "groupedbar": "grouped_bar",
            "grouped_bar_chart": "grouped_bar",
            "stacked_bar": "stacked_bar",
            "stacked_bar_chart": "stacked_bar",
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
        Enhanced with type-aware validation and fallback suggestions.
        """
        try:
            # Validate and enhance chart configuration with type-aware defaults
            enhanced_config = self._validate_and_enhance_config(chart_config)

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

            # Generate chart data with enhanced error handling
            chart_data = await self.render_chart_from_config(enhanced_config, dataset_doc["file_path"])

            # Generate suggestions if chart generation failed
            suggestions = []
            if not chart_data or (len(chart_data) == 1 and not chart_data[0].get('x') and not chart_data[0].get('y')):
                suggestions = self._generate_suggestions(enhanced_config)

            return {
                "chart_data": chart_data,
                "chart_config": enhanced_config,
                "dataset_id": dataset_id,
                "rendered_at": datetime.now().isoformat(),
                "suggestions": suggestions
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
        """Primary entry point — loads dataset and routes to correct renderer with enhanced error handling."""
        try:
            df = self._load_dataset_data(file_path)
            
            # Sample large datasets for performance
            max_rows = 10000
            if len(df) > max_rows:
                df = df.sample(n=max_rows, shuffle=True)
                logger.info(f"Sampled dataset to {max_rows} rows for rendering")
            
            # Auto-enhance aggregation based on actual data types
            self._auto_enhance_aggregation(df, chart_config)
            
            return self._render_chart_data(df, chart_config)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chart rendering error: {e}", exc_info=True)
            return self._get_no_data_traces(chart_config)

    def _auto_enhance_aggregation(self, df: pl.DataFrame, config: Dict[str, Any]) -> None:
        """Auto-enhance aggregation based on actual data types."""
        columns = config.get("columns", [])
        if not columns:
            return
            
        # Check the value column (usually the last one)
        value_col = self._find_safe_column_name(df, columns[-1])
        if value_col:
            dtype_str = str(df[value_col].dtype)
            
            # Auto-set aggregation based on data type
            if dtype_str in ['Utf8', 'Categorical']:
                config["aggregation"] = "count"
                logger.info(f"Auto-set aggregation to 'count' for categorical column '{value_col}'")
            elif dtype_str in ['Int64', 'Float64'] and config.get("aggregation") == "count":
                # Only change if it was set to count, otherwise respect user choice
                config["aggregation"] = "sum"
                logger.info(f"Auto-set aggregation to 'sum' for numeric column '{value_col}'")

    def _get_no_data_traces(self, config: Dict[str, Any]) -> List[Dict]:
        """Returns placeholder traces for 'No Data' states."""
        chart_type = config.get("chart_type", "bar")
        
        if chart_type == "pie":
            return [{
                "labels": ["No Data"],
                "values": [1],
                "type": "pie",
                "textinfo": "label",
                "marker": {"colors": ["#e0e0e0"]}
            }]
        else:
            return [{
                "x": [],
                "y": [],
                "type": "scatter",
                "mode": "text",
                "text": ["No data available for this configuration"],
                "textposition": "middle center",
                "showlegend": False
            }]

    def _validate_and_enhance_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validates the chart config, standardizes chart_type, and auto-sets type-aware defaults."""
        enhanced = config.copy()
        chart_type = enhanced.get("chart_type")
        if not chart_type:
            raise HTTPException(status_code=400, detail="chart_type is required")

        # Standardize chart_type
        mapped = self.chart_type_mapping.get(str(chart_type).lower())
        if mapped:
            enhanced["chart_type"] = mapped
        else:
            enhanced["chart_type"] = str(chart_type)

        # Validate columns
        columns = enhanced.get("columns", [])
        if not columns:
            raise HTTPException(status_code=400, detail="columns are required")

        # Auto-detect aggregation if not specified or set to 'auto'
        aggregation = enhanced.get("aggregation", "auto")
        if aggregation == "auto":
            # Will be refined after data loading, but set safe default
            enhanced["aggregation"] = "count"  # Safe for most categorical data

        return enhanced

    def _generate_suggestions(self, config: Dict[str, Any]) -> List[str]:
        """Generates UI-friendly suggestions based on chart generation failures."""
        chart_type = config.get("chart_type", "")
        columns = config.get("columns", [])
        
        suggestions = [
            "Use 'Count' aggregation for categorical columns (e.g., Region, Product).",
            "Try 'Pie Chart' for categorical vs categorical (e.g., Region vs Product).",
            "Use 'Bar Chart' for categorical vs numeric.",
            "Use 'Scatter/Line Chart' for numeric vs numeric.",
            "Ensure your dataset has sufficient non-null data points.",
            "Try different column combinations if current ones don't work."
        ]
        
        # Chart-specific suggestions
        if chart_type in ["bar", "line"]:
            suggestions.insert(0, "For categorical data, try using 'Count' instead of 'Sum' aggregation.")
        elif chart_type == "pie":
            suggestions.insert(0, "Pie charts work best with categorical data and 'Count' aggregation.")
        elif chart_type == "scatter":
            suggestions.insert(0, "Scatter plots require numeric data for both X and Y axes.")
        
        return suggestions[:4]  # Limit to 4 suggestions for UI

    def _load_dataset_data(self, file_path: str) -> pl.DataFrame:
        """Loads dataset using Polars based on file type."""
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Dataset file not found: {file_path}")

        file_ext = path.suffix.lower()
        try:
            if file_ext == ".csv":
                # Load CSV with dynamic categorical column detection
                df = pl.read_csv(file_path, infer_schema_length=10000)
                
                # Enhanced categorical detection and conversion
                categorical_columns = self._detect_categorical_columns(df)
                for col in categorical_columns:
                    try:
                        original_type = df[col].dtype
                        # Convert to Utf8 and normalize for consistent grouping
                        df = df.with_columns(pl.col(col).cast(pl.Utf8).str.to_lowercase())
                        logger.info(f"Enhanced: Converted '{col}' from {original_type} to categorical string")
                    except Exception as e:
                        # If casting fails, keep original type
                        logger.warning(f"Failed to convert column '{col}' to categorical: {e}")
                        pass
                
                return df
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
        
        # For new format: columns array contains [x_axis, y_axis]
        # For old format: group_by + columns array
        if not columns:
            logger.warning("Missing required columns in config")
            return []

        # Check if we have the new format (columns array with x,y) or old format (group_by + columns)
        if len(columns) >= 2 and not group_by:
            # New format: columns[0] = x_axis, columns[1] = y_axis
            logger.info(f"Using new format: columns={columns}")
        elif group_by and columns:
            # Old format: group_by + columns
            logger.info(f"Using old format: group_by={group_by}, columns={columns}")
        else:
            logger.warning("Invalid column configuration - need either [x_axis, y_axis] or group_by + columns")
            return []

        # Validate that selected columns exist in the dataset
        for col in columns:
            safe_col = self._find_safe_column_name(df, col)
            if not safe_col:
                logger.warning(f"Column '{col}' not found in dataset")
                return []
        
        # For old format, also validate group_by
        if group_by:
            safe_group_by = self._find_safe_column_name(df, group_by)
            if not safe_group_by:
                logger.warning(f"Group by column '{group_by}' not found in dataset")
                return []

        router = {
            # Basic Charts
            "bar": self._render_bar_chart,
            "line": self._render_line_chart,
            "area": self._render_area_chart,
            "pie": self._render_pie_chart,
            "donut": self._render_donut_chart,
            "scatter": self._render_scatter_plot,
            "histogram": self._render_histogram,
            "boxplot": self._render_box_plot,
            
            # Advanced Charts
            "heatmap": self._render_heatmap,
            "timeseries": self._render_timeseries,
            "candlestick": self._render_candlestick,
            "bubble": self._render_bubble,
            "funnel": self._render_funnel,
            "treemap": self._render_treemap,
            "sunburst": self._render_sunburst,
            "waterfall": self._render_waterfall,
            "radar": self._render_radar,
            "violin": self._render_violin,
            "wordcloud": self._render_wordcloud,
            
            # 3D Charts
            "scatter_3d": self._render_scatter_3d,
            "surface_3d": self._render_surface_3d,
            
            # Specialized Charts
            "contour": self._render_contour,
            "parallel_coordinate": self._render_parallel_coordinate,
            "ternary": self._render_ternary_plot,
            "log_chart": self._render_log_chart,
            "continuous_error_plot": self._render_continuous_error_plot,
            
            # Statistical Charts
            "correlation_matrix": self._render_correlation_matrix,
            
            # Grouped/Stacked Charts
            "grouped_bar": self._render_grouped_bar_chart,
            "stacked_bar": self._render_stacked_bar_chart,
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
    def _detect_categorical_columns(self, df: pl.DataFrame, cardinality_threshold: int = 50) -> List[str]:
        """Enhanced categorical detection for String/Utf8 columns with cardinality analysis."""
        categorical_columns = []
        
        for col in df.columns:
            col_type = df[col].dtype
            col_lower = col.lower()
            
            # Skip if already string type (Utf8)
            if col_type == pl.Utf8:
                continue
                
            # Check if column name suggests it's categorical
            categorical_keywords = [
                'product', 'category', 'name', 'type', 'brand', 'model', 'id', 'code',
                'status', 'state', 'region', 'country', 'city', 'department', 'division',
                'class', 'group', 'tag', 'label', 'description', 'title', 'subject',
                'date', 'time', 'invoice', 'order', 'customer', 'supplier'  # Added common business terms
            ]
            
            is_categorical_by_name = any(keyword in col_lower for keyword in categorical_keywords)
            
            # Analyze data patterns to determine if it's categorical
            is_categorical_by_data = self._analyze_column_for_categorical_pattern(df, col, cardinality_threshold)
            
            # If either name suggests categorical OR data pattern suggests categorical
            if is_categorical_by_name or is_categorical_by_data:
                categorical_columns.append(col)
                logger.info(f"Detected categorical column '{col}' (name_match: {is_categorical_by_name}, data_match: {is_categorical_by_data})")
        
        return categorical_columns
    
    def _analyze_column_for_categorical_pattern(self, df: pl.DataFrame, col: str, cardinality_threshold: int = 50) -> bool:
        """Analyze column data to determine if it should be treated as categorical."""
        try:
            # Get a sample of non-null values
            sample_size = min(1000, len(df))
            sample_data = df[col].drop_nulls().head(sample_size)
            
            if sample_data.is_empty():  # Use explicit empty check
                return False
            
            # Convert to list for analysis
            values = sample_data.to_list()
            
            # Check cardinality first - if low cardinality, likely categorical
            unique_count = len(set(values))
            if unique_count <= cardinality_threshold:
                logger.info(f"Column '{col}' has low cardinality ({unique_count}), treating as categorical")
                return True
            
            # Check if values look like categorical data
            unique_ratio = unique_count / len(values)
            
            # If high uniqueness ratio, might be categorical
            if unique_ratio > 0.8:
                # Check if values are mostly non-numeric strings or mixed
                non_numeric_count = 0
                for val in values[:100]:  # Check first 100 values
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        non_numeric_count += 1
                
                # If more than 30% are non-numeric, treat as categorical
                if non_numeric_count / min(100, len(values)) > 0.3:
                    return True
            
            # Check if values are integers but represent categories (like IDs)
            if unique_ratio > 0.5 and all(isinstance(v, (int, float)) and v == int(v) for v in values[:50]):
                # If they're sequential integers starting from 1, might be categorical
                if min(values[:50]) == 1 and max(values[:50]) <= len(values) * 2:
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error analyzing column '{col}' for categorical pattern: {e}")
            return False

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

    def _aggregate_data_universal(self, df: pl.DataFrame, x_col: str, y_col: str, agg_method: str = "auto") -> List[Dict]:
        """Universal aggregation method that always returns lists to avoid DataFrame boolean ambiguity."""
        if not x_col or not y_col or x_col not in df.columns or y_col not in df.columns:
            logger.warning(f"Invalid columns for aggregation: x={x_col}, y={y_col}. Available: {df.columns}")
            return []

        # Auto-detect aggregation if needed
        if agg_method == "auto":
            agg_method = self._get_default_agg(df[y_col].dtype)

        # Filter nulls with explicit empty check
        filtered_df = df.filter(pl.col(x_col).is_not_null() & pl.col(y_col).is_not_null())
        logger.info(f"After null filter: {len(filtered_df)} rows from {len(df)}")
        if filtered_df.is_empty():  # Use explicit empty check
            logger.warning("No data after null filtering")
            return []

        try:
            # Apply aggregation with explicit expressions
            if agg_method == "count":
                result = filtered_df.group_by(x_col).agg(pl.len().alias("y")).sort("y", descending=True)
            elif agg_method == "sum":
                if df[y_col].dtype in pl.NUMERIC_DTYPES:
                    result = filtered_df.group_by(x_col).agg(pl.sum(y_col).alias("y")).sort("y", descending=True)
                else:
                    # For non-numeric, fall back to count
                    result = filtered_df.group_by(x_col).agg(pl.len().alias("y")).sort("y", descending=True)
            elif agg_method == "mean":
                if df[y_col].dtype in pl.NUMERIC_DTYPES:
                    result = filtered_df.group_by(x_col).agg(pl.mean(y_col).alias("y")).sort("y", descending=True)
                else:
                    result = filtered_df.group_by(x_col).agg(pl.len().alias("y")).sort("y", descending=True)
            else:
                # Default to count for unknown aggregations
                result = filtered_df.group_by(x_col).agg(pl.len().alias("y")).sort("y", descending=True)

            # Critical: Convert to list to avoid DataFrame boolean ambiguity
            rows = result.rename({x_col: "x"}).to_dicts()
            logger.info(f"Universal aggregation '{agg_method}' produced {len(rows)} rows")
            return rows
        except Exception as e:
            logger.error(f"Universal aggregation failed ({agg_method}): {e}")
            return []

    def _get_default_agg(self, col_dtype: pl.DataType) -> str:
        """Returns default aggregation based on dtype."""
        dtype_str = str(col_dtype).lower()
        for key, agg in self.default_aggregations.items():
            if key in dtype_str:
                return agg
        return "count"  # Fallback for unknown types

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
        """Enhanced bar chart renderer with type-aware aggregation."""
        columns = config.get("columns", [])
        group_by = config.get("group_by") or config.get("category")
        aggregation = config.get("aggregation", "auto")

        if len(columns) < 2:
            logger.warning("Bar chart requires at least 2 columns: [x_axis, y_axis]")
            return []

        # For bar chart: columns[0] = X-axis (Product), columns[1] = Y-axis (Sales Method)
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        
        if not x_col:
            logger.warning(f"X-axis column '{columns[0]}' not found")
            return []
        if not y_col:
            logger.warning(f"Y-axis column '{columns[1]}' not found")
            return []

        try:
            # Auto-determine aggregation if needed
            if aggregation == "auto":
                dtype_str = str(df[y_col].dtype)
                aggregation = self.default_aggregations.get(dtype_str, "count")
                logger.info(f"Auto-determined aggregation '{aggregation}' for column '{y_col}' with type {dtype_str}")

            # Apply aggregation with robust error handling
            if aggregation == "raw":
                # Use raw data without aggregation
                subset = df.select([x_col, y_col]).drop_nulls()
                if subset.is_empty():  # Use explicit empty check
                    logger.warning("No data after null filtering for raw aggregation")
                    return []
                    
                unique_data = subset.unique(subset=[x_col], keep="first")
                
                is_numeric = df[y_col].dtype in pl.NUMERIC_DTYPES
                if is_numeric:
                    y_values = [self._safe_to_numeric(v) for v in unique_data[y_col].to_list()]
                else:
                    y_values = list(range(1, len(unique_data) + 1))
                    
                x_values = unique_data[x_col].to_list()
            else:
                # Apply universal aggregation (always returns list)
                aggregated_rows = self._aggregate_data_universal(df, x_col, y_col, aggregation)
                if not aggregated_rows:  # Safe list check
                    logger.warning(f"Aggregation '{aggregation}' failed for columns {x_col}, {y_col}")
                    return []
                
                x_values = [row["x"] for row in aggregated_rows]
                y_values = [self._safe_to_numeric(row["y"]) for row in aggregated_rows]
            
            # Validate we have data
            if not x_values or not y_values:
                logger.warning("No data points generated for bar chart")
                return []
            
            # Log the data for debugging
            logger.info(f"Bar chart data: {len(x_values)} x-values, {len(y_values)} y-values")
            logger.info(f"Sample x-values: {x_values[:3]}")
            logger.info(f"Sample y-values: {y_values[:3]}")
            
            return [{
                "x": x_values,
                "y": y_values,
                "type": "bar",
                "x_axis_label": columns[0],
                "y_axis_label": f"{aggregation.title()} of {columns[1]}" if aggregation != "raw" else columns[1]
            }]
        except Exception as e:
            logger.error(f"Failed to create bar chart: {e}", exc_info=True)
            return []

    def _apply_type_safe_aggregation(self, df: pl.DataFrame, group_col: str, value_col: str, aggregation: str) -> List[Dict]:
        """Apply type-safe aggregation with proper error handling and list conversion."""
        try:
            # Filter nulls first
            filtered_df = df.filter(pl.col(group_col).is_not_null() & pl.col(value_col).is_not_null())
            if filtered_df.is_empty():  # Use explicit empty check instead of len() == 0
                logger.warning("No data after null filtering")
                return []
            
            # Apply aggregation based on type and method
            if aggregation == "count":
                result = filtered_df.group_by(group_col).agg(pl.len().alias("value"))
            elif aggregation == "sum":
                if df[value_col].dtype in pl.NUMERIC_DTYPES:
                    result = filtered_df.group_by(group_col).agg(pl.sum(value_col).alias("value"))
                else:
                    # For non-numeric, fall back to count
                    result = filtered_df.group_by(group_col).agg(pl.len().alias("value"))
            elif aggregation == "mean":
                if df[value_col].dtype in pl.NUMERIC_DTYPES:
                    result = filtered_df.group_by(group_col).agg(pl.mean(value_col).alias("value"))
                else:
                    result = filtered_df.group_by(group_col).agg(pl.len().alias("value"))
            else:
                # Default to count for unknown aggregations
                result = filtered_df.group_by(group_col).agg(pl.len().alias("value"))
            
            # Critical: Convert to list to avoid DataFrame boolean ambiguity
            sorted_result = result.sort("value", descending=True)
            rows = sorted_result.rename({group_col: "x"}).to_dicts()
            logger.info(f"Aggregation '{aggregation}' produced {len(rows)} rows")
            return rows
        except Exception as e:
            logger.error(f"Type-safe aggregation failed: {e}")
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
        """Enhanced pie chart renderer with type-aware aggregation and limits."""
        columns = config.get("columns", [])
        group_by = config.get("group_by") or config.get("category")
        aggregation = config.get("aggregation", "count")

        # Support both old format (group_by + columns) and new format (columns array)
        if len(columns) < 2:
            logger.warning("Pie chart requires at least 2 columns: [x_axis, y_axis]")
            return []

        # For new format: columns[0] = x_axis (categories), columns[1] = y_axis (values)
        # For old format: group_by = categories, columns[0] = values
        if group_by:
            # Old format
            safe_group_by = self._find_safe_column_name(df, group_by)
            value_col = self._find_safe_column_name(df, columns[0])
            if not safe_group_by or not value_col:
                logger.warning(f"Missing columns for pie chart: group_by={group_by}, value={columns[0]}")
                return []
        else:
            # New format: columns[0] = categories, columns[1] = values
            safe_group_by = self._find_safe_column_name(df, columns[0])
            value_col = self._find_safe_column_name(df, columns[1])
            if not safe_group_by or not value_col:
                logger.warning(f"Missing columns for pie chart: x_axis={columns[0]}, y_axis={columns[1]}")
                return []

        try:
            # Force count aggregation for pie charts (best practice)
            aggregation = "count"
            
            # Apply universal aggregation (always returns list)
            aggregated_rows = self._aggregate_data_universal(df, safe_group_by, value_col, aggregation)
            if not aggregated_rows:  # Safe list check
                logger.warning("No data after aggregation for pie chart")
                return []
            
            # Limit to top categories for readability
            max_categories = 8
            if len(aggregated_rows) > max_categories:
                aggregated_rows = aggregated_rows[:max_categories]  # Slice list instead of DataFrame
                logger.info(f"Limited pie chart to top {max_categories} categories")
            
            # Convert to pie chart format
            labels = [row["x"] for row in aggregated_rows]
            values = [self._safe_to_numeric(row["y"]) for row in aggregated_rows]
            
            # Validate we have data
            if not labels or not values:
                logger.warning("No data points generated for pie chart")
                return []
            
            logger.info(f"Pie chart generated with {len(labels)} categories")
            logger.info(f"Sample labels: {labels[:3]}")
            logger.info(f"Sample values: {values[:3]}")
            
            return [{
                "labels": labels,
                "values": values,
                "type": "pie",
                "textinfo": "label+percent",
                "textposition": "outside"
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
        """Enhanced scatter plot renderer with proper column mapping."""
        columns = config.get("columns", [])
        
        if len(columns) < 2:
            logger.warning("Scatter plot requires at least 2 columns: [x_axis, y_axis]")
            return []

        # For scatter plot: columns[0] = X-axis, columns[1] = Y-axis
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        
        if not x_col or not y_col:
            logger.warning(f"Missing columns for scatter plot: x={x_col}, y={y_col}")
            return []

        try:
            # Get sample of data for scatter plot (limit to 1000 points for performance)
            subset = df.select([x_col, y_col]).drop_nulls().limit(1000)
            
            if subset.is_empty():
                logger.warning("No data after null filtering for scatter plot")
                return []
            
            # Convert to numeric if possible
            x_values = [self._safe_to_numeric(v) for v in subset[x_col].to_list()]
            y_values = [self._safe_to_numeric(v) for v in subset[y_col].to_list()]
            
            # Filter out any None values
            valid_pairs = [(x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None]
            
            if not valid_pairs:
                logger.warning("No valid numeric pairs for scatter plot")
                return []
            
            x_values, y_values = zip(*valid_pairs)
            
            logger.info(f"Scatter plot data: {len(x_values)} points")
            
            return [{
                "x": list(x_values),
                "y": list(y_values),
                "type": "scatter",
                "mode": "markers",
                "marker": {"size": 6, "opacity": 0.7},
                "x_axis_label": columns[0],
                "y_axis_label": columns[1]
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

    # ---------------------------
    # MISSING RENDERERS
    # ---------------------------
    def _render_contour(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a contour plot."""
        columns = config.get("columns", [])
        if len(columns) < 3:
            return []
        
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        z_col = self._find_safe_column_name(df, columns[2])
        
        if not x_col or not y_col or not z_col:
            return []
        
        try:
            # Sample data for performance
            sample_size = min(1000, len(df))
            subset = df.select([x_col, y_col, z_col]).drop_nulls()
            if len(subset) > sample_size:
                subset = subset.sample(n=sample_size, shuffle=True)
            
            # Convert to numeric
            x_values = [self._safe_to_numeric(v) for v in subset[x_col].to_list()]
            y_values = [self._safe_to_numeric(v) for v in subset[y_col].to_list()]
            z_values = [self._safe_to_numeric(v) for v in subset[z_col].to_list()]
            
            return [{
                "x": x_values,
                "y": y_values,
                "z": z_values,
                "type": "contour",
                "colorscale": "Viridis"
            }]
        except Exception as e:
            logger.error(f"Failed to create contour plot: {e}", exc_info=True)
            return []

    def _render_parallel_coordinate(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a parallel coordinate plot."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        
        # Get all numeric columns or specified columns
        numeric_cols = [self._find_safe_column_name(df, col) for col in columns]
        numeric_cols = [col for col in numeric_cols if col and df[col].dtype in pl.NUMERIC_DTYPES]
        
        if len(numeric_cols) < 2:
            return []
        
        try:
            # Sample data for performance
            sample_size = min(500, len(df))
            subset = df.select(numeric_cols).drop_nulls()
            if len(subset) > sample_size:
                subset = subset.sample(n=sample_size, shuffle=True)
            
            # Convert to list of dictionaries for parallel coordinates
            data = []
            for row in subset.to_dicts():
                data.append({col: self._safe_to_numeric(row[col]) for col in numeric_cols})
            
            return [{
                "dimensions": [{"label": col, "values": [row[col] for row in data]} for col in numeric_cols],
                "type": "parcoords"
            }]
        except Exception as e:
            logger.error(f"Failed to create parallel coordinate plot: {e}", exc_info=True)
            return []

    def _render_ternary_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a ternary plot."""
        columns = config.get("columns", [])
        if len(columns) < 3:
            return []
        
        a_col = self._find_safe_column_name(df, columns[0])
        b_col = self._find_safe_column_name(df, columns[1])
        c_col = self._find_safe_column_name(df, columns[2])
        
        if not a_col or not b_col or not c_col:
            return []
        
        try:
            # Sample data for performance
            sample_size = min(1000, len(df))
            subset = df.select([a_col, b_col, c_col]).drop_nulls()
            if len(subset) > sample_size:
                subset = subset.sample(n=sample_size, shuffle=True)
            
            # Convert to numeric and normalize
            a_values = [self._safe_to_numeric(v) for v in subset[a_col].to_list()]
            b_values = [self._safe_to_numeric(v) for v in subset[b_col].to_list()]
            c_values = [self._safe_to_numeric(v) for v in subset[c_col].to_list()]
            
            # Normalize to sum to 1 for ternary plot
            normalized_data = []
            for a, b, c in zip(a_values, b_values, c_values):
                total = a + b + c
                if total > 0:
                    normalized_data.append({
                        "a": a / total,
                        "b": b / total,
                        "c": c / total
                    })
            
            if not normalized_data:
                return []
            
            return [{
                "a": [row["a"] for row in normalized_data],
                "b": [row["b"] for row in normalized_data],
                "c": [row["c"] for row in normalized_data],
                "type": "scatterternary",
                "mode": "markers"
            }]
        except Exception as e:
            logger.error(f"Failed to create ternary plot: {e}", exc_info=True)
            return []

    def _render_log_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a logarithmic scale chart."""
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        aggregation = config.get("aggregation", "sum")
        
        if len(columns) < 1 or not group_by:
            return []
        
        safe_group_by = self._find_safe_column_name(df, group_by)
        value_col = self._find_safe_column_name(df, columns[0])
        
        if not safe_group_by or not value_col:
            return []
        
        try:
            # Apply aggregation
            agg_func = self._get_aggregation_function(aggregation, df[value_col].dtype)
            aggregated_data = df.group_by(safe_group_by).agg([
                agg_func(value_col).alias("value")
            ]).sort("value", descending=True)
            
            x_values = aggregated_data[safe_group_by].to_list()
            y_values = [self._safe_to_numeric(v) for v in aggregated_data["value"].to_list()]
            
            return [{
                "x": x_values,
                "y": y_values,
                "type": "scatter",
                "mode": "lines+markers",
                "xaxis": {"type": "log"},
                "yaxis": {"type": "log"}
            }]
        except Exception as e:
            logger.error(f"Failed to create log chart: {e}", exc_info=True)
            return []

    def _render_continuous_error_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a continuous error plot with error bars."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            return []
        
        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        error_col = self._find_safe_column_name(df, columns[2]) if len(columns) > 2 else None
        
        if not x_col or not y_col:
            return []
        
        try:
            # Sample data for performance
            sample_size = min(1000, len(df))
            subset = df.select([x_col, y_col] + ([error_col] if error_col else [])).drop_nulls()
            if len(subset) > sample_size:
                subset = subset.sample(n=sample_size, shuffle=True)
            
            x_values = [self._safe_to_numeric(v) for v in subset[x_col].to_list()]
            y_values = [self._safe_to_numeric(v) for v in subset[y_col].to_list()]
            
            # Calculate error bars if error column not provided
            if error_col:
                error_values = [self._safe_to_numeric(v) for v in subset[error_col].to_list()]
            else:
                # Calculate standard deviation as error
                import statistics
                error_values = [statistics.stdev(y_values) if len(y_values) > 1 else 0] * len(y_values)
            
            return [{
                "x": x_values,
                "y": y_values,
                "error_y": {
                    "type": "data",
                    "array": error_values,
                    "visible": True
                },
                "type": "scatter",
                "mode": "lines+markers"
            }]
        except Exception as e:
            logger.error(f"Failed to create continuous error plot: {e}", exc_info=True)
            return []

    # ---------------------------
    # MISSING CHART TYPE RENDERERS
    # ---------------------------
    def _render_radar(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Enhanced radar chart renderer."""
        columns = config.get("columns", [])
        if len(columns) < 2:
            logger.warning("Radar chart requires at least 2 columns: [categories, values]")
            return []

        # For radar: columns[0] = categories, columns[1] = values
        category_col = self._find_safe_column_name(df, columns[0])
        value_col = self._find_safe_column_name(df, columns[1])
        
        if not category_col or not value_col:
            logger.warning(f"Missing columns for radar chart: cat={category_col}, val={value_col}")
            return []

        try:
            # Get unique categories
            categories = df[category_col].unique().to_list()
            if not categories:
                logger.warning("No categories found for radar chart")
                return []

            # Calculate values for each category
            values = []
            for cat in categories:
                cat_data = df.filter(pl.col(category_col) == cat)[value_col].drop_nulls()
                if not cat_data.is_empty():
                    if df[value_col].dtype in pl.NUMERIC_DTYPES:
                        values.append(self._safe_to_numeric(cat_data.mean()))
                    else:
                        values.append(len(cat_data))
                else:
                    values.append(0)

            logger.info(f"Radar chart data: {len(categories)} categories")
            
            return [{
                "r": values,
                "theta": categories,
                "type": "scatterpolar",
                "fill": "toself",
                "name": "Radar Data"
            }]
        except Exception as e:
            logger.error(f"Failed to create radar chart: {e}", exc_info=True)
            return []

    def _render_heatmap(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Enhanced heatmap renderer."""
        columns = config.get("columns", [])
        if len(columns) < 3:
            logger.warning("Heatmap requires at least 3 columns: [x_axis, y_axis, z_axis]")
            return []

        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        z_col = self._find_safe_column_name(df, columns[2])

        if not all([x_col, y_col, z_col]):
            logger.warning(f"Missing columns for heatmap: x={x_col}, y={y_col}, z={z_col}")
            return []

        try:
            # Create pivot table for heatmap
            pivot_df = df.pivot(values=z_col, index=y_col, columns=x_col, aggregate_function="mean").fill_null(0)
            
            if pivot_df.is_empty():
                logger.warning("No data after pivot for heatmap")
                return []

            x_cats = [col for col in pivot_df.columns if col != y_col]
            y_cats = pivot_df[y_col].to_list()
            z_matrix = pivot_df.select(pl.exclude(y_col)).to_numpy().tolist()

            logger.info(f"Heatmap data: {len(x_cats)} x {len(y_cats)} matrix")
            
            return [{
                "x": x_cats,
                "y": y_cats,
                "z": z_matrix,
                "type": "heatmap",
                "colorscale": "Viridis"
            }]
        except Exception as e:
            logger.error(f"Failed to create heatmap: {e}", exc_info=True)
            return []

    def _render_bubble(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Enhanced bubble chart renderer."""
        columns = config.get("columns", [])
        if len(columns) < 3:
            logger.warning("Bubble chart requires at least 3 columns: [x_axis, y_axis, size]")
            return []

        x_col = self._find_safe_column_name(df, columns[0])
        y_col = self._find_safe_column_name(df, columns[1])
        size_col = self._find_safe_column_name(df, columns[2])
        text_col = self._find_safe_column_name(df, columns[3]) if len(columns) > 3 else None

        if not all([x_col, y_col, size_col]):
            logger.warning(f"Missing columns for bubble chart: x={x_col}, y={y_col}, size={size_col}")
            return []

        try:
            # Sample data for performance
            sample_size = min(500, len(df))
            subset = df.select([x_col, y_col, size_col] + ([text_col] if text_col else [])).drop_nulls()
            if len(subset) > sample_size:
                subset = subset.sample(n=sample_size, shuffle=True)

            if subset.is_empty():
                logger.warning("No data after filtering for bubble chart")
                return []

            x_values = [self._safe_to_numeric(v) for v in subset[x_col].to_list()]
            y_values = [self._safe_to_numeric(v) for v in subset[y_col].to_list()]
            sizes = [self._safe_to_numeric(v) for v in subset[size_col].to_list()]
            texts = [self._safe_to_string(v) for v in subset[text_col].to_list()] if text_col else None

            # Normalize sizes for better visualization
            if sizes:
                max_size = max(sizes)
                min_size = min(sizes)
                if max_size != min_size:
                    sizes = [(s - min_size) / (max_size - min_size) * 20 + 5 for s in sizes]

            logger.info(f"Bubble chart data: {len(x_values)} points")

            trace = {
                "x": x_values,
                "y": y_values,
                "marker": {"size": sizes},
                "type": "scatter",
                "mode": "markers"
            }
            
            if texts:
                trace["text"] = texts
                trace["textposition"] = "top center"

            return [trace]
        except Exception as e:
            logger.error(f"Failed to create bubble chart: {e}", exc_info=True)
            return []


# Singleton instance for easy import
chart_render_service = ChartRenderService()
