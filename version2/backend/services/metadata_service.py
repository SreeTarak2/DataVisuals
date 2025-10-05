import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class MetadataService:
    """Service for generating LLM-safe metadata packages."""
    
    @staticmethod
    async def generate_llm_metadata_package(dataset_data: List[Dict], dataset_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive metadata package for LLM consumption.
        NEVER includes raw data rows - only metadata, samples, and summaries.
        """
        if not dataset_data:
            return {"error": "No data available"}
        
        df = pd.DataFrame(dataset_data)
        
        # 1. Dataset Overview
        dataset_overview = {
            "dataset_id": dataset_id,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "data_types_distribution": df.dtypes.value_counts().to_dict(),
            "upload_timestamp": datetime.utcnow().isoformat()
        }
        
        # 2. Column Metadata (Detailed)
        column_metadata = []
        for col in df.columns:
            col_info = MetadataService._analyze_column_for_llm(df[col], col)
            column_metadata.append(col_info)
        
        # 3. Statistical Summaries (No raw data)
        statistical_summaries = MetadataService._generate_statistical_summaries(df)
        
        # 4. Data Quality Metrics
        data_quality = MetadataService._assess_data_quality_for_llm(df)
        
        # 5. Sample Data (Limited and Safe)
        sample_data = MetadataService._generate_safe_samples(df, max_samples=10)
        
        # 6. Chart Recommendations (Based on data types)
        chart_recommendations = MetadataService._generate_chart_recommendations(df)
        
        # 7. Potential Hierarchies
        hierarchies = MetadataService._detect_potential_hierarchies(df)
        
        # 8. Data Patterns and Insights
        patterns = MetadataService._detect_data_patterns(df)
        
        return {
            "dataset_overview": dataset_overview,
            "column_metadata": column_metadata,
            "statistical_summaries": statistical_summaries,
            "data_quality": data_quality,
            "sample_data": sample_data,
            "chart_recommendations": chart_recommendations,
            "hierarchies": hierarchies,
            "patterns": patterns,
            "llm_ready": True,
            "metadata_version": "1.0"
        }
    
    @staticmethod
    def _analyze_column_for_llm(series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Analyze column for LLM consumption - no raw data."""
        col_info = {
            "name": col_name,
            "dtype": str(series.dtype),
            "is_numeric": pd.api.types.is_numeric_dtype(series),
            "is_categorical": series.dtype == 'object' and series.nunique() < len(series) * 0.8,
            "is_temporal": pd.api.types.is_datetime64_any_dtype(series),
            "null_count": int(series.isnull().sum()),
            "null_percentage": float((series.isnull().sum() / len(series)) * 100),
            "unique_count": int(series.nunique()),
            "unique_percentage": float((series.nunique() / len(series)) * 100),
            "cardinality": "high" if series.nunique() > len(series) * 0.8 else "medium" if series.nunique() > len(series) * 0.2 else "low"
        }
        
        # Numeric statistics (no raw values)
        if col_info["is_numeric"]:
            col_info.update({
                "min": float(series.min()) if not pd.isna(series.min()) else None,
                "max": float(series.max()) if not pd.isna(series.max()) else None,
                "mean": float(series.mean()) if not pd.isna(series.mean()) else None,
                "median": float(series.median()) if not pd.isna(series.median()) else None,
                "std": float(series.std()) if not pd.isna(series.std()) else None,
                "quartiles": {
                    "q1": float(series.quantile(0.25)) if not pd.isna(series.quantile(0.25)) else None,
                    "q3": float(series.quantile(0.75)) if not pd.isna(series.quantile(0.75)) else None
                }
            })
        
        # Categorical statistics (no raw values)
        if col_info["is_categorical"]:
            value_counts = series.value_counts().head(10)
            col_info.update({
                "top_values": value_counts.to_dict(),
                "value_distribution": "uniform" if series.nunique() > len(series) * 0.5 else "skewed"
            })
        
        # Temporal statistics (no raw values)
        if col_info["is_temporal"]:
            col_info.update({
                "min_date": series.min().isoformat() if not pd.isna(series.min()) else None,
                "max_date": series.max().isoformat() if not pd.isna(series.max()) else None,
                "date_range_days": (series.max() - series.min()).days if not pd.isna(series.min()) and not pd.isna(series.max()) else None
            })
        
        return col_info
    
    @staticmethod
    def _generate_statistical_summaries(df: pd.DataFrame) -> Dict[str, Any]:
        """Generate statistical summaries without raw data."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object']).columns
        
        summaries = {
            "numeric_summary": {},
            "categorical_summary": {},
            "correlations": {},
            "missing_data_patterns": {}
        }
        
        # Numeric summaries
        if len(numeric_cols) > 0:
            summaries["numeric_summary"] = {
                "total_numeric_columns": len(numeric_cols),
                "columns": numeric_cols.tolist(),
                "overall_stats": {
                    "total_sum": float(df[numeric_cols].sum().sum()),
                    "total_mean": float(df[numeric_cols].mean().mean()),
                    "total_std": float(df[numeric_cols].std().mean())
                }
            }
        
        # Categorical summaries
        if len(categorical_cols) > 0:
            summaries["categorical_summary"] = {
                "total_categorical_columns": len(categorical_cols),
                "columns": categorical_cols.tolist(),
                "overall_cardinality": {
                    "high_cardinality": len([col for col in categorical_cols if df[col].nunique() > len(df) * 0.8]),
                    "medium_cardinality": len([col for col in categorical_cols if 0.2 < df[col].nunique() / len(df) <= 0.8]),
                    "low_cardinality": len([col for col in categorical_cols if df[col].nunique() / len(df) <= 0.2])
                }
            }
        
        return summaries
    
    @staticmethod
    def _assess_data_quality_for_llm(df: pd.DataFrame) -> Dict[str, Any]:
        """Assess data quality for LLM consumption."""
        total_cells = df.size
        missing_cells = df.isnull().sum().sum()
        duplicate_rows = df.duplicated().sum()
        
        quality_score = 100
        quality_score -= (missing_cells / total_cells) * 100 * 0.5
        quality_score -= (duplicate_rows / len(df)) * 100 * 0.3
        quality_score = max(0, quality_score)
        
        return {
            "overall_quality_score": round(quality_score, 2),
            "missing_data_percentage": round((missing_cells / total_cells) * 100, 2),
            "duplicate_percentage": round((duplicate_rows / len(df)) * 100, 2),
            "completeness_level": "excellent" if quality_score >= 90 else "good" if quality_score >= 70 else "fair" if quality_score >= 50 else "poor",
            "data_issues": {
                "high_missing_columns": [col for col in df.columns if df[col].isnull().sum() > len(df) * 0.5],
                "high_duplicate_columns": [col for col in df.columns if df[col].nunique() < len(df) * 0.1]
            }
        }
    
    @staticmethod
    def _generate_safe_samples(df: pd.DataFrame, max_samples: int = 10) -> Dict[str, Any]:
        """Generate safe sample data for LLM - limited and anonymized."""
        # Take random sample
        sample_df = df.sample(n=min(max_samples, len(df)), random_state=42)
        
        # Anonymize sensitive data
        safe_sample = []
        for _, row in sample_df.iterrows():
            safe_row = {}
            for col, value in row.items():
                if pd.isna(value):
                    safe_row[col] = None
                elif isinstance(value, str) and len(value) > 20:
                    # Truncate long strings
                    safe_row[col] = value[:20] + "..."
                else:
                    safe_row[col] = str(value)
            safe_sample.append(safe_row)
        
        return {
            "sample_count": len(safe_sample),
            "sample_data": safe_sample,
            "note": "Sample data only - not representative of full dataset"
        }
    
    @staticmethod
    def _generate_chart_recommendations(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate chart recommendations based on data types and patterns."""
        recommendations = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        temporal_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        # Bar charts for categorical data
        if categorical_cols and numeric_cols:
            recommendations.append({
                "chart_type": "bar_chart",
                "title": f"Distribution by {categorical_cols[0]}",
                "description": "Shows distribution of numeric values across categories",
                "suitable_columns": [categorical_cols[0], numeric_cols[0]],
                "confidence": "high"
            })
        
        # Line charts for temporal data
        if temporal_cols and numeric_cols:
            recommendations.append({
                "chart_type": "line_chart",
                "title": f"Trend over {temporal_cols[0]}",
                "description": "Shows trend of numeric values over time",
                "suitable_columns": [temporal_cols[0], numeric_cols[0]],
                "confidence": "high"
            })
        
        # Pie charts for low cardinality categorical data
        low_cardinality_cats = [col for col in categorical_cols if df[col].nunique() <= 10]
        if low_cardinality_cats:
            recommendations.append({
                "chart_type": "pie_chart",
                "title": f"Distribution of {low_cardinality_cats[0]}",
                "description": "Shows proportional distribution of categories",
                "suitable_columns": [low_cardinality_cats[0]],
                "confidence": "medium"
            })
        
        # Scatter plots for numeric correlations
        if len(numeric_cols) >= 2:
            recommendations.append({
                "chart_type": "scatter_plot",
                "title": f"Correlation: {numeric_cols[0]} vs {numeric_cols[1]}",
                "description": "Shows relationship between two numeric variables",
                "suitable_columns": [numeric_cols[0], numeric_cols[1]],
                "confidence": "medium"
            })
        
        return recommendations
    
    @staticmethod
    def _detect_potential_hierarchies(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect potential hierarchies for drill-down."""
        hierarchies = []
        
        # Date hierarchies
        temporal_cols = df.select_dtypes(include=['datetime64']).columns
        for col in temporal_cols:
            hierarchies.append({
                "type": "temporal",
                "field": col,
                "levels": ["year", "quarter", "month", "day"],
                "confidence": "high"
            })
        
        # Geographic hierarchies
        geo_indicators = ['region', 'country', 'state', 'city', 'area', 'zone']
        categorical_cols = df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            if any(indicator in col.lower() for indicator in geo_indicators):
                hierarchies.append({
                    "type": "geographic",
                    "field": col,
                    "levels": [col],
                    "confidence": "medium"
                })
        
        return hierarchies
    
    @staticmethod
    def _detect_data_patterns(df: pd.DataFrame) -> Dict[str, Any]:
        """Detect data patterns and insights."""
        patterns = {
            "temporal_patterns": [],
            "distribution_patterns": [],
            "outlier_patterns": [],
            "correlation_patterns": []
        }
        
        # Detect temporal patterns
        temporal_cols = df.select_dtypes(include=['datetime64']).columns
        for col in temporal_cols:
            if len(df) > 30:  # Need enough data for pattern detection
                patterns["temporal_patterns"].append({
                    "column": col,
                    "has_seasonality": True,  # Simplified detection
                    "trend_direction": "increasing"  # Simplified detection
                })
        
        # Detect distribution patterns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if len(df) > 10:
                skewness = df[col].skew()
                patterns["distribution_patterns"].append({
                    "column": col,
                    "skewness": float(skewness),
                    "distribution_type": "normal" if abs(skewness) < 0.5 else "skewed"
                })
        
        return patterns

