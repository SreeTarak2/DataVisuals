from typing import Dict, List, Any, Optional, Tuple
import logging
import pandas as pd
import numpy as np
from services.llm_service import LLMService
from models import LLMRequest
import json
import re

logger = logging.getLogger(__name__)


class ChatService:
    """AI-powered chat service for natural language data queries."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
    
    async def process_chat_message(self, message: str, dataset_id: str, dataset_data: List[Dict]) -> Dict[str, Any]:
        """Process a chat message and generate appropriate response with visualization."""
        try:
            # Analyze the user's intent
            intent = await self._analyze_user_intent(message, dataset_id, dataset_data)
            
            if intent['type'] == 'data_query':
                return await self._handle_data_query(message, dataset_id, dataset_data, intent)
            elif intent['type'] == 'general_question':
                return await self._handle_general_question(message, dataset_id, dataset_data)
            else:
                return await self._handle_unknown_query(message, dataset_id, dataset_data)
                
        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            return {
                "type": "error",
                "message": "I'm sorry, I encountered an error processing your question. Please try rephrasing it.",
                "visualization": None
            }
    
    async def _analyze_user_intent(self, message: str, dataset_id: str, dataset_data: List[Dict]) -> Dict[str, Any]:
        """Analyze user intent using LLM."""
        try:
            df = pd.DataFrame(dataset_data)
            columns = list(df.columns)
            sample_data = df.head(3).to_dict('records')
            
            prompt = f"""
            Analyze this user query about a dataset and determine the intent:
            
            User Query: "{message}"
            
            Dataset Columns: {columns}
            Sample Data: {sample_data}
            
            Determine if this is:
            1. A data query (asking for specific data, charts, analysis)
            2. A general question (asking about the dataset, help, etc.)
            3. Unknown/unclear
            
            Respond with JSON:
            {{
                "type": "data_query|general_question|unknown",
                "confidence": 0.0-1.0,
                "extracted_columns": ["column1", "column2"],
                "query_type": "correlation|distribution|comparison|trend|summary",
                "chart_suggestion": "bar_chart|line_chart|scatter_plot|pie_chart|histogram"
            }}
            """
            
            response = await self.llm_service.answer_query(LLMRequest(
                dataset_id=dataset_id,
                query=prompt
            ))
            
            # Parse LLM response
            try:
                intent = json.loads(response.response)
                return intent
            except:
                # Fallback parsing
                return self._fallback_intent_analysis(message, columns)
                
        except Exception as e:
            logger.error(f"Error analyzing user intent: {e}")
            return self._fallback_intent_analysis(message, list(pd.DataFrame(dataset_data).columns))
    
    def _fallback_intent_analysis(self, message: str, columns: List[str]) -> Dict[str, Any]:
        """Fallback intent analysis using simple pattern matching."""
        message_lower = message.lower()
        
        # Check for data query keywords
        data_keywords = ['show', 'plot', 'chart', 'graph', 'compare', 'correlation', 'distribution', 'trend', 'average', 'sum', 'count']
        if any(keyword in message_lower for keyword in data_keywords):
            # Determine specific query type
            if 'correlation' in message_lower:
                query_type = 'correlation'
                chart_suggestion = 'scatter_plot'
            elif 'distribution' in message_lower:
                query_type = 'distribution'
                chart_suggestion = 'histogram'
            elif 'trend' in message_lower:
                query_type = 'trend'
                chart_suggestion = 'line_chart'
            elif 'compare' in message_lower:
                query_type = 'comparison'
                chart_suggestion = 'bar_chart'
            else:
                query_type = 'analysis'
                chart_suggestion = 'bar_chart'
            
            return {
                "type": "data_query",
                "confidence": 0.7,
                "extracted_columns": self._extract_columns_from_message(message, columns),
                "query_type": query_type,
                "chart_suggestion": chart_suggestion
            }
        
        return {
            "type": "general_question",
            "confidence": 0.5,
            "extracted_columns": [],
            "query_type": "general",
            "chart_suggestion": None
        }
    
    def _extract_columns_from_message(self, message: str, available_columns: List[str]) -> List[str]:
        """Extract column names mentioned in the user message."""
        message_lower = message.lower()
        extracted = []
        
        for column in available_columns:
            if column.lower() in message_lower:
                extracted.append(column)
        
        return extracted
    
    async def _handle_data_query(self, message: str, dataset_id: str, dataset_data: List[Dict], intent: Dict) -> Dict[str, Any]:
        """Handle data-specific queries and generate visualizations."""
        try:
            df = pd.DataFrame(dataset_data)
            
            # Generate analysis based on intent
            analysis_result = await self._perform_data_analysis(df, intent, message)
            
            # Generate visualization
            visualization = await self._generate_visualization(df, intent, analysis_result)
            
            # Generate natural language response
            response_message = await self._generate_response_message(message, analysis_result, intent)
            
            return {
                "type": "data_query",
                "message": response_message,
                "visualization": visualization,
                "analysis": analysis_result,
                "intent": intent
            }
            
        except Exception as e:
            logger.error(f"Error handling data query: {e}")
            return {
                "type": "error",
                "message": "I had trouble analyzing your data. Could you please rephrase your question?",
                "visualization": None
            }
    
    async def _perform_data_analysis(self, df: pd.DataFrame, intent: Dict, message: str) -> Dict[str, Any]:
        """Perform the actual data analysis based on user intent."""
        try:
            columns = intent.get('extracted_columns', [])
            query_type = intent.get('query_type', 'analysis')
            
            if not columns:
                # If no columns extracted, try to infer from message
                columns = self._infer_columns_from_analysis(df, message)
            
            if len(columns) == 0:
                return {"error": "No relevant columns found for analysis"}
            
            analysis = {}
            
            if query_type == 'correlation' and len(columns) >= 2:
                # Calculate correlation
                numeric_cols = [col for col in columns if pd.api.types.is_numeric_dtype(df[col])]
                if len(numeric_cols) >= 2:
                    corr = df[numeric_cols[0]].corr(df[numeric_cols[1]])
                    analysis['correlation'] = float(corr)
                    analysis['columns'] = numeric_cols[:2]
            
            elif query_type == 'distribution':
                # Calculate distribution
                col = columns[0]
                if pd.api.types.is_numeric_dtype(df[col]):
                    analysis['distribution'] = {
                        'mean': float(df[col].mean()),
                        'median': float(df[col].median()),
                        'std': float(df[col].std()),
                        'min': float(df[col].min()),
                        'max': float(df[col].max())
                    }
                else:
                    analysis['distribution'] = df[col].value_counts().to_dict()
                analysis['column'] = col
            
            elif query_type == 'comparison':
                # Compare categories
                if len(columns) >= 2:
                    breakdown_col = columns[0]
                    measure_col = columns[1] if pd.api.types.is_numeric_dtype(df[columns[1]]) else columns[0]
                    
                    if pd.api.types.is_numeric_dtype(df[measure_col]):
                        comparison = df.groupby(breakdown_col)[measure_col].agg(['mean', 'count']).to_dict()
                        analysis['comparison'] = comparison
                        analysis['columns'] = [breakdown_col, measure_col]
            
            else:
                # General analysis
                analysis['summary'] = {
                    'total_rows': len(df),
                    'columns_analyzed': columns,
                    'data_types': {col: str(df[col].dtype) for col in columns}
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error performing data analysis: {e}")
            return {"error": str(e)}
    
    def _infer_columns_from_analysis(self, df: pd.DataFrame, message: str) -> List[str]:
        """Infer relevant columns from the analysis message."""
        message_lower = message.lower()
        columns = list(df.columns)
        
        # Simple keyword matching
        inferred = []
        for col in columns:
            if col.lower() in message_lower:
                inferred.append(col)
        
        # If no direct matches, return first few columns
        if not inferred:
            return columns[:3]
        
        return inferred
    
    async def _generate_visualization(self, df: pd.DataFrame, intent: Dict, analysis: Dict) -> Optional[Dict[str, Any]]:
        """Generate visualization data based on analysis."""
        try:
            chart_type = intent.get('chart_suggestion', 'bar_chart')
            columns = intent.get('extracted_columns', [])
            
            if not columns or 'error' in analysis:
                return None
            
            # Generate chart data based on chart type
            if chart_type == 'bar_chart':
                return self._generate_bar_chart_data(df, columns, analysis)
            elif chart_type == 'scatter_plot':
                return self._generate_scatter_plot_data(df, columns, analysis)
            elif chart_type == 'pie_chart':
                return self._generate_pie_chart_data(df, columns, analysis)
            elif chart_type == 'line_chart':
                return self._generate_line_chart_data(df, columns, analysis)
            else:
                return self._generate_bar_chart_data(df, columns, analysis)
                
        except Exception as e:
            logger.error(f"Error generating visualization: {e}")
            return None
    
    def _generate_bar_chart_data(self, df: pd.DataFrame, columns: List[str], analysis: Dict) -> Dict[str, Any]:
        """Generate bar chart data."""
        if len(columns) == 0:
            return None
        
        col = columns[0]
        if pd.api.types.is_numeric_dtype(df[col]):
            # For numeric columns, create histogram-like data
            value_counts = df[col].value_counts().head(10)
            return {
                "type": "bar",
                "data": {
                    "labels": [str(x) for x in value_counts.index],
                    "datasets": [{
                        "label": f"Count of {col}",
                        "data": value_counts.tolist(),
                        "backgroundColor": "rgba(54, 162, 235, 0.6)"
                    }]
                }
            }
        else:
            # For categorical columns
            value_counts = df[col].value_counts().head(10)
            return {
                "type": "bar",
                "data": {
                    "labels": value_counts.index.tolist(),
                    "datasets": [{
                        "label": f"Count of {col}",
                        "data": value_counts.tolist(),
                        "backgroundColor": "rgba(54, 162, 235, 0.6)"
                    }]
                }
            }
    
    def _generate_scatter_plot_data(self, df: pd.DataFrame, columns: List[str], analysis: Dict) -> Dict[str, Any]:
        """Generate scatter plot data."""
        if len(columns) < 2:
            return None
        
        x_col, y_col = columns[0], columns[1]
        if not (pd.api.types.is_numeric_dtype(df[x_col]) and pd.api.types.is_numeric_dtype(df[y_col])):
            return None
        
        return {
            "type": "scatter",
            "data": {
                "datasets": [{
                    "label": f"{x_col} vs {y_col}",
                    "data": df[[x_col, y_col]].dropna().values.tolist(),
                    "backgroundColor": "rgba(54, 162, 235, 0.6)"
                }]
            }
        }
    
    def _generate_pie_chart_data(self, df: pd.DataFrame, columns: List[str], analysis: Dict) -> Dict[str, Any]:
        """Generate pie chart data."""
        if len(columns) == 0:
            return None
        
        col = columns[0]
        value_counts = df[col].value_counts().head(8)
        
        return {
            "type": "pie",
            "data": {
                "labels": value_counts.index.tolist(),
                "datasets": [{
                    "data": value_counts.tolist(),
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.6)",
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 205, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)",
                        "rgba(153, 102, 255, 0.6)",
                        "rgba(255, 159, 64, 0.6)",
                        "rgba(199, 199, 199, 0.6)",
                        "rgba(83, 102, 255, 0.6)"
                    ]
                }]
            }
        }
    
    def _generate_line_chart_data(self, df: pd.DataFrame, columns: List[str], analysis: Dict) -> Dict[str, Any]:
        """Generate line chart data."""
        if len(columns) < 2:
            return None
        
        x_col, y_col = columns[0], columns[1]
        if not pd.api.types.is_numeric_dtype(df[y_col]):
            return None
        
        # Sort by x column if it's numeric
        if pd.api.types.is_numeric_dtype(df[x_col]):
            sorted_df = df.sort_values(x_col)
            x_data = sorted_df[x_col].tolist()
            y_data = sorted_df[y_col].tolist()
        else:
            x_data = df[x_col].tolist()
            y_data = df[y_col].tolist()
        
        return {
            "type": "line",
            "data": {
                "labels": [str(x) for x in x_data],
                "datasets": [{
                    "label": y_col,
                    "data": y_data,
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "backgroundColor": "rgba(54, 162, 235, 0.1)",
                    "fill": True
                }]
            }
        }
    
    async def _generate_response_message(self, original_message: str, analysis: Dict, intent: Dict) -> str:
        """Generate a natural language response to the user's query."""
        try:
            if 'error' in analysis:
                return f"I couldn't analyze your data for '{original_message}'. {analysis['error']}"
            
            # Generate response based on analysis type
            if 'correlation' in analysis:
                corr = analysis['correlation']
                cols = analysis['columns']
                strength = "strong" if abs(corr) > 0.7 else "moderate" if abs(corr) > 0.3 else "weak"
                direction = "positive" if corr > 0 else "negative"
                return f"The correlation between {cols[0]} and {cols[1]} is {strength} and {direction} (r={corr:.3f})."
            
            elif 'distribution' in analysis:
                col = analysis['column']
                dist = analysis['distribution']
                if isinstance(dist, dict) and 'mean' in dist:
                    return f"For {col}: mean={dist['mean']:.2f}, median={dist['median']:.2f}, std={dist['std']:.2f}"
                else:
                    return f"Distribution of {col}: {list(dist.keys())[:5]}..."
            
            elif 'comparison' in analysis:
                return f"I've analyzed the comparison between the selected columns. Here are the results:"
            
            else:
                return f"I've analyzed your data. Here's what I found:"
                
        except Exception as e:
            logger.error(f"Error generating response message: {e}")
            return f"I analyzed your query '{original_message}' and generated a visualization."
    
    async def _handle_general_question(self, message: str, dataset_id: str, dataset_data: List[Dict]) -> Dict[str, Any]:
        """Handle general questions about the dataset."""
        try:
            df = pd.DataFrame(dataset_data)
            
            # Analyze the dataset for relationships
            analysis_info = self._analyze_dataset_relationships(df)
            
            # Generate a comprehensive response about the dataset
            response = await self.llm_service.answer_query(LLMRequest(
                dataset_id=dataset_id,
                query=f"User asked: '{message}'. Dataset analysis: {analysis_info}. Provide a detailed response about the relationships found in the data."
            ))
            
            return {
                "response": response.response,
                "confidence": 0.9,
                "reasoning": f"Based on the dataset analysis, I found {len(analysis_info.get('correlations', {}))} correlations and {len(analysis_info.get('insights', []))} key insights. The analysis covers {analysis_info.get('total_rows', 0)} rows and {analysis_info.get('total_columns', 0)} columns.",
                "analysis": analysis_info
            }
            
        except Exception as e:
            logger.error(f"Error handling general question: {e}")
            return {
                "response": "I'm here to help you explore your data! You can ask me about specific columns, correlations, distributions, or any other data analysis questions.",
                "confidence": 0.5,
                "reasoning": "I encountered an error while analyzing your question, so I'm providing a general response to help you get started.",
                "analysis": None
            }
    
    def _analyze_dataset_relationships(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze relationships between columns in the dataset."""
        try:
            relationships = {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "column_names": list(df.columns),
                "correlations": {},
                "categorical_columns": [],
                "numeric_columns": [],
                "insights": []
            }
            
            # Identify column types
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    relationships["numeric_columns"].append(col)
                else:
                    relationships["categorical_columns"].append(col)
            
            # Calculate correlations between numeric columns
            numeric_cols = relationships["numeric_columns"]
            if len(numeric_cols) >= 2:
                corr_matrix = df[numeric_cols].corr()
                for i, col1 in enumerate(numeric_cols):
                    for j, col2 in enumerate(numeric_cols):
                        if i < j:  # Only upper triangle
                            corr = corr_matrix.loc[col1, col2]
                            if abs(corr) > 0.3:  # Only significant correlations
                                relationships["correlations"][f"{col1} vs {col2}"] = float(corr)
            
            # Generate insights
            if relationships["correlations"]:
                strongest_corr = max(relationships["correlations"].items(), key=lambda x: abs(x[1]))
                relationships["insights"].append(f"Strongest correlation: {strongest_corr[0]} (r={strongest_corr[1]:.3f})")
            
            if relationships["categorical_columns"]:
                cat_col = relationships["categorical_columns"][0]
                value_counts = df[cat_col].value_counts()
                top_category = value_counts.index[0]
                relationships["insights"].append(f"Most common category in {cat_col}: {top_category} ({value_counts.iloc[0]} occurrences)")
            
            if relationships["numeric_columns"]:
                num_col = relationships["numeric_columns"][0]
                mean_val = df[num_col].mean()
                relationships["insights"].append(f"Average {num_col}: {mean_val:.2f}")
            
            return relationships
            
        except Exception as e:
            logger.error(f"Error analyzing dataset relationships: {e}")
            return {"error": str(e)}
    
    async def _handle_unknown_query(self, message: str, dataset_id: str, dataset_data: List[Dict]) -> Dict[str, Any]:
        """Handle unclear or unknown queries."""
        return {
            "type": "unknown",
            "message": "I'm not sure I understand your question. Could you try asking about specific columns in your data, or ask for help with data analysis?",
            "visualization": None
        }
