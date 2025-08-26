from typing import Dict, List, Any, Tuple
from models import PersonaType, VisualizationRecommendation
import logging

logger = logging.getLogger(__name__)


class VisualizationRecommender:
    """Service for recommending appropriate visualizations based on data characteristics."""
    
    # Chart type suitability rules
    CHART_RULES = {
        'line_chart': {
            'requirements': ['temporal', 'numeric'],
            'min_columns': 2,
            'max_columns': 5,
            'description': 'Shows trends and patterns over time',
            'normal_persona': 'This chart shows how values change over time, making it easy to spot trends and patterns.',
            'expert_persona': 'Line chart reveals temporal patterns, seasonal variations, and trend analysis with potential for forecasting.'
        },
        'bar_chart': {
            'requirements': ['categorical', 'numeric'],
            'min_columns': 2,
            'max_columns': 3,
            'description': 'Compares categories or groups',
            'normal_persona': 'This chart makes it easy to compare different groups or categories at a glance.',
            'expert_persona': 'Bar chart enables categorical comparison with statistical significance testing and outlier identification.'
        },
        'scatter_plot': {
            'requirements': ['numeric', 'numeric'],
            'min_columns': 2,
            'max_columns': 3,
            'description': 'Shows relationship between two numeric variables',
            'normal_persona': 'This chart helps you see if there\'s a relationship between two different measurements.',
            'expert_persona': 'Scatter plot reveals correlation patterns, clustering, and potential outliers with correlation coefficient analysis.'
        },
        'histogram': {
            'requirements': ['numeric'],
            'min_columns': 1,
            'max_columns': 2,
            'description': 'Shows distribution of a single variable',
            'normal_persona': 'This chart shows how your data is spread out and where most values fall.',
            'expert_persona': 'Histogram reveals distribution shape, skewness, modality, and statistical properties of the data.'
        },
        'pie_chart': {
            'requirements': ['categorical'],
            'min_columns': 1,
            'max_columns': 2,
            'description': 'Shows proportions of a whole',
            'normal_persona': 'This chart shows how different parts make up the whole, like slices of a pie.',
            'expert_persona': 'Pie chart displays proportional composition with percentage breakdowns and category dominance analysis.'
        },
        'heatmap': {
            'requirements': ['numeric', 'numeric'],
            'min_columns': 3,
            'max_columns': 10,
            'description': 'Shows correlation matrix or 2D data',
            'normal_persona': 'This chart shows relationships between many variables using colors to represent values.',
            'expert_persona': 'Heatmap visualizes correlation matrices, revealing multicollinearity and variable relationships with statistical significance.'
        },
        'box_plot': {
            'requirements': ['categorical', 'numeric'],
            'min_columns': 2,
            'max_columns': 3,
            'description': 'Shows distribution and outliers by category',
            'normal_persona': 'This chart shows the spread of data within different groups and highlights unusual values.',
            'expert_persona': 'Box plot reveals distribution statistics, quartiles, outliers, and group comparisons with statistical testing.'
        }
    }
    
    @staticmethod
    async def recommend_visualizations(profile: Dict[str, Any], persona: PersonaType = PersonaType.NORMAL) -> List[VisualizationRecommendation]:
        """Recommend visualizations based on dataset profile."""
        try:
            recommendations = []
            columns = profile.get('columns', [])
            
            # Analyze column types
            column_types = VisualizationRecommender._analyze_column_types(columns)
            
            # Check each chart type for suitability
            for chart_type, rules in VisualizationRecommender.CHART_RULES.items():
                if VisualizationRecommender._is_chart_suitable(chart_type, rules, column_types, len(columns)):
                    recommendation = VisualizationRecommender._create_recommendation(
                        chart_type, rules, columns, column_types, persona
                    )
                    recommendations.append(recommendation)
            
            # Sort by suitability score
            recommendations.sort(key=lambda x: x.reasoning, reverse=True)
            
            return recommendations[:5]  # Return top 5 recommendations
            
        except Exception as e:
            logger.error(f"Error recommending visualizations: {e}")
            return []
    
    @staticmethod
    def _analyze_column_types(columns: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Analyze and categorize columns by type."""
        column_types = {
            'numeric': [],
            'categorical': [],
            'temporal': [],
            'text': []
        }
        
        for col in columns:
            col_name = col['name']
            if col.get('is_numeric'):
                column_types['numeric'].append(col_name)
            elif col.get('is_temporal'):
                column_types['temporal'].append(col_name)
            elif col.get('is_categorical'):
                column_types['categorical'].append(col_name)
            else:
                column_types['text'].append(col_name)
        
        return column_types
    
    @staticmethod
    def _is_chart_suitable(chart_type: str, rules: Dict[str, Any], column_types: Dict[str, List[str]], total_columns: int) -> bool:
        """Check if a chart type is suitable for the given data."""
        # Check column count requirements
        if total_columns < rules['min_columns'] or total_columns > rules['max_columns']:
            return False
        
        # Check type requirements
        required_types = rules['requirements']
        for req_type in required_types:
            if req_type == 'numeric' and not column_types['numeric']:
                return False
            elif req_type == 'categorical' and not column_types['categorical']:
                return False
            elif req_type == 'temporal' and not column_types['temporal']:
                return False
        
        return True
    
    @staticmethod
    def _create_recommendation(chart_type: str, rules: Dict[str, Any], columns: List[Dict[str, Any]], 
                             column_types: Dict[str, Any], persona: PersonaType) -> VisualizationRecommendation:
        """Create a visualization recommendation."""
        # Suggest appropriate fields based on chart type
        suggested_fields = VisualizationRecommender._suggest_fields(chart_type, column_types)
        
        # Create title
        title = f"{chart_type.replace('_', ' ').title()} of {', '.join(suggested_fields[:2])}"
        
        # Get persona-specific insights
        persona_insights = {
            PersonaType.NORMAL: rules['normal_persona'],
            PersonaType.EXPERT: rules['expert_persona']
        }
        
        # Calculate suitability score
        suitability_score = VisualizationRecommender._calculate_suitability_score(chart_type, columns, column_types)
        
        return VisualizationRecommendation(
            chart_type=chart_type,
            title=title,
            description=rules['description'],
            fields=suggested_fields,
            reasoning=f"Suitability score: {suitability_score}/100",
            persona_insights=persona_insights
        )
    
    @staticmethod
    def _suggest_fields(chart_type: str, column_types: Dict[str, List[str]]) -> List[str]:
        """Suggest appropriate fields for the chart type."""
        if chart_type == 'line_chart':
            return column_types['temporal'][:1] + column_types['numeric'][:2]
        elif chart_type == 'bar_chart':
            return column_types['categorical'][:1] + column_types['numeric'][:1]
        elif chart_type == 'scatter_plot':
            return column_types['numeric'][:2]
        elif chart_type == 'histogram':
            return column_types['numeric'][:1]
        elif chart_type == 'pie_chart':
            return column_types['categorical'][:1]
        elif chart_type == 'heatmap':
            return column_types['numeric'][:5]  # Limit to 5 for readability
        elif chart_type == 'box_plot':
            return column_types['categorical'][:1] + column_types['numeric'][:1]
        else:
            return []
    
    @staticmethod
    def _calculate_suitability_score(chart_type: str, columns: List[Dict[str, Any]], 
                                  column_types: Dict[str, List[str]]) -> int:
        """Calculate a suitability score (0-100) for the chart type."""
        score = 50  # Base score
        
        # Bonus for having ideal column counts
        ideal_columns = VisualizationRecommender.CHART_RULES[chart_type]['min_columns']
        if len(columns) == ideal_columns:
            score += 20
        
        # Bonus for data quality
        high_quality_cols = sum(1 for col in columns if col.get('null_percentage', 0) < 5)
        score += (high_quality_cols / len(columns)) * 20
        
        # Bonus for having many options of required types
        required_types = VisualizationRecommender.CHART_RULES[chart_type]['requirements']
        for req_type in required_types:
            if req_type in column_types and len(column_types[req_type]) > 1:
                score += 10
        
        return min(100, score)
    
    @staticmethod
    async def get_available_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
        """Get available fields with their types and characteristics."""
        try:
            columns = profile.get('columns', [])
            field_info = {}
            
            for col in columns:
                field_info[col['name']] = {
                    'type': col['dtype'],
                    'is_numeric': col.get('is_numeric', False),
                    'is_temporal': col.get('is_temporal', False),
                    'is_categorical': col.get('is_categorical', False),
                    'null_count': col.get('null_count', 0),
                    'unique_count': col.get('unique_count', 0),
                    'sample_values': col.get('sample_values', [])
                }
            
            return field_info
            
        except Exception as e:
            logger.error(f"Error getting available fields: {e}")
            return {}


