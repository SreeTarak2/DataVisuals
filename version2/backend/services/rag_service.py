import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)

class RAGService:
    """Retrieval-Augmented Generation service for fetching relevant data slices."""
    
    def __init__(self):
        self.query_patterns = {
            "temporal": r"(time|date|year|month|day|trend|over time|historical)",
            "geographic": r"(region|country|state|city|location|geographic|map)",
            "categorical": r"(category|type|group|class|segment|breakdown)",
            "numeric": r"(sum|total|average|mean|count|maximum|minimum|statistics)",
            "comparison": r"(compare|versus|vs|difference|between)",
            "distribution": r"(distribution|spread|range|percentile|quartile)"
        }
    
    async def retrieve_relevant_slices(
        self, 
        query: str, 
        dataset_metadata: Dict[str, Any], 
        dataset_data: List[Dict],
        max_slices: int = 5
    ) -> Dict[str, Any]:
        """
        Use RAG to retrieve only relevant data slices based on query.
        Never returns full dataset - only relevant portions.
        """
        try:
            # 1. Analyze query intent
            query_intent = self._analyze_query_intent(query)
            
            # 2. Identify relevant columns
            relevant_columns = self._identify_relevant_columns(query_intent, dataset_metadata)
            
            # 3. Generate data slices based on query
            data_slices = await self._generate_data_slices(
                query_intent, 
                relevant_columns, 
                dataset_data, 
                max_slices
            )
            
            # 4. Create context for LLM
            context = self._create_llm_context(query_intent, data_slices, dataset_metadata)
            
            return {
                "query_intent": query_intent,
                "relevant_columns": relevant_columns,
                "data_slices": data_slices,
                "context": context,
                "slice_count": len(data_slices),
                "rag_ready": True
            }
            
        except Exception as e:
            logger.error(f"Error in RAG retrieval: {e}")
            return {"error": str(e), "rag_ready": False}
    
    def _analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query to understand intent and requirements."""
        query_lower = query.lower()
        
        intent = {
            "query_type": "unknown",
            "temporal_focus": False,
            "geographic_focus": False,
            "categorical_focus": False,
            "numeric_focus": False,
            "comparison_focus": False,
            "distribution_focus": False,
            "chart_type_hint": None,
            "aggregation_hint": None,
            "filter_hints": []
        }
        
        # Detect query patterns
        for pattern_type, pattern in self.query_patterns.items():
            if re.search(pattern, query_lower):
                intent[f"{pattern_type}_focus"] = True
        
        # Determine primary query type
        if intent["temporal_focus"]:
            intent["query_type"] = "temporal_analysis"
        elif intent["geographic_focus"]:
            intent["query_type"] = "geographic_analysis"
        elif intent["categorical_focus"]:
            intent["query_type"] = "categorical_analysis"
        elif intent["numeric_focus"]:
            intent["query_type"] = "numeric_analysis"
        elif intent["comparison_focus"]:
            intent["query_type"] = "comparative_analysis"
        elif intent["distribution_focus"]:
            intent["query_type"] = "distribution_analysis"
        
        # Detect chart type hints
        if "bar" in query_lower or "column" in query_lower:
            intent["chart_type_hint"] = "bar_chart"
        elif "line" in query_lower or "trend" in query_lower:
            intent["chart_type_hint"] = "line_chart"
        elif "pie" in query_lower or "donut" in query_lower:
            intent["chart_type_hint"] = "pie_chart"
        elif "scatter" in query_lower or "correlation" in query_lower:
            intent["chart_type_hint"] = "scatter_plot"
        elif "histogram" in query_lower or "distribution" in query_lower:
            intent["chart_type_hint"] = "histogram"
        
        # Detect aggregation hints
        if "sum" in query_lower or "total" in query_lower:
            intent["aggregation_hint"] = "sum"
        elif "average" in query_lower or "mean" in query_lower:
            intent["aggregation_hint"] = "mean"
        elif "count" in query_lower:
            intent["aggregation_hint"] = "count"
        elif "maximum" in query_lower or "max" in query_lower:
            intent["aggregation_hint"] = "max"
        elif "minimum" in query_lower or "min" in query_lower:
            intent["aggregation_hint"] = "min"
        
        return intent
    
    def _identify_relevant_columns(
        self, 
        query_intent: Dict[str, Any], 
        dataset_metadata: Dict[str, Any]
    ) -> List[str]:
        """Identify which columns are relevant to the query."""
        relevant_columns = []
        column_metadata = dataset_metadata.get("column_metadata", [])
        
        for col_info in column_metadata:
            col_name = col_info["name"]
            is_relevant = False
            
            # Check if column matches query intent
            if query_intent["temporal_focus"] and col_info["is_temporal"]:
                is_relevant = True
            elif query_intent["geographic_focus"] and col_info["is_categorical"]:
                # Check for geographic indicators
                geo_indicators = ['region', 'country', 'state', 'city', 'area', 'zone']
                if any(indicator in col_name.lower() for indicator in geo_indicators):
                    is_relevant = True
            elif query_intent["categorical_focus"] and col_info["is_categorical"]:
                is_relevant = True
            elif query_intent["numeric_focus"] and col_info["is_numeric"]:
                is_relevant = True
            
            if is_relevant:
                relevant_columns.append(col_name)
        
        # If no specific columns identified, return all columns
        if not relevant_columns:
            relevant_columns = [col["name"] for col in column_metadata]
        
        return relevant_columns
    
    async def _generate_data_slices(
        self,
        query_intent: Dict[str, Any],
        relevant_columns: List[str],
        dataset_data: List[Dict],
        max_slices: int
    ) -> List[Dict[str, Any]]:
        """Generate relevant data slices based on query intent."""
        if not dataset_data:
            return []
        
        df = pd.DataFrame(dataset_data)
        slices = []
        
        # Slice 1: Top-level aggregation
        if query_intent["query_type"] in ["categorical_analysis", "geographic_analysis"]:
            slice_data = await self._create_aggregation_slice(
                df, relevant_columns, query_intent, "top_level"
            )
            if slice_data:
                slices.append(slice_data)
        
        # Slice 2: Sample data (always include)
        sample_slice = await self._create_sample_slice(df, relevant_columns, max_samples=20)
        if sample_slice:
            slices.append(sample_slice)
        
        return slices[:max_slices]
    
    async def _create_aggregation_slice(
        self, 
        df: pd.DataFrame, 
        relevant_columns: List[str], 
        query_intent: Dict[str, Any],
        slice_type: str
    ) -> Optional[Dict[str, Any]]:
        """Create aggregation slice for categorical/geographic analysis."""
        try:
            # Find categorical column for grouping
            categorical_cols = [col for col in relevant_columns if col in df.columns and df[col].dtype == 'object']
            numeric_cols = [col for col in relevant_columns if col in df.columns and df[col].dtype in ['int64', 'float64']]
            
            if not categorical_cols or not numeric_cols:
                return None
            
            group_col = categorical_cols[0]
            value_col = numeric_cols[0]
            
            # Perform aggregation
            aggregation_type = query_intent.get("aggregation_hint", "sum")
            if aggregation_type == "sum":
                result = df.groupby(group_col)[value_col].sum().reset_index()
            elif aggregation_type == "mean":
                result = df.groupby(group_col)[value_col].mean().reset_index()
            elif aggregation_type == "count":
                result = df.groupby(group_col).size().reset_index(name=value_col)
            else:
                result = df.groupby(group_col)[value_col].sum().reset_index()
            
            # Sort and limit
            result = result.sort_values(by=value_col, ascending=False).head(20)
            
            return {
                "slice_type": slice_type,
                "title": f"{aggregation_type.title()} by {group_col}",
                "data": result.to_dict('records'),
                "columns": [group_col, value_col],
                "row_count": len(result),
                "description": f"Aggregated data showing {aggregation_type} of {value_col} by {group_col}"
            }
            
        except Exception as e:
            logger.error(f"Error creating aggregation slice: {e}")
            return None
    
    async def _create_sample_slice(
        self, 
        df: pd.DataFrame, 
        relevant_columns: List[str], 
        max_samples: int = 20
    ) -> Optional[Dict[str, Any]]:
        """Create sample data slice."""
        try:
            # Select relevant columns
            available_cols = [col for col in relevant_columns if col in df.columns]
            if not available_cols:
                available_cols = df.columns.tolist()
            
            sample_df = df[available_cols].sample(n=min(max_samples, len(df)), random_state=42)
            
            return {
                "slice_type": "sample",
                "title": "Sample Data",
                "data": sample_df.to_dict('records'),
                "columns": available_cols,
                "row_count": len(sample_df),
                "description": "Random sample of the dataset"
            }
            
        except Exception as e:
            logger.error(f"Error creating sample slice: {e}")
            return None
    
    def _create_llm_context(
        self, 
        query_intent: Dict[str, Any], 
        data_slices: List[Dict[str, Any]], 
        dataset_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create context package for LLM consumption."""
        return {
            "query_analysis": query_intent,
            "available_slices": len(data_slices),
            "slice_summaries": [
                {
                    "type": slice_data["slice_type"],
                    "title": slice_data["title"],
                    "row_count": slice_data["row_count"],
                    "description": slice_data["description"]
                }
                for slice_data in data_slices
            ],
            "dataset_context": {
                "total_rows": dataset_metadata.get("dataset_overview", {}).get("total_rows", 0),
                "total_columns": dataset_metadata.get("dataset_overview", {}).get("total_columns", 0),
                "data_quality": dataset_metadata.get("data_quality", {}).get("overall_quality_score", 0)
            },
            "recommended_chart": query_intent.get("chart_type_hint"),
            "recommended_aggregation": query_intent.get("aggregation_hint")
        }

