import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from services.metadata_service import MetadataService
from services.rag_service import RAGService
from services.chart_validation_service import ChartValidationService

logger = logging.getLogger(__name__)

class EnhancedLLMService:
    """
    Enhanced LLM service that implements the three critical strategies:
    1. Never feed raw rows → only metadata, samples, summaries
    2. Use RAG to fetch relevant slices
    3. Always validate AI chart choice with datatype rules
    """
    
    def __init__(self, base_llm_service):
        self.base_llm_service = base_llm_service
        self.metadata_service = MetadataService()
        self.rag_service = RAGService()
        self.chart_validation_service = ChartValidationService()
    
    async def process_dataset_query(
        self, 
        query: str, 
        dataset_id: str, 
        dataset_data: List[Dict]
    ) -> Dict[str, Any]:
        """
        Process a dataset query using the three critical strategies.
        """
        try:
            # Step 1: Generate metadata package (NO raw data)
            logger.info(f"Generating metadata package for dataset {dataset_id}")
            metadata_package = await self.metadata_service.generate_llm_metadata_package(
                dataset_data, dataset_id
            )
            
            # Step 2: Use RAG to retrieve relevant data slices
            logger.info(f"Using RAG to retrieve relevant slices for query: {query}")
            rag_result = await self.rag_service.retrieve_relevant_slices(
                query, metadata_package, dataset_data, max_slices=3
            )
            
            # Step 3: Generate LLM response with metadata only
            logger.info("Generating LLM response with metadata only")
            llm_response = await self._generate_llm_response(
                query, metadata_package, rag_result, persona
            )
            
            # Step 4: Validate any chart recommendations
            if "chart_recommendation" in llm_response:
                logger.info("Validating chart recommendation")
                validation_result = self._validate_chart_recommendation(
                    llm_response["chart_recommendation"], 
                    rag_result
                )
                llm_response["chart_validation"] = validation_result
            
            return {
                "query": query,
                "dataset_id": dataset_id,
                "response": llm_response,
                "metadata_used": True,
                "rag_used": True,
                "validation_performed": "chart_recommendation" in llm_response,
                "raw_data_excluded": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing dataset query: {e}")
            return {
                "error": str(e),
                "query": query,
                "dataset_id": dataset_id,
                "metadata_used": False,
                "rag_used": False,
                "validation_performed": False
            }
    
    async def recommend_visualization(
        self, 
        query: str, 
        dataset_metadata: Dict[str, Any], 
        dataset_data: List[Dict]
    ) -> Dict[str, Any]:
        """
        Recommend visualization using the three critical strategies.
        """
        try:
            # Step 1: Use RAG to get relevant data slices
            rag_result = await self.rag_service.retrieve_relevant_slices(
                query, dataset_metadata, dataset_data, max_slices=2
            )
            
            # Step 2: Generate chart recommendation based on metadata
            chart_recommendation = await self._generate_chart_recommendation(
                query, dataset_metadata, rag_result, persona
            )
            
            # Step 3: Validate the recommendation
            validation_result = self._validate_chart_recommendation(
                chart_recommendation, rag_result
            )
            
            # Step 4: Generate final response
            return {
                "query": query,
                "chart_recommendation": chart_recommendation,
                "validation": validation_result,
                "rag_context": rag_result.get("context", {}),
                "confidence_score": validation_result.get("confidence_score", 0.0),
                "alternative_charts": validation_result.get("alternative_charts", []),
                "metadata_based": True,
                "raw_data_excluded": True
            }
            
        except Exception as e:
            logger.error(f"Error recommending visualization: {e}")
            return {"error": str(e)}
    
    async def _generate_llm_response(
        self, 
        query: str, 
        metadata_package: Dict[str, Any], 
        rag_result: Dict[str, Any], 
        persona: str
    ) -> Dict[str, Any]:
        """Generate LLM response using only metadata and RAG slices."""
        
        # Prepare context for LLM (NO raw data)
        context = {
            "query": query,
            "dataset_overview": metadata_package.get("dataset_overview", {}),
            "column_metadata": metadata_package.get("column_metadata", []),
            "statistical_summaries": metadata_package.get("statistical_summaries", {}),
            "data_quality": metadata_package.get("data_quality", {}),
            "sample_data": metadata_package.get("sample_data", {}),
            "rag_context": rag_result.get("context", {}),
            "available_slices": rag_result.get("slice_count", 0),
            "persona": persona
        }
        
        # Generate response using base LLM service with context only
        response = await self.base_llm_service.generate_response_with_context(context)
        
        return response
    
    async def _generate_chart_recommendation(
        self, 
        query: str, 
        dataset_metadata: Dict[str, Any], 
        rag_result: Dict[str, Any], 
        persona: str
    ) -> Dict[str, Any]:
        """Generate chart recommendation based on metadata and RAG context."""
        
        # Get available chart recommendations from metadata
        chart_recommendations = dataset_metadata.get("chart_recommendations", [])
        
        # Get RAG context
        rag_context = rag_result.get("context", {})
        query_intent = rag_result.get("query_intent", {})
        
        # Select best chart based on query intent
        best_chart = None
        confidence = 0.0
        
        for rec in chart_recommendations:
            chart_type = rec.get("chart_type")
            rec_confidence = rec.get("confidence", 0.5)
            
            # Match with query intent
            if query_intent.get("chart_type_hint") == chart_type:
                confidence = min(0.9, rec_confidence + 0.2)
            else:
                confidence = rec_confidence
            
            if confidence > 0.6:
                best_chart = rec
                break
        
        # Fallback to first recommendation
        if not best_chart and chart_recommendations:
            best_chart = chart_recommendations[0]
            confidence = 0.5
        
        return {
            "chart_type": best_chart.get("chart_type") if best_chart else "bar_chart",
            "title": best_chart.get("title") if best_chart else "Data Visualization",
            "description": best_chart.get("description") if best_chart else "Visual representation of data",
            "suitable_columns": best_chart.get("suitable_columns", []),
            "confidence": confidence,
            "based_on_query": True,
            "metadata_driven": True
        }
    
    def _validate_chart_recommendation(
        self, 
        chart_recommendation: Dict[str, Any], 
        rag_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate chart recommendation using datatype rules."""
        
        chart_type = chart_recommendation.get("chart_type", "bar_chart")
        suitable_columns = chart_recommendation.get("suitable_columns", [])
        
        # Get data slices from RAG
        data_slices = rag_result.get("data_slices", [])
        if not data_slices:
            return {
                "valid": False,
                "error": "No data slices available for validation",
                "confidence_score": 0.0
            }
        
        # Use first data slice for validation
        first_slice = data_slices[0]
        data = first_slice.get("data", [])
        columns = first_slice.get("columns", suitable_columns)
        
        # Validate chart recommendation
        validation_result = self.chart_validation_service.validate_chart_recommendation(
            chart_type, columns, data, {}
        )
        
        return validation_result
    
    async def explain_dataset(
        self, 
        dataset_metadata: Dict[str, Any], 
        persona: str = "normal"
    ) -> Dict[str, Any]:
        """
        Explain dataset using only metadata - NO raw data.
        """
        try:
            # Extract key insights from metadata
            overview = dataset_metadata.get("dataset_overview", {})
            column_metadata = dataset_metadata.get("column_metadata", [])
            data_quality = dataset_metadata.get("data_quality", {})
            patterns = dataset_metadata.get("patterns", {})
            
            # Generate explanation
            explanation = {
                "dataset_summary": {
                    "total_rows": overview.get("total_rows", 0),
                    "total_columns": overview.get("total_columns", 0),
                    "data_types": overview.get("data_types_distribution", {}),
                    "memory_usage": overview.get("memory_usage_mb", 0)
                },
                "column_insights": [],
                "data_quality_assessment": {
                    "overall_score": data_quality.get("overall_quality_score", 0),
                    "completeness_level": data_quality.get("completeness_level", "unknown"),
                    "main_issues": data_quality.get("data_issues", {})
                },
                "key_patterns": patterns,
                "recommendations": []
            }
            
            # Analyze each column
            for col_info in column_metadata:
                col_insight = {
                    "name": col_info["name"],
                    "type": col_info["dtype"],
                    "data_quality": {
                        "null_percentage": col_info.get("null_percentage", 0),
                        "unique_percentage": col_info.get("unique_percentage", 0),
                        "cardinality": col_info.get("cardinality", "unknown")
                    },
                    "characteristics": {
                        "is_numeric": col_info.get("is_numeric", False),
                        "is_categorical": col_info.get("is_categorical", False),
                        "is_temporal": col_info.get("is_temporal", False)
                    }
                }
                
                # Add statistical insights for numeric columns
                if col_info.get("is_numeric"):
                    col_insight["statistics"] = {
                        "min": col_info.get("min"),
                        "max": col_info.get("max"),
                        "mean": col_info.get("mean"),
                        "median": col_info.get("median"),
                        "std": col_info.get("std")
                    }
                
                explanation["column_insights"].append(col_insight)
            
            # Generate recommendations
            recommendations = []
            
            # Data quality recommendations
            if data_quality.get("overall_quality_score", 0) < 70:
                recommendations.append("Consider data cleaning to improve quality score")
            
            # Column-specific recommendations
            for col_info in column_metadata:
                if col_info.get("null_percentage", 0) > 20:
                    recommendations.append(f"High null percentage in '{col_info['name']}' - consider imputation")
                
                if col_info.get("is_categorical") and col_info.get("unique_percentage", 0) > 80:
                    recommendations.append(f"High cardinality in '{col_info['name']}' - consider grouping")
            
            explanation["recommendations"] = recommendations
            
            return {
                "explanation": explanation,
                "metadata_based": True,
                "raw_data_excluded": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error explaining dataset: {e}")
            return {"error": str(e)}
    
    async def answer_query(
        self, 
        query: str, 
        dataset_metadata: Dict[str, Any], 
        rag_result: Dict[str, Any],
        persona: str = "normal"
    ) -> Dict[str, Any]:
        """
        Answer natural language query using metadata and RAG.
        """
        try:
            # Prepare context from metadata and RAG
            context = {
                "query": query,
                "dataset_metadata": dataset_metadata,
                "rag_context": rag_result.get("context", {}),
                "available_slices": rag_result.get("slice_count", 0),
                "persona": persona
            }
            
            # Generate answer using base LLM service
            answer = await self.base_llm_service.generate_response_with_context(context)
            
            return {
                "query": query,
                "answer": answer,
                "metadata_based": True,
                "rag_enhanced": True,
                "raw_data_excluded": True
            }
            
        except Exception as e:
            logger.error(f"Error answering query: {e}")
            return {"error": str(e)}
