from fastapi import HTTPException
from typing import List, Dict, Any, Optional
import logging
import json
import re
import requests
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class AIVisualizationService:
    def __init__(self):
        # Ollama configuration
        self.ollama_url = "http://localhost:11434"
        self.model = "llama2"  # or whatever model you have
        
        # QUIS methodology question templates
        self.quis_question_templates = {
            'pattern_analysis': [
                "What are the main patterns in this dataset?",
                "What trends can be observed across different categories?",
                "Are there any seasonal or cyclical patterns in the data?"
            ],
            'performance_analysis': [
                "Which categories show the highest values?",
                "What are the top-performing segments?",
                "Which metrics exceed expectations?"
            ],
            'correlation_analysis': [
                "What relationships exist between variables?",
                "Which factors are most strongly correlated?",
                "Are there any unexpected correlations?"
            ],
            'quality_analysis': [
                "What data quality issues should be addressed?",
                "Are there any outliers that need attention?",
                "What missing data patterns exist?"
            ],
            'distribution_analysis': [
                "How is the data distributed across different categories?",
                "What are the most common values in each column?",
                "Are there any skewed distributions?"
            ]
        }
        
        self.chart_recommendations = {
            'bar': {
                'description': 'Bar charts are perfect for comparing values across categories',
                'best_for': ['categorical', 'nominal', 'ordinal'],
                'confidence_threshold': 0.7
            },
            'pie': {
                'description': 'Pie charts show proportions and percentages of a whole',
                'best_for': ['categorical', 'nominal'],
                'confidence_threshold': 0.6
            },
            'line': {
                'description': 'Line charts track trends and changes over time',
                'best_for': ['time_series', 'continuous'],
                'confidence_threshold': 0.8
            },
            'scatter': {
                'description': 'Scatter plots reveal correlations between two variables',
                'best_for': ['continuous', 'numeric'],
                'confidence_threshold': 0.75
            },
            'area': {
                'description': 'Area charts show cumulative data over time',
                'best_for': ['time_series', 'cumulative'],
                'confidence_threshold': 0.7
            },
            'gauge': {
                'description': 'Gauges display single values with context and targets',
                'best_for': ['kpi', 'single_value'],
                'confidence_threshold': 0.6
            }
        }

    async def recommend_fields(self, columns: List[Dict], dataset_name: str) -> Dict[str, Any]:
        """AI-powered field recommendations for visualization"""
        try:
            recommendations = []
            
            # Analyze column types and generate recommendations
            numeric_cols = [col for col in columns if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in columns if col.get('type') in ['object', 'category']]
            datetime_cols = [col for col in columns if 'date' in col.get('name', '').lower() or 'time' in col.get('name', '').lower()]
            
            # Generate recommendations based on data patterns
            if len(numeric_cols) >= 2:
                recommendations.append({
                    'chartType': 'scatter',
                    'fields': [numeric_cols[0]['name'], numeric_cols[1]['name']],
                    'confidence': 0.9,
                    'reasoning': 'Two numeric variables detected - perfect for correlation analysis',
                    'insight': f'Explore relationship between {numeric_cols[0]["name"]} and {numeric_cols[1]["name"]}',
                    'ai_analysis': self._analyze_correlation_potential(numeric_cols[0], numeric_cols[1])
                })
            
            if categorical_cols and numeric_cols:
                recommendations.append({
                    'chartType': 'bar',
                    'fields': [categorical_cols[0]['name'], numeric_cols[0]['name']],
                    'confidence': 0.85,
                    'reasoning': 'Categorical vs numeric data - ideal for comparison analysis',
                    'insight': f'Compare {numeric_cols[0]["name"]} across {categorical_cols[0]["name"]} categories',
                    'ai_analysis': self._analyze_distribution_patterns(categorical_cols[0], numeric_cols[0])
                })
            
            if categorical_cols:
                unique_count = categorical_cols[0].get('unique_count', 0)
                if 2 <= unique_count <= 10:
                    recommendations.append({
                        'chartType': 'pie',
                        'fields': [categorical_cols[0]['name']],
                        'confidence': 0.8,
                        'reasoning': f'Categorical data with {unique_count} unique values - good for proportion analysis',
                        'insight': f'Show distribution of {categorical_cols[0]["name"]} as percentages',
                        'ai_analysis': self._analyze_categorical_distribution(categorical_cols[0])
                    })
            
            if datetime_cols and numeric_cols:
                recommendations.append({
                    'chartType': 'line',
                    'fields': [datetime_cols[0]['name'], numeric_cols[0]['name']],
                    'confidence': 0.9,
                    'reasoning': 'Time series data detected - perfect for trend analysis',
                    'insight': f'Track {numeric_cols[0]["name"]} trends over {datetime_cols[0]["name"]}',
                    'ai_analysis': self._analyze_trend_potential(datetime_cols[0], numeric_cols[0])
                })
            
            # Add KPI recommendation if we have a single important numeric column
            if len(numeric_cols) == 1 and numeric_cols[0].get('name', '').lower() in ['sales', 'revenue', 'profit', 'score', 'rating']:
                recommendations.append({
                    'chartType': 'gauge',
                    'fields': [numeric_cols[0]['name']],
                    'confidence': 0.7,
                    'reasoning': 'Single important metric detected - ideal for KPI display',
                    'insight': f'Display {numeric_cols[0]["name"]} as a key performance indicator',
                    'ai_analysis': self._analyze_kpi_potential(numeric_cols[0])
                })
            
            return {
                'recommendations': recommendations,
                'dataset_analysis': {
                    'total_columns': len(columns),
                    'numeric_columns': len(numeric_cols),
                    'categorical_columns': len(categorical_cols),
                    'datetime_columns': len(datetime_cols),
                    'analysis_confidence': 0.85
                }
            }
            
        except Exception as e:
            logger.error(f"Error in field recommendations: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate field recommendations")

    async def generate_insights(self, dataset_metadata: Dict, dataset_name: str) -> Dict[str, Any]:
        """Generate AI-powered insights using QUIS methodology from research paper"""
        try:
            # Generate QUIS-style insight cards
            insight_cards = await self._generate_quis_insight_cards(dataset_metadata, dataset_name)
            
            # Generate follow-up questions
            follow_up_questions = await self._generate_follow_up_questions(insight_cards, dataset_metadata)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(insight_cards)
            
            return {
                'insight_cards': insight_cards,
                'follow_up_questions': follow_up_questions,
                'summary': {
                    'total_insights': len(insight_cards),
                    'overall_confidence': overall_confidence,
                    'generated_at': datetime.utcnow().isoformat(),
                    'methodology': 'QUIS (Question-based User Insight System)'
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating QUIS insights: {e}")
            # Fallback to rule-based insights
            return await self._generate_fallback_insights(dataset_metadata, dataset_name)

    async def process_natural_query(self, query: str, dataset_metadata: Dict, dataset_name: str) -> Dict[str, Any]:
        """Process natural language queries about the dataset"""
        try:
            query_lower = query.lower()
            
            # Pattern matching for common queries
            if any(word in query_lower for word in ['trend', 'time', 'over time', 'change']):
                return self._handle_trend_query(query, dataset_metadata)
            elif any(word in query_lower for word in ['correlation', 'relationship', 'compare', 'vs']):
                return self._handle_correlation_query(query, dataset_metadata)
            elif any(word in query_lower for word in ['distribution', 'spread', 'frequency']):
                return self._handle_distribution_query(query, dataset_metadata)
            elif any(word in query_lower for word in ['top', 'best', 'highest', 'lowest']):
                return self._handle_ranking_query(query, dataset_metadata)
            else:
                return self._handle_general_query(query, dataset_metadata)
                
        except Exception as e:
            logger.error(f"Error processing natural query: {e}")
            raise HTTPException(status_code=500, detail="Failed to process query")

    def _analyze_correlation_potential(self, col1: Dict, col2: Dict) -> str:
        """Analyze potential correlation between two numeric columns"""
        return f"Potential correlation analysis between {col1['name']} and {col2['name']}. Look for linear or non-linear relationships."

    def _analyze_distribution_patterns(self, cat_col: Dict, num_col: Dict) -> str:
        """Analyze distribution patterns for categorical vs numeric data"""
        return f"Compare {num_col['name']} distribution across {cat_col['name']} categories. Look for significant differences between groups."

    def _analyze_categorical_distribution(self, col: Dict) -> str:
        """Analyze categorical distribution patterns"""
        unique_count = col.get('unique_count', 0)
        if unique_count <= 5:
            return f"Perfect for pie chart - {col['name']} has {unique_count} categories with clear proportions."
        else:
            return f"Consider bar chart instead - {col['name']} has {unique_count} categories (too many for pie chart)."

    def _analyze_trend_potential(self, time_col: Dict, value_col: Dict) -> str:
        """Analyze trend analysis potential"""
        return f"Time series analysis of {value_col['name']} over {time_col['name']}. Look for seasonal patterns, trends, and anomalies."

    def _analyze_kpi_potential(self, col: Dict) -> str:
        """Analyze KPI potential for a single metric"""
        return f"Key Performance Indicator: {col['name']} - perfect for dashboard display with targets and benchmarks."

    def _handle_trend_query(self, query: str, metadata: Dict) -> Dict[str, Any]:
        """Handle trend-related queries"""
        return {
            'response': 'I can help you analyze trends in your data. Based on your dataset, I recommend using line charts to track changes over time. Would you like me to create a trend visualization?',
            'suggested_chart': 'line',
            'confidence': 0.8,
            'follow_up_questions': [
                'What time period are you interested in?',
                'Which metric should we track over time?',
                'Do you want to see seasonal patterns?'
            ]
        }

    def _handle_correlation_query(self, query: str, metadata: Dict) -> Dict[str, Any]:
        """Handle correlation-related queries"""
        return {
            'response': 'I can help you find correlations in your data. Scatter plots are perfect for discovering relationships between variables. Let me analyze your numeric columns for potential correlations.',
            'suggested_chart': 'scatter',
            'confidence': 0.85,
            'follow_up_questions': [
                'Which two variables are you most interested in?',
                'Are you looking for positive or negative correlations?',
                'Do you want to see correlation strength?'
            ]
        }

    def _handle_distribution_query(self, query: str, metadata: Dict) -> Dict[str, Any]:
        """Handle distribution-related queries"""
        return {
            'response': 'I can help you understand data distributions. Bar charts show frequency distributions, while histograms reveal data spread. What type of distribution are you looking for?',
            'suggested_chart': 'bar',
            'confidence': 0.8,
            'follow_up_questions': [
                'Which variable should we analyze?',
                'Do you want to see frequency or percentage distributions?',
                'Are you interested in normal distribution patterns?'
            ]
        }

    def _handle_ranking_query(self, query: str, metadata: Dict) -> Dict[str, Any]:
        """Handle ranking and comparison queries"""
        return {
            'response': 'I can help you find top performers and rankings in your data. Bar charts are excellent for comparing values and identifying leaders. What would you like to rank?',
            'suggested_chart': 'bar',
            'confidence': 0.9,
            'follow_up_questions': [
                'What metric should we use for ranking?',
                'How many top items do you want to see?',
                'Do you want ascending or descending order?'
            ]
        }

    def _handle_general_query(self, query: str, metadata: Dict) -> Dict[str, Any]:
        """Handle general queries"""
        return {
            'response': f'I understand you want to explore your dataset. Based on your data structure, I can help you create visualizations that reveal insights. What specific aspect of your data interests you most?',
            'suggested_chart': 'bar',
            'confidence': 0.6,
            'follow_up_questions': [
                'What questions do you want to answer?',
                'Which variables are most important to you?',
                'What type of insights are you looking for?'
            ]
        }

    async def generate_chart(self, dataset: Dict, columns: List, data_sample: List) -> Dict[str, Any]:
        """Generate AI-powered chart from dataset"""
        try:
            # Analyze data structure to determine best chart type
            chart_type = self._analyze_best_chart_type(dataset, columns, data_sample)
            
            # Generate chart configuration
            chart_config = self._generate_chart_config(dataset, columns, data_sample, chart_type)
            
            # Create chart data
            chart_data = self._create_chart_data(dataset, columns, data_sample, chart_type)
            
            return {
                'chart_type': chart_type,
                'chart_config': chart_config,
                'chart_data': chart_data,
                'title': f"{dataset.get('name', 'Dataset')} Analysis",
                'description': f"AI-generated {chart_type} visualization",
                'confidence': 0.85
            }
            
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate chart")

    def _analyze_best_chart_type(self, dataset: Dict, columns: List, data_sample: List) -> str:
        """Analyze data to determine the best chart type"""
        try:
            # Get column metadata
            column_metadata = dataset.get('metadata', {}).get('column_metadata', [])
            
            # Count numeric and categorical columns
            numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
            
            # Determine best chart type based on data characteristics
            if len(numeric_cols) >= 2:
                return 'scatter'  # Scatter plot for correlation analysis
            elif len(numeric_cols) == 1 and len(categorical_cols) >= 1:
                return 'bar'  # Bar chart for categorical vs numeric
            elif len(categorical_cols) >= 1:
                # Check if categorical has few unique values
                if categorical_cols[0].get('unique_count', 0) <= 10:
                    return 'pie'  # Pie chart for small categorical data
                else:
                    return 'bar'  # Bar chart for larger categorical data
            else:
                return 'bar'  # Default to bar chart
                
        except Exception as e:
            logger.error(f"Error analyzing chart type: {e}")
            return 'bar'  # Default fallback

    def _generate_chart_config(self, dataset: Dict, columns: List, data_sample: List, chart_type: str) -> Dict[str, Any]:
        """Generate chart configuration based on type"""
        base_config = {
            'responsive': True,
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
        }
        
        if chart_type == 'scatter':
            base_config.update({
                'title': f"{dataset.get('name', 'Dataset')} - Correlation Analysis",
                'xaxis': {'title': 'X Axis'},
                'yaxis': {'title': 'Y Axis'}
            })
        elif chart_type == 'bar':
            base_config.update({
                'title': f"{dataset.get('name', 'Dataset')} - Distribution Analysis",
                'xaxis': {'title': 'Categories'},
                'yaxis': {'title': 'Values'}
            })
        elif chart_type == 'pie':
            base_config.update({
                'title': f"{dataset.get('name', 'Dataset')} - Proportion Analysis"
            })
            
        return base_config

    def _create_chart_data(self, dataset: Dict, columns: List, data_sample: List, chart_type: str) -> List[Dict[str, Any]]:
        """Create chart data based on type and sample data"""
        try:
            if not data_sample or len(data_sample) == 0:
                # Return empty chart if no data
                return [{
                    'x': [],
                    'y': [],
                    'type': chart_type,
                    'name': 'No Data'
                }]
            
            # Get column metadata
            column_metadata = dataset.get('metadata', {}).get('column_metadata', [])
            numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
            
            if chart_type == 'scatter' and len(numeric_cols) >= 2:
                # Create scatter plot data
                x_col = numeric_cols[0]['name']
                y_col = numeric_cols[1]['name']
                
                x_data = [row.get(x_col, 0) for row in data_sample if x_col in row]
                y_data = [row.get(y_col, 0) for row in data_sample if y_col in row]
                
                return [{
                    'x': x_data,
                    'y': y_data,
                    'type': 'scatter',
                    'mode': 'markers',
                    'name': f'{x_col} vs {y_col}',
                    'marker': {'color': '#3B82F6', 'size': 8}
                }]
                
            elif chart_type == 'bar' and len(categorical_cols) >= 1:
                # Create bar chart data
                cat_col = categorical_cols[0]['name']
                
                # Count occurrences of each category
                category_counts = {}
                for row in data_sample:
                    if cat_col in row:
                        value = row[cat_col]
                        category_counts[value] = category_counts.get(value, 0) + 1
                
                categories = list(category_counts.keys())
                counts = list(category_counts.values())
                
                return [{
                    'x': categories,
                    'y': counts,
                    'type': 'bar',
                    'name': cat_col,
                    'marker': {'color': '#3B82F6'}
                }]
                
            elif chart_type == 'pie' and len(categorical_cols) >= 1:
                # Create pie chart data
                cat_col = categorical_cols[0]['name']
                
                # Count occurrences of each category
                category_counts = {}
                for row in data_sample:
                    if cat_col in row:
                        value = row[cat_col]
                        category_counts[value] = category_counts.get(value, 0) + 1
                
                labels = list(category_counts.keys())
                values = list(category_counts.values())
                
                return [{
                    'labels': labels,
                    'values': values,
                    'type': 'pie',
                    'name': cat_col,
                    'marker': {'colors': ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']}
                }]
            
            else:
                # Default fallback - simple bar chart
                return [{
                    'x': ['Sample 1', 'Sample 2', 'Sample 3'],
                    'y': [10, 20, 15],
                    'type': 'bar',
                    'name': 'Sample Data',
                    'marker': {'color': '#3B82F6'}
                }]
                
        except Exception as e:
            logger.error(f"Error creating chart data: {e}")
            # Return empty chart on error
            return [{
                'x': [],
                'y': [],
                'type': chart_type,
                'name': 'Error'
            }]

    async def _generate_quis_insight_cards(self, dataset_metadata: Dict, dataset_name: str) -> List[Dict[str, Any]]:
        """Generate QUIS-style insight cards using research paper methodology"""
        try:
            insight_cards = []
            
            # Get dataset information
            overview = dataset_metadata.get('dataset_overview', {})
            column_metadata = dataset_metadata.get('column_metadata', [])
            data_quality = dataset_metadata.get('data_quality', {})
            
            total_rows = overview.get('total_rows', 0)
            total_columns = overview.get('total_columns', 0)
            numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
            datetime_cols = [col for col in column_metadata if 'date' in col.get('name', '').lower() or 'time' in col.get('name', '').lower()]
            
            # Generate questions for each analysis type
            analysis_types = ['pattern_analysis', 'performance_analysis', 'correlation_analysis', 'quality_analysis', 'distribution_analysis']
            
            for analysis_type in analysis_types:
                questions = self.quis_question_templates.get(analysis_type, [])
                
                for question in questions:
                    # Generate AI-powered answer using LLM
                    answer = await self._generate_llm_answer(question, dataset_metadata, dataset_name)
                    
                    # Calculate confidence based on data characteristics
                    confidence = self._calculate_question_confidence(question, analysis_type, dataset_metadata)
                    
                    # Determine breakdown and measure
                    breakdown, measure = self._determine_breakdown_measure(analysis_type, column_metadata)
                    
                    insight_card = {
                        'question': question,
                        'answer': answer,
                        'reason': self._get_question_reasoning(analysis_type, question),
                        'breakdown': breakdown,
                        'measure': measure,
                        'confidence': confidence,
                        'analysis_type': analysis_type,
                        'actionable_insights': self._generate_actionable_insights(analysis_type, answer, dataset_metadata)
                    }
                    
                    insight_cards.append(insight_card)
            
            # Sort by confidence and return top insights
            insight_cards.sort(key=lambda x: x['confidence'], reverse=True)
            return insight_cards[:8]  # Return top 8 insights
            
        except Exception as e:
            logger.error(f"Error generating QUIS insight cards: {e}")
            return []

    async def _generate_follow_up_questions(self, insight_cards: List[Dict], dataset_metadata: Dict) -> List[Dict[str, Any]]:
        """Generate follow-up questions based on initial insights"""
        try:
            follow_up_questions = []
            
            # Generate follow-up questions for high-confidence insights
            high_confidence_insights = [card for card in insight_cards if card['confidence'] > 0.8]
            
            for insight in high_confidence_insights[:3]:  # Top 3 insights
                follow_up = await self._generate_llm_follow_up(insight, dataset_metadata)
                if follow_up:
                    follow_up_questions.append(follow_up)
            
            return follow_up_questions
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {e}")
            return []

    def _calculate_overall_confidence(self, insight_cards: List[Dict]) -> float:
        """Calculate overall confidence score for all insights"""
        if not insight_cards:
            return 0.0
        
        # Weighted average of individual confidences
        total_confidence = sum(card['confidence'] for card in insight_cards)
        return round(total_confidence / len(insight_cards), 3)

    def _calculate_question_confidence(self, question: str, analysis_type: str, dataset_metadata: Dict) -> float:
        """Calculate confidence score for a specific question based on data characteristics"""
        try:
            base_confidence = 0.5
            
            # Data quality factor
            data_quality = dataset_metadata.get('data_quality', {})
            completeness = data_quality.get('completeness', 100)
            quality_factor = completeness / 100
            
            # Data size factor
            overview = dataset_metadata.get('dataset_overview', {})
            total_rows = overview.get('total_rows', 0)
            size_factor = min(1.0, total_rows / 1000)  # More data = higher confidence
            
            # Column type factor
            column_metadata = dataset_metadata.get('column_metadata', [])
            numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
            
            type_factor = 0.5
            if analysis_type == 'correlation_analysis' and len(numeric_cols) >= 2:
                type_factor = 0.9
            elif analysis_type == 'distribution_analysis' and len(categorical_cols) >= 1:
                type_factor = 0.8
            elif analysis_type == 'pattern_analysis' and len(numeric_cols) >= 1:
                type_factor = 0.7
            elif analysis_type == 'quality_analysis':
                type_factor = 0.9  # Always relevant
            elif analysis_type == 'performance_analysis' and len(numeric_cols) >= 1:
                type_factor = 0.8
            
            # Calculate final confidence
            confidence = base_confidence + (quality_factor * 0.3) + (size_factor * 0.2) + (type_factor * 0.3)
            
            return min(0.95, max(0.1, confidence))  # Clamp between 0.1 and 0.95
            
        except Exception as e:
            logger.error(f"Error calculating question confidence: {e}")
            return 0.5

    def _determine_breakdown_measure(self, analysis_type: str, column_metadata: List[Dict]) -> tuple:
        """Determine appropriate breakdown and measure for analysis type"""
        categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
        numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
        
        if analysis_type == 'pattern_analysis':
            return 'category', 'count'
        elif analysis_type == 'performance_analysis':
            return 'category', 'sum'
        elif analysis_type == 'correlation_analysis':
            return 'numeric', 'correlation'
        elif analysis_type == 'quality_analysis':
            return 'column', 'percentage'
        elif analysis_type == 'distribution_analysis':
            return 'category', 'count'
        else:
            return 'category', 'count'

    def _get_question_reasoning(self, analysis_type: str, question: str) -> str:
        """Get reasoning for why this question is relevant"""
        reasoning_map = {
            'pattern_analysis': 'This question helps identify overall trends and distributions in the data',
            'performance_analysis': 'This question reveals the top-performing categories or segments',
            'correlation_analysis': 'This question uncovers relationships between different variables',
            'quality_analysis': 'This question identifies data quality issues that need attention',
            'distribution_analysis': 'This question shows how data is spread across different categories'
        }
        return reasoning_map.get(analysis_type, 'This question provides valuable insights about your data')

    def _generate_actionable_insights(self, analysis_type: str, answer: str, dataset_metadata: Dict) -> List[str]:
        """Generate actionable insights based on the analysis type and answer"""
        actions = []
        
        if analysis_type == 'pattern_analysis':
            actions.extend([
                'Create trend visualizations to explore patterns further',
                'Apply time series analysis if temporal data exists',
                'Look for seasonal or cyclical patterns'
            ])
        elif analysis_type == 'performance_analysis':
            actions.extend([
                'Focus on top-performing segments for business strategy',
                'Investigate factors driving high performance',
                'Create performance dashboards for monitoring'
            ])
        elif analysis_type == 'correlation_analysis':
            actions.extend([
                'Create scatter plots to visualize correlations',
                'Investigate causal relationships between variables',
                'Use correlation insights for predictive modeling'
            ])
        elif analysis_type == 'quality_analysis':
            actions.extend([
                'Clean missing data before further analysis',
                'Investigate outliers and their impact',
                'Implement data quality monitoring'
            ])
        elif analysis_type == 'distribution_analysis':
            actions.extend([
                'Create distribution charts (histograms, box plots)',
                'Identify skewed distributions and their implications',
                'Consider data transformation if needed'
            ])
        
        return actions[:3]  # Return top 3 actions

    async def _generate_llm_answer(self, question: str, dataset_metadata: Dict, dataset_name: str) -> str:
        """Generate AI-powered answer using LLM (Ollama or fallback)"""
        try:
            # Try Ollama first
            answer = await self._call_ollama_for_insight(question, dataset_metadata, dataset_name)
            if answer:
                return answer
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
        
        # Fallback to rule-based answer
        return self._generate_rule_based_answer(question, dataset_metadata)

    async def _call_ollama_for_insight(self, question: str, dataset_metadata: Dict, dataset_name: str) -> str:
        """Call Ollama to generate insight answer"""
        try:
            # Create context for the question
            context = self._create_insight_context(dataset_metadata, dataset_name)
            
            prompt = f"""
            You are DataSage AI, an expert data analyst. Answer this question about the dataset:
            
            Question: {question}
            
            Dataset Context:
            {context}
            
            Provide a clear, actionable answer in 2-3 sentences. Focus on insights that would be valuable for data analysis.
            """
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 200
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                raise Exception(f"Ollama API returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise e

    def _create_insight_context(self, dataset_metadata: Dict, dataset_name: str) -> str:
        """Create context for LLM insight generation"""
        overview = dataset_metadata.get('dataset_overview', {})
        column_metadata = dataset_metadata.get('column_metadata', [])
        data_quality = dataset_metadata.get('data_quality', {})
        
        context = f"""
        Dataset: {dataset_name}
        Rows: {overview.get('total_rows', 0):,}
        Columns: {overview.get('total_columns', 0)}
        Data Quality: {data_quality.get('completeness', 100):.1f}% complete
        
        Column Types:
        """
        
        for col in column_metadata[:5]:  # First 5 columns
            context += f"- {col.get('name', 'Unknown')}: {col.get('type', 'unknown')} ({col.get('unique_count', 0)} unique values)\n"
        
        return context

    def _generate_rule_based_answer(self, question: str, dataset_metadata: Dict) -> str:
        """Generate rule-based answer when LLM is not available"""
        question_lower = question.lower()
        
        # Get dataset information
        overview = dataset_metadata.get('dataset_overview', {})
        column_metadata = dataset_metadata.get('column_metadata', [])
        data_quality = dataset_metadata.get('data_quality', {})
        
        total_rows = overview.get('total_rows', 0)
        total_columns = overview.get('total_columns', 0)
        numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
        categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
        missing_percentage = data_quality.get('completeness', 100)
        
        if 'pattern' in question_lower:
            if numeric_cols:
                return f"Your dataset with {total_rows:,} rows shows patterns across {len(numeric_cols)} numeric columns. Look for trends in {', '.join([col['name'] for col in numeric_cols[:3]])} to identify key patterns."
            else:
                return f"Pattern analysis reveals insights across {len(categorical_cols)} categorical columns. Examine frequency distributions to find recurring patterns."
        
        elif 'highest' in question_lower or 'top' in question_lower:
            if numeric_cols:
                return f"Top performers can be identified by analyzing {numeric_cols[0]['name']} and other numeric columns. The dataset contains {total_rows:,} records to rank and compare."
            else:
                return f"Top categories can be found by examining the frequency distribution of {categorical_cols[0]['name'] if categorical_cols else 'categorical columns'}."
        
        elif 'relationship' in question_lower or 'correlation' in question_lower:
            if len(numeric_cols) >= 2:
                return f"Correlation analysis between {numeric_cols[0]['name']} and {numeric_cols[1]['name']} can reveal strong relationships. With {total_rows:,} data points, statistical significance is likely."
            else:
                return f"Relationship analysis works best with numeric data. Your dataset has {len(numeric_cols)} numeric columns available for correlation analysis."
        
        elif 'quality' in question_lower or 'missing' in question_lower:
            if missing_percentage < 95:
                return f"Data quality shows {100-missing_percentage:.1f}% missing values across {total_columns} columns. Focus on columns with the highest missing rates first."
            else:
                return f"Excellent data quality with {missing_percentage:.1f}% completeness across {total_rows:,} rows and {total_columns} columns. Ready for analysis."
        
        elif 'distribution' in question_lower:
            if numeric_cols:
                return f"Distribution analysis of {numeric_cols[0]['name']} shows the spread of values across {total_rows:,} records. Check for normal distribution or skewness."
            elif categorical_cols:
                return f"Distribution of {categorical_cols[0]['name']} reveals the frequency of different categories. Look for dominant categories or balanced distributions."
            else:
                return f"Distribution analysis across {total_columns} columns will show how data is spread. Use histograms for numeric data and bar charts for categories."
        
        else:
            return f"This dataset with {total_rows:,} rows and {total_columns} columns contains valuable insights. Focus on {len(numeric_cols)} numeric and {len(categorical_cols)} categorical columns for comprehensive analysis."

    async def _generate_llm_follow_up(self, insight: Dict, dataset_metadata: Dict) -> Dict[str, Any]:
        """Generate follow-up question using LLM"""
        try:
            prompt = f"""
            Based on this insight: "{insight['answer']}"
            
            Generate a follow-up question that would help the user dive deeper into this analysis.
            Return only the question, no additional text.
            """
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "max_tokens": 100
                    }
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                follow_up_question = result.get("response", "").strip()
                
                return {
                    'question': follow_up_question,
                    'parent_insight': insight['question'],
                    'confidence': 0.7,
                    'reasoning': 'Generated to explore the topic further'
                }
            
        except Exception as e:
            logger.error(f"Error generating follow-up question: {e}")
        
        return None

    async def _generate_fallback_insights(self, dataset_metadata: Dict, dataset_name: str) -> Dict[str, Any]:
        """Generate fallback insights when QUIS methodology fails"""
        try:
            insights = []
            overview = dataset_metadata.get('dataset_overview', {})
            column_metadata = dataset_metadata.get('column_metadata', [])
            data_quality = dataset_metadata.get('data_quality', {})
            
            total_rows = overview.get('total_rows', 0)
            total_columns = overview.get('total_columns', 0)
            numeric_cols = [col for col in column_metadata if col.get('type') in ['int64', 'float64']]
            categorical_cols = [col for col in column_metadata if col.get('type') in ['object', 'category']]
            missing_percentage = data_quality.get('completeness', 100)
            
            # Dataset structure insight
            insights.append({
                'question': 'What is the overall structure of this dataset?',
                'answer': f'This dataset contains {total_rows:,} rows and {total_columns} columns, providing a solid foundation for analysis.',
                'reason': 'Understanding dataset structure is essential for effective analysis',
                'breakdown': 'dataset',
                'measure': 'count',
                'confidence': 0.8,
                'analysis_type': 'pattern_analysis',
                'actionable_insights': ['Explore data types and distributions', 'Check for missing values', 'Identify key variables']
            })
            
            # Data quality insight
            if missing_percentage < 95:
                insights.append({
                    'question': 'What data quality issues should be addressed?',
                    'answer': f'Data quality shows {100-missing_percentage:.1f}% missing values across {total_columns} columns. Focus on columns with the highest missing rates first.',
                    'reason': 'Data quality assessment is crucial for reliable analysis',
                    'breakdown': 'data_quality',
                    'measure': 'completeness',
                    'confidence': 0.9,
                    'analysis_type': 'quality_analysis',
                    'actionable_insights': ['Identify columns with most missing data', 'Consider imputation strategies', 'Document data limitations']
                })
            else:
                insights.append({
                    'question': 'What is the data quality status?',
                    'answer': f'Excellent data quality with {missing_percentage:.1f}% completeness across {total_rows:,} rows and {total_columns} columns. Ready for analysis.',
                    'reason': 'High data quality enables confident analysis',
                    'breakdown': 'data_quality',
                    'measure': 'completeness',
                    'confidence': 0.9,
                    'analysis_type': 'quality_analysis',
                    'actionable_insights': ['Proceed with analysis confidently', 'Focus on insights rather than data cleaning', 'Document the high quality']
                })
            
            # Column type analysis
            if numeric_cols and categorical_cols:
                insights.append({
                    'question': 'What types of analysis are possible with this data?',
                    'answer': f'Mixed data types enable comprehensive analysis: {len(numeric_cols)} numeric columns for statistical analysis and {len(categorical_cols)} categorical columns for grouping and segmentation.',
                    'reason': 'Understanding data types guides analysis approach',
                    'breakdown': 'column_types',
                    'measure': 'count',
                    'confidence': 0.8,
                    'analysis_type': 'distribution_analysis',
                    'actionable_insights': ['Use numeric columns for correlations and trends', 'Use categorical columns for grouping', 'Combine both for advanced analytics']
                })
            elif numeric_cols:
                insights.append({
                    'question': 'What statistical analysis opportunities exist?',
                    'answer': f'With {len(numeric_cols)} numeric columns, you can perform correlation analysis, trend analysis, and statistical modeling.',
                    'reason': 'Numeric data enables statistical analysis',
                    'breakdown': 'numeric_analysis',
                    'measure': 'count',
                    'confidence': 0.8,
                    'analysis_type': 'correlation_analysis',
                    'actionable_insights': ['Calculate correlations between variables', 'Identify trends and patterns', 'Build predictive models']
                })
            elif categorical_cols:
                insights.append({
                    'question': 'What categorical analysis is possible?',
                    'answer': f'With {len(categorical_cols)} categorical columns, you can analyze frequency distributions, segment data, and identify dominant categories.',
                    'reason': 'Categorical data enables segmentation analysis',
                    'breakdown': 'categorical_analysis',
                    'measure': 'count',
                    'confidence': 0.8,
                    'analysis_type': 'distribution_analysis',
                    'actionable_insights': ['Analyze frequency distributions', 'Identify top categories', 'Segment data for deeper insights']
                })
            
            return {
                'insight_cards': insights,
                'follow_up_questions': [],
                'summary': {
                    'total_insights': len(insights),
                    'overall_confidence': 0.8,
                    'generated_at': datetime.utcnow().isoformat(),
                    'methodology': 'Rule-based Fallback'
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating fallback insights: {e}")
            return {
                'insight_cards': [],
                'follow_up_questions': [],
                'summary': {
                    'total_insights': 0,
                    'overall_confidence': 0.0,
                    'generated_at': datetime.utcnow().isoformat(),
                    'methodology': 'Error - No insights generated'
                }
            }

# Create service instance
ai_visualization_service = AIVisualizationService()

