"""
Chart Insights Service
======================
Production-grade service for generating AI-powered insights from charts.

Features:
- Automatic insight generation from chart data
- Pattern detection (trends, anomalies, correlations)
- Natural language summaries
- Cached insights for performance
- LLM-powered deep insights
- Quality gates: rejects generic/weak explanations before caching
- Rich chart-type-specific context extraction for prompts

Author: Signal AI Team
Version: 3.0 (Productive Explanations with Quality Gates)
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import polars as pl
import json

logger = logging.getLogger(__name__)

# Technical jargon replacement map for human-friendly explanations
JARGON_REPLACEMENTS = {
    "skewed": "lopsided",
    "skew": "lopsided",
    "volatility": "ups and downs",
    "volatile": "unstable",
    "concentrated": "most values are",
    "concentration": "most",
    "anomaly": "unusual value",
    "anomalies": "unusual values",
    "outlier": "extreme value",
    "outliers": "extreme values",
    "filter to": "click to see",
    "filter by": "click",
    "correlation": "link between",
    "correlates": "is linked to",
    "distribution": "spread",
    "distributions": "spreads",
    "median": "middle value",
    "mode": "most common",
    "symmetric": "even",
    "percentile": "percentage point",
    "aggregate": "total",
    "variance": "spread",
    "deviation": "difference",
    "iqr": "range",
    "quartile": "quarter",
    "p-value": "statistical significance",
    "r-value": "strength of link",
    "coefficient": "factor",
}


def _humanize_text(text: str) -> str:
    """Replace technical jargon with plain alternatives."""
    if not text:
        return text
    result = text.lower()
    for jargon, plain in JARGON_REPLACEMENTS.items():
        result = re.sub(rf"\b{jargon}\b", plain, result, flags=re.IGNORECASE)
    # Capitalize first letter
    if result:
        result = result[0].upper() + result[1:]
    return result


def _detect_data_errors(data_stats: str, explanation: str) -> Optional[str]:
    """Detect obvious data errors that should be flagged."""
    if not data_stats or not explanation:
        return None

    # Extract numbers from data_stats
    numbers_in_data = set()
    for match in re.findall(r"\b\d+\.?\d*\b", data_stats):
        try:
            numbers_in_data.add(float(match))
        except:
            pass

    # Check for impossibly large values mentioned in explanation
    # Common data quality issues
    error_patterns = [
        (913283, "impossibly large duration (likely data error: minutes vs seconds)"),
        (999999, "suspicious max value"),
        (999999999, "likely placeholder/error value"),
    ]

    explanation_lower = explanation.lower()
    for number, reason in error_patterns:
        if str(number) in explanation_lower:
            return f"LIKELY DATA ERROR: {reason}"

    return None


def _humanize_explanation(
    llm_response: Dict[str, Any],
    data_stats: str,
    chart_type: str = "",
    chart_title: str = "",
) -> Dict[str, Any]:
    """
    Post-process LLM response to ensure:
    1. No technical jargon
    2. Numbers are verified against data
    3. Data errors are flagged
    4. business_impact field added
    """
    if not llm_response:
        return llm_response

    result = llm_response.copy()

    # Humanize all text fields
    for field in ["explanation", "reading_guide"]:
        if result.get(field):
            result[field] = _humanize_text(result[field])

    # Humanize key_insights
    if result.get("key_insights") and isinstance(result["key_insights"], list):
        result["key_insights"] = [
            _humanize_text(insight) if insight else ""
            for insight in result["key_insights"]
        ]

    # Detect data errors in explanation
    explanation_text = result.get("explanation", "")
    data_error = _detect_data_errors(data_stats, explanation_text)

    # Set anomaly_flag to data error if found, otherwise keep original
    if data_error:
        result["anomaly_flag"] = data_error
        result["data_verified"] = False
    else:
        # Check if anomaly_flag exists and humanize it
        if result.get("anomaly_flag"):
            result["anomaly_flag"] = _humanize_text(result["anomaly_flag"])
        result["data_verified"] = True

    # Add business_impact if not present
    if "business_impact" not in result:
        # Generate simple business impact from explanation
        if explanation_text:
            # Extract first number and create simple impact
            impact = f"So what: {explanation_text}"
            result["business_impact"] = impact[:100]  # Truncate if too long
        else:
            result["business_impact"] = ""

    # Ensure required fields exist with safe defaults
    if not result.get("chart_id"):
        result["chart_id"] = chart_title or "Untitled Chart"

    # Mark quality source so downstream logging is accurate
    result["_quality_source"] = "LLM"

    return result


# ─────────────────────────────────────────────────────────────
# QUALITY GATE: patterns that indicate weak/generic LLM output
# ─────────────────────────────────────────────────────────────

_WEAK_EXPLANATION_PATTERNS = [
    "stable data points",
    "this chart shows",
    "the data reveals",
    "as seen in",
    "values for ",
    "are consistently",
    "data distributions",
    "explore this data further",
    "consider filtering by different",
    "gain insights",
    "further analysis",
    "the chart displays",
    "a variety of",
    "various data points",
    "interesting patterns",
]

_WEAK_READING_GUIDE_PATTERNS = [
    "filter by the highest-value segment",
    "explore this data further",
    "see what drives it",
    "consider filtering by different",
    "gain insights",
    "look for patterns",
    "examine the data",
]


def _is_weak_text(text: str, patterns: List[str]) -> bool:
    """Return True if text matches any weak/generic pattern."""
    if not text:
        return True
    lower = text.lower().strip()
    if len(lower) < 12:
        return True
    return any(p in lower for p in patterns)


def _has_numeric_anchor(text: str) -> bool:
    """Return True if text contains at least one number, %, or currency symbol."""
    return bool(re.search(r"[\d£$€%]", text or ""))


def _has_named_entity(text: str, chart_config: Dict[str, Any]) -> bool:
    """Return True if text references a real column name or category from the chart."""
    if not text or not chart_config:
        return False
    lower = text.lower()
    for field in ("x", "y", "group_by", "column"):
        val = chart_config.get(field)
        if val and isinstance(val, str) and val.lower() in lower:
            return True
    title = chart_config.get("title") or chart_config.get("title_insight", "")
    if title and len(title) > 4:
        words = [w for w in title.lower().split() if len(w) > 3]
        if any(w in lower for w in words):
            return True
    return False


class ChartInsightsService:
    """
    Generates intelligent insights from chart data using pattern detection + LLM.
    """

    # Cache version — bump this to invalidate stale weak explanations
    CACHE_VERSION = "v3.0"

    def __init__(self):
        self._cache = {}
        self._insight_count = 0

    async def generate_chart_insight(
        self,
        chart_data: Dict[str, Any],
        df: Optional[pl.DataFrame] = None,
        use_llm: bool = True,
        chart_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate insights for a chart.

        Args:
            chart_data: Rendered chart data with traces
            df: Optional source DataFrame for deeper analysis
            use_llm: Whether to use LLM for enhanced insights
            chart_config: Optional chart configuration (x, y, aggregation, group_by, title)

        Returns:
            Dict with insights, patterns, and recommendations
        """
        try:
            chart_type = chart_data.get("chart_type", "unknown")
            logger.info(f"Generating insights for {chart_type} chart...")

            # Extract data from chart
            traces = chart_data.get("data") or chart_data.get("traces", [])
            if not traces:
                return self._generate_fallback_insight(chart_data, [])

            # Pattern detection based on chart type
            patterns = self._detect_patterns(chart_type, traces, df)

            # Generate natural language summary
            summary = self._generate_summary(chart_type, patterns, traces)

            # LLM-enhanced insights (optional)
            enhanced_insight = None
            if use_llm and df is not None:
                try:
                    enhanced_insight = await self._generate_llm_insight(
                        chart_type, patterns, traces, df, chart_config
                    )
                except Exception as e:
                    logger.warning(f"LLM insight generation failed: {e}")

            # Recommendations
            recommendations = self._generate_recommendations(chart_type, patterns)

            insight = {
                "summary": summary,
                "patterns": patterns,
                "recommendations": recommendations,
                "enhanced_insight": enhanced_insight,
                "chart_type": chart_type,
                "generated_at": datetime.utcnow().isoformat(),
                "confidence": self._calculate_confidence(patterns),
                "cache_version": self.CACHE_VERSION,
                "_quality_source": enhanced_insight.get("_quality_source", "unknown")
                if enhanced_insight
                else "fallback",
            }

            self._insight_count += 1
            logger.info(
                f"✓ Generated insight with {len(patterns)} pattern(s) "
                f"[source: {insight['_quality_source']}]"
            )

            return insight

        except Exception as e:
            logger.error(f"✗ Insight generation failed: {e}")
            return self._generate_fallback_insight(chart_data, [])

    def _detect_patterns(
        self, chart_type: str, traces: List[Dict], df: Optional[pl.DataFrame]
    ) -> List[Dict[str, Any]]:
        """Detect patterns in chart data."""
        patterns = []

        try:
            if chart_type == "line":
                patterns.extend(self._detect_trend_patterns(traces))

            elif chart_type == "bar":
                patterns.extend(self._detect_comparison_patterns(traces))

            elif chart_type == "scatter":
                patterns.extend(self._detect_correlation_patterns(traces))

            elif chart_type == "pie":
                patterns.extend(self._detect_composition_patterns(traces))

            elif chart_type == "heatmap":
                patterns.extend(self._detect_intensity_patterns(traces))

        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")

        return patterns

    def _detect_trend_patterns(self, traces: List[Dict]) -> List[Dict]:
        """Detect trends in line charts."""
        patterns = []

        for trace in traces:
            y_data = trace.get("y", [])
            if len(y_data) < 3:
                continue

            # Advanced trend detection using Linear Regression
            if all(isinstance(y, (int, float)) and y is not None for y in y_data):
                n = len(y_data)
                x = list(range(n))
                sum_x = sum(x)
                sum_y = sum(y_data)
                sum_xy = sum(x[i] * y_data[i] for i in range(n))
                sum_xx = sum(x[i] ** 2 for i in range(n))

                denominator = n * sum_xx - sum_x**2
                if denominator == 0:
                    continue

                # Calculate slope (m) and intercept (b)
                m = (n * sum_xy - sum_x * sum_y) / denominator
                b = (sum_y - m * sum_x) / n

                # Predict first and last points to calculate overall change % based on the trend line
                start_pred = m * 0 + b
                end_pred = m * (n - 1) + b

                change_pct = (
                    ((end_pred - start_pred) / start_pred * 100)
                    if start_pred != 0
                    else 0
                )

                # Calculate R-squared for confidence
                y_mean = sum_y / n
                ss_tot = sum((y - y_mean) ** 2 for y in y_data)
                ss_res = sum((y_data[i] - (m * x[i] + b)) ** 2 for i in range(n))
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                if abs(change_pct) > 5 and r_squared > 0.3:
                    trend = "increasing" if m > 0 else "decreasing"
                    strength = "strong" if r_squared > 0.7 else "moderate"
                    patterns.append(
                        {
                            "type": "trend",
                            "pattern": f"{strength}_{trend}_trend",
                            "description": f"Data shows a {strength} {trend} trend with {abs(change_pct):.1f}% overall linear change (R²={r_squared:.2f})",
                            "confidence": min(r_squared + 0.1, 0.95),
                            "metric": trace.get("name", "Value"),
                        }
                    )
        return patterns

    def _detect_comparison_patterns(self, traces: List[Dict]) -> List[Dict]:
        """Detect patterns in bar charts."""
        patterns = []

        for trace in traces:
            y_data = trace.get("y", [])
            x_data = trace.get("x", [])

            if len(y_data) < 2:
                continue

            # Find max and min
            if all(isinstance(y, (int, float)) for y in y_data):
                max_val = max(y_data)
                min_val = min(y_data)
                max_idx = y_data.index(max_val)
                min_idx = y_data.index(min_val)

                # Significant difference?
                if max_val > min_val * 2:  # 2x difference
                    patterns.append(
                        {
                            "type": "comparison",
                            "pattern": "significant_difference",
                            "description": f"Highest: {x_data[max_idx] if max_idx < len(x_data) else 'N/A'} ({max_val:.0f}), Lowest: {x_data[min_idx] if min_idx < len(x_data) else 'N/A'} ({min_val:.0f})",
                            "confidence": 0.9,
                            "max_value": max_val,
                            "min_value": min_val,
                        }
                    )

        return patterns

    def _detect_correlation_patterns(self, traces: List[Dict]) -> List[Dict]:
        """Detect correlation in scatter plots."""
        patterns = []

        for trace in traces:
            x_data = trace.get("x", [])
            y_data = trace.get("y", [])

            if len(x_data) < 5 or len(y_data) < 5:
                continue

            # Simple correlation detection
            try:
                import numpy as np

                x_array = np.array(
                    [float(x) for x in x_data if isinstance(x, (int, float))]
                )
                y_array = np.array(
                    [float(y) for y in y_data if isinstance(y, (int, float))]
                )

                if len(x_array) > 2 and len(y_array) > 2:
                    correlation = np.corrcoef(x_array, y_array)[0, 1]

                    if abs(correlation) > 0.5:
                        direction = "positive" if correlation > 0 else "negative"
                        strength = "strong" if abs(correlation) > 0.7 else "moderate"

                        patterns.append(
                            {
                                "type": "correlation",
                                "pattern": f"{direction}_correlation",
                                "description": f"{strength.capitalize()} {direction} correlation (r={correlation:.2f})",
                                "confidence": abs(correlation),
                                "correlation_value": correlation,
                            }
                        )
            except Exception as e:
                logger.warning(f"Correlation calculation failed: {e}")

        return patterns

    def _detect_composition_patterns(self, traces: List[Dict]) -> List[Dict]:
        """Detect patterns in pie charts."""
        patterns = []

        for trace in traces:
            values = trace.get("values", [])
            labels = trace.get("labels", [])

            if not values:
                continue

            total = sum(values)
            if total == 0:
                continue

            # Find dominant category
            max_val = max(values)
            max_idx = values.index(max_val)
            max_pct = (max_val / total) * 100

            if max_pct > 50:
                patterns.append(
                    {
                        "type": "composition",
                        "pattern": "dominant_category",
                        "description": f"{labels[max_idx] if max_idx < len(labels) else 'Top category'} dominates with {max_pct:.1f}%",
                        "confidence": 0.9,
                        "dominant_category": labels[max_idx]
                        if max_idx < len(labels)
                        else "Unknown",
                        "percentage": max_pct,
                    }
                )

        return patterns

    def _detect_intensity_patterns(self, traces: List[Dict]) -> List[Dict]:
        """Detect patterns in heatmaps."""
        patterns = []

        for trace in traces:
            if trace.get("type") != "heatmap" or "z" not in trace:
                continue

            z_data = trace.get("z", [])
            if (
                not z_data
                or not isinstance(z_data, list)
                or not isinstance(z_data[0], list)
            ):
                continue

            # Flatten to find min/max
            flat_z = []
            for row in z_data:
                flat_z.extend([val for val in row if isinstance(val, (int, float))])

            if not flat_z:
                continue

            z_max = max(flat_z)
            z_mean = sum(flat_z) / len(flat_z)

            # Find the coordinates of the max value (hotspots)
            max_coords = []
            for i, row in enumerate(z_data):
                for j, val in enumerate(row):
                    if val == z_max:
                        x_val = (
                            trace.get("x", [])[j]
                            if "x" in trace and j < len(trace["x"])
                            else f"Col {j}"
                        )
                        y_val = (
                            trace.get("y", [])[i]
                            if "y" in trace and i < len(trace["y"])
                            else f"Row {i}"
                        )
                        max_coords.append((x_val, y_val))

            if z_max > z_mean * 1.5:
                # Strong hotspot
                coords_str = ", ".join([f"({x}, {y})" for x, y in max_coords[:3]])
                if len(max_coords) > 3:
                    coords_str += f" and {len(max_coords) - 3} others"

                patterns.append(
                    {
                        "type": "intensity",
                        "pattern": "heatmap_hotspot",
                        "description": f"Strong intensity concentration (hotspot) detected around {coords_str} with peak value {z_max:.1f}",
                        "confidence": 0.85,
                        "metric": trace.get("name", "Intensity"),
                    }
                )

        return patterns

    def _generate_summary(
        self, chart_type: str, patterns: List[Dict], traces: List[Dict]
    ) -> str:
        """Generate natural language summary."""
        if not patterns:
            return f"This {chart_type} chart displays the data distribution."

        # Construct summary from patterns
        summaries = []
        for pattern in patterns[:3]:  # Top 3 patterns
            summaries.append(pattern.get("description", ""))

        if len(summaries) == 1:
            return summaries[0]
        elif len(summaries) == 2:
            return f"{summaries[0]}. Additionally, {summaries[1].lower()}"
        else:
            return f"{summaries[0]}. {summaries[1]}. {summaries[2]}"

    def _generate_recommendations(
        self, chart_type: str, patterns: List[Dict]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        for pattern in patterns:
            pattern_type = pattern.get("pattern", "")

            if "increasing_trend" in pattern_type:
                recommendations.append("Monitor continued growth and capacity planning")

            elif "decreasing_trend" in pattern_type:
                recommendations.append(
                    "Investigate causes of decline and implement corrective actions"
                )

            elif "significant_difference" in pattern_type:
                recommendations.append("Analyze top and bottom performers for insights")

            elif "positive_correlation" in pattern_type:
                recommendations.append(
                    "Leverage this relationship for predictive modeling"
                )

            elif "negative_correlation" in pattern_type:
                recommendations.append("Consider trade-offs between these variables")

            elif "dominant_category" in pattern_type:
                recommendations.append(
                    "Focus resources on dominant segment or diversify"
                )

        return recommendations[:3]  # Top 3 recommendations

    async def _generate_llm_insight(
        self,
        chart_type: str,
        patterns: List[Dict],
        traces: List[Dict],
        df: pl.DataFrame,
        chart_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """Generate enhanced insight using LLM."""
        try:
            from services.llm_router import llm_router

            chart_summary = self._build_chart_summary(chart_type, traces, chart_config)
            data_stats = self._build_data_stats(traces, df, chart_config)
            dataset_context = self._build_dataset_context(df, chart_config)

            from core.prompt_templates import get_chart_explanation_prompt

            prompt = get_chart_explanation_prompt(
                chart_summary=chart_summary,
                dataset_context=dataset_context,
                data_stats=data_stats,
                include_context=bool(dataset_context),
            )

            response = await llm_router.call(
                prompt,
                model_role="chart_explanation",
                expect_json=True,
                temperature=0.4,
                max_tokens=500,
            )

            # Post-process response to humanize and validate
            if isinstance(response, dict):
                return _humanize_explanation(
                    response,
                    data_stats,
                    chart_type=chart_type,
                    chart_title=chart_config.get("title", "") if chart_config else "",
                )
            elif isinstance(response, str):
                import json

                try:
                    parsed = json.loads(response)
                    return _humanize_explanation(
                        parsed,
                        data_stats,
                        chart_type=chart_type,
                        chart_title=chart_config.get("title", "")
                        if chart_config
                        else "",
                    )
                except:
                    return None
            return None

        except Exception as e:
            logger.warning(f"LLM insight generation failed: {e}")
            return None

    def _build_chart_summary(
        self,
        chart_type: str,
        traces: List[Dict],
        chart_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build rich chart summary string for prompt, including title and axis info."""
        parts = []

        # Include chart title if available — this is the most important context
        title = ""
        if chart_config:
            title = chart_config.get("title_insight") or chart_config.get("title") or ""
        if title:
            parts.append(f'"{title}"')

        parts.append(f"({chart_type} chart)")

        # Include axis/column info from config
        if chart_config:
            x_col = chart_config.get("x") or chart_config.get("x_column", "")
            y_col = chart_config.get("y") or chart_config.get("y_column", "")
            group_by = chart_config.get("group_by", "")
            agg = chart_config.get("aggregation", "")
            column = chart_config.get("column", "")

            axis_info = []
            if x_col:
                axis_info.append(f"X-axis: {x_col}")
            if y_col:
                axis_info.append(f"Y-axis: {y_col}")
            if column and not x_col:
                axis_info.append(f"Column: {column}")
            if agg:
                axis_info.append(f"Aggregation: {agg}")
            if group_by:
                axis_info.append(f"Grouped by: {group_by}")
            if axis_info:
                parts.append(f"[{', '.join(axis_info)}]")

        # Include trace names for multi-series charts
        if traces and len(traces) > 1:
            trace_names = [t.get("name", "") for t in traces if t.get("name")]
            if trace_names:
                parts.append(f"Series: {', '.join(trace_names[:5])}")

        return " ".join(parts) if parts else f"{chart_type} chart"

    def _build_data_stats(
        self,
        traces: List[Dict],
        df: pl.DataFrame,
        chart_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build rich data statistics string from traces and dataframe."""
        stat_parts = []
        stat_parts.append(f"Dataset: {len(df)} rows, {len(df.columns)} columns")
        stat_parts.append(f"Columns: {', '.join(df.columns[:15])}")

        for trace in traces:
            name = trace.get("name", "Series")
            x_data = trace.get("x", [])
            y_data = trace.get("y", [])

            # Y-axis statistics
            if y_data and all(
                isinstance(v, (int, float)) for v in y_data if v is not None
            ):
                numeric_vals = [v for v in y_data if isinstance(v, (int, float))]
                if numeric_vals:
                    sorted_vals = sorted(numeric_vals)
                    n = len(sorted_vals)
                    min_val = sorted_vals[0]
                    max_val = sorted_vals[-1]
                    avg_val = sum(sorted_vals) / n
                    median_val = sorted_vals[n // 2]
                    total_val = sum(sorted_vals)

                    stat_parts.append(
                        f"  {name}: min={min_val:,.2f}, max={max_val:,.2f}, "
                        f"avg={avg_val:,.2f}, median={median_val:,.2f}, "
                        f"total={total_val:,.2f}, count={n}"
                    )

            # X-axis: show actual labels/categories (not just count)
            if x_data:
                # Show first and last few categories for context
                str_labels = [str(v) for v in x_data if v is not None]
                if len(str_labels) <= 10:
                    stat_parts.append(f"  X-axis values: {', '.join(str_labels)}")
                else:
                    preview = str_labels[:5] + ["..."] + str_labels[-3:]
                    stat_parts.append(
                        f"  X-axis ({len(str_labels)} values): {', '.join(preview)}"
                    )

            # For histograms: show top bins with counts
            if y_data and x_data and len(x_data) == len(y_data):
                pairs = list(zip(x_data, y_data))
                pairs_sorted = sorted(
                    [(x, y) for x, y in pairs if isinstance(y, (int, float))],
                    key=lambda p: p[1],
                    reverse=True,
                )
                if pairs_sorted:
                    top_bins = pairs_sorted[:3]
                    stat_parts.append(
                        f"  Top values: "
                        + ", ".join(f"{x}={y:,.0f}" for x, y in top_bins)
                    )

        return "\n".join(stat_parts)

    def _build_dataset_context(
        self, df: pl.DataFrame, chart_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build dataset context string describing what the data is about."""
        context_parts = []

        # Dataset name from config
        dataset_name = ""
        if chart_config:
            dataset_name = chart_config.get("dataset_name", "")
        if dataset_name:
            context_parts.append(f"Dataset: {dataset_name}")

        # Describe columns with sample values for context
        col_descriptions = []
        for col in df.columns[:12]:
            try:
                dtype = str(df[col].dtype)
                non_null = df[col].drop_nulls()
                if len(non_null) == 0:
                    continue

                if df[col].dtype in (pl.Utf8, pl.Categorical):
                    unique_count = non_null.n_unique()
                    samples = non_null.unique().head(5).to_list()
                    sample_str = ", ".join(str(s) for s in samples[:5])
                    col_descriptions.append(
                        f"  {col} ({dtype}, {unique_count} unique): e.g. {sample_str}"
                    )
                elif df[col].dtype in (
                    pl.Int8,
                    pl.Int16,
                    pl.Int32,
                    pl.Int64,
                    pl.UInt8,
                    pl.UInt16,
                    pl.UInt32,
                    pl.UInt64,
                    pl.Float32,
                    pl.Float64,
                ):
                    min_v = non_null.min()
                    max_v = non_null.max()
                    col_descriptions.append(
                        f"  {col} ({dtype}): range {min_v} to {max_v}"
                    )
            except Exception:
                continue

        if col_descriptions:
            context_parts.append("Column overview:\n" + "\n".join(col_descriptions))

        return "\n".join(context_parts) if context_parts else ""

    def _calculate_confidence(self, patterns: List[Dict]) -> float:
        """Calculate overall confidence score."""
        if not patterns:
            return 0.5

        confidences = [p.get("confidence", 0.5) for p in patterns]
        return sum(confidences) / len(confidences)

    def _generate_fallback_insight(
        self, chart_data: Dict[str, Any], patterns: List[Dict]
    ) -> Dict[str, Any]:
        """Generate fallback insight when analysis fails."""
        chart_type = chart_data.get("chart_type", "unknown")

        return {
            "summary": f"This {chart_type} chart visualizes the data distribution.",
            "patterns": patterns,
            "recommendations": ["Review data quality and completeness"],
            "enhanced_insight": None,
            "chart_type": chart_type,
            "generated_at": datetime.utcnow().isoformat(),
            "confidence": 0.5,
        }

    async def get_dataset_cached_charts(
        self, dataset_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get cached charts for a dataset (placeholder).

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier

        Returns:
            List of cached charts with insights
        """
        logger.info(f"Retrieving cached charts for dataset {dataset_id}...")

        try:
            from services.cache.dashboard_cache_service import dashboard_cache_service

            charts_dict = await dashboard_cache_service.get_cached_charts(
                dataset_id, user_id
            )
            if charts_dict:
                return list(charts_dict.values())
        except Exception as e:
            logger.warning(f"Failed to retrieve cached charts from MongoDB: {e}")

        return []

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {"total_insights": self._insight_count, "cache_size": len(self._cache)}


# Singleton instance
chart_insights_service = ChartInsightsService()
