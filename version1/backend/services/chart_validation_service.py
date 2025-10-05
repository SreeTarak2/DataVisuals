import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ChartType(Enum):
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    BOX_PLOT = "box_plot"
    AREA_CHART = "area_chart"
    DONUT_CHART = "donut_chart"
    TREEMAP = "treemap"

class DataType(Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    BOOLEAN = "boolean"
    TEXT = "text"

class ChartValidationService:
    """Service for validating AI chart recommendations against datatype rules."""
    
    def __init__(self):
        self.chart_rules = self._initialize_chart_rules()
        self.data_type_rules = self._initialize_data_type_rules()
    
    def _initialize_chart_rules(self) -> Dict[ChartType, Dict[str, Any]]:
        """Initialize chart type validation rules."""
        return {
            ChartType.BAR_CHART: {
                "min_columns": 1,
                "max_columns": 2,
                "required_types": [DataType.CATEGORICAL],
                "optional_types": [DataType.NUMERIC],
                "max_categories": 50,
                "min_data_points": 2,
                "description": "Bar charts are best for comparing categories with numeric values"
            },
            ChartType.LINE_CHART: {
                "min_columns": 2,
                "max_columns": 3,
                "required_types": [DataType.TEMPORAL, DataType.NUMERIC],
                "optional_types": [DataType.CATEGORICAL],
                "max_data_points": 1000,
                "min_data_points": 2,
                "description": "Line charts show trends over time or continuous data"
            },
            ChartType.PIE_CHART: {
                "min_columns": 1,
                "max_columns": 2,
                "required_types": [DataType.CATEGORICAL],
                "optional_types": [DataType.NUMERIC],
                "max_categories": 10,
                "min_categories": 2,
                "min_data_points": 2,
                "description": "Pie charts show proportional distribution of categories"
            },
            ChartType.SCATTER_PLOT: {
                "min_columns": 2,
                "max_columns": 3,
                "required_types": [DataType.NUMERIC, DataType.NUMERIC],
                "optional_types": [DataType.CATEGORICAL],
                "max_data_points": 1000,
                "min_data_points": 10,
                "description": "Scatter plots show correlation between two numeric variables"
            },
            ChartType.HISTOGRAM: {
                "min_columns": 1,
                "max_columns": 1,
                "required_types": [DataType.NUMERIC],
                "optional_types": [],
                "max_data_points": 10000,
                "min_data_points": 10,
                "description": "Histograms show distribution of a single numeric variable"
            },
            ChartType.HEATMAP: {
                "min_columns": 3,
                "max_columns": 3,
                "required_types": [DataType.CATEGORICAL, DataType.CATEGORICAL, DataType.NUMERIC],
                "optional_types": [],
                "max_categories": 20,
                "min_data_points": 4,
                "description": "Heatmaps show correlation matrix or categorical cross-tabulation"
            },
            ChartType.BOX_PLOT: {
                "min_columns": 2,
                "max_columns": 2,
                "required_types": [DataType.CATEGORICAL, DataType.NUMERIC],
                "optional_types": [],
                "max_categories": 20,
                "min_data_points": 10,
                "description": "Box plots show distribution of numeric data across categories"
            },
            ChartType.AREA_CHART: {
                "min_columns": 2,
                "max_columns": 3,
                "required_types": [DataType.TEMPORAL, DataType.NUMERIC],
                "optional_types": [DataType.CATEGORICAL],
                "max_data_points": 1000,
                "min_data_points": 2,
                "description": "Area charts show cumulative values over time"
            },
            ChartType.DONUT_CHART: {
                "min_columns": 1,
                "max_columns": 2,
                "required_types": [DataType.CATEGORICAL],
                "optional_types": [DataType.NUMERIC],
                "max_categories": 10,
                "min_categories": 2,
                "min_data_points": 2,
                "description": "Donut charts are similar to pie charts but with a hollow center"
            },
            ChartType.TREEMAP: {
                "min_columns": 2,
                "max_columns": 3,
                "required_types": [DataType.CATEGORICAL, DataType.NUMERIC],
                "optional_types": [DataType.CATEGORICAL],
                "max_categories": 50,
                "min_data_points": 4,
                "description": "Treemaps show hierarchical data with proportional rectangles"
            }
        }
    
    def _initialize_data_type_rules(self) -> Dict[DataType, Dict[str, Any]]:
        """Initialize data type validation rules."""
        return {
            DataType.NUMERIC: {
                "min_values": 2,
                "max_unique_ratio": 0.95,  # Max 95% unique values
                "min_non_null_ratio": 0.1,  # Min 10% non-null values
                "description": "Numeric data suitable for mathematical operations"
            },
            DataType.CATEGORICAL: {
                "min_values": 2,
                "max_unique_ratio": 0.8,  # Max 80% unique values
                "min_non_null_ratio": 0.1,  # Min 10% non-null values
                "max_categories": 1000,
                "description": "Categorical data with limited distinct values"
            },
            DataType.TEMPORAL: {
                "min_values": 2,
                "min_non_null_ratio": 0.1,
                "description": "Date/time data suitable for temporal analysis"
            },
            DataType.BOOLEAN: {
                "min_values": 2,
                "max_unique_values": 2,
                "description": "Boolean data with true/false values"
            },
            DataType.TEXT: {
                "min_values": 1,
                "description": "Text data for labels and descriptions"
            }
        }
    
    def validate_chart_recommendation(
        self, 
        chart_type: str, 
        columns: List[str], 
        data: List[Dict], 
        dataset_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate AI chart recommendation against datatype rules.
        Returns validation result with recommendations.
        """
        try:
            # Convert chart type to enum
            try:
                chart_enum = ChartType(chart_type)
            except ValueError:
                return {
                    "valid": False,
                    "error": f"Unknown chart type: {chart_type}",
                    "recommendations": []
                }
            
            # Get chart rules
            chart_rules = self.chart_rules[chart_enum]
            
            # Analyze data types
            column_analysis = self._analyze_columns(columns, data, dataset_metadata)
            
            # Validate against rules
            validation_result = self._validate_against_rules(
                chart_enum, chart_rules, column_analysis, data
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                chart_enum, validation_result, column_analysis, data
            )
            
            return {
                "valid": validation_result["valid"],
                "chart_type": chart_type,
                "confidence_score": validation_result["confidence_score"],
                "validation_details": validation_result,
                "column_analysis": column_analysis,
                "recommendations": recommendations,
                "alternative_charts": self._suggest_alternatives(
                    chart_enum, column_analysis, data
                )
            }
            
        except Exception as e:
            logger.error(f"Error validating chart recommendation: {e}")
            return {
                "valid": False,
                "error": str(e),
                "recommendations": []
            }
    
    def _analyze_columns(
        self, 
        columns: List[str], 
        data: List[Dict], 
        dataset_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze columns to determine their data types and characteristics."""
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        column_analysis = {}
        
        for col in columns:
            if col not in df.columns:
                column_analysis[col] = {
                    "data_type": DataType.TEXT,
                    "valid": False,
                    "error": "Column not found in data"
                }
                continue
            
            series = df[col]
            analysis = self._analyze_single_column(series, col, dataset_metadata)
            column_analysis[col] = analysis
        
        return column_analysis
    
    def _analyze_single_column(
        self, 
        series: pd.Series, 
        col_name: str, 
        dataset_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze a single column to determine its data type and characteristics."""
        # Get metadata if available
        column_metadata = None
        if dataset_metadata and "column_metadata" in dataset_metadata:
            for col_info in dataset_metadata["column_metadata"]:
                if col_info["name"] == col_name:
                    column_metadata = col_info
                    break
        
        # Basic statistics
        total_values = len(series)
        non_null_values = series.count()
        unique_values = series.nunique()
        null_count = series.isnull().sum()
        
        # Determine data type
        data_type = self._determine_data_type(series, column_metadata)
        
        # Validate against data type rules
        type_rules = self.data_type_rules[data_type]
        validation = self._validate_data_type(series, data_type, type_rules)
        
        return {
            "data_type": data_type,
            "total_values": total_values,
            "non_null_values": non_null_values,
            "unique_values": unique_values,
            "null_count": null_count,
            "null_percentage": (null_count / total_values) * 100 if total_values > 0 else 0,
            "unique_percentage": (unique_values / non_null_values) * 100 if non_null_values > 0 else 0,
            "validation": validation,
            "valid": validation["valid"],
            "sample_values": series.dropna().head(5).tolist() if non_null_values > 0 else []
        }
    
    def _determine_data_type(self, series: pd.Series, column_metadata: Optional[Dict]) -> DataType:
        """Determine the data type of a column."""
        # Use metadata if available
        if column_metadata:
            if column_metadata.get("is_numeric", False):
                return DataType.NUMERIC
            elif column_metadata.get("is_temporal", False):
                return DataType.TEMPORAL
            elif column_metadata.get("is_categorical", False):
                return DataType.CATEGORICAL
            else:
                return DataType.TEXT
        
        # Fallback to pandas type detection
        if pd.api.types.is_numeric_dtype(series):
            return DataType.NUMERIC
        elif pd.api.types.is_datetime64_any_dtype(series):
            return DataType.TEMPORAL
        elif series.dtype == 'bool':
            return DataType.BOOLEAN
        elif series.dtype == 'object':
            # Check if it's categorical
            unique_ratio = series.nunique() / len(series)
            if unique_ratio < 0.8:  # Less than 80% unique values
                return DataType.CATEGORICAL
            else:
                return DataType.TEXT
        else:
            return DataType.TEXT
    
    def _validate_data_type(
        self, 
        series: pd.Series, 
        data_type: DataType, 
        type_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a column against its data type rules."""
        total_values = len(series)
        non_null_values = series.count()
        unique_values = series.nunique()
        
        validation = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check minimum values
        if total_values < type_rules.get("min_values", 1):
            validation["valid"] = False
            validation["errors"].append(f"Not enough values: {total_values} < {type_rules['min_values']}")
        
        # Check non-null ratio
        non_null_ratio = non_null_values / total_values if total_values > 0 else 0
        min_non_null_ratio = type_rules.get("min_non_null_ratio", 0)
        if non_null_ratio < min_non_null_ratio:
            validation["warnings"].append(f"Low non-null ratio: {non_null_ratio:.2%} < {min_non_null_ratio:.2%}")
        
        # Check unique ratio
        unique_ratio = unique_values / non_null_values if non_null_values > 0 else 0
        max_unique_ratio = type_rules.get("max_unique_ratio", 1.0)
        if unique_ratio > max_unique_ratio:
            validation["warnings"].append(f"High unique ratio: {unique_ratio:.2%} > {max_unique_ratio:.2%}")
        
        # Check max categories
        max_categories = type_rules.get("max_categories", float('inf'))
        if unique_values > max_categories:
            validation["warnings"].append(f"Too many categories: {unique_values} > {max_categories}")
        
        # Check max unique values for boolean
        if data_type == DataType.BOOLEAN:
            max_unique_values = type_rules.get("max_unique_values", 2)
            if unique_values > max_unique_values:
                validation["valid"] = False
                validation["errors"].append(f"Boolean data should have max {max_unique_values} unique values, got {unique_values}")
        
        return validation
    
    def _validate_against_rules(
        self, 
        chart_type: ChartType, 
        chart_rules: Dict[str, Any], 
        column_analysis: Dict[str, Any], 
        data: List[Dict]
    ) -> Dict[str, Any]:
        """Validate chart recommendation against chart rules."""
        validation = {
            "valid": True,
            "confidence_score": 0.0,
            "errors": [],
            "warnings": []
        }
        
        # Check column count
        column_count = len(column_analysis)
        min_columns = chart_rules["min_columns"]
        max_columns = chart_rules["max_columns"]
        
        if column_count < min_columns:
            validation["valid"] = False
            validation["errors"].append(f"Not enough columns: {column_count} < {min_columns}")
        elif column_count > max_columns:
            validation["warnings"].append(f"Too many columns: {column_count} > {max_columns}")
        
        # Check data types
        required_types = chart_rules["required_types"]
        optional_types = chart_rules["optional_types"]
        
        column_types = [analysis["data_type"] for analysis in column_analysis.values() if analysis["valid"]]
        
        # Check if all required types are present
        missing_required = []
        for required_type in required_types:
            if required_type not in column_types:
                missing_required.append(required_type)
        
        if missing_required:
            validation["valid"] = False
            validation["errors"].append(f"Missing required data types: {missing_required}")
        
        # Check data points
        data_count = len(data)
        min_data_points = chart_rules.get("min_data_points", 1)
        max_data_points = chart_rules.get("max_data_points", float('inf'))
        
        if data_count < min_data_points:
            validation["valid"] = False
            validation["errors"].append(f"Not enough data points: {data_count} < {min_data_points}")
        elif data_count > max_data_points:
            validation["warnings"].append(f"Too many data points: {data_count} > {max_data_points}")
        
        # Check categories for categorical charts
        if chart_type in [ChartType.BAR_CHART, ChartType.PIE_CHART, ChartType.DONUT_CHART]:
            max_categories = chart_rules.get("max_categories", 50)
            for col, analysis in column_analysis.items():
                if analysis["data_type"] == DataType.CATEGORICAL:
                    if analysis["unique_values"] > max_categories:
                        validation["warnings"].append(f"Too many categories in {col}: {analysis['unique_values']} > {max_categories}")
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(validation, column_analysis, data)
        validation["confidence_score"] = confidence_score
        
        return validation
    
    def _calculate_confidence_score(
        self, 
        validation: Dict[str, Any], 
        column_analysis: Dict[str, Any], 
        data: List[Dict]
    ) -> float:
        """Calculate confidence score for the chart recommendation."""
        base_score = 1.0
        
        # Deduct for errors
        base_score -= len(validation["errors"]) * 0.3
        
        # Deduct for warnings
        base_score -= len(validation["warnings"]) * 0.1
        
        # Bonus for good data quality
        valid_columns = [analysis for analysis in column_analysis.values() if analysis["valid"]]
        if valid_columns:
            avg_null_percentage = sum(analysis["null_percentage"] for analysis in valid_columns) / len(valid_columns)
            if avg_null_percentage < 5:
                base_score += 0.1
            elif avg_null_percentage > 20:
                base_score -= 0.1
        
        # Bonus for appropriate data size
        data_count = len(data)
        if 10 <= data_count <= 1000:
            base_score += 0.1
        elif data_count > 10000:
            base_score -= 0.1
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_recommendations(
        self, 
        chart_type: ChartType, 
        validation: Dict[str, Any], 
        column_analysis: Dict[str, Any], 
        data: List[Dict]
    ) -> List[str]:
        """Generate recommendations for improving the chart."""
        recommendations = []
        
        if not validation["valid"]:
            recommendations.extend(validation["errors"])
        
        if validation["warnings"]:
            recommendations.extend(validation["warnings"])
        
        # Data quality recommendations
        for col, analysis in column_analysis.items():
            if analysis["null_percentage"] > 10:
                recommendations.append(f"Consider handling null values in column '{col}' ({analysis['null_percentage']:.1f}% null)")
            
            if analysis["data_type"] == DataType.CATEGORICAL and analysis["unique_values"] > 50:
                recommendations.append(f"Consider grouping categories in column '{col}' (too many unique values: {analysis['unique_values']})")
        
        # Chart-specific recommendations
        if chart_type == ChartType.PIE_CHART:
            for col, analysis in column_analysis.items():
                if analysis["data_type"] == DataType.CATEGORICAL and analysis["unique_values"] > 10:
                    recommendations.append(f"Pie charts work best with fewer categories. Consider grouping '{col}' or using a bar chart instead")
        
        elif chart_type == ChartType.SCATTER_PLOT:
            numeric_cols = [col for col, analysis in column_analysis.items() if analysis["data_type"] == DataType.NUMERIC]
            if len(numeric_cols) < 2:
                recommendations.append("Scatter plots require at least two numeric columns")
        
        return recommendations
    
    def _suggest_alternatives(
        self, 
        chart_type: ChartType, 
        column_analysis: Dict[str, Any], 
        data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Suggest alternative chart types based on data characteristics."""
        alternatives = []
        
        # Get data types
        column_types = [analysis["data_type"] for analysis in column_analysis.values() if analysis["valid"]]
        data_count = len(data)
        
        # Suggest based on data types
        if DataType.CATEGORICAL in column_types and DataType.NUMERIC in column_types:
            if data_count <= 20:
                alternatives.append({
                    "chart_type": ChartType.PIE_CHART.value,
                    "confidence": 0.8,
                    "reason": "Good for small categorical data with numeric values"
                })
            else:
                alternatives.append({
                    "chart_type": ChartType.BAR_CHART.value,
                    "confidence": 0.9,
                    "reason": "Best for comparing categories with numeric values"
                })
        
        if DataType.TEMPORAL in column_types and DataType.NUMERIC in column_types:
            alternatives.append({
                "chart_type": ChartType.LINE_CHART.value,
                "confidence": 0.9,
                "reason": "Ideal for showing trends over time"
            })
        
        if len([t for t in column_types if t == DataType.NUMERIC]) >= 2:
            alternatives.append({
                "chart_type": ChartType.SCATTER_PLOT.value,
                "confidence": 0.8,
                "reason": "Good for showing correlation between numeric variables"
            })
        
        if DataType.NUMERIC in column_types and data_count > 50:
            alternatives.append({
                "chart_type": ChartType.HISTOGRAM.value,
                "confidence": 0.7,
                "reason": "Good for showing distribution of numeric data"
            })
        
        return sorted(alternatives, key=lambda x: x["confidence"], reverse=True)

