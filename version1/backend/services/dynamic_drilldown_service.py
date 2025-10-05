import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

class DynamicDrillDownService:
    """
    Universal drill-down service that works with ANY dataset.
    Automatically detects hierarchies and creates drill-down paths.
    """
    
    def __init__(self):
        self.hierarchy_patterns = {
            'temporal': {
                'keywords': ['date', 'time', 'year', 'month', 'day', 'hour', 'timestamp', 'created', 'updated'],
                'patterns': [r'\d{4}-\d{2}-\d{2}', r'\d{2}/\d{2}/\d{4}', r'\d{4}'],
                'levels': ['year', 'quarter', 'month', 'day', 'hour']
            },
            'geographic': {
                'keywords': ['country', 'state', 'region', 'city', 'area', 'zone', 'location', 'address', 'place'],
                'patterns': [],
                'levels': ['country', 'state', 'city', 'area']
            },
            'categorical': {
                'keywords': ['category', 'type', 'class', 'group', 'segment', 'division', 'department', 'team'],
                'patterns': [],
                'levels': ['category', 'subcategory', 'item']
            },
            'hierarchical': {
                'keywords': ['level', 'tier', 'rank', 'grade', 'status', 'priority', 'order'],
                'patterns': [],
                'levels': ['level1', 'level2', 'level3']
            }
        }
    
    async def analyze_dataset_for_drilldown(self, dataset_data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze any dataset to detect potential drill-down hierarchies.
        Works with any data structure and column names.
        """
        if not dataset_data:
            return {"hierarchies": [], "drillable_columns": [], "analysis": "no_data"}
        
        df = pd.DataFrame(dataset_data)
        analysis_result = {
            "dataset_info": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns)
            },
            "hierarchies": [],
            "drillable_columns": [],
            "aggregation_opportunities": [],
            "chart_recommendations": []
        }
        
        # 1. Detect temporal hierarchies
        temporal_hierarchies = await self._detect_temporal_hierarchies(df)
        analysis_result["hierarchies"].extend(temporal_hierarchies)
        
        # 2. Detect geographic hierarchies
        geographic_hierarchies = await self._detect_geographic_hierarchies(df)
        analysis_result["hierarchies"].extend(geographic_hierarchies)
        
        # 3. Detect categorical hierarchies
        categorical_hierarchies = await self._detect_categorical_hierarchies(df)
        analysis_result["hierarchies"].extend(categorical_hierarchies)
        
        # 4. Detect custom hierarchies based on data patterns
        custom_hierarchies = await self._detect_custom_hierarchies(df)
        analysis_result["hierarchies"].extend(custom_hierarchies)
        
        # 5. Identify drillable columns
        drillable_columns = await self._identify_drillable_columns(df)
        analysis_result["drillable_columns"] = drillable_columns
        
        # 6. Find aggregation opportunities
        aggregation_ops = await self._find_aggregation_opportunities(df)
        analysis_result["aggregation_opportunities"] = aggregation_ops
        
        # 7. Generate chart recommendations
        chart_recs = await self._generate_chart_recommendations(df)
        analysis_result["chart_recommendations"] = chart_recs
        
        return analysis_result
    
    async def _detect_temporal_hierarchies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect temporal hierarchies in any dataset."""
        hierarchies = []
        
        for col in df.columns:
            if self._is_temporal_column(df[col], col):
                hierarchy = {
                    "type": "temporal",
                    "field": col,
                    "name": f"{col.title()} Time Series",
                    "levels": await self._create_temporal_levels(df[col]),
                    "confidence": 0.9,
                    "drillable": True
                }
                hierarchies.append(hierarchy)
        
        return hierarchies
    
    async def _detect_geographic_hierarchies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect geographic hierarchies in any dataset."""
        hierarchies = []
        
        # Find columns that might be geographic
        geo_columns = []
        for col in df.columns:
            if self._is_geographic_column(col, df[col]):
                geo_columns.append(col)
        
        # Create geographic hierarchy
        if geo_columns:
            hierarchy = {
                "type": "geographic",
                "field": geo_columns[0],  # Primary geographic field
                "name": f"{geo_columns[0].title()} Geography",
                "levels": await self._create_geographic_levels(geo_columns),
                "confidence": 0.8,
                "drillable": True,
                "all_geo_columns": geo_columns
            }
            hierarchies.append(hierarchy)
        
        return hierarchies
    
    async def _detect_categorical_hierarchies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect categorical hierarchies in any dataset."""
        hierarchies = []
        
        # Find categorical columns
        categorical_cols = []
        for col in df.columns:
            if self._is_categorical_column(df[col]):
                categorical_cols.append(col)
        
        # Group related categorical columns
        grouped_cats = await self._group_related_categorical_columns(df, categorical_cols)
        
        for group in grouped_cats:
            if len(group) >= 2:  # Need at least 2 levels for hierarchy
                hierarchy = {
                    "type": "categorical",
                    "field": group[0],  # Primary field
                    "name": f"{group[0].title()} Categories",
                    "levels": await self._create_categorical_levels(group),
                    "confidence": 0.7,
                    "drillable": True,
                    "all_categorical_columns": group
                }
                hierarchies.append(hierarchy)
        
        return hierarchies
    
    async def _detect_custom_hierarchies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect custom hierarchies based on data patterns."""
        hierarchies = []
        
        # Look for columns that might have hierarchical relationships
        for col in df.columns:
            if self._has_hierarchical_pattern(df[col], col):
                hierarchy = {
                    "type": "custom",
                    "field": col,
                    "name": f"{col.title()} Hierarchy",
                    "levels": await self._create_custom_levels(df[col]),
                    "confidence": 0.6,
                    "drillable": True
                }
                hierarchies.append(hierarchy)
        
        return hierarchies
    
    def _is_temporal_column(self, series: pd.Series, col_name: str) -> bool:
        """Check if a column contains temporal data."""
        # Check pandas datetime type
        if pd.api.types.is_datetime64_any_dtype(series):
            return True
        
        # Check column name patterns
        col_lower = col_name.lower()
        temporal_keywords = self.hierarchy_patterns['temporal']['keywords']
        if any(keyword in col_lower for keyword in temporal_keywords):
            return True
        
        # Check data patterns
        if series.dtype == 'object':
            sample_values = series.dropna().head(10)
            for value in sample_values:
                if isinstance(value, str):
                    # Check for date patterns
                    for pattern in self.hierarchy_patterns['temporal']['patterns']:
                        if re.search(pattern, str(value)):
                            return True
        
        return False
    
    def _is_geographic_column(self, col_name: str, series: pd.Series) -> bool:
        """Check if a column contains geographic data."""
        col_lower = col_name.lower()
        geo_keywords = self.hierarchy_patterns['geographic']['keywords']
        
        # Check column name
        if any(keyword in col_lower for keyword in geo_keywords):
            return True
        
        # Check if it's categorical with geographic-like values
        if series.dtype == 'object' and series.nunique() < len(series) * 0.8:
            sample_values = series.dropna().head(20)
            geo_indicators = ['north', 'south', 'east', 'west', 'central', 'region', 'area', 'zone']
            geo_count = sum(1 for val in sample_values if any(indicator in str(val).lower() for indicator in geo_indicators))
            if geo_count > len(sample_values) * 0.3:  # 30% of values look geographic
                return True
        
        return False
    
    def _is_categorical_column(self, series: pd.Series) -> bool:
        """Check if a column is categorical."""
        if series.dtype == 'object':
            unique_ratio = series.nunique() / len(series)
            return unique_ratio < 0.8  # Less than 80% unique values
        return False
    
    def _has_hierarchical_pattern(self, series: pd.Series, col_name: str) -> bool:
        """Check if a column has hierarchical patterns."""
        if series.dtype == 'object':
            # Look for hierarchical patterns like "Level1-Level2-Level3"
            sample_values = series.dropna().head(20)
            hierarchical_count = 0
            for value in sample_values:
                if isinstance(value, str):
                    # Check for common hierarchical separators
                    if any(sep in value for sep in ['-', '_', '.', '/', '|']):
                        hierarchical_count += 1
            
            return hierarchical_count > len(sample_values) * 0.5  # 50% have hierarchical patterns
        
        return False
    
    async def _create_temporal_levels(self, series: pd.Series) -> List[Dict[str, Any]]:
        """Create temporal drill-down levels."""
        levels = []
        
        # Convert to datetime if possible
        try:
            if not pd.api.types.is_datetime64_any_dtype(series):
                series = pd.to_datetime(series, errors='coerce')
            
            if series.notna().any():
                # Year level
                levels.append({
                    "level": 1,
                    "name": "Year",
                    "field": f"{series.name}_year",
                    "parent": None,
                    "aggregation": "year",
                    "description": "Group by year"
                })
                
                # Quarter level
                levels.append({
                    "level": 2,
                    "name": "Quarter",
                    "field": f"{series.name}_quarter",
                    "parent": f"{series.name}_year",
                    "aggregation": "quarter",
                    "description": "Group by quarter within year"
                })
                
                # Month level
                levels.append({
                    "level": 3,
                    "name": "Month",
                    "field": f"{series.name}_month",
                    "parent": f"{series.name}_quarter",
                    "aggregation": "month",
                    "description": "Group by month within quarter"
                })
                
                # Day level
                levels.append({
                    "level": 4,
                    "name": "Day",
                    "field": series.name,
                    "parent": f"{series.name}_month",
                    "aggregation": "day",
                    "description": "Group by day within month"
                })
        
        except Exception as e:
            logger.warning(f"Could not create temporal levels for {series.name}: {e}")
        
        return levels
    
    async def _create_geographic_levels(self, geo_columns: List[str]) -> List[Dict[str, Any]]:
        """Create geographic drill-down levels."""
        levels = []
        
        for i, col in enumerate(geo_columns):
            level = {
                "level": i + 1,
                "name": col.title(),
                "field": col,
                "parent": geo_columns[i-1] if i > 0 else None,
                "aggregation": "group",
                "description": f"Group by {col}"
            }
            levels.append(level)
        
        return levels
    
    async def _create_categorical_levels(self, categorical_columns: List[str]) -> List[Dict[str, Any]]:
        """Create categorical drill-down levels."""
        levels = []
        
        for i, col in enumerate(categorical_columns):
            level = {
                "level": i + 1,
                "name": col.title(),
                "field": col,
                "parent": categorical_columns[i-1] if i > 0 else None,
                "aggregation": "group",
                "description": f"Group by {col}"
            }
            levels.append(level)
        
        return levels
    
    async def _create_custom_levels(self, series: pd.Series) -> List[Dict[str, Any]]:
        """Create custom drill-down levels based on data patterns."""
        levels = []
        
        # Analyze the data to determine levels
        if series.dtype == 'object':
            sample_values = series.dropna().head(100)
            # Look for common separators to determine hierarchy depth
            separators = ['-', '_', '.', '/', '|']
            max_depth = 1
            
            for value in sample_values:
                if isinstance(value, str):
                    depth = sum(1 for sep in separators if sep in value)
                    max_depth = max(max_depth, depth + 1)
            
            # Create levels based on detected depth
            for i in range(max_depth):
                level = {
                    "level": i + 1,
                    "name": f"Level {i + 1}",
                    "field": f"{series.name}_level_{i + 1}",
                    "parent": f"{series.name}_level_{i}" if i > 0 else None,
                    "aggregation": "group",
                    "description": f"Group by level {i + 1}"
                }
                levels.append(level)
        
        return levels
    
    async def _group_related_categorical_columns(self, df: pd.DataFrame, categorical_cols: List[str]) -> List[List[str]]:
        """Group related categorical columns that might form hierarchies."""
        groups = []
        used_cols = set()
        
        for col in categorical_cols:
            if col in used_cols:
                continue
            
            group = [col]
            used_cols.add(col)
            
            # Find related columns
            for other_col in categorical_cols:
                if other_col in used_cols:
                    continue
                
                # Check if columns are related (similar values, correlation, etc.)
                if self._are_columns_related(df[col], df[other_col]):
                    group.append(other_col)
                    used_cols.add(other_col)
            
            if len(group) > 1:  # Only include groups with multiple columns
                groups.append(group)
        
        return groups
    
    def _are_columns_related(self, col1: pd.Series, col2: pd.Series) -> bool:
        """Check if two columns are related (might form a hierarchy)."""
        # Check for similar naming patterns
        name1, name2 = col1.name.lower(), col2.name.lower()
        if any(word in name1 for word in ['category', 'type', 'class']) and any(word in name2 for word in ['sub', 'detail', 'item']):
            return True
        
        # Check for value overlap
        if col1.dtype == 'object' and col2.dtype == 'object':
            values1 = set(col1.dropna().unique())
            values2 = set(col2.dropna().unique())
            overlap = len(values1.intersection(values2))
            if overlap > 0 and overlap / min(len(values1), len(values2)) > 0.1:  # 10% overlap
                return True
        
        return False
    
    async def _identify_drillable_columns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify columns that can be used for drill-down operations."""
        drillable = []
        
        for col in df.columns:
            series = df[col]
            drillability_score = 0
            reasons = []
            
            # Check if it's categorical (good for drill-down)
            if series.dtype == 'object' and series.nunique() < len(series) * 0.8:
                drillability_score += 0.4
                reasons.append("categorical_data")
            
            # Check if it's temporal (excellent for drill-down)
            if self._is_temporal_column(series, col):
                drillability_score += 0.5
                reasons.append("temporal_data")
            
            # Check if it's geographic (good for drill-down)
            if self._is_geographic_column(col, series):
                drillability_score += 0.4
                reasons.append("geographic_data")
            
            # Check cardinality (not too high, not too low)
            unique_ratio = series.nunique() / len(series)
            if 0.01 < unique_ratio < 0.5:  # 1% to 50% unique values
                drillability_score += 0.3
                reasons.append("good_cardinality")
            
            # Check data quality
            null_ratio = series.isnull().sum() / len(series)
            if null_ratio < 0.2:  # Less than 20% null values
                drillability_score += 0.2
                reasons.append("good_data_quality")
            
            if drillability_score > 0.3:  # Threshold for drillability
                drillable.append({
                    "column": col,
                    "score": drillability_score,
                    "reasons": reasons,
                    "data_type": str(series.dtype),
                    "unique_values": series.nunique(),
                    "null_percentage": (series.isnull().sum() / len(series)) * 100
                })
        
        return sorted(drillable, key=lambda x: x["score"], reverse=True)
    
    async def _find_aggregation_opportunities(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Find opportunities for data aggregation."""
        opportunities = []
        
        # Find numeric columns for aggregation
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        # Group by categorical columns, aggregate numeric columns
        for cat_col in categorical_cols:
            if df[cat_col].nunique() < 50:  # Not too many categories
                for num_col in numeric_cols:
                    opportunities.append({
                        "type": "group_aggregation",
                        "group_by": cat_col,
                        "aggregate": num_col,
                        "operations": ["sum", "mean", "count", "max", "min"],
                        "description": f"Group by {cat_col}, aggregate {num_col}"
                    })
        
        # Time-based aggregation
        temporal_cols = [col for col in df.columns if self._is_temporal_column(df[col], col)]
        for temp_col in temporal_cols:
            for num_col in numeric_cols:
                opportunities.append({
                    "type": "temporal_aggregation",
                    "time_field": temp_col,
                    "aggregate": num_col,
                    "operations": ["sum", "mean", "count"],
                    "time_periods": ["year", "quarter", "month", "day"],
                    "description": f"Time series aggregation of {num_col} by {temp_col}"
                })
        
        return opportunities
    
    async def _generate_chart_recommendations(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate chart recommendations based on data analysis."""
        recommendations = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
        temporal_cols = [col for col in df.columns if self._is_temporal_column(df[col], col)]
        
        # Bar charts for categorical + numeric
        if categorical_cols and numeric_cols:
            cat_col = categorical_cols[0]
            num_col = numeric_cols[0]
            if df[cat_col].nunique() <= 20:  # Not too many categories
                recommendations.append({
                    "chart_type": "bar_chart",
                    "title": f"{num_col} by {cat_col}",
                    "x_axis": cat_col,
                    "y_axis": num_col,
                    "confidence": 0.9,
                    "description": f"Bar chart showing {num_col} grouped by {cat_col}"
                })
        
        # Line charts for temporal data
        if temporal_cols and numeric_cols:
            temp_col = temporal_cols[0]
            num_col = numeric_cols[0]
            recommendations.append({
                "chart_type": "line_chart",
                "title": f"{num_col} over time",
                "x_axis": temp_col,
                "y_axis": num_col,
                "confidence": 0.9,
                "description": f"Line chart showing {num_col} trend over {temp_col}"
            })
        
        # Pie charts for categorical distribution
        if categorical_cols:
            cat_col = categorical_cols[0]
            if df[cat_col].nunique() <= 10:  # Good for pie chart
                recommendations.append({
                    "chart_type": "pie_chart",
                    "title": f"Distribution of {cat_col}",
                    "category_field": cat_col,
                    "confidence": 0.8,
                    "description": f"Pie chart showing distribution of {cat_col}"
                })
        
        # Scatter plots for numeric correlations
        if len(numeric_cols) >= 2:
            recommendations.append({
                "chart_type": "scatter_plot",
                "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
                "x_axis": numeric_cols[0],
                "y_axis": numeric_cols[1],
                "confidence": 0.7,
                "description": f"Scatter plot showing correlation between {numeric_cols[0]} and {numeric_cols[1]}"
            })
        
        return sorted(recommendations, key=lambda x: x["confidence"], reverse=True)
    
    async def execute_drilldown(
        self, 
        dataset_data: List[Dict], 
        hierarchy: Dict[str, Any], 
        current_level: int, 
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute drill-down operation for any dataset and hierarchy.
        """
        if not dataset_data:
            return {"error": "No data available"}
        
        df = pd.DataFrame(dataset_data)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if field in df.columns:
                    df = df[df[field] == value]
        
        # Get current level info
        levels = hierarchy.get("levels", [])
        if current_level > len(levels):
            return {"error": "Invalid drill-down level"}
        
        current_level_info = levels[current_level - 1]
        field = current_level_info["field"]
        aggregation = current_level_info.get("aggregation", "group")
        
        # Execute aggregation based on type
        if aggregation == "group":
            result = await self._execute_group_aggregation(df, field, hierarchy)
        elif aggregation in ["year", "quarter", "month", "day"]:
            result = await self._execute_temporal_aggregation(df, field, aggregation, hierarchy)
        else:
            result = await self._execute_custom_aggregation(df, field, hierarchy)
        
        return {
            "data": result["data"],
            "level": current_level,
            "field": field,
            "aggregation_type": aggregation,
            "total_records": result["total_records"],
            "hierarchy_info": hierarchy,
            "can_drill_down": current_level < len(levels),
            "can_drill_up": current_level > 1
        }
    
    async def _execute_group_aggregation(self, df: pd.DataFrame, field: str, hierarchy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute group-based aggregation."""
        if field not in df.columns:
            return {"data": [], "total_records": 0}
        
        # Find numeric columns for aggregation
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if numeric_cols:
            # Group by field and aggregate numeric columns
            result = df.groupby(field)[numeric_cols].agg(['sum', 'mean', 'count']).reset_index()
            result.columns = [field] + [f"{col}_{agg}" for col in numeric_cols for agg in ['sum', 'mean', 'count']]
        else:
            # Just count records
            result = df.groupby(field).size().reset_index(name='count')
        
        # Sort by first numeric column or count
        sort_col = result.columns[1] if len(result.columns) > 1 else result.columns[0]
        result = result.sort_values(by=sort_col, ascending=False)
        
        return {
            "data": result.to_dict('records'),
            "total_records": len(result)
        }
    
    async def _execute_temporal_aggregation(self, df: pd.DataFrame, field: str, aggregation: str, hierarchy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute temporal aggregation."""
        if field not in df.columns:
            return {"data": [], "total_records": 0}
        
        # Convert to datetime if needed
        try:
            if not pd.api.types.is_datetime64_any_dtype(df[field]):
                df[field] = pd.to_datetime(df[field], errors='coerce')
        except:
            return {"data": [], "total_records": 0}
        
        # Create time period column
        if aggregation == "year":
            df['time_period'] = df[field].dt.year
        elif aggregation == "quarter":
            df['time_period'] = df[field].dt.to_period('Q')
        elif aggregation == "month":
            df['time_period'] = df[field].dt.to_period('M')
        elif aggregation == "day":
            df['time_period'] = df[field].dt.date
        
        # Find numeric columns for aggregation
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [col for col in numeric_cols if col != 'time_period']
        
        if numeric_cols:
            result = df.groupby('time_period')[numeric_cols].sum().reset_index()
        else:
            result = df.groupby('time_period').size().reset_index(name='count')
        
        # Convert time period to string
        result['time_period'] = result['time_period'].astype(str)
        
        return {
            "data": result.to_dict('records'),
            "total_records": len(result)
        }
    
    async def _execute_custom_aggregation(self, df: pd.DataFrame, field: str, hierarchy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom aggregation based on data patterns."""
        if field not in df.columns:
            return {"data": [], "total_records": 0}
        
        # For custom aggregations, use group by
        return await self._execute_group_aggregation(df, field, hierarchy)

