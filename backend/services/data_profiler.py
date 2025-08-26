import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataProfiler:
    """Service for profiling and analyzing datasets."""
    
    @staticmethod
    async def profile_dataset(file_path: str) -> Dict[str, Any]:
        """Profile a dataset and return comprehensive analysis."""
        try:
            # Read dataset
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValueError("Unsupported file format")
            
            # Basic info
            profile = {
                'row_count': len(df),
                'column_count': len(df.columns),
                'memory_usage': df.memory_usage(deep=True).sum(),
                'columns': [],
                'summary_stats': {},
                'data_quality': {}
            }
            
            # Column analysis
            for col in df.columns:
                col_info = DataProfiler._analyze_column(df[col], col)
                profile['columns'].append(col_info)
            
            # Overall statistics
            profile['summary_stats'] = DataProfiler._generate_summary_stats(df)
            profile['data_quality'] = DataProfiler._assess_data_quality(df)
            
            return profile
            
        except Exception as e:
            logger.error(f"Error profiling dataset: {e}")
            raise e
    
    @staticmethod
    def _analyze_column(series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Analyze individual column characteristics."""
        col_info = {
            'name': col_name,
            'dtype': str(series.dtype),
            'null_count': series.isnull().sum(),
            'null_percentage': (series.isnull().sum() / len(series)) * 100,
            'unique_count': series.nunique(),
            'unique_percentage': (series.nunique() / len(series)) * 100,
            'sample_values': series.dropna().head(5).tolist()
        }
        
        # Type classification
        col_info['is_numeric'] = pd.api.types.is_numeric_dtype(series)
        col_info['is_temporal'] = pd.api.types.is_datetime64_any_dtype(series)
        col_info['is_categorical'] = series.dtype == 'object' and series.nunique() < len(series) * 0.5
        
        # Numeric statistics
        if col_info['is_numeric']:
            col_info.update({
                'min': float(series.min()) if not pd.isna(series.min()) else None,
                'max': float(series.max()) if not pd.isna(series.max()) else None,
                'mean': float(series.mean()) if not pd.isna(series.mean()) else None,
                'median': float(series.median()) if not pd.isna(series.median()) else None,
                'std': float(series.std()) if not pd.isna(series.std()) else None
            })
        
        # Temporal statistics
        if col_info['is_temporal']:
            col_info.update({
                'min_date': series.min().isoformat() if not pd.isna(series.min()) else None,
                'max_date': series.max().isoformat() if not pd.isna(series.max()) else None,
                'date_range_days': (series.max() - series.min()).days if not pd.isna(series.min()) and not pd.isna(series.max()) else None
            })
        
        return col_info
    
    @staticmethod
    def _generate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """Generate overall dataset statistics."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object']).columns
        temporal_cols = df.select_dtypes(include=['datetime64']).columns
        
        summary = {
            'total_cells': df.size,
            'missing_cells': df.isnull().sum().sum(),
            'missing_percentage': (df.isnull().sum().sum() / df.size) * 100,
            'numeric_columns': len(numeric_cols),
            'categorical_columns': len(categorical_cols),
            'temporal_columns': len(temporal_cols),
            'duplicate_rows': df.duplicated().sum(),
            'duplicate_percentage': (df.duplicated().sum() / len(df)) * 100
        }
        
        # Correlation matrix for numeric columns
        if len(numeric_cols) > 1:
            try:
                corr_matrix = df[numeric_cols].corr()
                # Get top correlations
                correlations = []
                for i in range(len(corr_matrix.columns)):
                    for j in range(i+1, len(corr_matrix.columns)):
                        corr_value = corr_matrix.iloc[i, j]
                        if abs(corr_value) > 0.5:  # Strong correlation threshold
                            correlations.append({
                                'column1': corr_matrix.columns[i],
                                'column2': corr_matrix.columns[j],
                                'correlation': float(corr_value)
                            })
                
                summary['strong_correlations'] = sorted(correlations, key=lambda x: abs(x['correlation']), reverse=True)[:5]
            except Exception as e:
                logger.warning(f"Could not compute correlations: {e}")
                summary['strong_correlations'] = []
        
        return summary
    
    @staticmethod
    def _assess_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
        """Assess overall data quality."""
        quality_score = 100
        
        # Deduct points for various quality issues
        null_percentage = (df.isnull().sum().sum() / df.size) * 100
        quality_score -= null_percentage * 0.5  # Each 1% missing data = -0.5 points
    
        duplicate_percentage = (df.duplicated().sum() / len(df)) * 100
        quality_score -= duplicate_percentage * 0.3  # Each 1% duplicates = -0.3 points
        
        # Ensure score doesn't go below 0
        quality_score = max(0, quality_score)
        
        return {
            'overall_score': round(quality_score, 2),
            'missing_data_impact': round(null_percentage * 0.5, 2),
            'duplicate_impact': round(duplicate_percentage * 0.3, 2),
            'quality_level': 'Excellent' if quality_score >= 90 else 'Good' if quality_score >= 70 else 'Fair' if quality_score >= 50 else 'Poor'
        }


