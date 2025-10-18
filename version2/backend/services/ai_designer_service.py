# backend/services/ai_designer_service.py

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

from database import get_database
from services.ai_service import ai_service
from core.prompts import get_ai_designer_prompt

logger = logging.getLogger(__name__)


class AIDesignerService:
    """
    AI Designer Service that creates intelligent, contextually-aware dashboard designs.
    
    This service transforms DataSage from an "AI Generator" to an "AI Designer" by:
    1. Analyzing dataset context to determine the best design pattern
    2. Using few-shot prompting with design blueprints
    3. Creating story-driven, professional dashboard layouts
    """

    def __init__(self):
        self.db = get_database()
        
        # Design patterns library - these are our "few-shot" examples
        self.design_patterns = {
            "executive_kpi_trend": {
                "name": "Executive KPI & Trend Dashboard",
                "use_cases": ["sales", "marketing", "finance", "performance"],
                "blueprint": {
                    "layout_grid": "repeat(4, 1fr)",
                    "components": [
                        # Top Row: 4 KPI Cards
                        {"type": "kpi", "title": "Total Revenue", "span": 1, "config": {"column": "revenue", "aggregation": "sum"}},
                        {"type": "kpi", "title": "Total Customers", "span": 1, "config": {"column": "customer_id", "aggregation": "count"}},
                        {"type": "kpi", "title": "Average Order", "span": 1, "config": {"column": "order_value", "aggregation": "mean"}},
                        {"type": "kpi", "title": "Growth Rate", "span": 1, "config": {"column": "growth", "aggregation": "mean"}},
                        
                        # Middle Row: Hero chart + secondary chart
                        {"type": "chart", "title": "Revenue Trend Over Time", "span": 3, "config": {"chart_type": "line", "columns": ["date", "revenue"], "aggregation": "sum", "group_by": ["date"]}},
                        {"type": "chart", "title": "Revenue by Category", "span": 1, "config": {"chart_type": "pie", "columns": ["category", "revenue"], "aggregation": "sum", "group_by": ["category"]}},
                        
                        # Bottom Row: Detail table
                        {"type": "table", "title": "Recent Transactions", "span": 4, "config": {"columns": ["id", "customer", "date", "amount", "status"]}}
                    ]
                },
                "style_guide": "Executive dashboards prioritize high-level KPIs, trend analysis, and summary insights. Always lead with metrics, tell the story with time series, and provide detail in tables."
            },
            
            "comparative_analysis": {
                "name": "Comparative Analysis Dashboard", 
                "use_cases": ["logistics", "inventory", "product_comparison", "regional_analysis"],
                "blueprint": {
                    "layout_grid": "repeat(3, 1fr)",
                    "components": [
                        # Top Row: Key metrics
                        {"type": "kpi", "title": "Total Items", "span": 1, "config": {"column": "item_count", "aggregation": "count"}},
                        {"type": "kpi", "title": "Average Performance", "span": 1, "config": {"column": "performance", "aggregation": "mean"}},
                        {"type": "kpi", "title": "Top Performer", "span": 1, "config": {"column": "top_score", "aggregation": "max"}},
                        
                        # Middle Row: Comparison charts
                        {"type": "chart", "title": "Performance by Category", "span": 2, "config": {"chart_type": "grouped_bar_chart", "columns": ["category", "performance"], "aggregation": "mean", "group_by": ["category"]}},
                        {"type": "chart", "title": "Distribution", "span": 1, "config": {"chart_type": "histogram", "columns": ["performance"], "aggregation": "none"}},
                        
                        # Bottom Row: Detailed comparison
                        {"type": "table", "title": "Detailed Comparison", "span": 3, "config": {"columns": ["item", "category", "performance", "rank", "change"]}}
                    ]
                },
                "style_guide": "Comparative dashboards focus on relative performance. Use grouped bar charts for direct comparisons, histograms for distributions, and ranking tables for detailed analysis."
            },
            
            "entity_breakdown": {
                "name": "Entity Breakdown Dashboard",
                "use_cases": ["student_profile", "product_details", "campaign_analysis", "customer_profile"],
                "blueprint": {
                    "layout_grid": "repeat(2, 1fr)",
                    "components": [
                        # Header: Entity overview
                        {"type": "kpi", "title": "Entity ID", "span": 1, "config": {"column": "entity_id", "aggregation": "count"}},
                        {"type": "kpi", "title": "Status", "span": 1, "config": {"column": "status", "aggregation": "count"}},
                        
                        # Multiple smaller charts for different aspects
                        {"type": "chart", "title": "Performance Over Time", "span": 1, "config": {"chart_type": "line", "columns": ["date", "score"], "aggregation": "mean", "group_by": ["date"]}},
                        {"type": "chart", "title": "Category Breakdown", "span": 1, "config": {"chart_type": "bar", "columns": ["category", "count"], "aggregation": "count", "group_by": ["category"]}},
                        
                        # Activity/events table
                        {"type": "table", "title": "Recent Activity", "span": 2, "config": {"columns": ["date", "event", "details", "impact"]}}
                    ]
                },
                "style_guide": "Entity dashboards provide deep-dive analysis. Use multiple smaller charts to show different aspects of the entity, with detailed activity logs and performance metrics."
            }
        }

    async def design_intelligent_dashboard(
        self, 
        dataset_id: str, 
        user_id: str,
        design_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an intelligent dashboard design based on dataset analysis and design patterns.
        """
        try:
            # Get dataset and metadata
            dataset_doc = await self.db.datasets.find_one({
                "_id": ObjectId(dataset_id),
                "user_id": user_id
            })
            
            if not dataset_doc or not dataset_doc.get("metadata"):
                raise Exception("Dataset not ready for dashboard design.")

            # Analyze dataset to determine best design pattern
            best_pattern = await self._analyze_dataset_for_pattern(
                dataset_doc["metadata"], 
                design_preference
            )
            
            # Get the selected pattern
            pattern = self.design_patterns[best_pattern]
            
            # Create enhanced prompt with the pattern as few-shot example
            enhanced_prompt = self._create_designer_prompt(
                dataset_doc["metadata"], 
                pattern
            )
            
            # Generate dashboard design using AI
            design_response = await ai_service._call_ollama(
                enhanced_prompt,
                model_role="layout_designer",
                expect_json=True
            )
            
            # Validate and enhance the design
            dashboard_blueprint = self._validate_and_enhance_design(
                design_response.get("dashboard", {}),
                dataset_doc["metadata"],
                pattern
            )
            
            # Save the design
            design_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "design_pattern": best_pattern,
                "blueprint": dashboard_blueprint,
                "created_at": datetime.utcnow(),
                "is_default": True
            }
            
            await self.db.dashboards.insert_one(design_doc)
            
            return {
                "dashboard_blueprint": dashboard_blueprint,
                "design_pattern": best_pattern,
                "pattern_name": pattern["name"],
                "reasoning": design_response.get("reasoning", "AI-generated design based on dataset analysis")
            }
            
        except Exception as e:
            logger.error(f"AI Designer error: {e}")
            raise Exception(f"Failed to design dashboard: {str(e)}")

    async def _analyze_dataset_for_pattern(
        self, 
        dataset_metadata: Dict, 
        user_preference: Optional[str]
    ) -> str:
        """
        Analyzes dataset metadata to determine the best design pattern.
        """
        # If user specified a preference, use it if valid
        if user_preference and user_preference in self.design_patterns:
            return user_preference
        
        # Analyze dataset characteristics
        column_metadata = dataset_metadata.get("column_metadata", [])
        total_rows = dataset_metadata.get("dataset_overview", {}).get("total_rows", 0)
        
        # Count column types
        numeric_cols = sum(1 for col in column_metadata if col.get("type") in ["numeric", "integer", "float"])
        categorical_cols = sum(1 for col in column_metadata if col.get("type") in ["string", "categorical"])
        temporal_cols = sum(1 for col in column_metadata if col.get("type") in ["date", "datetime"])
        
        # Determine pattern based on data characteristics
        if temporal_cols > 0 and numeric_cols >= 2:
            # Time series data - perfect for executive trend dashboard
            return "executive_kpi_trend"
        elif categorical_cols >= 2 and numeric_cols >= 1:
            # Multiple categories - good for comparative analysis
            return "comparative_analysis"
        elif total_rows < 1000 and categorical_cols >= 1:
            # Smaller dataset with categories - entity breakdown
            return "entity_breakdown"
        else:
            # Default to executive pattern
            return "executive_kpi_trend"

    def _create_designer_prompt(
        self, 
        dataset_metadata: Dict, 
        selected_pattern: Dict
    ) -> str:
        """
        Creates an enhanced prompt using few-shot learning with design patterns.
        """
        dataset_context = self._create_dataset_context_string(dataset_metadata)
        pattern_blueprint = json.dumps(selected_pattern["blueprint"], indent=2)
        
        return f"""
        You are DataSage Designer, a world-class dashboard design expert. Your task is to create a professional, story-driven dashboard layout.

        **DESIGN PHILOSOPHY:**
        {selected_pattern["style_guide"]}

        **EXAMPLE DESIGN PATTERN:**
        Here's an example of a professional {selected_pattern["name"]}:
        
        ```json
        {pattern_blueprint}
        ```

        **DESIGN RULES:**
        1. **Hierarchy First:** Always start with 3-4 KPI components for high-level metrics
        2. **Tell a Story:** Include a "hero" chart (line/bar) that spans 2-3 columns
        3. **Provide Detail:** End with a table component spanning all columns
        4. **Component Variety:** Use at least 3 different component types (kpi, chart, table)
        5. **Smart Spanning:** Charts should span 2-3 columns, KPIs span 1, tables span all
        6. **Contextual Relevance:** Choose columns and aggregations that make sense for the data

        **DATASET CONTEXT:**
        {dataset_context}

        **YOUR TASK:**
        Design a dashboard that follows the example pattern but is perfectly tailored to this dataset. 
        
        **IMPORTANT:** 
        - Use actual column names from the dataset
        - Choose appropriate chart types based on data types
        - Ensure aggregations match the data (sum for numeric, count for categorical)
        - Create a cohesive story that answers business questions

        **OUTPUT FORMAT:**
        Provide a JSON object with:
        {{
            "dashboard": {{
                "layout_grid": "repeat(X, 1fr)",
                "components": [
                    // Your designed components here
                ]
            }},
            "reasoning": "Brief explanation of your design choices"
        }}

        **COMPONENT TYPES AVAILABLE:**
        - "kpi": {{"column": "column_name", "aggregation": "sum|mean|count|nunique"}}
        - "chart": {{"chart_type": "bar|line|pie|scatter|histogram|box_plot|grouped_bar_chart", "columns": ["col1", "col2"], "aggregation": "sum|mean|count|none", "group_by": ["col"]}}
        - "table": {{"columns": ["col1", "col2", "col3"]}}

        Provide only the JSON response.
        """

    def _validate_and_enhance_design(
        self, 
        dashboard_blueprint: Dict, 
        dataset_metadata: Dict,
        pattern: Dict
    ) -> Dict:
        """
        Validates and enhances the AI-generated design.
        """
        if not dashboard_blueprint or "components" not in dashboard_blueprint:
            # Fallback to pattern blueprint
            logger.warning("AI design was invalid, using pattern fallback")
            return pattern["blueprint"]
        
        # Ensure required components exist
        components = dashboard_blueprint.get("components", [])
        component_types = [comp.get("type") for comp in components]
        
        # Add missing KPI if none exist
        if "kpi" not in component_types:
            # Add a default KPI
            components.insert(0, {
                "type": "kpi",
                "title": "Total Records",
                "span": 1,
                "config": {"column": "id", "aggregation": "count"}
            })
        
        # Ensure layout grid is set
        if "layout_grid" not in dashboard_blueprint:
            dashboard_blueprint["layout_grid"] = "repeat(4, 1fr)"
        
        return dashboard_blueprint

    def _create_dataset_context_string(self, dataset_metadata: Dict) -> str:
        """Create context string from dataset metadata."""
        overview = dataset_metadata.get('dataset_overview', {})
        columns = dataset_metadata.get('column_metadata', [])
        
        col_strings = []
        for col in columns[:15]:  # Limit to first 15 columns
            col_name = col.get('name', 'unknown')
            col_type = col.get('type', 'unknown')
            col_strings.append(f"{col_name} ({col_type})")
        
        context = (
            f"Dataset: {overview.get('total_rows', 'N/A')} rows, {overview.get('total_columns', 'N/A')} columns.\n"
            f"Columns: {', '.join(col_strings)}"
        )
        
        if len(columns) > 15:
            context += f"\n... and {len(columns) - 15} more columns"
            
        return context

    async def get_available_patterns(self) -> Dict[str, Any]:
        """Get available design patterns for user selection."""
        return {
            "patterns": [
                {
                    "id": pattern_id,
                    "name": pattern["name"],
                    "use_cases": pattern["use_cases"]
                }
                for pattern_id, pattern in self.design_patterns.items()
            ]
        }


# Singleton instance
ai_designer_service = AIDesignerService()

