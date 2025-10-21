# backend/services/chart_insights_service.py

import logging
import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from database import get_database
from config import settings

logger = logging.getLogger(__name__)


class ChartInsightsService:
    """
    Service for generating AI-powered insights for charts and caching rendered charts.
    """

    def __init__(self):
        self.db = get_database()

    async def generate_chart_insight(self, chart_config: Dict[str, Any], chart_data: List[Dict], dataset_metadata: Dict) -> Dict[str, Any]:
        """
        Generate user-friendly insights for a chart using AI.
        """
        try:
            # Create insight prompt
            insight_prompt = self._create_insight_prompt(chart_config, chart_data, dataset_metadata)
            
            # Call qwen3 for insights
            from services.ai_service import ai_service
            llm_response = await ai_service._call_ollama(insight_prompt, model_role="insight_engine", expect_json=True)
            
            if llm_response.get("fallback"):
                return self._generate_fallback_insight(chart_config, chart_data)
            
            return {
                "insight": llm_response.get("insight", {}),
                "confidence": llm_response.get("confidence", "Medium"),
                "generated_at": datetime.utcnow().isoformat(),
                "chart_type": chart_config.get("chart_type", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error generating chart insight: {e}")
            return self._generate_fallback_insight(chart_config, chart_data)

    def _create_insight_prompt(self, chart_config: Dict[str, Any], chart_data: List[Dict], dataset_metadata: Dict) -> str:
        """Create a prompt for generating chart insights."""
        
        chart_type = chart_config.get("chart_type", "unknown")
        x_axis = chart_config.get("x_axis", "X")
        y_axis = chart_config.get("y_axis", "Y")
        
        # Sample the data for context (first 10 items)
        sample_data = chart_data[:10] if len(chart_data) > 10 else chart_data
        
        prompt = f"""
You are an expert data analyst creating user-friendly insights for charts. Generate clear, actionable insights that help users understand what the chart shows and what they should do about it.

CHART DETAILS:
- Chart Type: {chart_type}
- X-Axis: {x_axis}
- Y-Axis: {y_axis}
- Data Points: {len(chart_data)}

SAMPLE DATA:
{json.dumps(sample_data, indent=2)}

DATASET CONTEXT:
{json.dumps(dataset_metadata.get('dataset_overview', {}), indent=2)}

INSTRUCTIONS:
1. Write a clear, non-technical summary of what the chart shows
2. Identify the most important patterns or trends
3. Provide actionable recommendations based on the data
4. Use simple language that anyone can understand
5. Focus on business value and practical insights

RESPONSE FORMAT (JSON):
{{
    "insight": {{
        "title": "Clear, descriptive title",
        "summary": "One-sentence summary of what the chart shows",
        "key_findings": [
            "Finding 1: What stands out most",
            "Finding 2: Important pattern or trend",
            "Finding 3: Notable data point or comparison"
        ],
        "recommendations": [
            "Action 1: What to do based on this data",
            "Action 2: Next steps to take",
            "Action 3: Areas to investigate further"
        ],
        "business_impact": "How this insight affects business decisions",
        "confidence_level": "High/Medium/Low"
    }},
    "confidence": "High/Medium/Low"
}}
"""

        return prompt

    def _generate_fallback_insight(self, chart_config: Dict[str, Any], chart_data: List[Dict]) -> Dict[str, Any]:
        """Generate fallback insights when AI fails."""
        
        chart_type = chart_config.get("chart_type", "unknown")
        x_axis = chart_config.get("x_axis", "X")
        y_axis = chart_config.get("y_axis", "Y")
        
        return {
            "insight": {
                "title": f"{chart_type.title()} Analysis",
                "summary": f"This {chart_type} chart shows the relationship between {x_axis} and {y_axis}.",
                "key_findings": [
                    f"Data visualization of {len(chart_data)} data points",
                    f"Shows {chart_type} relationship between {x_axis} and {y_axis}",
                    "Patterns and trends are visible in the data"
                ],
                "recommendations": [
                    "Review the data patterns shown in the chart",
                    "Consider how these insights apply to your business",
                    "Look for opportunities to optimize based on the trends"
                ],
                "business_impact": "This chart provides valuable insights for data-driven decision making.",
                "confidence_level": "Medium"
            },
            "confidence": "Medium"
        }

    async def cache_rendered_chart(self, dataset_id: str, user_id: str, chart_config: Dict[str, Any], chart_data: List[Dict], insight: Dict[str, Any]) -> str:
        """
        Cache a successfully rendered chart with its data and insights.
        """
        try:
            # Create a unique hash for the chart configuration
            chart_hash = self._generate_chart_hash(chart_config)
            
            cached_chart = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "chart_config": chart_config,
                "chart_data": chart_data,
                "insight": insight,
                "chart_hash": chart_hash,
                "created_at": datetime.utcnow(),
                "last_accessed": datetime.utcnow(),
                "access_count": 1
            }
            
            # Check if chart already exists
            existing_chart = await self.db.cached_charts.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id,
                "chart_hash": chart_hash
            })
            
            if existing_chart:
                # Update access count and timestamp
                await self.db.cached_charts.update_one(
                    {"_id": existing_chart["_id"]},
                    {
                        "$set": {"last_accessed": datetime.utcnow()},
                        "$inc": {"access_count": 1}
                    }
                )
                return str(existing_chart["_id"])
            else:
                # Insert new cached chart
                result = await self.db.cached_charts.insert_one(cached_chart)
                return str(result.inserted_id)
                
        except Exception as e:
            logger.error(f"Error caching chart: {e}")
            return None

    async def get_cached_chart(self, dataset_id: str, user_id: str, chart_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached chart if it exists.
        """
        try:
            chart_hash = self._generate_chart_hash(chart_config)
            
            cached_chart = await self.db.cached_charts.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id,
                "chart_hash": chart_hash
            })
            
            if cached_chart:
                # Update access count and timestamp
                await self.db.cached_charts.update_one(
                    {"_id": cached_chart["_id"]},
                    {
                        "$set": {"last_accessed": datetime.utcnow()},
                        "$inc": {"access_count": 1}
                    }
                )
                
                # Convert ObjectId to string
                cached_chart["_id"] = str(cached_chart["_id"])
                return cached_chart
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached chart: {e}")
            return None

    def _generate_chart_hash(self, chart_config: Dict[str, Any]) -> str:
        """Generate a unique hash for chart configuration."""
        # Create a normalized version of the config for hashing
        normalized_config = {
            "chart_type": chart_config.get("chart_type"),
            "x_axis": chart_config.get("x_axis"),
            "y_axis": chart_config.get("y_axis"),
            "aggregation": chart_config.get("aggregation"),
            "filters": chart_config.get("filters", {}),
            "sorting": chart_config.get("sorting", {})
        }
        
        # Convert to JSON string and hash
        config_str = json.dumps(normalized_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    async def get_dataset_cached_charts(self, dataset_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get all cached charts for a dataset."""
        try:
            charts = await self.db.cached_charts.find({
                "dataset_id": dataset_id,
                "user_id": user_id
            }).sort("created_at", -1).to_list(length=50)
            
            # Convert ObjectIds to strings
            for chart in charts:
                chart["_id"] = str(chart["_id"])
            
            return charts
            
        except Exception as e:
            logger.error(f"Error getting cached charts: {e}")
            return []

    async def clear_old_cached_charts(self, days_old: int = 30):
        """Clear cached charts older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            result = await self.db.cached_charts.delete_many({
                "last_accessed": {"$lt": cutoff_date}
            })
            
            logger.info(f"Cleared {result.deleted_count} old cached charts")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing old cached charts: {e}")
            return 0


# Global instance
chart_insights_service = ChartInsightsService()
