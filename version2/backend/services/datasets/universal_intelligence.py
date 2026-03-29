"""
Universal Dataset Intelligence Service
====================================
Universal analysis for ANY dataset type:

1. Data Fingerprint - Statistical profile (unique, distributions, correlations)
2. Story Detection - What is the data trying to tell us?
3. Semantic Column Detection - What do columns mean?
4. Universal Pattern Selection - Best dashboard pattern for this data

Author: DataSage AI Team
Version: 1.0
"""

import logging
from typing import Dict, List, Any, Optional
import polars as pl
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class UniversalDatasetIntelligence:
    """
    Universal intelligence for ANY dataset - no domain assumptions.

    Produces a data fingerprint that drives intelligent chart/KPI selection
    regardless of whether it's automotive, healthcare, sales, or any other domain.
    """

    def __init__(self):
        pass

    async def analyze(
        self, df: pl.DataFrame, column_metadata: List[Dict], use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Complete universal analysis of any dataset.

        Args:
            df: Polars DataFrame
            column_metadata: Column metadata from dataset
            use_llm: Whether to use LLM for semantic detection

        Returns:
            Universal intelligence profile with fingerprint, stories, and recommendations
        """
        logger.info(
            f"Starting universal analysis for {len(df)} rows, {len(column_metadata)} columns"
        )

        # Step 1: Create data fingerprint
        fingerprint = self._create_fingerprint(df, column_metadata)

        # Step 2: Detect stories in data
        stories = self._detect_stories(df, fingerprint, column_metadata)

        # Step 3: Analyze correlations
        correlations = self._analyze_correlations(df, column_metadata)

        # Step 4: Detect anomalies
        anomalies = self._detect_anomalies(df, column_metadata)

        # Step 5: Generate recommendations
        recommendations = self._generate_recommendations(
            fingerprint, stories, correlations, anomalies
        )

        result = {
            "fingerprint": fingerprint,
            "stories": stories,
            "correlations": correlations,
            "anomalies": anomalies,
            "recommendations": recommendations,
            "data_characteristics": self._summarize_characteristics(
                df, column_metadata
            ),
        }

        logger.info(
            f"Universal analysis complete. Detected {len(stories)} stories, {len(correlations)} correlations"
        )
        return result

    def _create_fingerprint(
        self, df: pl.DataFrame, column_metadata: List[Dict]
    ) -> Dict[str, Any]:
        """
        Create a statistical fingerprint of the dataset.
        This drives all downstream decisions without requiring domain knowledge.
        """
        fingerprint = {
            "row_count": len(df),
            "column_count": len(column_metadata),
            "column_types": {},
            "cardinality_profile": {},
            "numeric_summary": {},
            "temporal_presence": False,
            "categorical_diversity": {},
            "complexity_score": 0,
        }

        numeric_cols = []
        categorical_cols = []
        temporal_cols = []

        for col_meta in column_metadata:
            col_name = col_meta["name"]
            col_type = col_meta["type"]

            # Classify column type
            is_numeric = any(
                t in str(col_type).lower() for t in ["int", "float", "numeric"]
            )
            is_categorical = any(
                t in str(col_type).lower() for t in ["str", "utf8", "categorical"]
            )
            is_temporal = any(t in str(col_type).lower() for t in ["date", "time"])

            if is_numeric:
                numeric_cols.append(col_name)
            if is_categorical:
                categorical_cols.append(col_name)
            if is_temporal:
                temporal_cols.append(col_name)

            # Cardinality profile
            if col_name in df.columns:
                unique_ratio = df[col_name].n_unique() / max(len(df), 1)

                if is_numeric:
                    fingerprint["cardinality_profile"][col_name] = {
                        "type": "numeric",
                        "unique_count": df[col_name].n_unique(),
                        "unique_ratio": round(unique_ratio, 4),
                        "category": "continuous"
                        if unique_ratio > 0.5
                        else "discrete_numeric",
                    }
                elif is_categorical:
                    unique_count = df[col_name].n_unique()

                    if unique_ratio < 0.05:
                        cardinality_cat = "very_low"  # Great for grouping
                    elif unique_ratio < 0.15:
                        cardinality_cat = "low"  # Good for grouping
                    elif unique_ratio < 0.50:
                        cardinality_cat = "medium"  # Some segments
                    else:
                        cardinality_cat = "high"  # Unique identifiers

                    fingerprint["cardinality_profile"][col_name] = {
                        "type": "categorical",
                        "unique_count": unique_count,
                        "unique_ratio": round(unique_ratio, 4),
                        "category": cardinality_cat,
                    }

        # Numeric summary statistics
        for col in numeric_cols[:5]:  # Top 5 numeric columns
            if col in df.columns:
                series = df[col].drop_nulls()
                if len(series) > 0:
                    vals = series.to_numpy()
                    fingerprint["numeric_summary"][col] = {
                        "mean": round(float(np.mean(vals)), 2),
                        "median": round(float(np.median(vals)), 2),
                        "std": round(float(np.std(vals)), 2),
                        "min": round(float(np.min(vals)), 2),
                        "max": round(float(np.max(vals)), 2),
                        "skewness": round(float(stats.skew(vals)), 2)
                        if len(vals) > 2
                        else 0,
                        "kurtosis": round(float(stats.kurtosis(vals)), 2)
                        if len(vals) > 3
                        else 0,
                    }

        # Temporal presence
        fingerprint["temporal_presence"] = len(temporal_cols) > 0
        fingerprint["temporal_columns"] = temporal_cols

        # Categorical diversity
        fingerprint["categorical_diversity"] = {
            "count": len(categorical_cols),
            "columns": categorical_cols,
            "has_grouping_potential": any(
                c.get("category") in ["very_low", "low"]
                for c in fingerprint["cardinality_profile"].values()
                if c.get("type") == "categorical"
            ),
        }

        # Calculate complexity score (0-10)
        complexity = 0
        if len(numeric_cols) >= 3:
            complexity += 3
        elif len(numeric_cols) >= 1:
            complexity += 1
        if len(categorical_cols) >= 2:
            complexity += 2
        if len(temporal_cols) >= 1:
            complexity += 2
        if fingerprint["row_count"] > 10000:
            complexity += 2
        elif fingerprint["row_count"] > 1000:
            complexity += 1
        fingerprint["complexity_score"] = min(complexity, 10)

        return fingerprint

    def _detect_stories(
        self, df: pl.DataFrame, fingerprint: Dict, column_metadata: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Detect what stories the data is telling us.
        These are universal patterns that work for any domain.
        """
        stories = []

        # Story 1: Trend Detection (if temporal data exists)
        if fingerprint["temporal_presence"]:
            temporal_cols = fingerprint.get("temporal_columns", [])
            numeric_cols = [
                c
                for c in fingerprint.get("column_types", {}).keys()
                if fingerprint["column_types"][c] == "numeric"
            ]

            for time_col in temporal_cols[:1]:  # Check first temporal column
                for num_col in numeric_cols[:2]:  # Check top 2 numeric columns
                    if time_col in df.columns and num_col in df.columns:
                        trend = self._detect_trend(df, time_col, num_col)
                        if trend:
                            stories.append(trend)

        # Story 2: Concentration Detection
        concentration = self._detect_concentration(df, fingerprint)
        if concentration:
            stories.append(concentration)

        # Story 3: Distribution Shape
        distribution = self._detect_distribution_shape(df, fingerprint)
        if distribution:
            stories.append(distribution)

        # Story 4: Comparison/Segmentation (if categorical diversity exists)
        if fingerprint["categorical_diversity"].get("has_grouping_potential"):
            comparison = self._detect_comparison_potential(df, fingerprint)
            if comparison:
                stories.append(comparison)

        # Story 5: Correlation Story
        correlation_story = self._detect_correlation_story(df, fingerprint)
        if correlation_story:
            stories.append(correlation_story)

        # Story 6: Growth/Decline (time-based)
        growth = self._detect_growth_pattern(df, fingerprint)
        if growth:
            stories.append(growth)

        return stories[:5]  # Return top 5 stories

    def _detect_trend(
        self, df: pl.DataFrame, time_col: str, value_col: str
    ) -> Optional[Dict[str, Any]]:
        """Detect trend patterns in time series data."""
        try:
            # Sample data for trend detection
            sample = df.select([time_col, value_col]).drop_nulls()
            if len(sample) < 10:
                return None

            # Simple linear regression for trend
            x = np.arange(len(sample))
            y = sample[value_col].to_numpy()

            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # Calculate percentage change
            first_val = float(y[0])
            last_val = float(y[-1])
            pct_change = (
                ((last_val - first_val) / abs(first_val) * 100) if first_val != 0 else 0
            )

            # Determine trend direction
            if abs(r_value) < 0.3:
                trend_type = "stable"
                description = f"{value_col} remains relatively stable over time"
            elif slope > 0:
                if r_value > 0.7:
                    trend_type = "strong_upward"
                    description = f"{value_col} shows strong upward trend ({pct_change:+.1f}% overall)"
                else:
                    trend_type = "upward"
                    description = (
                        f"{value_col} trending upward ({pct_change:+.1f}% overall)"
                    )
            else:
                if r_value < -0.7:
                    trend_type = "strong_downward"
                    description = f"{value_col} shows strong downward trend ({pct_change:+.1f}% overall)"
                else:
                    trend_type = "downward"
                    description = (
                        f"{value_col} trending downward ({pct_change:+.1f}% overall)"
                    )

            return {
                "story_type": "trend",
                "title": f"{value_col} Over Time",
                "description": description,
                "columns": [time_col, value_col],
                "metrics": {
                    "r_squared": round(r_value**2, 3),
                    "p_value": round(p_value, 4),
                    "pct_change": round(pct_change, 1),
                    "direction": trend_type,
                },
                "recommended_chart": "line",
                "insight_priority": "high" if abs(r_value) > 0.5 else "medium",
            }
        except Exception as e:
            logger.warning(f"Trend detection failed: {e}")
            return None

    def _detect_concentration(
        self, df: pl.DataFrame, fingerprint: Dict
    ) -> Optional[Dict[str, Any]]:
        """Detect if data is concentrated in a few categories."""
        for col_name, profile in fingerprint["cardinality_profile"].items():
            if (
                profile.get("type") == "categorical"
                and profile.get("unique_count", 0) <= 10
            ):
                try:
                    # Get value counts
                    value_counts = (
                        df[col_name].value_counts().sort("count", descending=True)
                    )

                    if len(value_counts) >= 2:
                        top_pct = value_counts["count"][0] / len(df) * 100

                        if top_pct > 60:
                            # Concentration detected
                            top_values = value_counts.head(3)[col_name].to_list()

                            return {
                                "story_type": "concentration",
                                "title": f"{col_name} Concentration",
                                "description": f"{top_pct:.0f}% of records are in the top category ({top_values[0]})",
                                "columns": [col_name],
                                "metrics": {
                                    "top_category_pct": round(top_pct, 1),
                                    "top_categories": top_values,
                                    "total_categories": profile["unique_count"],
                                },
                                "recommended_chart": "pie"
                                if profile["unique_count"] <= 6
                                else "bar",
                                "insight_priority": "medium",
                            }
                except Exception:
                    continue
        return None

    def _detect_distribution_shape(
        self, df: pl.DataFrame, fingerprint: Dict
    ) -> Optional[Dict[str, Any]]:
        """Detect distribution shape characteristics."""
        for col_name, stats_data in fingerprint.get("numeric_summary", {}).items():
            skewness = stats_data.get("skewness")
            kurtosis = stats_data.get("kurtosis", 0)

            if skewness is None:
                continue

            # Normal distribution: skewness ~0, kurtosis ~0
            # Skewed: |skewness| > 1
            # Heavy tails: |kurtosis| > 2

            if abs(skewness) > 1.5:
                direction = "right-skewed" if skewness > 0 else "left-skewed"
                return {
                    "story_type": "distribution",
                    "title": f"{col_name} Distribution",
                    "description": f"{col_name} is {direction}, indicating concentration at one end",
                    "columns": [col_name],
                    "metrics": {
                        "skewness": skewness,
                        "kurtosis": kurtosis,
                        "mean_vs_median": "mean > median"
                        if skewness > 0
                        else "mean < median",
                    },
                    "recommended_chart": "histogram",
                    "insight_priority": "medium",
                }

            if kurtosis > 3:  # Heavy tails (leptokurtic)
                return {
                    "story_type": "distribution",
                    "title": f"{col_name} Has Outliers",
                    "description": f"{col_name} has heavy tails, indicating potential outliers",
                    "columns": [col_name],
                    "metrics": {"kurtosis": kurtosis, "skewness": skewness},
                    "recommended_chart": "box",
                    "insight_priority": "high",
                }

        return None

    def _detect_comparison_potential(
        self, df: pl.DataFrame, fingerprint: Dict
    ) -> Optional[Dict[str, Any]]:
        """Detect if data has good comparison/segmentation potential."""
        low_card_cols = [
            col
            for col, profile in fingerprint["cardinality_profile"].items()
            if profile.get("category") in ["very_low", "low"]
        ]

        if low_card_cols:
            col = low_card_cols[0]
            try:
                unique_vals = df[col].unique().to_list()

                # Find numeric columns to compare
                numeric_cols = [
                    c
                    for c, p in fingerprint["cardinality_profile"].items()
                    if p.get("type") == "numeric"
                ]

                if numeric_cols:
                    return {
                        "story_type": "comparison",
                        "title": f"Comparison by {col}",
                        "description": f"Data can be segmented into {len(unique_vals)} groups by {col}",
                        "columns": [col] + numeric_cols[:2],
                        "metrics": {
                            "segment_count": len(unique_vals),
                            "segments": unique_vals[:5],
                            "comparison_columns": numeric_cols[:3],
                        },
                        "recommended_chart": "grouped_bar",
                        "insight_priority": "high",
                    }
            except Exception:
                pass

        return None

    def _detect_correlation_story(
        self, df: pl.DataFrame, fingerprint: Dict
    ) -> Optional[Dict[str, Any]]:
        """Detect strong correlations between numeric columns."""
        numeric_cols = [
            col
            for col, profile in fingerprint["cardinality_profile"].items()
            if profile.get("type") == "numeric"
        ]

        if len(numeric_cols) >= 2:
            # Check top pairs
            for i, col1 in enumerate(numeric_cols[:3]):
                for col2 in numeric_cols[i + 1 : 4]:
                    try:
                        # Remove nulls
                        valid_mask = df[col1].is_not_null() & df[col2].is_not_null()
                        if valid_mask.sum() < 10:
                            continue

                        x = df.filter(valid_mask)[col1].to_numpy()
                        y = df.filter(valid_mask)[col2].to_numpy()

                        if len(x) > 5:
                            corr, p_value = stats.pearsonr(x, y)

                            if abs(corr) > 0.7 and p_value < 0.05:
                                direction = "positive" if corr > 0 else "negative"
                                return {
                                    "story_type": "correlation",
                                    "title": f"{col1} vs {col2}",
                                    "description": f"Strong {direction} correlation ({corr:.2f}) between {col1} and {col2}",
                                    "columns": [col1, col2],
                                    "metrics": {
                                        "correlation": round(corr, 3),
                                        "p_value": round(p_value, 4),
                                        "strength": "strong"
                                        if abs(corr) > 0.8
                                        else "moderate",
                                    },
                                    "recommended_chart": "scatter",
                                    "insight_priority": "high",
                                }
                    except Exception:
                        continue

        return None

    def _detect_growth_pattern(
        self, df: pl.DataFrame, fingerprint: Dict
    ) -> Optional[Dict[str, Any]]:
        """Detect growth or decline patterns in time series."""
        if not fingerprint["temporal_presence"]:
            return None

        # Check if any metric shows significant growth/decline
        for col_name, stats_data in fingerprint.get("numeric_summary", {}).items():
            mean_val = stats_data.get("mean", 0)
            std_val = stats_data.get("std", 0)

            # Coefficient of variation
            if mean_val != 0:
                cv = abs(std_val / mean_val)

                if cv > 2:  # High variability
                    return {
                        "story_type": "variability",
                        "title": f"High Variability in {col_name}",
                        "description": f"{col_name} shows high variability (CV: {cv:.1f}), indicating inconsistent performance",
                        "columns": [col_name],
                        "metrics": {
                            "coefficient_of_variation": round(cv, 2),
                            "mean": mean_val,
                            "std": std_val,
                        },
                        "recommended_chart": "line",
                        "insight_priority": "medium",
                    }

        return None

    def _analyze_correlations(
        self, df: pl.DataFrame, column_metadata: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Analyze correlations between numeric columns."""
        correlations = []

        numeric_cols = [
            col["name"]
            for col in column_metadata
            if any(t in str(col.get("type", "")).lower() for t in ["int", "float"])
        ]

        # Limit correlation analysis for performance
        numeric_cols = numeric_cols[:10]

        for i, col1 in enumerate(numeric_cols):
            for col2 in numeric_cols[i + 1 :]:
                try:
                    if col1 not in df.columns or col2 not in df.columns:
                        continue

                    valid_mask = df[col1].is_not_null() & df[col2].is_not_null()
                    if valid_mask.sum() < 10:
                        continue

                    x = df.filter(valid_mask)[col1].to_numpy()
                    y = df.filter(valid_mask)[col2].to_numpy()

                    if len(x) > 5:
                        corr, p_value = stats.pearsonr(x, y)

                        strength = "negligible"
                        if abs(corr) > 0.7:
                            strength = "strong"
                        elif abs(corr) > 0.4:
                            strength = "moderate"
                        elif abs(corr) > 0.2:
                            strength = "weak"

                        if abs(corr) > 0.3:  # Only report meaningful correlations
                            correlations.append(
                                {
                                    "column1": col1,
                                    "column2": col2,
                                    "correlation": round(corr, 3),
                                    "p_value": round(p_value, 4),
                                    "strength": strength,
                                    "direction": "positive" if corr > 0 else "negative",
                                }
                            )
                except Exception as e:
                    logger.warning(
                        f"Correlation analysis failed for {col1} vs {col2}: {e}"
                    )
                    continue

        # Sort by absolute correlation strength
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return correlations[:10]

    def _detect_anomalies(
        self, df: pl.DataFrame, column_metadata: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Detect potential anomalies in the data."""
        anomalies = []

        numeric_cols = [
            col["name"]
            for col in column_metadata
            if any(t in str(col.get("type", "")).lower() for t in ["int", "float"])
        ]

        for col in numeric_cols[:5]:  # Check top 5 numeric columns
            if col not in df.columns:
                continue

            try:
                series = df[col].drop_nulls()
                if len(series) < 10:
                    continue

                vals = series.to_numpy()

                # Z-score method for outlier detection
                z_scores = np.abs(stats.zscore(vals))
                outlier_mask = z_scores > 3
                outlier_count = outlier_mask.sum()
                outlier_pct = outlier_count / len(vals) * 100

                if outlier_pct > 1:  # More than 1% outliers
                    anomalies.append(
                        {
                            "column": col,
                            "type": "statistical_outliers",
                            "outlier_count": int(outlier_count),
                            "outlier_percentage": round(outlier_pct, 2),
                            "detection_method": "z_score",
                            "threshold": 3,
                            "severity": "high" if outlier_pct > 5 else "medium",
                        }
                    )

                # IQR method
                q1 = np.percentile(vals, 25)
                q3 = np.percentile(vals, 75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                iqr_outliers = ((vals < lower_bound) | (vals > upper_bound)).sum()
                iqr_pct = iqr_outliers / len(vals) * 100

                if 0 < iqr_pct < 15:  # Reasonable percentage
                    anomalies.append(
                        {
                            "column": col,
                            "type": "iqr_outliers",
                            "outlier_count": int(iqr_outliers),
                            "outlier_percentage": round(iqr_pct, 2),
                            "bounds": {
                                "lower": round(lower_bound, 2),
                                "upper": round(upper_bound, 2),
                            },
                            "severity": "low",
                        }
                    )

            except Exception as e:
                logger.warning(f"Anomaly detection failed for {col}: {e}")
                continue

        return anomalies

    def _generate_recommendations(
        self,
        fingerprint: Dict,
        stories: List[Dict],
        correlations: List[Dict],
        anomalies: List[Dict],
    ) -> Dict[str, Any]:
        """Generate universal dashboard recommendations based on analysis."""
        recommendations = {
            "chart_types": [],
            "kpi_suggestions": [],
            "dashboard_pattern": None,
            "layout_priority": [],
            "story_driven_charts": [],
        }

        # Chart type recommendations based on stories
        for story in stories:
            if "recommended_chart" in story:
                recommendations["story_driven_charts"].append(
                    {
                        "chart_type": story["recommended_chart"],
                        "reason": story["description"],
                        "priority": story.get("insight_priority", "medium"),
                    }
                )

        # Universal chart recommendations
        if fingerprint["temporal_presence"]:
            recommendations["chart_types"].append(
                {
                    "type": "line",
                    "reason": "Time series data detected",
                    "priority": "high",
                }
            )

        if fingerprint["categorical_diversity"].get("has_grouping_potential"):
            recommendations["chart_types"].append(
                {
                    "type": "bar",
                    "reason": "Categorical columns for grouping",
                    "priority": "high",
                }
            )

        if len(correlations) > 0:
            recommendations["chart_types"].append(
                {
                    "type": "scatter",
                    "reason": f"{len(correlations)} strong correlations detected",
                    "priority": "high",
                }
            )

        if any(a.get("type") == "statistical_outliers" for a in anomalies):
            recommendations["chart_types"].append(
                {
                    "type": "box",
                    "reason": "Outliers detected in data",
                    "priority": "medium",
                }
            )

        # Universal KPI suggestions
        recommendations["kpi_suggestions"] = [
            {"name": "Total Records", "aggregation": "count", "column": "id"},
            {
                "name": "Numeric Columns Summary",
                "aggregation": "various",
                "priority": "high",
            },
        ]

        # Pattern selection based on data characteristics
        pattern = self._select_universal_pattern(fingerprint, stories)
        recommendations["dashboard_pattern"] = pattern

        return recommendations

    def _select_universal_pattern(self, fingerprint: Dict, stories: List[Dict]) -> str:
        """
        Select the best universal pattern based on data fingerprint.
        These patterns work for ANY domain.
        """
        # Pattern selection logic
        has_temporal = fingerprint.get("temporal_presence", False)
        has_grouping = fingerprint["categorical_diversity"].get(
            "has_grouping_potential", False
        )
        complexity = fingerprint.get("complexity_score", 0)
        story_types = [s.get("story_type") for s in stories]

        # Select pattern based on data characteristics
        if has_temporal and complexity >= 4:
            return "temporal_overview"  # Line charts + KPIs + trends
        elif has_temporal and has_grouping:
            return "trend_comparison"  # Line + Bar comparison
        elif has_grouping:
            return "segmentation_dashboard"  # Bar charts + KPIs per segment
        elif complexity >= 5:
            return "multivariate_analysis"  # Scatter, correlations, heatmap
        else:
            return "simple_overview"  # Basic KPIs + single chart

    def _summarize_characteristics(
        self, df: pl.DataFrame, column_metadata: List[Dict]
    ) -> Dict[str, Any]:
        """Provide a human-readable summary of dataset characteristics."""
        characteristics = {
            "size_category": "small"
            if len(df) < 1000
            else "medium"
            if len(df) < 10000
            else "large",
            "complexity_category": "simple"
            if len(column_metadata) < 5
            else "moderate"
            if len(column_metadata) < 15
            else "complex",
            "has_temporal_data": False,
            "has_categorical_data": False,
            "has_numeric_data": False,
            "suitable_patterns": [],
        }

        for col_meta in column_metadata:
            col_type = str(col_meta.get("type", "")).lower()

            if any(t in col_type for t in ["date", "time"]):
                characteristics["has_temporal_data"] = True
            if any(t in col_type for t in ["str", "utf8", "categorical"]):
                characteristics["has_categorical_data"] = True
            if any(t in col_type for t in ["int", "float", "numeric"]):
                characteristics["has_numeric_data"] = True

        # Recommend suitable patterns
        if characteristics["has_temporal_data"]:
            characteristics["suitable_patterns"].append("temporal_overview")
        if characteristics["has_categorical_data"]:
            characteristics["suitable_patterns"].append("segmentation_dashboard")
        if characteristics["has_numeric_data"]:
            characteristics["suitable_patterns"].append("distribution_analysis")

        if len(characteristics["suitable_patterns"]) == 0:
            characteristics["suitable_patterns"].append("simple_overview")

        return characteristics


# Singleton instance
universal_intelligence = UniversalDatasetIntelligence()
