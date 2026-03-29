"""
Chart Validator Service
=====================
LLM-powered chart validation to ensure best chart selection.

Features:
1. Story Validation - "Does this chart reveal the story in the data?"
2. Axis Recommendations - % vs absolute, log vs linear
3. Chart Quality Scoring - Is this the best visualization?
4. Alternative Suggestions - Better chart types if needed

Author: DataSage AI Team
Version: 1.0
"""

import logging
from typing import Dict, List, Any, Optional
import polars as pl
from services.llm_router import llm_router

logger = logging.getLogger(__name__)


class ChartValidator:
    """
    Validates chart recommendations using LLM for quality assurance.

    Asks: "Does this chart reveal the story? If not, suggest better alternatives."
    """

    def __init__(self):
        self.validation_prompt_template = """You are a data visualization expert. Evaluate this chart recommendation.

DATA PROFILE:
{stats_summary}

RECOMMENDED CHART:
- Type: {chart_type}
- Title: {chart_title}
- Columns: {columns}
- Aggregation: {aggregation}

DETECTED STORIES IN DATA:
{stories}

TASK:
1. Does this chart reveal one of the detected stories?
2. Is this the BEST chart type for revealing insights?
3. What would be a better alternative if any?

Return JSON:
{{
    "is_valid": true/false,
    "revels_story": "which story it reveals or null",
    "quality_score": 1-10,
    "reason": "brief explanation",
    "suggested_alternative": {{"type": "...", "reason": "..."}} or null,
    "axis_recommendations": {{
        "x_scale": "linear/log/percentage",
        "y_scale": "linear/log/percentage",
        "show_trend_line": true/false
    }}
}}"""

    async def validate_chart(
        self,
        chart_config: Dict[str, Any],
        df_stats: Dict[str, Any],
        stories: List[Dict[str, Any]],
        column_metadata: List[Dict],
    ) -> Dict[str, Any]:
        """
        Validate a single chart recommendation using LLM.

        Args:
            chart_config: Chart configuration (type, title, columns, etc.)
            df_stats: Data statistics for context
            stories: Detected stories in the data
            column_metadata: Column metadata

        Returns:
            Validation result with quality score and suggestions
        """
        try:
            # Build stats summary
            stats_summary = self._build_stats_summary(df_stats, column_metadata)

            # Build stories summary
            stories_summary = self._build_stories_summary(stories)

            # Build prompt
            prompt = self.validation_prompt_template.format(
                stats_summary=stats_summary,
                chart_type=chart_config.get("chart_type", "unknown"),
                chart_title=chart_config.get("title", "Untitled"),
                columns=str(
                    chart_config.get(
                        "columns", chart_config.get("config", {}).get("columns", [])
                    )
                ),
                aggregation=chart_config.get("config", {}).get("aggregation", "none"),
                stories=stories_summary,
            )

            # Call LLM
            response = await llm_router.call(
                prompt=prompt,
                model_role="chart_recommendation",
                expect_json=True,
                temperature=0.1,  # Low temperature for consistent validation
            )

            # Parse response
            if isinstance(response, dict):
                return self._parse_validation_response(response, chart_config)
            else:
                logger.warning(f"Invalid validation response: {response}")
                return self._default_validation(chart_config)

        except Exception as e:
            logger.warning(f"Chart validation failed: {e}")
            return self._default_validation(chart_config)

    async def validate_charts_batch(
        self,
        charts: List[Dict[str, Any]],
        df_stats: Dict[str, Any],
        stories: List[Dict[str, Any]],
        column_metadata: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple charts in batch (optimized for cost).

        Uses a single LLM call to validate all charts together.
        """
        if not charts:
            return []

        try:
            # Build batch prompt
            prompt = self._build_batch_validation_prompt(
                charts, df_stats, stories, column_metadata
            )

            # Single LLM call for all charts
            response = await llm_router.call(
                prompt=prompt,
                model_role="chart_recommendation",
                expect_json=True,
                temperature=0.1,
            )

            # Parse and match responses to charts
            if isinstance(response, dict) and "validations" in response:
                return self._match_validations_to_charts(
                    response["validations"], charts
                )
            else:
                # Fallback to default validation
                return [self._default_validation(c) for c in charts]

        except Exception as e:
            logger.warning(f"Batch validation failed: {e}")
            return [self._default_validation(c) for c in charts]

    def _build_stats_summary(self, df_stats: Dict, column_metadata: List[Dict]) -> str:
        """Build a concise stats summary for the prompt."""
        lines = [
            f"Rows: {df_stats.get('row_count', 'unknown')}",
            f"Columns: {df_stats.get('column_count', 'unknown')}",
            f"Numeric columns: {df_stats.get('numeric_count', 0)}",
            f"Categorical columns: {df_stats.get('categorical_count', 0)}",
            f"Has time data: {df_stats.get('has_time_column', False)}",
        ]

        # Add correlation info
        correlations = df_stats.get("correlations", [])
        if correlations:
            top_corr = correlations[:3]
            corr_str = ", ".join(
                [
                    f"{c.get('column1')}↔{c.get('column2')}: {c.get('correlation', 0):.2f}"
                    for c in top_corr
                ]
            )
            lines.append(f"Top correlations: {corr_str}")

        # Add cardinality info
        low_card = df_stats.get("low_cardinality_dims", [])
        if low_card:
            lines.append(
                f"Low cardinality columns (good for grouping): {', '.join(low_card[:5])}"
            )

        return "\n".join(lines)

    def _build_stories_summary(self, stories: List[Dict]) -> str:
        """Build stories summary for the prompt."""
        if not stories:
            return "No specific stories detected yet."

        lines = []
        for i, story in enumerate(stories[:5], 1):
            lines.append(
                f"{i}. {story.get('title', 'Story')}: {story.get('description', '')}"
            )

        return "\n".join(lines) if lines else "No stories detected."

    def _build_batch_validation_prompt(
        self,
        charts: List[Dict[str, Any]],
        df_stats: Dict,
        stories: List[Dict[str, Any]],
        column_metadata: List[Dict],
    ) -> str:
        """Build a batch validation prompt."""
        stats_summary = self._build_stats_summary(df_stats, column_metadata)
        stories_summary = self._build_stories_summary(stories)

        charts_json = []
        for i, chart in enumerate(charts, 1):
            charts_json.append(f"""
Chart {i}:
- Type: {chart.get("chart_type", "unknown")}
- Title: {chart.get("title", "Untitled")}
- Columns: {chart.get("columns", chart.get("config", {}).get("columns", []))}
- Aggregation: {chart.get("config", {}).get("aggregation", "none")}
""")

        return f"""You are a data visualization expert. Validate each chart recommendation.

DATA PROFILE:
{stats_summary}

DETECTED STORIES:
{stories_summary}

CHARTS TO VALIDATE:
{chr(10).join(charts_json)}

TASK:
For EACH chart, evaluate:
1. Does it reveal one of the detected stories?
2. Is it the BEST chart type for this data?
3. Quality score 1-10

Return JSON with array of validations:
{{
    "validations": [
        {{"chart_index": 1, "is_valid": true/false, "quality_score": 1-10, "reason": "...", "suggested_alternative": null}},
        ...
    ]
}}"""

    def _parse_validation_response(
        self, response: Dict, chart_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM validation response."""
        return {
            "chart_type": chart_config.get("chart_type"),
            "is_valid": response.get("is_valid", True),
            "revels_story": response.get("revels_story"),
            "quality_score": response.get("quality_score", 7),
            "reason": response.get("reason", ""),
            "suggested_alternative": response.get("suggested_alternative"),
            "axis_recommendations": response.get("axis_recommendations", {}),
            "validated": True,
        }

    def _match_validations_to_charts(
        self, validations: List[Dict], charts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Match validation results to corresponding charts."""
        results = []

        for i, chart in enumerate(charts):
            # Find matching validation
            validation = None
            for v in validations:
                if v.get("chart_index") == i + 1:
                    validation = v
                    break

            if validation:
                results.append(
                    {
                        "chart_type": chart.get("chart_type"),
                        "is_valid": validation.get("is_valid", True),
                        "quality_score": validation.get("quality_score", 7),
                        "reason": validation.get("reason", ""),
                        "suggested_alternative": validation.get(
                            "suggested_alternative"
                        ),
                        "validated": True,
                    }
                )
            else:
                results.append(self._default_validation(chart))

        return results

    def _default_validation(self, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Default validation when LLM call fails."""
        return {
            "chart_type": chart_config.get("chart_type"),
            "is_valid": True,
            "revels_story": None,
            "quality_score": 7,
            "reason": "Default validation (LLM unavailable)",
            "suggested_alternative": None,
            "axis_recommendations": self._get_default_axis_recommendations(
                chart_config
            ),
            "validated": False,  # Indicates this wasn't LLM validated
        }

    def _get_default_axis_recommendations(self, chart_config: Dict) -> Dict[str, str]:
        """Get default axis recommendations based on chart type."""
        chart_type = chart_config.get("chart_type", "")

        if "percentage" in chart_type or "pie" in chart_type:
            return {
                "x_scale": "linear",
                "y_scale": "percentage",
                "show_trend_line": False,
            }
        elif "line" in chart_type:
            return {"x_scale": "linear", "y_scale": "linear", "show_trend_line": True}
        elif "bar" in chart_type:
            return {"x_scale": "linear", "y_scale": "linear", "show_trend_line": False}
        else:
            return {"x_scale": "linear", "y_scale": "linear", "show_trend_line": False}


class StoryDrivenChartSelector:
    """
    Selects charts based on detected stories in the data.

    Ensures each story has a corresponding chart that reveals it.
    """

    # Mapping story types to recommended chart types
    STORY_CHART_MAP = {
        "trend": ["line", "area"],
        "concentration": ["pie", "donut", "bar"],
        "distribution": ["histogram", "box", "violin"],
        "comparison": ["bar", "grouped_bar", "radar"],
        "correlation": ["scatter", "bubble", "heatmap"],
        "variability": ["line", "box", "error_bar"],
        "growth": ["line", "area"],
        "composition": ["pie", "stacked_bar", "treemap"],
    }

    def select_charts_for_stories(
        self,
        stories: List[Dict[str, Any]],
        available_columns: List[Dict],
        max_charts: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Select charts that specifically reveal the detected stories.

        Args:
            stories: Detected stories from universal intelligence
            available_columns: Column metadata
            max_charts: Maximum number of charts to return

        Returns:
            List of chart configurations that reveal the stories
        """
        charts = []

        # Group columns by type
        numeric_cols = [
            c["name"]
            for c in available_columns
            if any(t in str(c.get("type", "")).lower() for t in ["int", "float"])
        ]
        categorical_cols = [
            c["name"]
            for c in available_columns
            if any(t in str(c.get("type", "")).lower() for t in ["str", "utf8"])
        ]
        temporal_cols = [
            c["name"]
            for c in available_columns
            if any(t in str(c.get("type", "")).lower() for t in ["date", "time"])
        ]

        for story in stories[:max_charts]:
            story_type = story.get("story_type", "")
            story_cols = story.get("columns", [])

            # Get recommended chart types for this story
            recommended_types = self.STORY_CHART_MAP.get(story_type, ["bar"])

            # Build chart config
            chart_config = self._build_chart_for_story(
                story,
                recommended_types[0],  # Use primary recommended type
                story_cols,
                numeric_cols,
                categorical_cols,
                temporal_cols,
            )

            if chart_config:
                chart_config["story"] = story
                chart_config["story_type"] = story_type
                charts.append(chart_config)

        return charts

    def _build_chart_for_story(
        self,
        story: Dict[str, Any],
        chart_type: str,
        story_cols: List[str],
        numeric_cols: List[str],
        categorical_cols: List[str],
        temporal_cols: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Build chart configuration for a specific story."""

        # Use columns from story if available
        primary_col = (
            story_cols[0] if story_cols else (numeric_cols[0] if numeric_cols else None)
        )
        secondary_col = story_cols[1] if len(story_cols) > 1 else None

        if not primary_col:
            return None

        config = {
            "chart_type": chart_type,
            "title": story.get("title", "Story Chart"),
            "config": {"columns": [primary_col], "aggregation": "sum"},
            "story_driven": True,
            "reason": story.get("description", ""),
        }

        # Configure based on chart type
        if chart_type in ["line", "area"]:
            # Need temporal column for x-axis
            x_col = (
                temporal_cols[0]
                if temporal_cols
                else story_cols[0]
                if len(story_cols) > 1
                else primary_col
            )
            config["config"]["columns"] = [x_col, primary_col]
            config["config"]["group_by"] = [x_col]

        elif chart_type in ["bar", "grouped_bar"]:
            # Use categorical for x-axis
            x_col = categorical_cols[0] if categorical_cols else primary_col
            y_col = secondary_col if secondary_col in numeric_cols else primary_col
            config["config"]["columns"] = [x_col, y_col]
            config["config"]["group_by"] = [x_col]

        elif chart_type in ["pie", "donut"]:
            # Need categorical column
            config["config"]["columns"] = [
                categorical_cols[0] if categorical_cols else primary_col
            ]
            config["config"]["aggregation"] = "count"

        elif chart_type == "scatter":
            # Need two numeric columns
            if len(numeric_cols) >= 2:
                config["config"]["columns"] = [numeric_cols[0], numeric_cols[1]]
            elif secondary_col:
                config["config"]["columns"] = [primary_col, secondary_col]
            else:
                return None  # Can't build scatter with one column

        elif chart_type in ["histogram", "box", "violin"]:
            config["config"]["columns"] = [primary_col]
            config["config"]["aggregation"] = "none"

        return config


class SmartAxisRecommender:
    """
    Recommends optimal axis settings for charts.

    Analyzes data distribution to recommend:
    - Linear vs Log scale
    - Percentage vs Absolute values
    - Trend lines
    - Reference lines
    """

    def recommend_axis_settings(
        self,
        chart_config: Dict[str, Any],
        df: pl.DataFrame,
        column_metadata: List[Dict],
    ) -> Dict[str, Any]:
        """
        Recommend optimal axis settings for a chart.

        Returns:
            Dict with axis recommendations
        """
        recommendations = {
            "x_scale": "linear",
            "y_scale": "linear",
            "show_trend_line": False,
            "show_percentage": False,
            "reference_line": None,
            "zero_baseline": False,
        }

        chart_type = chart_config.get("chart_type", "")
        columns = chart_config.get("config", {}).get("columns", [])

        if not columns:
            return recommendations

        primary_col = columns[0]

        if primary_col not in df.columns:
            return recommendations

        # Analyze the primary column
        try:
            series = df[primary_col].drop_nulls()
            if len(series) == 0:
                return recommendations

            vals = series.to_numpy()

            # Check for wide range (suggest log scale)
            if len(vals) > 0:
                min_val = float(np.min(vals))
                max_val = float(np.max(vals))

                if min_val > 0 and max_val / min_val > 100:
                    recommendations["y_scale"] = "log"

                # Check for negative values (can't use log)
                if min_val <= 0:
                    recommendations["y_scale"] = "linear"

            # Check for percentage-like data
            if all(0 <= v <= 1 for v in vals[: min(100, len(vals))]):
                recommendations["show_percentage"] = True
                recommendations["y_scale"] = "percentage"

            # Add trend line for time series
            if chart_type == "line" and len(columns) > 1:
                recommendations["show_trend_line"] = True

            # Suggest zero baseline for bar charts
            if chart_type in ["bar", "grouped_bar"]:
                recommendations["zero_baseline"] = True

            # Add reference line for comparison charts
            if chart_type in ["bar", "grouped_bar"]:
                mean_val = float(np.mean(vals))
                if not np.isnan(mean_val):
                    recommendations["reference_line"] = {
                        "value": round(mean_val, 2),
                        "label": "Average",
                    }

        except Exception as e:
            logger.warning(f"Axis recommendation failed: {e}")

        return recommendations


# Import numpy for calculations
import numpy as np


# Singleton instances
chart_validator = ChartValidator()
story_chart_selector = StoryDrivenChartSelector()
axis_recommender = SmartAxisRecommender()
