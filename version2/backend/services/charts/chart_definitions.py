# backend/core/chart_definitions.py
"""
Chart Definition Registry for DataSage AI.

This is the single source of truth for chart knowledge. Each chart entry contains:
- id: machine id
- name: human friendly
- description: purpose & guidance
- rules: structural validation rules (data types, column counts, special limits)
- use_cases: keywords to help AI map intent -> chart
- example_config: minimal UI-friendly example of how chart_config should look
"""

from enum import Enum
from typing import List, Dict, Any


class DataType(Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    BOOLEAN = "boolean"
    TEXT = "text"  # generic text


# A helper type alias for readability
ChartDef = Dict[str, Any]

CHART_DEFINITIONS: List[ChartDef] = [
    {
        "id": "bar",
        "name": "Bar Chart",
        "description": "Compare values across distinct categories. Good for ranking and discrete comparisons.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4},
            ],
            "min_columns": 1,
            "max_columns": 5,
            "max_categories": 200,
        },
        "use_cases": ["compare", "rank", "count", "top n", "distribution", "category"],
        "example_config": {
            "chart_type": "bar",
            "x": "category_col",
            "y": "value_col",
            "orientation": "vertical",
        },
    },
    {
        "id": "grouped_bar",
        "name": "Grouped Bar Chart",
        "description": "Compare multiple series across categories side by side. Ideal for multi-category comparisons.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 2},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 3},
            ],
            "min_columns": 2,
            "max_columns": 4,
        },
        "use_cases": [
            "compare groups",
            "side by side",
            "multi-category",
            "multi-metric comparison",
        ],
        "example_config": {
            "chart_type": "grouped_bar",
            "x": "category_col",
            "y": "value_col",
            "group": "subcategory_col",
        },
    },
    {
        "id": "stacked_bar",
        "name": "Stacked Bar Chart",
        "description": "Show total and composition across categories. Bars are stacked to show part-to-whole relationships.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 2},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 3},
            ],
            "min_columns": 2,
            "max_columns": 4,
        },
        "use_cases": [
            "total and composition",
            "part-to-whole",
            "cumulative comparison",
            "breakdown",
        ],
        "example_config": {
            "chart_type": "stacked_bar",
            "x": "category_col",
            "y": "value_col",
            "group": "subcategory_col",
        },
    },
    {
        "id": "line",
        "name": "Line Chart",
        "description": "Show trend or progression over a continuous axis (usually time).",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4},
            ],
            "min_columns": 2,
            "max_columns": 5,
        },
        "use_cases": ["trend", "time-series", "over time", "progress", "change"],
        "example_config": {
            "chart_type": "line",
            "x": "date_col",
            "y": "value_col",
            "interpolate": False,
        },
    },
    {
        "id": "multi_line",
        "name": "Multi-Line Chart",
        "description": "Compare multiple metrics over time on a single chart. Great for showing parallel trends.",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 2, "max": 5},
            ],
            "min_columns": 3,
            "max_columns": 6,
        },
        "use_cases": [
            "multiple trends",
            "compare metrics",
            "parallel time series",
            "multi-stream analysis",
        ],
        "example_config": {
            "chart_type": "multi_line",
            "x": "date_col",
            "y": ["value_col_1", "value_col_2", "value_col_3"],
            "aggregation": "sum",
        },
    },
    {
        "id": "stacked_area",
        "name": "Stacked Area Chart",
        "description": "Show cumulative composition of multiple metrics over time.",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 2, "max": 5},
            ],
            "min_columns": 3,
            "max_columns": 6,
        },
        "use_cases": [
            "cumulative trends",
            "composition over time",
            "stacked growth",
            "layered trends",
        ],
        "example_config": {
            "chart_type": "stacked_area",
            "x": "date_col",
            "y": ["value_col_1", "value_col_2"],
            "stacked": True,
        },
    },
    {
        "id": "scatter",
        "name": "Scatter Plot",
        "description": "Display relationship between two numeric variables; optionally color/size by category.",
        "rules": {
            "data_types": [
                {"type": DataType.NUMERIC.value, "min": 2, "max": 2},
                {"type": DataType.CATEGORICAL.value, "min": 0, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 3,
            "min_data_points": 10,
        },
        "use_cases": ["correlation", "relationship", "outliers", "clustering"],
        "example_config": {
            "chart_type": "scatter",
            "x": "num_col_1",
            "y": "num_col_2",
            "color": "category_col",
        },
    },
    {
        "id": "bubble",
        "name": "Bubble Chart",
        "description": "Display three variables (x, y, size) simultaneously. Great for 3D analysis on 2D canvas.",
        "rules": {
            "data_types": [
                {"type": DataType.NUMERIC.value, "min": 2, "max": 3},
                {"type": DataType.CATEGORICAL.value, "min": 0, "max": 1},
            ],
            "min_columns": 3,
            "max_columns": 4,
            "min_data_points": 10,
        },
        "use_cases": [
            "three variable analysis",
            "magnitude comparison",
            "market analysis",
            "performance metrics",
        ],
        "example_config": {
            "chart_type": "bubble",
            "x": "num_col_1",
            "y": "num_col_2",
            "size": "num_col_3",
            "color": "category_col",
        },
    },
    {
        "id": "pie",
        "name": "Pie Chart",
        "description": "Show proportions of a whole. Best for small numbers of categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
            "max_categories": 8,
        },
        "use_cases": ["composition", "proportion", "share", "percentage"],
        "example_config": {
            "chart_type": "pie",
            "labels": "category_col",
            "values": "value_col",
        },
    },
    {
        "id": "donut",
        "name": "Donut Chart",
        "description": "Pie chart with a hollow center. Modern alternative to pie charts.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
            "max_categories": 8,
        },
        "use_cases": ["composition", "proportion", "modern visualization"],
        "example_config": {
            "chart_type": "donut",
            "labels": "category_col",
            "values": "value_col",
        },
    },
    {
        "id": "treemap",
        "name": "Treemap",
        "description": "Visualize hierarchical proportion and size in nested rectangles.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 3},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 4,
        },
        "use_cases": ["hierarchy", "composition", "relative size", "nested categories"],
        "example_config": {
            "chart_type": "treemap",
            "path": ["category_level_1", "category_level_2"],
            "values": "value_col",
        },
    },
    {
        "id": "sunburst",
        "name": "Sunburst Chart",
        "description": "Radial hierarchical chart showing multi-level composition.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 3},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 4,
        },
        "use_cases": [
            "hierarchical composition",
            "multi-level breakdown",
            "radial hierarchy",
        ],
        "example_config": {
            "chart_type": "sunburst",
            "path": ["category_level_1", "category_level_2"],
            "values": "value_col",
        },
    },
    {
        "id": "histogram",
        "name": "Histogram",
        "description": "Show distribution of a single numeric variable.",
        "rules": {
            "data_types": [{"type": DataType.NUMERIC.value, "min": 1, "max": 1}],
            "min_columns": 1,
            "max_columns": 1,
            "min_data_points": 10,
        },
        "use_cases": ["distribution", "frequency", "skewness", "kurtosis"],
        "example_config": {"chart_type": "histogram", "x": "numeric_col", "bins": 30},
    },
    {
        "id": "box_plot",
        "name": "Box Plot",
        "description": "Visualize distribution (quartiles) and outliers across categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
        },
        "use_cases": [
            "compare spread",
            "outliers",
            "quartiles",
            "distribution across groups",
        ],
        "example_config": {
            "chart_type": "box_plot",
            "x": "category_col",
            "y": "numeric_col",
        },
    },
    {
        "id": "violin_plot",
        "name": "Violin Plot",
        "description": "Combine density plot and box plot to show distribution across categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
        },
        "use_cases": [
            "distribution across groups",
            "density",
            "compare spread",
            "probability density",
        ],
        "example_config": {
            "chart_type": "violin_plot",
            "x": "category_col",
            "y": "numeric_col",
        },
    },
    {
        "id": "heatmap",
        "name": "Heatmap",
        "description": "Show magnitude between two categorical axes (or a matrix) using color intensity.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 2, "max": 2},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 3,
            "max_columns": 3,
        },
        "use_cases": [
            "correlation matrix",
            "density",
            "magnitude between categories",
            "intensity map",
        ],
        "example_config": {
            "chart_type": "heatmap",
            "x": "category_x",
            "y": "category_y",
            "z": "value_col",
        },
    },
    {
        "id": "correlation_matrix",
        "name": "Correlation Matrix",
        "description": "Show pairwise correlations between all numeric variables.",
        "rules": {
            "data_types": [{"type": DataType.NUMERIC.value, "min": 3, "max": 10}],
            "min_columns": 3,
            "max_columns": 10,
        },
        "use_cases": [
            "correlation analysis",
            "variable relationships",
            "multivariate analysis",
        ],
        "example_config": {
            "chart_type": "correlation_matrix",
            "columns": ["num_col_1", "num_col_2", "num_col_3"],
        },
    },
    {
        "id": "area",
        "name": "Area Chart",
        "description": "Show cumulative totals over time or area under a line. Good for stacked trends.",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4},
            ],
            "min_columns": 2,
            "max_columns": 6,
        },
        "use_cases": ["cumulative", "time trend", "stacked area", "volume analysis"],
        "example_config": {
            "chart_type": "area",
            "x": "date_col",
            "y": "value_col",
            "stacked": False,
        },
    },
    {
        "id": "radar",
        "name": "Radar Chart",
        "description": "Compare multiple metrics across categories on a radial plot. Great for performance profiles.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 3, "max": 8},
            ],
            "min_columns": 4,
            "max_columns": 9,
        },
        "use_cases": [
            "performance profile",
            "skill comparison",
            "multi-metric overview",
            "strengths analysis",
        ],
        "example_config": {
            "chart_type": "radar",
            "category": "entity_col",
            "metrics": ["metric_1", "metric_2", "metric_3", "metric_4"],
        },
    },
    {
        "id": "waterfall",
        "name": "Waterfall Chart",
        "description": "Show sequential changes or cumulative effect of positive/negative values.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
        },
        "use_cases": [
            "financial flow",
            "profit breakdown",
            "cumulative effect",
            "sequential changes",
        ],
        "example_config": {
            "chart_type": "waterfall",
            "x": "stage_col",
            "y": "value_col",
        },
    },
    {
        "id": "funnel",
        "name": "Funnel Chart",
        "description": "Show progressive reduction of values through stages. Great for conversion analysis.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1},
            ],
            "min_columns": 2,
            "max_columns": 2,
            "max_categories": 8,
        },
        "use_cases": [
            "conversion funnel",
            "sales pipeline",
            "drop-off analysis",
            "stage progression",
        ],
        "example_config": {"chart_type": "funnel", "x": "stage_col", "y": "value_col"},
    },
]

# Convenience dictionary for fast lookup by id
CHART_DEFINITIONS_BY_ID = {c["id"]: c for c in CHART_DEFINITIONS}
