# backend/services/analysis_service.py

import logging
import polars as pl
from typing import List, Dict, Any, Optional
import numpy as np
from itertools import combinations
from scipy.stats import spearmanr, ttest_ind, chi2_contingency
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)

class AnalysisService:
    """
    AnalysisService: A full-featured computational engine for datasets.
    Performs statistical analysis, data quality checks, advanced metrics,
    and structured insights ready for LLM summarization.
    """

    def __init__(self):
        self.numeric_dtypes = pl.NUMERIC_DTYPES
        self.categorical_dtypes = [pl.Utf8, pl.Categorical]
        self.temporal_dtypes = [pl.Date, pl.Datetime]
        # Simple in-memory cache for expensive QUIS results keyed by dataset id
        # Format: { dataset_id: { 'result': {...}, 'ts': timestamp } }
        self._quis_cache = {}
        # Cache TTL in seconds (avoid recomputing too frequently)
        self._quis_cache_ttl = 30

    # ---------------- Basic Statistical Analyses ----------------

    def find_strong_correlations(self, df: pl.DataFrame, threshold: float = 0.7) -> List[Dict[str, Any]]:
        results = []
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns

        for col1, col2 in combinations(numeric_cols, 2):
            try:
                # Pearson correlation
                series1 = df[col1].to_numpy()
                series2 = df[col2].to_numpy()
                if len(series1) != len(series2):
                    continue
                mask = ~np.isnan(series1) & ~np.isnan(series2)
                if mask.sum() < 5:
                    continue
                # Guard against zero std deviation which causes divide-by-zero warnings
                a = series1[mask]
                b = series2[mask]
                if np.nanstd(a) == 0 or np.nanstd(b) == 0:
                    continue
                corr = np.corrcoef(a, b)[0, 1]
                if abs(corr) >= threshold:
                    results.append({
                        "type": "correlation",
                        "method": "pearson",
                        "columns": [col1, col2],
                        "value": round(float(corr), 3),
                        "strength": "strong" if abs(corr) > 0.8 else "moderate"
                    })
            except Exception as e:
                logger.warning(f"Correlation failed for {col1}-{col2}: {e}")
        return results

    def find_spearman_correlations(self, df: pl.DataFrame, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Detect monotonic non-linear correlations."""
        results = []
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
        for col1, col2 in combinations(numeric_cols, 2):
            try:
                s1, s2 = df[col1].to_numpy(), df[col2].to_numpy()
                mask = ~np.isnan(s1) & ~np.isnan(s2)
                if mask.sum() < 5:
                    continue
                corr, pval = spearmanr(s1[mask], s2[mask])
                if abs(corr) >= threshold:
                    results.append({
                        "type": "correlation",
                        "method": "spearman",
                        "columns": [col1, col2],
                        "value": round(float(corr), 3),
                        "p_value": round(float(pval), 5)
                    })
            except Exception as e:
                logger.warning(f"Spearman correlation failed for {col1}-{col2}: {e}")
        return results

    def detect_outliers_iqr(self, df: pl.DataFrame, multiplier: float = 1.5) -> List[Dict[str, Any]]:
        results = []
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
        for col in numeric_cols:
            try:
                series = df[col].drop_nulls().to_numpy()
                if len(series) < 10:
                    continue
                q1, q3 = np.percentile(series, [25, 75])
                iqr = q3 - q1
                lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
                outliers = series[(series < lower) | (series > upper)]
                if len(outliers) / len(series) > 0.01:
                    results.append({
                        "type": "outlier",
                        "column": col,
                        "count": int(len(outliers)),
                        "percentage": round(len(outliers) / len(series) * 100, 2),
                        "method": "IQR"
                    })
            except Exception as e:
                logger.warning(f"Outlier detection failed for {col}: {e}")
        return results

    def find_dominant_categories(self, df: pl.DataFrame, threshold: float = 0.5) -> List[Dict[str, Any]]:
        results = []
        categorical_cols = df.select(pl.col(self.categorical_dtypes)).columns
        for col in categorical_cols:
            try:
                # Get value counts as a dictionary
                vc_df = df[col].value_counts()
                vc_dict = {}
                for row in vc_df.to_dicts():
                    value = row[col]
                    count = row['count']
                    vc_dict[value] = count
                
                if not vc_dict:
                    continue
                    
                total = sum(vc_dict.values())
                top_value, top_count = max(vc_dict.items(), key=lambda x: x[1])
                if top_count / total >= threshold:
                    results.append({
                        "type": "dominant_category",
                        "column": col,
                        "dominant_value": top_value,
                        "percentage": round(top_count / total * 100, 2)
                    })
            except Exception as e:
                logger.warning(f"Dominant category check failed for {col}: {e}")
        return results

    # ---------------- Advanced Analyses ----------------

    def analyze_distribution(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        results = []
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
        for col in numeric_cols:
            series = df[col].drop_nulls().to_numpy()
            if len(series) < 5:
                continue
            skewness = float(np.mean(((series - np.mean(series))**3)) / (np.std(series)**3))
            results.append({
                "type": "distribution",
                "column": col,
                "mean": float(np.mean(series)),
                "std": float(np.std(series)),
                "skewness": round(skewness, 3)
            })
        return results

    def detect_missing_patterns(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        results = []
        total_rows = len(df)
        for col in df.columns:
            missing = df[col].null_count()
            if missing > 0:
                results.append({
                    "type": "missing_values",
                    "column": col,
                    "count": missing,
                    "percentage": round(missing / total_rows * 100, 2)
                })
        return results

    def duplicate_rows(self, df: pl.DataFrame) -> Dict[str, Any]:
        dup_count = df.is_duplicated().sum()
        return {"type": "duplicate_rows", "count": int(dup_count)}

    # ---------------- Statistical Significance ----------------

    def t_test_between_groups(self, df: pl.DataFrame, group_col: str, value_col: str) -> Dict[str, Any]:
        try:
            groups = df.select([group_col, value_col]).drop_nulls().to_numpy()
            unique_groups = np.unique(groups[:,0])
            if len(unique_groups) != 2:
                return {}
            g1 = groups[groups[:,0] == unique_groups[0], 1].astype(float)
            g2 = groups[groups[:,0] == unique_groups[1], 1].astype(float)
            stat, pval = ttest_ind(g1, g2)
            return {
                "type": "t_test",
                "groups": list(unique_groups),
                "statistic": float(stat),
                "p_value": float(pval)
            }
        except Exception as e:
            logger.warning(f"T-test failed: {e}")
            return {}

    def chi_square_test(self, df: pl.DataFrame, col1: str, col2: str) -> Dict[str, Any]:
        try:
            # Drop null values before creating crosstab
            clean_df = df.select([col1, col2]).drop_nulls()
            if len(clean_df) < 10:  # Need sufficient data for chi-square test
                logger.warning("Not enough valid data for chi-square test")
                return {}
            
            crosstab = clean_df.to_pandas().crosstab(clean_df[col1].to_pandas(), clean_df[col2].to_pandas())
            chi2, p, dof, expected = chi2_contingency(crosstab)
            return {
                "type": "chi_square",
                "columns": [col1, col2],
                "chi2_stat": float(chi2),
                "p_value": float(p),
                "dof": int(dof)
            }
        except Exception as e:
            logger.warning(f"Chi-square test failed: {e}")
            return {}

    # ---------------- Multi-dimensional / ML Analyses ----------------

    def run_pca(self, df: pl.DataFrame, n_components: int = 2) -> Dict[str, Any]:
        try:
            numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
            if len(numeric_cols) < 2:
                logger.warning("PCA requires at least 2 numeric columns")
                return {}
            
            # Get data and handle NaN values
            data = df.select(numeric_cols).to_numpy()
            
            # Check for NaN values and handle them
            if np.isnan(data).any():
                logger.info("Found NaN values in data, dropping rows with NaN values for PCA")
                # Drop rows with any NaN values
                mask = ~np.isnan(data).any(axis=1)
                if mask.sum() < 5:  # Need at least 5 valid rows
                    logger.warning("Not enough valid rows for PCA after removing NaN values")
                    return {}
                data = data[mask]
            
            if len(data) < n_components:
                logger.warning(f"Not enough data points ({len(data)}) for {n_components} components")
                return {}
            
            pca = PCA(n_components=min(n_components, len(numeric_cols)))
            pca.fit(data)
            explained = pca.explained_variance_ratio_
            return {"type": "pca", "explained_variance_ratio": explained.tolist()}
        except Exception as e:
            logger.warning(f"PCA failed: {e}")
            return {}

    def run_kmeans(self, df: pl.DataFrame, n_clusters: int = 3) -> Dict[str, Any]:
        try:
            numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
            if len(numeric_cols) < 2:
                logger.warning("KMeans requires at least 2 numeric columns")
                return {}
            
            # Get data and handle NaN values
            data = df.select(numeric_cols).to_numpy()
            
            # Check for NaN values and handle them
            if np.isnan(data).any():
                logger.info("Found NaN values in data, dropping rows with NaN values for KMeans")
                # Drop rows with any NaN values
                mask = ~np.isnan(data).any(axis=1)
                if mask.sum() < n_clusters * 2:  # Need at least 2 points per cluster
                    logger.warning("Not enough valid rows for KMeans after removing NaN values")
                    return {}
                data = data[mask]
            
            if len(data) < n_clusters:
                logger.warning(f"Not enough data points ({len(data)}) for {n_clusters} clusters")
                return {}
            
            kmeans = KMeans(n_clusters=min(n_clusters, len(data)), random_state=42).fit(data)
            return {
                "type": "kmeans",
                "n_clusters": kmeans.n_clusters,
                "inertia": float(kmeans.inertia_),
                "cluster_centers": kmeans.cluster_centers_.tolist()
            }
        except Exception as e:
            logger.warning(f"KMeans failed: {e}")
            return {}

    # ---------------- QUIS Subspace Search (Advanced Insights) ----------------

    def find_deep_insights(self, df: pl.DataFrame, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        QUIS Subspace Search: Find insights that become much stronger in filtered data segments.
        This implements the core QUIS methodology for discovering hidden patterns.
        """
        logger.info("Starting QUIS subspace search for deep insights...")
        
        deep_insights = []
        
        # Step 1: Find basic insights in the full dataset
        basic_correlations = self.find_strong_correlations(df, threshold=0.3)  # Lower threshold for exploration
        
        # Step 2: For each moderate correlation, search for subspaces where it's stronger
        for correlation in basic_correlations:
            if abs(correlation["value"]) < 0.8:  # Only explore moderate correlations
                subspace_insights = self._search_correlation_subspaces(
                    df, correlation, max_depth=max_depth
                )
                deep_insights.extend(subspace_insights)
        
        # Step 3: Search for category-specific patterns
        category_patterns = self._find_category_specific_patterns(df, max_depth=max_depth)
        deep_insights.extend(category_patterns)
        
        # Step 4: Search for temporal patterns in subsets
        temporal_patterns = self._find_temporal_subspace_patterns(df, max_depth=max_depth)
        deep_insights.extend(temporal_patterns)
        
        logger.info(f"QUIS subspace search completed. Found {len(deep_insights)} deep insights.")
        return deep_insights

    def _search_correlation_subspaces(self, df: pl.DataFrame, correlation: Dict, max_depth: int) -> List[Dict[str, Any]]:
        """Search for subspaces where a correlation becomes much stronger."""
        insights = []
        col1, col2 = correlation["columns"]
        base_correlation = abs(correlation["value"])
        
        # Get categorical columns for filtering
        categorical_cols = df.select(pl.col(self.categorical_dtypes)).columns
        
        # Single-level subspace search
        for cat_col in categorical_cols[:5]:  # Limit to top 5 categorical columns for performance
            try:
                unique_values = df[cat_col].drop_nulls().unique().to_list()
                if len(unique_values) > 10:  # Skip columns with too many categories
                    continue
                    
                for value in unique_values[:5]:  # Limit to top 5 values per column
                    # Filter the dataset
                    filtered_df = df.filter(pl.col(cat_col) == value)
                    
                    if len(filtered_df) < 10:  # Need minimum data points
                        continue
                    
                    # Recalculate correlation in this subspace
                    subspace_correlation = self._calculate_correlation(
                        filtered_df, col1, col2
                    )
                    
                    if subspace_correlation is not None:
                        correlation_strength = abs(subspace_correlation)
                        
                        # Check if correlation is significantly stronger in this subspace
                        if correlation_strength > base_correlation + 0.2:  # At least 0.2 improvement
                            insights.append({
                                "type": "subspace_correlation",
                                "base_insight": correlation,
                                "subspace": {cat_col: value},
                                "subspace_correlation": round(subspace_correlation, 3),
                                "improvement": round(correlation_strength - base_correlation, 3),
                                "subspace_size": len(filtered_df),
                                "significance": "high" if correlation_strength > 0.8 else "moderate"
                            })
            except Exception as e:
                logger.warning(f"Subspace search failed for {cat_col}: {e}")
                continue
        
        # Two-level subspace search (if max_depth allows)
        if max_depth >= 2 and len(categorical_cols) >= 2:
            insights.extend(self._search_two_level_subspaces(df, correlation, categorical_cols))
        
        return insights

    def _search_two_level_subspaces(self, df: pl.DataFrame, correlation: Dict, categorical_cols: List[str]) -> List[Dict[str, Any]]:
        """Search for two-level subspaces (e.g., Region=North AND Category=Electronics)."""
        insights = []
        col1, col2 = correlation["columns"]
        base_correlation = abs(correlation["value"])
        
        # Try combinations of two categorical columns
        for cat_col1, cat_col2 in combinations(categorical_cols[:3], 2):  # Limit combinations
            try:
                values1 = df[cat_col1].drop_nulls().unique().to_list()[:3]
                values2 = df[cat_col2].drop_nulls().unique().to_list()[:3]
                
                for val1 in values1:
                    for val2 in values2:
                        # Filter by both conditions
                        filtered_df = df.filter(
                            (pl.col(cat_col1) == val1) & (pl.col(cat_col2) == val2)
                        )
                        
                        if len(filtered_df) < 10:
                            continue
                        
                        # Recalculate correlation
                        subspace_correlation = self._calculate_correlation(
                            filtered_df, col1, col2
                        )
                        
                        if subspace_correlation is not None:
                            correlation_strength = abs(subspace_correlation)
                            
                            # Only report if significantly stronger
                            if correlation_strength > base_correlation + 0.3:  # Higher threshold for 2-level
                                insights.append({
                                    "type": "two_level_subspace_correlation",
                                    "base_insight": correlation,
                                    "subspace": {cat_col1: val1, cat_col2: val2},
                                    "subspace_correlation": round(subspace_correlation, 3),
                                    "improvement": round(correlation_strength - base_correlation, 3),
                                    "subspace_size": len(filtered_df),
                                    "significance": "very_high" if correlation_strength > 0.9 else "high"
                                })
            except Exception as e:
                logger.warning(f"Two-level subspace search failed: {e}")
                continue
        
        return insights

    def _find_category_specific_patterns(self, df: pl.DataFrame, max_depth: int) -> List[Dict[str, Any]]:
        """Find patterns that are specific to certain categories."""
        insights = []
        
        # Look for categories with unusual statistical properties
        categorical_cols = df.select(pl.col(self.categorical_dtypes)).columns
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
        
        for cat_col in categorical_cols[:3]:  # Limit for performance
            for num_col in numeric_cols[:3]:
                try:
                    # Calculate overall statistics
                    overall_mean = df[num_col].mean()
                    overall_std = df[num_col].std()
                    
                    unique_values = df[cat_col].drop_nulls().unique().to_list()
                    
                    for value in unique_values[:5]:
                        filtered_df = df.filter(pl.col(cat_col) == value)
                        
                        if len(filtered_df) < 10:
                            continue
                        
                        subspace_mean = filtered_df[num_col].mean()
                        subspace_std = filtered_df[num_col].std()
                        
                        # Check for significant deviations
                        mean_deviation = abs(subspace_mean - overall_mean) / overall_std if overall_std > 0 else 0
                        
                        if mean_deviation > 1.5:  # More than 1.5 standard deviations different
                            insights.append({
                                "type": "category_specific_pattern",
                                "category_column": cat_col,
                                "category_value": value,
                                "numeric_column": num_col,
                                "overall_mean": round(float(overall_mean), 3),
                                "subspace_mean": round(float(subspace_mean), 3),
                                "deviation": round(float(mean_deviation), 3),
                                "subspace_size": len(filtered_df),
                                "significance": "high" if mean_deviation > 2.0 else "moderate"
                            })
                except Exception as e:
                    logger.warning(f"Category-specific pattern search failed: {e}")
                    continue
        
        return insights

    def _find_temporal_subspace_patterns(self, df: pl.DataFrame, max_depth: int) -> List[Dict[str, Any]]:
        """Find temporal patterns that are stronger in certain subspaces."""
        insights = []
        
        # Look for temporal columns
        temporal_cols = df.select(pl.col(self.temporal_dtypes)).columns
        numeric_cols = df.select(pl.col(self.numeric_dtypes)).columns
        categorical_cols = df.select(pl.col(self.categorical_dtypes)).columns
        
        if not temporal_cols or not numeric_cols:
            return insights
        
        # For each temporal + numeric combination, look for trends in categories
        for temp_col in temporal_cols[:1]:  # Usually just one temporal column
            for num_col in numeric_cols[:2]:
                for cat_col in categorical_cols[:2]:
                    try:
                        # Get unique categories
                        unique_categories = df[cat_col].drop_nulls().unique().to_list()
                        
                        for category in unique_categories[:3]:
                            # Filter by category
                            filtered_df = df.filter(pl.col(cat_col) == category)
                            
                            if len(filtered_df) < 20:  # Need enough data for trend analysis
                                continue
                            
                            # Try to detect trend in this subspace
                            trend_strength = self._calculate_trend_strength(
                                filtered_df, temp_col, num_col
                            )
                            
                            if trend_strength > 0.6:  # Strong trend threshold
                                insights.append({
                                    "type": "temporal_subspace_trend",
                                    "category_column": cat_col,
                                    "category_value": category,
                                    "temporal_column": temp_col,
                                    "numeric_column": num_col,
                                    "trend_strength": round(trend_strength, 3),
                                    "subspace_size": len(filtered_df),
                                    "significance": "high" if trend_strength > 0.8 else "moderate"
                                })
                    except Exception as e:
                        logger.warning(f"Temporal subspace pattern search failed: {e}")
                        continue
        
        return insights

    def _calculate_correlation(self, df: pl.DataFrame, col1: str, col2: str) -> Optional[float]:
        """Helper method to calculate correlation between two columns."""
        try:
            series1 = df[col1].to_numpy()
            series2 = df[col2].to_numpy()
            
            mask = ~np.isnan(series1) & ~np.isnan(series2)
            if mask.sum() < 5:
                return None

            a = series1[mask]
            b = series2[mask]
            if np.nanstd(a) == 0 or np.nanstd(b) == 0:
                return None

            corr = np.corrcoef(a, b)[0, 1]
            return float(corr) if not np.isnan(corr) else None
        except Exception:
            return None

    def _calculate_trend_strength(self, df: pl.DataFrame, temp_col: str, num_col: str) -> float:
        """Calculate trend strength using linear regression correlation."""
        try:
            # Convert temporal column to numeric (days since epoch)
            if df[temp_col].dtype in self.temporal_dtypes:
                df_with_numeric_time = df.with_columns([
                    pl.col(temp_col).dt.epoch("days").alias("_temp_numeric")
                ])
                temp_numeric_col = "_temp_numeric"
            else:
                temp_numeric_col = temp_col
            
            series1 = df_with_numeric_time[temp_numeric_col].to_numpy()
            series2 = df_with_numeric_time[num_col].to_numpy()
            
            mask = ~np.isnan(series1) & ~np.isnan(series2)
            if mask.sum() < 5:
                return 0.0

            a = series1[mask]
            b = series2[mask]
            if np.nanstd(a) == 0 or np.nanstd(b) == 0:
                return 0.0

            corr = np.corrcoef(a, b)[0, 1]
            return abs(float(corr)) if not np.isnan(corr) else 0.0
        except Exception:
            return 0.0

    # ---------------- Master Function ----------------

    def run_all_statistical_checks(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        findings = []
        findings.extend(self.find_strong_correlations(df))
        findings.extend(self.find_spearman_correlations(df))
        findings.extend(self.detect_outliers_iqr(df))
        findings.extend(self.find_dominant_categories(df))
        findings.extend(self.analyze_distribution(df))
        findings.extend(self.detect_missing_patterns(df))
        findings.append(self.duplicate_rows(df))
        # PCA and KMeans for multivariate insights
        findings.append(self.run_pca(df))
        findings.append(self.run_kmeans(df))
        return findings

    def run_quis_analysis(self, df: pl.DataFrame, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Master QUIS analysis function that combines basic insights with deep subspace search.
        This is the main entry point for the enhanced QUIS methodology.
        """
        logger.info("Starting comprehensive QUIS analysis...")

        # If a dataset_id is provided, try to use cached results to avoid repeated heavy computation
        if dataset_id:
            import time
            cached = self._quis_cache.get(dataset_id)
            if cached and (time.time() - cached.get('ts', 0) < self._quis_cache_ttl):
                logger.info(f"Returning cached QUIS results for dataset {dataset_id}")
                return cached['result']
        
        # Run basic statistical checks
        basic_insights = self.run_all_statistical_checks(df)
        
        # Run deep subspace search
        deep_insights = self.find_deep_insights(df, max_depth=2)
        
        # Combine and structure the results
        quis_results = {
            "basic_insights": basic_insights,
            "deep_insights": deep_insights,
            "summary": {
                "total_basic_insights": len(basic_insights),
                "total_deep_insights": len(deep_insights),
                "high_significance_insights": len([i for i in deep_insights if i.get("significance") == "high"]),
                "very_high_significance_insights": len([i for i in deep_insights if i.get("significance") == "very_high"])
            }
        }
        
        logger.info(f"QUIS analysis completed: {quis_results['summary']}")

        # Store in cache if dataset_id provided
        if dataset_id:
            import time
            self._quis_cache[dataset_id] = {'result': quis_results, 'ts': time.time()}
        return quis_results


# Singleton instance for easy import
analysis_service = AnalysisService()
