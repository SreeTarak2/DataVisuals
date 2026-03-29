# backend/services/analysis/insight_interpreter.py

"""
Insight Interpreter
===================
Translates statistical results into human-readable, data scientist-level explanations.
Provides contextual interpretations that can be used directly in reports or LLM prompts.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class InsightInterpreter:
    """
    Convert statistical outputs to human-readable insights.
    Designed for data scientists and business stakeholders.
    """
    
    def interpret_correlation(self, result: Dict[str, Any]) -> str:
        """
        Interpret correlation analysis result.
        
        Example output:
        "Strong positive correlation (r=0.85, p<0.001) between revenue and marketing_spend. 
         95% CI: [0.78, 0.90]. 72% of variance explained."
        """
        r = result.get('correlation', 0)
        p = result.get('p_value', 1)
        col1 = result.get('column1', 'Variable 1')
        col2 = result.get('column2', 'Variable 2')
        method = result.get('method', 'pearson')
        strength = result.get('strength', 'unknown')
        ci = result.get('confidence_interval')
        
        # Direction
        direction = "positive" if r > 0 else "negative"
        
        # Significance
        if p < 0.001:
            sig_text = "p<0.001"
        elif p < 0.01:
            sig_text = f"p={p:.3f}"
        else:
            sig_text = f"p={p:.3f}"
        
        # Build interpretation
        r_squared = r ** 2 * 100
        
        interpretation = f"{strength.capitalize()} {direction} correlation ({method} r={r:.3f}, {sig_text}) between {col1} and {col2}."
        
        if ci:
            interpretation += f" 95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]."
        
        if abs(r) >= 0.3:
            interpretation += f" {r_squared:.1f}% of variance explained."
        
        return interpretation
    
    def interpret_hypothesis_test(self, result: Dict[str, Any]) -> str:
        """
        Interpret hypothesis test result.
        
        Example output:
        "Statistically significant difference (p=0.003, Cohen's d=0.8 [large effect]) 
         between treatment and control groups. 95% CI for difference: [2.3, 5.7]."
        """
        test_name = result.get('test_name', 'hypothesis test')
        p = result.get('p_value', 1)
        effect_size = result.get('effect_size')
        effect_interp = result.get('effect_size_interpretation', '')
        ci = result.get('confidence_interval')
        interpretation_label = result.get('interpretation', 'unknown')
        
        # Significance interpretation
        if interpretation_label == "highly_significant":
            sig_text = "Highly statistically significant"
        elif interpretation_label == "significant":
            sig_text = "Statistically significant"
        elif interpretation_label == "borderline":
            sig_text = "Borderline significant (marginal)"
        else:
            sig_text = "No statistically significant"
        
        # Build interpretation
        interpretation = f"{sig_text} difference (p={p:.4f}"
        
        if effect_size is not None:
            interpretation += f", effect size={effect_size:.3f} [{effect_interp}]"
        
        interpretation += ")."
        
        if ci:
            interpretation += f" 95% CI for difference: [{ci[0]:.3f}, {ci[1]:.3f}]."
        
        # Add test-specific context
        test_context = {
            "welch_t_test": "Welch's t-test does not assume equal variances.",
            "mann_whitney_u": "Non-parametric test; suitable for non-normal data.",
            "one_way_anova": "One-way ANOVA comparing group means.",
            "kruskal_wallis": "Non-parametric alternative to ANOVA.",
            "chi_square_independence": "Chi-square test of independence."
        }
        
        if test_name in test_context:
            interpretation += f" {test_context[test_name]}"
        
        return interpretation
    
    def interpret_distribution(self, result: Dict[str, Any]) -> str:
        """
        Interpret distribution analysis result.
        
        Example output:
        "Column 'revenue' follows a right-skewed distribution (skewness=1.2, kurtosis=2.3).
         Failed normality test (Shapiro-Wilk p=0.002). Consider log transformation."
        """
        col = result.get('column', 'column')
        dist_type = result.get('distribution_type', 'unknown')
        skewness = result.get('skewness', 0)
        kurtosis = result.get('kurtosis', 0)
        is_normal = result.get('is_normal', True)
        normality_test = result.get('normality_test', '')
        normality_p = result.get('normality_p_value', 1)
        
        interpretation = f"Column '{col}' follows a {dist_type.replace('_', ' ')} distribution "
        interpretation += f"(skewness={skewness:.2f}, excess kurtosis={kurtosis:.2f}). "
        
        if is_normal:
            interpretation += f"Passed normality test ({normality_test}, p={normality_p:.3f})."
        else:
            interpretation += f"Failed normality test ({normality_test}, p={normality_p:.3f}). "
            
            # Recommendations
            if skewness > 0.5:
                interpretation += "Consider log or square root transformation."
            elif skewness < -0.5:
                interpretation += "Consider reflection and log transformation."
            elif kurtosis > 1:
                interpretation += "Heavy tails may affect outlier detection."
        
        return interpretation
    
    def interpret_anomaly(self, result: Dict[str, Any]) -> str:
        """
        Interpret anomaly detection result.
        
        Example output:
        "Detected 23 outliers (2.3%) in 'revenue' using Isolation Forest.
         Outliers are concentrated in upper range."
        """
        col = result.get('column', 'column')
        method = result.get('method', 'unknown')
        count = result.get('outlier_count', 0)
        percentage = result.get('outlier_percentage', 0)
        
        method_names = {
            "isolation_forest": "Isolation Forest (ML-based)",
            "zscore": "Z-score method",
            "modified_zscore_mad": "Modified Z-score (MAD-based, robust)",
            "IQR": "Interquartile Range (IQR)"
        }
        
        method_display = method_names.get(method, method)
        
        interpretation = f"Detected {count} outliers ({percentage:.1f}%) in '{col}' using {method_display}."
        
        if percentage > 5:
            interpretation += " High outlier proportion may indicate data quality issues or genuine extreme values."
        elif percentage > 1:
            interpretation += " Moderate outlier presence; investigate for data errors or interesting edge cases."
        else:
            interpretation += " Low outlier proportion; data appears relatively clean."
        
        return interpretation
    
    def interpret_trend(self, result: Dict[str, Any]) -> str:
        """
        Interpret time series trend analysis.
        
        Example output:
        "Statistically significant increasing trend detected (Mann-Kendall τ=0.45, p=0.002).
         Strong positive autocorrelation at lags 1, 2, 12 suggests seasonality."
        """
        trend = result.get('trend_analysis', {})
        acf = result.get('autocorrelation', {})
        col = result.get('column', 'series')
        
        trend_dir = trend.get('trend', 'no_trend')
        tau = trend.get('tau', 0)
        p_value = trend.get('p_value', 1)
        is_significant = trend.get('is_significant', False)
        
        if trend_dir == 'no_trend':
            interpretation = f"No statistically significant trend detected in '{col}' (p={p_value:.3f})."
        else:
            sig_text = "Statistically significant" if is_significant else "Non-significant"
            interpretation = f"{sig_text} {trend_dir} trend detected in '{col}' (Mann-Kendall τ={tau:.3f}, p={p_value:.3f})."
        
        # Autocorrelation insights
        sig_lags = acf.get('significant_lags', [])
        if sig_lags:
            if 12 in sig_lags or 24 in sig_lags:
                interpretation += f" Significant autocorrelation at lags {sig_lags[:5]} suggests potential seasonality."
            elif 1 in sig_lags:
                interpretation += f" Strong short-term autocorrelation detected (lags: {sig_lags[:5]})."
        
        return interpretation
    
    def interpret_feature_importance(self, result: Dict[str, Any]) -> str:
        """
        Interpret feature importance analysis.
        
        Example output:
        "Top predictors for 'revenue': marketing_spend (0.35), customer_count (0.22), 
         ad_clicks (0.18). Mutual information confirms non-linear relationships."
        """
        target = result.get('target_column', 'target')
        rf_result = result.get('random_forest_importance', {})
        mi_scores = result.get('mutual_information', {})
        
        importances = rf_result.get('importances', {})
        
        if not importances:
            return f"Unable to calculate feature importance for '{target}'."
        
        # Get top 5 features
        top_features = list(importances.items())[:5]
        
        interpretation = f"Top predictors for '{target}': "
        interpretation += ", ".join([f"{feat} ({imp:.3f})" for feat, imp in top_features])
        interpretation += "."
        
        # Compare with mutual information
        if mi_scores:
            mi_top = sorted(mi_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            mi_features = [f[0] for f in mi_top]
            rf_features = [f[0] for f in top_features[:3]]
            
            if set(mi_features) == set(rf_features):
                interpretation += " Mutual information confirms these relationships."
            else:
                interpretation += f" Mutual information highlights {', '.join(mi_features)} — may indicate non-linear effects."
        
        return interpretation
    
    def interpret_group_comparison(self, result: Dict[str, Any]) -> str:
        """
        Interpret group comparison result.
        
        Example output:
        "Significant difference between groups A and B (Welch's t-test, p=0.003, 
         Cohen's d=0.72 [medium effect]). Group A mean: 45.2, Group B mean: 38.7."
        """
        comparison_type = result.get('comparison_type', 'unknown')
        groups = result.get('groups', [])
        test_result = result.get('test_result', {})
        group_stats = result.get('group_statistics', {})
        
        test_name = test_result.get('test_name', 'hypothesis test')
        interpretation_label = test_result.get('interpretation', 'unknown')
        
        # Start with significance
        if interpretation_label in ["highly_significant", "significant"]:
            sig_text = "Significant"
        elif interpretation_label == "borderline":
            sig_text = "Borderline"
        else:
            sig_text = "No significant"
        
        if comparison_type == "two_group" and len(groups) == 2:
            interpretation = f"{sig_text} difference between {groups[0]} and {groups[1]}. "
        else:
            interpretation = f"{sig_text} differences across groups ({', '.join(groups[:3])}{'...' if len(groups) > 3 else ''}). "
        
        # Add test details
        interpretation += self.interpret_hypothesis_test(test_result)
        
        # Add group means
        if group_stats and len(group_stats) <= 4:
            means_text = ". ".join([f"{name} mean: {stats.get('mean', 'N/A')}" 
                                    for name, stats in list(group_stats.items())[:4]])
            interpretation += f" {means_text}."
        
        return interpretation
    
    # =========================================================
    # BUSINESS REGISTER
    # Plain English variants — no p-values, no CI notation.
    # Use these for user-facing dashboard cards and annotations.
    # Use the statistical variants above for LLM prompt context.
    # =========================================================

    def interpret_correlation_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English correlation for a non-technical reader.

        Example output:
        "Revenue and marketing spend move together strongly —
         when one rises, the other reliably follows. This link
         explains roughly 72% of the variation in revenue."
        """
        r = result.get("correlation", 0)
        col1 = result.get("column1", "Variable 1")
        col2 = result.get("column2", "Variable 2")
        strength = result.get("strength", "moderate")
        effect = result.get("effect_size", abs(r))

        col1_clean = col1.replace("_", " ")
        col2_clean = col2.replace("_", " ")

        direction_phrase = (
            "move together" if r > 0 else "move in opposite directions"
        )
        strength_phrase = {
            "very_strong": "very strongly",
            "strong": "strongly",
            "moderate": "moderately",
            "weak": "weakly",
        }.get(strength, "noticeably")

        r_squared_pct = round(r ** 2 * 100)
        sentence = (
            f"{col1_clean.capitalize()} and {col2_clean} {strength_phrase} "
            f"{direction_phrase} — when one changes, the other tends to follow."
        )
        if r_squared_pct >= 20:
            sentence += (
                f" This relationship accounts for roughly {r_squared_pct}% "
                f"of the variation in {col2_clean}."
            )
        return sentence

    def interpret_hypothesis_test_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English significance test result.

        Example output:
        "The difference between these groups is real, not random chance —
         the gap is large enough to be commercially meaningful."
        """
        interpretation_label = result.get("interpretation", "not_significant")
        effect_interp = result.get("effect_size_interpretation", "")

        if interpretation_label in ("highly_significant", "significant"):
            verdict = "The difference between these groups is real, not random chance."
        elif interpretation_label == "borderline":
            verdict = "There may be a difference between these groups, but the evidence is borderline."
        else:
            verdict = "No meaningful difference detected between these groups."

        effect_phrase = {
            "large": " The gap is large enough to be commercially meaningful.",
            "medium": " The gap is moderate — worth watching.",
            "small": " The gap is small in practical terms.",
        }.get(effect_interp.lower(), "")

        return verdict + effect_phrase

    def interpret_distribution_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English distribution insight.

        Example output:
        "Most revenue values cluster at the lower end, with a long tail
         of very high values pulling the average up. The typical value
         (median) is a more reliable summary than the mean here."
        """
        col = result.get("column", "this column").replace("_", " ")
        skewness = result.get("skewness", 0)
        dist_type = result.get("distribution_type", "")

        if skewness > 1.0:
            return (
                f"Most {col} values are low, but a small number of very high values "
                f"pull the average up significantly. The median is a more reliable "
                f"summary than the mean for this column."
            )
        elif skewness > 0.3:
            return (
                f"{col.capitalize()} leans toward lower values with some high outliers. "
                f"The average overstates the typical value."
            )
        elif skewness < -1.0:
            return (
                f"Most {col} values are high, with a few very low values pulling "
                f"the average down. The median better represents the typical case."
            )
        elif skewness < -0.3:
            return (
                f"{col.capitalize()} leans toward higher values with some low outliers."
            )
        else:
            return (
                f"{col.capitalize()} is evenly distributed — the average reliably "
                f"represents the typical value."
            )

    def interpret_anomaly_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English anomaly summary.

        Example output:
        "23 records (2.3%) stand out as unusual in revenue —
         worth reviewing for data errors or exceptional cases."
        """
        col = result.get("column", "this column").replace("_", " ")
        count = result.get("outlier_count", 0)
        percentage = result.get("outlier_percentage", 0)

        if count == 0:
            return f"No unusual values detected in {col}."

        if percentage > 5:
            return (
                f"{count} records ({percentage:.1f}%) in {col} look unusual — "
                f"a high proportion that may point to data quality issues."
            )
        elif percentage > 1:
            return (
                f"{count} records ({percentage:.1f}%) in {col} stand out as "
                f"exceptional. Worth investigating — these could be errors or "
                f"genuinely interesting edge cases."
            )
        else:
            return (
                f"{count} records ({percentage:.1f}%) in {col} are outliers. "
                f"The data is mostly clean; these are rare exceptions."
            )

    def interpret_trend_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English trend insight.

        Example output:
        "Revenue has been steadily climbing over time —
         the upward direction is consistent, not just noise."
        """
        col = result.get("column", "this metric").replace("_", " ")
        trend_data = result.get("trend_analysis", result)
        trend_dir = trend_data.get("trend", "no_trend")
        is_significant = trend_data.get("is_significant", False)
        tau = abs(trend_data.get("tau", 0))

        strength = "steadily" if tau > 0.5 else "gradually"

        if trend_dir == "no_trend" or not is_significant:
            return f"{col.capitalize()} shows no consistent direction over time — values are relatively stable."
        elif trend_dir in ("increasing", "upward"):
            return (
                f"{col.capitalize()} has been {strength} climbing over time — "
                f"the upward direction is consistent, not random noise."
            )
        elif trend_dir in ("decreasing", "downward"):
            return (
                f"{col.capitalize()} has been {strength} declining over time — "
                f"the downward direction is consistent, not random noise."
            )
        return f"{col.capitalize()} shows a {trend_dir} trend over time."

    def interpret_group_comparison_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English group comparison.

        Example output:
        "Group A consistently outperforms Group B — the gap
         between them is large enough to matter in practice."
        """
        groups = result.get("groups", [])
        group_stats = result.get("group_statistics", {})
        test_result = result.get("test_result", result)
        interpretation_label = test_result.get("interpretation", "not_significant")
        effect_interp = test_result.get("effect_size_interpretation", "")

        if interpretation_label not in ("highly_significant", "significant", "borderline"):
            return "No meaningful difference detected across these groups."

        if len(groups) == 2 and group_stats:
            g1, g2 = groups[0], groups[1]
            m1 = group_stats.get(g1, {}).get("mean")
            m2 = group_stats.get(g2, {}).get("mean")
            if m1 is not None and m2 is not None:
                higher, lower = (g1, g2) if m1 > m2 else (g2, g1)
                size_phrase = {
                    "large": "by a wide margin",
                    "medium": "by a noticeable margin",
                    "small": "by a small margin",
                }.get(effect_interp.lower(), "meaningfully")
                return (
                    f"{higher.replace('_', ' ').capitalize()} consistently runs "
                    f"higher than {lower.replace('_', ' ')} {size_phrase}."
                )

        size_phrase = {
            "large": "The differences are large and commercially significant.",
            "medium": "The differences are moderate and worth acting on.",
            "small": "The differences are small but consistent.",
        }.get(effect_interp.lower(), "The differences are statistically meaningful.")

        groups_str = ", ".join(g.replace("_", " ") for g in groups[:3])
        return f"Meaningful differences exist across {groups_str}. {size_phrase}"

    def interpret_feature_importance_business(self, result: Dict[str, Any]) -> str:
        """
        Plain English feature importance.

        Example output:
        "Marketing spend is the single biggest driver of revenue,
         followed by customer count and ad clicks."
        """
        target = result.get("target_column", "the outcome").replace("_", " ")
        importances = result.get("random_forest_importance", {}).get("importances", {})

        if not importances:
            return f"Could not determine the key drivers of {target}."

        top = list(importances.items())[:3]
        if len(top) == 1:
            return (
                f"{top[0][0].replace('_', ' ').capitalize()} is the primary "
                f"driver of {target}."
            )
        elif len(top) == 2:
            return (
                f"{top[0][0].replace('_', ' ').capitalize()} and "
                f"{top[1][0].replace('_', ' ')} are the two main drivers of {target}."
            )
        else:
            return (
                f"{top[0][0].replace('_', ' ').capitalize()} is the biggest driver "
                f"of {target}, followed by {top[1][0].replace('_', ' ')} and "
                f"{top[2][0].replace('_', ' ')}."
            )

    def interpret_quis_finding_business(self, finding: Dict[str, Any]) -> str:
        """
        Dispatcher: route a QUIS top_insights finding dict to the right
        business-register method.

        Accepts the raw dict from QUISInsight.to_dict() and returns a
        plain English sentence suitable for a dashboard card or annotation.
        """
        insight_type = finding.get("insight_type", "")
        columns = finding.get("columns", [])
        description = finding.get("description", "")
        effect = finding.get("effect_size", 0)
        effect_interp = finding.get("effect_interpretation", "")
        statistic = finding.get("statistic", 0)
        p_value = finding.get("p_value", 1)

        col1 = columns[0] if len(columns) > 0 else "Variable 1"
        col2 = columns[1] if len(columns) > 1 else "Variable 2"

        if insight_type == "correlation":
            return self.interpret_correlation_business({
                "correlation": statistic,
                "column1": col1,
                "column2": col2,
                "strength": effect_interp,
                "effect_size": effect,
            })

        elif insight_type in ("comparison", "group_comparison"):
            return self.interpret_group_comparison_business({
                "groups": columns,
                "test_result": {
                    "interpretation": "significant" if p_value < 0.05 else "not_significant",
                    "effect_size_interpretation": effect_interp,
                },
                "group_statistics": {},
            })

        elif insight_type == "trend":
            direction = "increasing" if statistic > 0 else "decreasing"
            return self.interpret_trend_business({
                "column": col1,
                "trend_analysis": {
                    "trend": direction,
                    "is_significant": p_value < 0.05,
                    "tau": statistic,
                },
            })

        elif insight_type == "anomaly":
            # QUIS anomaly findings don't carry count/percentage — fall back to description
            col_clean = col1.replace("_", " ")
            return (
                f"Unusual values detected in {col_clean} — "
                f"these records stand out from the rest of the data."
            )

        elif insight_type == "simpson_paradox":
            col_clean = col1.replace("_", " ")
            col2_clean = col2.replace("_", " ")
            return (
                f"⚠ The relationship between {col_clean} and {col2_clean} reverses "
                f"when the data is broken into subgroups — overall averages are misleading here."
            )

        elif insight_type == "subspace":
            # Subspace findings describe a pattern in a filtered slice
            col_clean = col1.replace("_", " ")
            return (
                f"A specific segment of {col_clean} shows a pattern that doesn't "
                f"appear in the overall data — drill down to see the full picture."
            )

        # Fallback: clean up the raw description
        return description.replace("_", " ") if description else "Notable pattern detected."

    def generate_summary(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate an executive summary of the full analysis.
        
        Returns a concise paragraph suitable for reports or LLM context.
        """
        summary_parts = []
        
        # Dataset overview
        row_count = analysis_results.get('row_count', 0)
        col_count = analysis_results.get('column_count', 0)
        summary_parts.append(f"Dataset: {row_count:,} rows, {col_count} columns.")
        
        # Distributions
        distributions = analysis_results.get('distributions', [])
        non_normal = [d for d in distributions if not d.get('is_normal', True)]
        if non_normal:
            summary_parts.append(f"{len(non_normal)} columns deviate from normality.")
        
        # Correlations
        correlations = analysis_results.get('correlations', [])
        strong_corr = [c for c in correlations if abs(c.get('correlation', 0)) >= 0.7]
        if strong_corr:
            summary_parts.append(f"{len(strong_corr)} strong correlations found.")
        
        # Outliers
        outliers = analysis_results.get('outliers_iqr', []) or analysis_results.get('anomalies_ml', [])
        if outliers:
            total_outliers = sum(o.get('outlier_count', o.get('count', 0)) for o in outliers)
            summary_parts.append(f"{total_outliers} outliers detected across columns.")
        
        # Time series
        ts_results = analysis_results.get('time_series', {})
        if ts_results:
            trends = [v.get('trend_analysis', {}).get('trend', 'no_trend') 
                      for v in ts_results.values() if isinstance(v, dict)]
            significant_trends = [t for t in trends if t != 'no_trend']
            if significant_trends:
                summary_parts.append(f"Trend detected in {len(significant_trends)} time series.")
        
        return " ".join(summary_parts)


# Singleton instance
insight_interpreter = InsightInterpreter()
