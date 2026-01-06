# backend/services/analysis/advanced_stats.py

"""
Advanced Statistical Analysis Module
=====================================
Data scientist-level statistical methods including:
- Proper hypothesis testing with p-values
- Effect size calculations (Cohen's d, eta-squared, Cramér's V)
- Confidence intervals (bootstrap and parametric)
- Normality testing
- Non-parametric alternatives

All methods return structured results with interpretations.
"""

import logging
import numpy as np
import polars as pl
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from scipy import stats
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)


# ============================================================
# STRUCTURED RESULT TYPES
# ============================================================

@dataclass
class HypothesisTestResult:
    """Structured result for hypothesis tests with interpretation."""
    test_name: str
    statistic: float
    p_value: float
    effect_size: Optional[float] = None
    effect_size_interpretation: Optional[str] = None  # "negligible", "small", "medium", "large"
    confidence_interval: Optional[Tuple[float, float]] = None
    interpretation: str = ""  # "significant", "not_significant", "borderline"
    sample_sizes: Optional[Dict[str, int]] = None
    assumptions_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert tuple to list for JSON serialization
        if result['confidence_interval']:
            result['confidence_interval'] = list(result['confidence_interval'])
        return result


@dataclass
class DistributionTestResult:
    """Result of distribution analysis."""
    column: str
    mean: float
    std: float
    median: float
    skewness: float
    kurtosis: float
    is_normal: bool
    normality_p_value: float
    normality_test: str
    distribution_type: str  # "normal", "right_skewed", "left_skewed", "heavy_tailed", "light_tailed"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorrelationResult:
    """Enhanced correlation result with statistical details."""
    column1: str
    column2: str
    method: str  # "pearson", "spearman", "kendall"
    correlation: float
    p_value: float
    confidence_interval: Optional[Tuple[float, float]] = None
    strength: str = ""  # "negligible", "weak", "moderate", "strong", "very_strong"
    is_significant: bool = True
    sample_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if result['confidence_interval']:
            result['confidence_interval'] = list(result['confidence_interval'])
        return result


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    column: str
    method: str
    outlier_count: int
    outlier_percentage: float
    outlier_indices: List[int]
    threshold: Optional[float] = None
    scores: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Don't include large arrays in the dict representation
        if result['outlier_indices'] and len(result['outlier_indices']) > 100:
            result['outlier_indices'] = result['outlier_indices'][:100]
            result['outlier_indices_truncated'] = True
        if result['scores']:
            del result['scores']  # Too large for JSON
        return result


# ============================================================
# EFFECT SIZE CALCULATIONS
# ============================================================

class EffectSizeCalculator:
    """Calculate and interpret effect sizes for various statistical tests."""
    
    @staticmethod
    def cohens_d(group1: np.ndarray, group2: np.ndarray) -> Tuple[float, str]:
        """
        Calculate Cohen's d for two independent groups.
        
        Interpretation:
        - |d| < 0.2: negligible
        - 0.2 <= |d| < 0.5: small
        - 0.5 <= |d| < 0.8: medium
        - |d| >= 0.8: large
        """
        n1, n2 = len(group1), len(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        
        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        if pooled_std == 0:
            return 0.0, "undefined"
        
        d = (np.mean(group1) - np.mean(group2)) / pooled_std
        
        # Interpretation
        abs_d = abs(d)
        if abs_d < 0.2:
            interpretation = "negligible"
        elif abs_d < 0.5:
            interpretation = "small"
        elif abs_d < 0.8:
            interpretation = "medium"
        else:
            interpretation = "large"
        
        return round(d, 4), interpretation
    
    @staticmethod
    def eta_squared(f_statistic: float, df_between: int, df_within: int) -> Tuple[float, str]:
        """
        Calculate eta-squared (η²) for ANOVA.
        
        Interpretation:
        - η² < 0.01: negligible
        - 0.01 <= η² < 0.06: small
        - 0.06 <= η² < 0.14: medium
        - η² >= 0.14: large
        """
        eta_sq = (f_statistic * df_between) / (f_statistic * df_between + df_within)
        
        if eta_sq < 0.01:
            interpretation = "negligible"
        elif eta_sq < 0.06:
            interpretation = "small"
        elif eta_sq < 0.14:
            interpretation = "medium"
        else:
            interpretation = "large"
        
        return round(eta_sq, 4), interpretation
    
    @staticmethod
    def cramers_v(chi2: float, n: int, min_dim: int) -> Tuple[float, str]:
        """
        Calculate Cramér's V for chi-square test.
        
        Interpretation (depends on df, using conservative estimates):
        - V < 0.1: negligible
        - 0.1 <= V < 0.3: small
        - 0.3 <= V < 0.5: medium
        - V >= 0.5: large
        """
        v = np.sqrt(chi2 / (n * (min_dim - 1))) if (n * (min_dim - 1)) > 0 else 0
        
        if v < 0.1:
            interpretation = "negligible"
        elif v < 0.3:
            interpretation = "small"
        elif v < 0.5:
            interpretation = "medium"
        else:
            interpretation = "large"
        
        return round(v, 4), interpretation
    
    @staticmethod
    def rank_biserial_correlation(u_stat: float, n1: int, n2: int) -> Tuple[float, str]:
        """
        Calculate rank-biserial correlation for Mann-Whitney U test.
        This is the effect size for non-parametric comparisons.
        """
        r = 1 - (2 * u_stat) / (n1 * n2)
        
        abs_r = abs(r)
        if abs_r < 0.1:
            interpretation = "negligible"
        elif abs_r < 0.3:
            interpretation = "small"
        elif abs_r < 0.5:
            interpretation = "medium"
        else:
            interpretation = "large"
        
        return round(r, 4), interpretation


# ============================================================
# CONFIDENCE INTERVAL CALCULATORS
# ============================================================

class ConfidenceIntervalCalculator:
    """Calculate confidence intervals using various methods."""
    
    @staticmethod
    def mean_ci_parametric(data: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Calculate parametric confidence interval for the mean using t-distribution.
        """
        n = len(data)
        mean = np.mean(data)
        se = stats.sem(data)
        
        # t critical value
        alpha = 1 - confidence
        t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)
        
        margin = t_crit * se
        return (round(mean - margin, 4), round(mean + margin, 4))
    
    @staticmethod
    def bootstrap_ci(data: np.ndarray, statistic_func=np.mean, 
                     n_bootstrap: int = 1000, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Calculate bootstrap confidence interval for any statistic.
        """
        bootstrap_stats = []
        n = len(data)
        
        for _ in range(n_bootstrap):
            sample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats.append(statistic_func(sample))
        
        alpha = 1 - confidence
        lower = np.percentile(bootstrap_stats, 100 * alpha / 2)
        upper = np.percentile(bootstrap_stats, 100 * (1 - alpha / 2))
        
        return (round(lower, 4), round(upper, 4))
    
    @staticmethod
    def correlation_ci(r: float, n: int, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Calculate confidence interval for Pearson correlation using Fisher's z-transformation.
        """
        # Fisher's z transformation
        z = 0.5 * np.log((1 + r) / (1 - r)) if abs(r) < 1 else 0
        se_z = 1 / np.sqrt(n - 3) if n > 3 else 0
        
        alpha = 1 - confidence
        z_crit = stats.norm.ppf(1 - alpha / 2)
        
        z_lower = z - z_crit * se_z
        z_upper = z + z_crit * se_z
        
        # Back-transform
        r_lower = (np.exp(2 * z_lower) - 1) / (np.exp(2 * z_lower) + 1)
        r_upper = (np.exp(2 * z_upper) - 1) / (np.exp(2 * z_upper) + 1)
        
        return (round(r_lower, 4), round(r_upper, 4))


# ============================================================
# HYPOTHESIS TESTING SUITE
# ============================================================

class HypothesisTester:
    """Comprehensive hypothesis testing with proper statistical rigor."""
    
    def __init__(self):
        self.effect_calc = EffectSizeCalculator()
        self.ci_calc = ConfidenceIntervalCalculator()
    
    def test_normality(self, data: np.ndarray, alpha: float = 0.05) -> Dict[str, Any]:
        """
        Test normality using multiple methods:
        - Shapiro-Wilk (best for n < 5000)
        - D'Agostino-Pearson (best for larger samples)
        """
        data = data[~np.isnan(data)]
        n = len(data)
        
        if n < 8:
            return {
                "is_normal": None,
                "p_value": None,
                "test": "insufficient_data",
                "message": "At least 8 observations required for normality testing"
            }
        
        # Choose test based on sample size
        if n < 5000:
            stat, p_value = stats.shapiro(data)
            test_name = "shapiro_wilk"
        else:
            stat, p_value = stats.normaltest(data)
            test_name = "dagostino_pearson"
        
        is_normal = p_value >= alpha
        
        return {
            "is_normal": is_normal,
            "p_value": round(p_value, 6),
            "statistic": round(stat, 4),
            "test": test_name,
            "interpretation": "Data appears normally distributed" if is_normal else "Data deviates significantly from normal distribution",
            "sample_size": n
        }
    
    def welch_t_test(self, group1: np.ndarray, group2: np.ndarray, 
                     alpha: float = 0.05) -> HypothesisTestResult:
        """
        Welch's t-test for comparing two independent groups.
        More robust than Student's t-test when variances are unequal.
        """
        group1 = group1[~np.isnan(group1)]
        group2 = group2[~np.isnan(group2)]
        
        stat, p_value = stats.ttest_ind(group1, group2, equal_var=False)
        effect_size, effect_interp = self.effect_calc.cohens_d(group1, group2)
        
        # Mean difference CI
        mean_diff = np.mean(group1) - np.mean(group2)
        se = np.sqrt(np.var(group1, ddof=1)/len(group1) + np.var(group2, ddof=1)/len(group2))
        df = self._welch_df(group1, group2)
        t_crit = stats.t.ppf(0.975, df)
        ci = (round(mean_diff - t_crit * se, 4), round(mean_diff + t_crit * se, 4))
        
        if p_value < 0.001:
            interpretation = "highly_significant"
        elif p_value < alpha:
            interpretation = "significant"
        elif p_value < 0.1:
            interpretation = "borderline"
        else:
            interpretation = "not_significant"
        
        return HypothesisTestResult(
            test_name="welch_t_test",
            statistic=round(stat, 4),
            p_value=round(p_value, 6),
            effect_size=effect_size,
            effect_size_interpretation=effect_interp,
            confidence_interval=ci,
            interpretation=interpretation,
            sample_sizes={"group1": len(group1), "group2": len(group2)},
            assumptions_notes="Welch's t-test does not assume equal variances"
        )
    
    def _welch_df(self, g1: np.ndarray, g2: np.ndarray) -> float:
        """Calculate Welch-Satterthwaite degrees of freedom."""
        n1, n2 = len(g1), len(g2)
        v1, v2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
        
        num = (v1/n1 + v2/n2)**2
        denom = (v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1)
        
        return num / denom if denom > 0 else n1 + n2 - 2
    
    def mann_whitney_u_test(self, group1: np.ndarray, group2: np.ndarray,
                           alpha: float = 0.05) -> HypothesisTestResult:
        """
        Mann-Whitney U test (non-parametric alternative to t-test).
        Use when normality assumption is violated.
        """
        group1 = group1[~np.isnan(group1)]
        group2 = group2[~np.isnan(group2)]
        
        stat, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')
        effect_size, effect_interp = self.effect_calc.rank_biserial_correlation(
            stat, len(group1), len(group2)
        )
        
        if p_value < 0.001:
            interpretation = "highly_significant"
        elif p_value < alpha:
            interpretation = "significant"
        elif p_value < 0.1:
            interpretation = "borderline"
        else:
            interpretation = "not_significant"
        
        return HypothesisTestResult(
            test_name="mann_whitney_u",
            statistic=round(stat, 4),
            p_value=round(p_value, 6),
            effect_size=effect_size,
            effect_size_interpretation=effect_interp,
            interpretation=interpretation,
            sample_sizes={"group1": len(group1), "group2": len(group2)},
            assumptions_notes="Non-parametric test; does not assume normal distribution"
        )
    
    def one_way_anova(self, *groups, alpha: float = 0.05) -> HypothesisTestResult:
        """
        One-way ANOVA for comparing 3+ groups.
        Returns eta-squared as effect size.
        """
        clean_groups = [g[~np.isnan(g)] for g in groups]
        
        stat, p_value = stats.f_oneway(*clean_groups)
        
        # Calculate eta-squared
        df_between = len(clean_groups) - 1
        df_within = sum(len(g) - 1 for g in clean_groups)
        effect_size, effect_interp = self.effect_calc.eta_squared(stat, df_between, df_within)
        
        if p_value < 0.001:
            interpretation = "highly_significant"
        elif p_value < alpha:
            interpretation = "significant"
        elif p_value < 0.1:
            interpretation = "borderline"
        else:
            interpretation = "not_significant"
        
        return HypothesisTestResult(
            test_name="one_way_anova",
            statistic=round(stat, 4),
            p_value=round(p_value, 6),
            effect_size=effect_size,
            effect_size_interpretation=effect_interp,
            interpretation=interpretation,
            sample_sizes={f"group_{i}": len(g) for i, g in enumerate(clean_groups)},
            assumptions_notes="Assumes homogeneity of variances; consider Welch's ANOVA if violated"
        )
    
    def kruskal_wallis_test(self, *groups, alpha: float = 0.05) -> HypothesisTestResult:
        """
        Kruskal-Wallis H test (non-parametric alternative to one-way ANOVA).
        """
        clean_groups = [g[~np.isnan(g)] for g in groups]
        
        stat, p_value = stats.kruskal(*clean_groups)
        
        # Epsilon-squared effect size for Kruskal-Wallis
        n = sum(len(g) for g in clean_groups)
        epsilon_sq = stat / (n - 1) if n > 1 else 0
        
        if epsilon_sq < 0.01:
            effect_interp = "negligible"
        elif epsilon_sq < 0.06:
            effect_interp = "small"
        elif epsilon_sq < 0.14:
            effect_interp = "medium"
        else:
            effect_interp = "large"
        
        if p_value < 0.001:
            interpretation = "highly_significant"
        elif p_value < alpha:
            interpretation = "significant"
        elif p_value < 0.1:
            interpretation = "borderline"
        else:
            interpretation = "not_significant"
        
        return HypothesisTestResult(
            test_name="kruskal_wallis",
            statistic=round(stat, 4),
            p_value=round(p_value, 6),
            effect_size=round(epsilon_sq, 4),
            effect_size_interpretation=effect_interp,
            interpretation=interpretation,
            sample_sizes={f"group_{i}": len(g) for i, g in enumerate(clean_groups)},
            assumptions_notes="Non-parametric test; does not assume normal distribution"
        )
    
    def chi_square_test(self, contingency_table: np.ndarray, 
                        alpha: float = 0.05) -> HypothesisTestResult:
        """
        Chi-square test of independence with Cramér's V effect size.
        """
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        n = contingency_table.sum()
        min_dim = min(contingency_table.shape) 
        effect_size, effect_interp = self.effect_calc.cramers_v(chi2, n, min_dim)
        
        if p_value < 0.001:
            interpretation = "highly_significant"
        elif p_value < alpha:
            interpretation = "significant"
        elif p_value < 0.1:
            interpretation = "borderline"
        else:
            interpretation = "not_significant"
        
        return HypothesisTestResult(
            test_name="chi_square_independence",
            statistic=round(chi2, 4),
            p_value=round(p_value, 6),
            effect_size=effect_size,
            effect_size_interpretation=effect_interp,
            interpretation=interpretation,
            sample_sizes={"total_observations": int(n), "degrees_of_freedom": dof},
            assumptions_notes="Expected frequencies should be >= 5 for validity"
        )


# ============================================================
# DISTRIBUTION ANALYZER
# ============================================================

class DistributionAnalyzer:
    """Comprehensive distribution analysis."""
    
    def __init__(self):
        self.hypothesis_tester = HypothesisTester()
    
    def analyze_full(self, data: np.ndarray, column_name: str = "column") -> DistributionTestResult:
        """
        Comprehensive distribution analysis with normality testing.
        """
        data = data[~np.isnan(data)]
        
        if len(data) < 5:
            return DistributionTestResult(
                column=column_name,
                mean=0, std=0, median=0, skewness=0, kurtosis=0,
                is_normal=False, normality_p_value=0,
                normality_test="insufficient_data",
                distribution_type="unknown"
            )
        
        mean = float(np.mean(data))
        std = float(np.std(data, ddof=1))
        median = float(np.median(data))
        skewness = float(stats.skew(data))
        kurtosis = float(stats.kurtosis(data))  # Excess kurtosis (0 for normal)
        
        # Normality test
        normality_result = self.hypothesis_tester.test_normality(data)
        
        # Determine distribution type
        distribution_type = self._classify_distribution(skewness, kurtosis, normality_result['is_normal'])
        
        return DistributionTestResult(
            column=column_name,
            mean=round(mean, 4),
            std=round(std, 4),
            median=round(median, 4),
            skewness=round(skewness, 4),
            kurtosis=round(kurtosis, 4),
            is_normal=normality_result.get('is_normal', False),
            normality_p_value=normality_result.get('p_value', 0) or 0,
            normality_test=normality_result.get('test', 'unknown'),
            distribution_type=distribution_type
        )
    
    def _classify_distribution(self, skewness: float, kurtosis: float, is_normal: bool) -> str:
        """Classify distribution based on shape characteristics."""
        if is_normal:
            return "normal"
        
        if skewness > 0.5:
            return "right_skewed"
        elif skewness < -0.5:
            return "left_skewed"
        elif kurtosis > 1:
            return "heavy_tailed"
        elif kurtosis < -1:
            return "light_tailed"
        else:
            return "approximately_normal"


# ============================================================
# CORRELATION ANALYZER
# ============================================================

class CorrelationAnalyzer:
    """Enhanced correlation analysis with multiple methods."""
    
    def __init__(self):
        self.ci_calc = ConfidenceIntervalCalculator()
    
    def analyze_correlation(self, x: np.ndarray, y: np.ndarray,
                           col1: str, col2: str,
                           method: str = "pearson",
                           alpha: float = 0.05) -> CorrelationResult:
        """
        Calculate correlation with p-value, CI, and effect interpretation.
        """
        # Clean data
        mask = ~(np.isnan(x) | np.isnan(y))
        x_clean, y_clean = x[mask], y[mask]
        n = len(x_clean)
        
        if n < 5:
            return CorrelationResult(
                column1=col1, column2=col2, method=method,
                correlation=0, p_value=1, strength="insufficient_data",
                is_significant=False, sample_size=n
            )
        
        if method == "pearson":
            r, p_value = stats.pearsonr(x_clean, y_clean)
            ci = self.ci_calc.correlation_ci(r, n)
        elif method == "spearman":
            r, p_value = stats.spearmanr(x_clean, y_clean)
            ci = self.ci_calc.correlation_ci(r, n)  # Approximate CI
        elif method == "kendall":
            r, p_value = stats.kendalltau(x_clean, y_clean)
            ci = None  # CI not straightforward for Kendall
        else:
            raise ValueError(f"Unknown method: {method}")
        
        strength = self._interpret_strength(r)
        is_significant = p_value < alpha
        
        return CorrelationResult(
            column1=col1,
            column2=col2,
            method=method,
            correlation=round(r, 4),
            p_value=round(p_value, 6),
            confidence_interval=ci,
            strength=strength,
            is_significant=is_significant,
            sample_size=n
        )
    
    def _interpret_strength(self, r: float) -> str:
        """Interpret correlation strength."""
        abs_r = abs(r)
        if abs_r < 0.1:
            return "negligible"
        elif abs_r < 0.3:
            return "weak"
        elif abs_r < 0.5:
            return "moderate"
        elif abs_r < 0.7:
            return "strong"
        else:
            return "very_strong"


# ============================================================
# ANOMALY DETECTOR
# ============================================================

class AnomalyDetector:
    """Advanced anomaly detection methods."""
    
    def detect_isolation_forest(self, data: np.ndarray, column_name: str,
                                contamination: float = 0.05) -> AnomalyResult:
        """
        Isolation Forest-based anomaly detection.
        Good for high-dimensional data and non-linear patterns.
        """
        data_clean = data[~np.isnan(data)].reshape(-1, 1)
        
        if len(data_clean) < 10:
            return AnomalyResult(
                column=column_name, method="isolation_forest",
                outlier_count=0, outlier_percentage=0, outlier_indices=[]
            )
        
        clf = IsolationForest(contamination=contamination, random_state=42)
        predictions = clf.fit_predict(data_clean)
        scores = clf.score_samples(data_clean)
        
        # -1 indicates outlier in sklearn
        outlier_indices = np.where(predictions == -1)[0].tolist()
        
        return AnomalyResult(
            column=column_name,
            method="isolation_forest",
            outlier_count=len(outlier_indices),
            outlier_percentage=round(len(outlier_indices) / len(data_clean) * 100, 2),
            outlier_indices=outlier_indices,
            scores=scores.tolist()
        )
    
    def detect_zscore(self, data: np.ndarray, column_name: str,
                      threshold: float = 3.0, use_mad: bool = False) -> AnomalyResult:
        """
        Z-score based outlier detection.
        use_mad=True uses Median Absolute Deviation (more robust).
        """
        data_clean = data[~np.isnan(data)]
        
        if len(data_clean) < 5:
            return AnomalyResult(
                column=column_name, method="zscore",
                outlier_count=0, outlier_percentage=0, outlier_indices=[]
            )
        
        if use_mad:
            # Robust z-score using MAD
            median = np.median(data_clean)
            mad = np.median(np.abs(data_clean - median))
            mad_scale = mad * 1.4826  # Scale factor for normal distribution
            z_scores = np.abs(data_clean - median) / mad_scale if mad_scale > 0 else np.zeros_like(data_clean)
            method_name = "modified_zscore_mad"
        else:
            # Standard z-score
            mean = np.mean(data_clean)
            std = np.std(data_clean, ddof=1)
            z_scores = np.abs((data_clean - mean) / std) if std > 0 else np.zeros_like(data_clean)
            method_name = "zscore"
        
        outlier_indices = np.where(z_scores > threshold)[0].tolist()
        
        return AnomalyResult(
            column=column_name,
            method=method_name,
            outlier_count=len(outlier_indices),
            outlier_percentage=round(len(outlier_indices) / len(data_clean) * 100, 2),
            outlier_indices=outlier_indices,
            threshold=threshold,
            scores=z_scores.tolist()
        )


# ============================================================
# FEATURE ANALYZER
# ============================================================

class FeatureAnalyzer:
    """Feature importance and relationship analysis."""
    
    def calculate_mutual_information(self, X: np.ndarray, y: np.ndarray,
                                     feature_names: List[str],
                                     is_classification: bool = False) -> Dict[str, float]:
        """
        Calculate mutual information between features and target.
        Detects non-linear relationships.
        """
        # Handle NaN
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean, y_clean = X[mask], y[mask]
        
        if len(X_clean) < 10:
            return {name: 0.0 for name in feature_names}
        
        if is_classification:
            mi_scores = mutual_info_classif(X_clean, y_clean, random_state=42)
        else:
            mi_scores = mutual_info_regression(X_clean, y_clean, random_state=42)
        
        return {name: round(score, 4) for name, score in zip(feature_names, mi_scores)}
    
    def calculate_feature_importance_rf(self, X: np.ndarray, y: np.ndarray,
                                        feature_names: List[str],
                                        is_classification: bool = False) -> Dict[str, Any]:
        """
        Calculate feature importance using Random Forest.
        """
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean, y_clean = X[mask], y[mask]
        
        if len(X_clean) < 20:
            return {"error": "insufficient_data", "importances": {}}
        
        if is_classification:
            # Encode labels if needed
            if not np.issubdtype(y_clean.dtype, np.number):
                le = LabelEncoder()
                y_clean = le.fit_transform(y_clean)
            model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        else:
            model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        
        model.fit(X_clean, y_clean)
        importances = model.feature_importances_
        
        # Sort by importance
        importance_dict = {name: round(imp, 4) for name, imp in zip(feature_names, importances)}
        sorted_importances = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
        
        return {
            "importances": sorted_importances,
            "model_type": "random_forest_classifier" if is_classification else "random_forest_regressor",
            "n_samples": len(X_clean)
        }


# ============================================================
# TIME SERIES ANALYZER
# ============================================================

class TimeSeriesAnalyzer:
    """Time series specific analysis methods."""
    
    def detect_trend(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Mann-Kendall trend test.
        Non-parametric test for monotonic trends.
        """
        data = data[~np.isnan(data)]
        n = len(data)
        
        if n < 10:
            return {"trend": "insufficient_data", "p_value": None, "tau": None}
        
        # Calculate S statistic
        s = 0
        for k in range(n - 1):
            for j in range(k + 1, n):
                s += np.sign(data[j] - data[k])
        
        # Calculate variance
        unique, counts = np.unique(data, return_counts=True)
        ties = counts[counts > 1]
        
        var_s = (n * (n - 1) * (2 * n + 5)) / 18
        if len(ties) > 0:
            for t in ties:
                var_s -= (t * (t - 1) * (2 * t + 5)) / 18
        
        # Calculate z-statistic
        if s > 0:
            z = (s - 1) / np.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / np.sqrt(var_s)
        else:
            z = 0
        
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        tau = s / (n * (n - 1) / 2)  # Kendall's tau
        
        if p_value < 0.05:
            if tau > 0:
                trend = "increasing"
            else:
                trend = "decreasing"
        else:
            trend = "no_trend"
        
        return {
            "trend": trend,
            "tau": round(tau, 4),
            "z_statistic": round(z, 4),
            "p_value": round(p_value, 6),
            "is_significant": p_value < 0.05
        }
    
    def calculate_autocorrelation(self, data: np.ndarray, max_lag: int = 20) -> Dict[str, Any]:
        """
        Calculate autocorrelation function (ACF) for time series.
        """
        data = data[~np.isnan(data)]
        n = len(data)
        
        if n < max_lag + 5:
            max_lag = max(1, n - 5)
        
        mean = np.mean(data)
        var = np.var(data)
        
        if var == 0:
            return {"acf": [], "significant_lags": []}
        
        acf = []
        for lag in range(1, max_lag + 1):
            numerator = np.sum((data[lag:] - mean) * (data[:-lag] - mean))
            acf.append(round(numerator / (n * var), 4))
        
        # Significance threshold (approximate)
        threshold = 1.96 / np.sqrt(n)
        significant_lags = [lag + 1 for lag, val in enumerate(acf) if abs(val) > threshold]
        
        return {
            "acf": acf,
            "lags": list(range(1, max_lag + 1)),
            "significant_lags": significant_lags,
            "significance_threshold": round(threshold, 4)
        }


# ============================================================
# SINGLETON INSTANCES
# ============================================================

hypothesis_tester = HypothesisTester()
distribution_analyzer = DistributionAnalyzer()
correlation_analyzer = CorrelationAnalyzer()
anomaly_detector = AnomalyDetector()
feature_analyzer = FeatureAnalyzer()
time_series_analyzer = TimeSeriesAnalyzer()
effect_size_calculator = EffectSizeCalculator()
ci_calculator = ConfidenceIntervalCalculator()
