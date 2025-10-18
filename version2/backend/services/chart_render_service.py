# backend/services/chart_render_service.py

import logging
from typing import Dict, List, Any, Optional
import polars as pl
from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId
from pathlib import Path

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
            "bar chart": "bar_chart",
            "line": "line_chart",
            "line chart": "line_chart",
            "pie": "pie_chart",
            "pie chart": "pie_chart",
            "scatter": "scatter_plot",
            "scatter plot": "scatter_plot",
            "histogram": "histogram",
            "box": "box_plot",
            "box plot": "box_plot",
            "grouped bar": "grouped_bar_chart",
            "grouped bar chart": "grouped_bar_chart",
            "heatmap": "heatmap",
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
            # Validate chart configuration
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
        except Exception as e:
            logger.error(f"Chart rendering error: {e}", exc_info=True)
            return []

    def _validate_and_standardize_config(self, config: Dict[str, Any]):
        """Validates the chart config and standardizes chart_type."""
        chart_type = config.get("chart_type")
        if not chart_type:
            raise ValueError("chart_type is required")
        # Map to internal type if needed
        config["chart_type"] = self.chart_type_mapping.get(chart_type.lower(), chart_type)

    def _load_dataset_data(self, file_path: str) -> pl.DataFrame:
        """Loads dataset using Polars based on file type."""
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"Dataset file not found: {file_path}")

        file_ext = path.suffix.lower()
        try:
            if file_ext == ".csv":
                return pl.read_csv(file_path, infer_schema_length=10000)
            elif file_ext in [".xlsx", ".xls"]:
                return pl.read_excel(file_path)
            elif file_ext == ".json":
                return pl.read_json(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
        except Exception as e:
            logger.error(f"Failed to load dataset from {file_path}: {e}")
            raise ValueError(f"Could not load dataset: {str(e)}")

    def _render_chart_data(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Routes to specific renderer based on chart_type."""
        chart_type = config.get("chart_type", "bar_chart")
        if chart_type == "bar_chart":
            return self._render_bar_chart(df, config)
        elif chart_type == "line_chart":
            return self._render_line_chart(df, config)
        elif chart_type == "pie_chart":
            return self._render_pie_chart(df, config)
        elif chart_type == "scatter_plot":
            return self._render_scatter_plot(df, config)
        elif chart_type == "histogram":
            return self._render_histogram(df, config)
        elif chart_type == "box_plot":
            return self._render_box_plot(df, config)
        elif chart_type == "grouped_bar_chart":
            return self._render_grouped_bar_chart(df, config)
        else:
            logger.warning(f"Unsupported chart type: {chart_type}. Defaulting to bar_chart.")
            return self._render_bar_chart(df, config)

    # ---------------------------
    # SPECIFIC RENDER METHODS
    # ---------------------------
    def _render_bar_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a bar chart."""
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        aggregation = config.get("aggregation", "sum")

        if len(columns) < 1 or not group_by:
            return []

        safe_group_by = self._find_safe_column_name(df, group_by)
        if not safe_group_by:
            return []

        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]

        if not safe_cols:
            return []

        value_col = safe_cols[0]  # First column for values

        try:
            agg_df = df.group_by(safe_group_by).agg(
                pl.col(value_col).agg(getattr(pl, aggregation)()).alias("value")
            ).sort("value", descending=True).head(10)
            return [{
                "x": agg_df[safe_group_by].to_list(),
                "y": agg_df["value"].to_list(),
                "type": "bar"
            }]
        except Exception as e:
            logger.error(f"Failed to create bar chart: {e}", exc_info=True)
            return []

    def _render_line_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a line chart."""
        columns = config.get("columns", [])
        group_by = config.get("group_by")
        aggregation = config.get("aggregation", "sum")

        if len(columns) < 2 or not group_by:
            return []

        safe_group_by = self._find_safe_column_name(df, group_by)
        if not safe_group_by:
            return []

        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]

        if len(safe_cols) < 2:
            return []

        x_col, y_col = safe_cols[0], safe_cols[1]

        try:
            agg_df = df.group_by(safe_group_by).agg(
                pl.col(y_col).agg(getattr(pl, aggregation)()).alias("value")
            ).sort(safe_group_by)
            return [{
                "x": agg_df[safe_group_by].to_list(),
                "y": agg_df["value"].to_list(),
                "type": "scatter",
                "mode": "lines"
            }]
        except Exception as e:
            logger.error(f"Failed to create line chart: {e}", exc_info=True)
            return []

    def _render_pie_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a pie chart."""
        columns = config.get("columns", [])
        aggregation = config.get("aggregation", "sum")

        if len(columns) < 2:
            return []

        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]

        if len(safe_cols) < 2:
            return []

        labels_col, values_col = safe_cols[0], safe_cols[1]

        try:
            agg_df = df.group_by(labels_col).agg(
                pl.col(values_col).agg(getattr(pl, aggregation)()).alias("value")
            ).sort("value", descending=True).head(10)
            return [{
                "labels": agg_df[labels_col].to_list(),
                "values": agg_df["value"].to_list(),
                "type": "pie"
            }]
        except Exception as e:
            logger.error(f"Failed to create pie chart: {e}", exc_info=True)
            return []

    def _render_scatter_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a scatter plot."""
        columns = config.get("columns", [])
        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]
        if len(safe_cols) < 2:
            return []

        x_col, y_col = safe_cols[0], safe_cols[1]
        result_df = df.select([x_col, y_col]).drop_nulls().sample(
            n=min(len(df), 2000), shuffle=True
        )
        return [{
            "x": result_df[x_col].to_list(),
            "y": result_df[y_col].to_list(),
            "type": "scatter",
            "mode": "markers"
        }]

    def _render_histogram(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a histogram."""
        columns = config.get("columns", [])
        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]

        numeric_col = next((c for c in safe_cols if df[c].dtype in pl.NUMERIC_DTYPES), None)
        if not numeric_col:
            return []

        return [{
            "x": df[numeric_col].drop_nulls().to_list(),
            "type": "histogram"
        }]

    def _render_box_plot(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a box plot."""
        columns = config.get("columns", [])
        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]
        if len(safe_cols) < 2:
            return []

        cat_col = next((c for c in safe_cols if df[c].dtype in [pl.Utf8, pl.Categorical]), None)
        num_col = next((c for c in safe_cols if df[c].dtype in pl.NUMERIC_DTYPES), None)
        if not cat_col or not num_col:
            return []

        traces = []
        categories = df[cat_col].unique().drop_nulls().to_list()
        for cat in categories[:20]:  # Limit to 20 categories
            traces.append({
                "y": df.filter(pl.col(cat_col) == cat)[num_col].drop_nulls().to_list(),
                "type": "box",
                "name": str(cat),
            })
        return traces

    def _render_grouped_bar_chart(self, df: pl.DataFrame, config: Dict) -> List[Dict]:
        """Renders data for a grouped bar chart."""
        columns, group_by_raw = config.get("columns", []), config.get("group_by")
        if len(columns) < 2 or not group_by_raw:
            return []

        safe_cols = [self._find_safe_column_name(df, c) for c in columns if c]
        safe_cols = [c for c in safe_cols if c]

        group_by_list = [group_by_raw] if isinstance(group_by_raw, str) else group_by_raw
        safe_group_by = [self._find_safe_column_name(df, c) for c in group_by_list if c]
        safe_group_by = [c for c in safe_group_by if c]

        if len(safe_group_by) < 1 or len(safe_cols) < 2:
            return []

        index_col = safe_group_by[0]
        pivot_col = safe_group_by[1] if len(safe_group_by) > 1 else safe_cols[0]
        value_col = next((c for c in safe_cols if c not in [index_col, pivot_col]), None)
        if not value_col:
            return []

        try:
            # FIXED: Fallback to "count" if value_col is non-numeric
            value_col_dtype = df[value_col].dtype
            agg_fn = "sum" if value_col_dtype in pl.NUMERIC_DTYPES else "count"
            pivot_df = df.pivot(index=index_col, columns=pivot_col, values=value_col, aggregate_function=agg_fn).fill_null(0)
            traces = []
            for col in pivot_df.columns:
                if col != index_col:
                    traces.append({
                        "x": pivot_df[index_col].to_list(),
                        "y": pivot_df[col].to_list(),
                        "type": "bar",
                        "name": col,
                    })
            return traces
        except Exception as e:
            logger.error(f"Failed to create grouped bar chart: {e}", exc_info=True)
            return []

    def _find_safe_column_name(self, df: pl.DataFrame, col_name: str) -> Optional[str]:
        """Finds the closest matching column name."""
        if col_name in df.columns:
            return col_name
        # Simple fuzzy match: find columns containing the name
        matching = [col for col in df.columns if col_name.lower() in col.lower()]
        return matching[0] if matching else None


# Singleton instance for easy import
chart_render_service = ChartRenderService()