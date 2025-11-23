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
        "id": "bar_chart",
        "name": "Bar Chart",
        "description": "Compare values across distinct categories. Good for ranking and discrete comparisons.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4}
            ],
            "min_columns": 1,
            "max_columns": 5,
            "max_categories": 200
        },
        "use_cases": ["compare", "rank", "count", "top n", "distribution", "category"],
        "example_config": {
            "chart_type": "bar",
            "x": "category_col",
            "y": "value_col",
            "orientation": "vertical"
        }
    },
    {
        "id": "line_chart",
        "name": "Line Chart",
        "description": "Show trend or progression over a continuous axis (usually time).",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4}
            ],
            "min_columns": 2,
            "max_columns": 5
        },
        "use_cases": ["trend", "time-series", "over time", "progress", "change"],
        "example_config": {
            "chart_type": "line",
            "x": "date_col",
            "y": "value_col",
            "interpolate": False
        }
    },
    {
        "id": "scatter_plot",
        "name": "Scatter Plot",
        "description": "Display relationship between two numeric variables; optionally color/size by category.",
        "rules": {
            "data_types": [
                {"type": DataType.NUMERIC.value, "min": 2, "max": 2},
                {"type": DataType.CATEGORICAL.value, "min": 0, "max": 1}
            ],
            "min_columns": 2,
            "max_columns": 3,
            "min_data_points": 10
        },
        "use_cases": ["correlation", "relationship", "outliers", "clustering"],
        "example_config": {
            "chart_type": "scatter",
            "x": "num_col_1",
            "y": "num_col_2",
            "color": "category_col"
        }
    },
    {
        "id": "pie_chart",
        "name": "Pie Chart",
        "description": "Show proportions of a whole. Best for small numbers of categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 2,
            "max_columns": 2,
            "max_categories": 8
        },
        "use_cases": ["composition", "proportion", "share", "percentage"],
        "example_config": {
            "chart_type": "pie",
            "labels": "category_col",
            "values": "value_col"
        }
    },
    {
        "id": "histogram",
        "name": "Histogram",
        "description": "Show distribution of a single numeric variable.",
        "rules": {
            "data_types": [
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 1,
            "max_columns": 1,
            "min_data_points": 10
        },
        "use_cases": ["distribution", "frequency", "skewness", "kurtosis"],
        "example_config": {
            "chart_type": "histogram",
            "x": "numeric_col",
            "bins": 30
        }
    },
    {
        "id": "box_plot",
        "name": "Box Plot",
        "description": "Visualize distribution (quartiles) and outliers across categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 2,
            "max_columns": 2
        },
        "use_cases": ["compare spread", "outliers", "quartiles", "distribution across groups"],
        "example_config": {
            "chart_type": "box",
            "x": "category_col",
            "y": "numeric_col"
        }
    },
    {
        "id": "heatmap",
        "name": "Heatmap",
        "description": "Show magnitude between two categorical axes (or a matrix) using color intensity.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 2, "max": 2},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 3,
            "max_columns": 3
        },
        "use_cases": ["correlation matrix", "density", "magnitude between categories"],
        "example_config": {
            "chart_type": "heatmap",
            "x": "category_x",
            "y": "category_y",
            "z": "value_col"
        }
    },
    {
        "id": "area_chart",
        "name": "Area Chart",
        "description": "Show cumulative totals over time or area under a line. Good for stacked trends.",
        "rules": {
            "data_types": [
                {"type": DataType.TEMPORAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 4}
            ],
            "min_columns": 2,
            "max_columns": 6
        },
        "use_cases": ["cumulative", "time trend", "stacked area"],
        "example_config": {
            "chart_type": "area",
            "x": "date_col",
            "y": "value_col",
            "stacked": False
        }
    },
    {
        "id": "treemap",
        "name": "Treemap",
        "description": "Visualize hierarchical proportion and size in nested rectangles.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 3},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 2,
            "max_columns": 4
        },
        "use_cases": ["hierarchy", "composition", "relative size"],
        "example_config": {
            "chart_type": "treemap",
            "path": ["category_level_1", "category_level_2"],
            "values": "value_col"
        }
    },
    {
        "id": "violin_plot",
        "name": "Violin Plot",
        "description": "Combine density plot and box plot to show distribution across categories.",
        "rules": {
            "data_types": [
                {"type": DataType.CATEGORICAL.value, "min": 1, "max": 1},
                {"type": DataType.NUMERIC.value, "min": 1, "max": 1}
            ],
            "min_columns": 2,
            "max_columns": 2
        },
        "use_cases": ["distribution across groups", "density", "compare spread"],
        "example_config": {
            "chart_type": "violin",
            "x": "category_col",
            "y": "numeric_col"
        }
    }
]

# Convenience dictionary for fast lookup by id
CHART_DEFINITIONS_BY_ID = {c["id"]: c for c in CHART_DEFINITIONS}
