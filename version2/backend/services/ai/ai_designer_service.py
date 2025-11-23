# backend/services/ai/ai_designer_service.py

import logging
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

from db.database import get_database
from services.llm_router import llm_router

logger = logging.getLogger(__name__)


class AIDesignerService:
    """
    AI Designer Service: Produces intelligent, context-aware dashboard blueprints.

    Responsibilities:
    - Analyze dataset metadata
    - Select a design pattern
    - Build a schema-aware prompt (few-shot guided)
    - Ask LLM for a JSON blueprint
    - Validate/repair blueprint
    - Persist the design
    """

    def __init__(self):
        self._db = None
        
        # --- FEW-SHOT DESIGN PATTERNS ---
        self.design_patterns = {
            "executive_kpi_trend": {
                "name": "Executive KPI & Trend Dashboard",
                "use_cases": ["sales", "marketing", "finance", "performance"],
                "blueprint": {
                    "layout_grid": "repeat(4, 1fr)",
                    "components": [
                        {"type": "kpi", "title": "Total Revenue", "span": 1,
                         "config": {"column": "revenue", "aggregation": "sum"}},
                        {"type": "kpi", "title": "Total Customers", "span": 1,
                         "config": {"column": "customer_id", "aggregation": "count"}},
                        {"type": "kpi", "title": "Average Order", "span": 1,
                         "config": {"column": "order_value", "aggregation": "mean"}},
                        {"type": "kpi", "title": "Growth Rate", "span": 1,
                         "config": {"column": "growth", "aggregation": "mean"}},

                        {"type": "chart", "title": "Revenue Trend Over Time", "span": 3,
                         "config": {"chart_type": "line", "columns": ["date", "revenue"],
                                    "aggregation": "sum", "group_by": ["date"]}},

                        {"type": "chart", "title": "Revenue by Category", "span": 1,
                         "config": {"chart_type": "pie", "columns": ["category", "revenue"],
                                    "aggregation": "sum", "group_by": ["category"]}},

                        {"type": "table", "title": "Recent Transactions", "span": 4,
                         "config": {"columns": ["id", "customer", "date", "amount", "status"]}}
                    ]
                },
                "style_guide": (
                    "Executive dashboards prioritize KPIs, trend analysis and summary insights. "
                    "Lead with metrics, tell the story with time series, and provide detail in tables."
                )
            },
            
            "comparative_analysis": {
                "name": "Comparative Analysis Dashboard",
                "use_cases": ["logistics", "inventory", "product_comparison", "regional_analysis"],
                "blueprint": {
                    "layout_grid": "repeat(3, 1fr)",
                    "components": [
                        {"type": "kpi", "title": "Total Items", "span": 1,
                         "config": {"column": "item_count", "aggregation": "count"}},
                        {"type": "kpi", "title": "Average Performance", "span": 1,
                         "config": {"column": "performance", "aggregation": "mean"}},
                        {"type": "kpi", "title": "Top Performer", "span": 1,
                         "config": {"column": "top_score", "aggregation": "first"}},

                        {"type": "chart", "title": "Performance by Category", "span": 2,
                         "config": {"chart_type": "grouped_bar",
                                    "columns": ["category", "performance"],
                                    "aggregation": "mean", "group_by": ["category"]}},

                        {"type": "chart", "title": "Distribution", "span": 1,
                         "config": {"chart_type": "histogram",
                                    "columns": ["performance"], "aggregation": "none"}},

                        {"type": "table", "title": "Detailed Comparison", "span": 3,
                         "config": {"columns": ["item", "category", "performance", "rank", "change"]}}
                    ]
                },
                "style_guide": (
                    "Comparative dashboards focus on relative performance. "
                    "Use grouped bars for comparison, histograms for distributions, "
                    "and ranking tables for details."
                )
            },
            
            "entity_breakdown": {
                "name": "Entity Breakdown Dashboard",
                "use_cases": ["student_profile", "product_details", "campaign_analysis", "customer_profile"],
                "blueprint": {
                    "layout_grid": "repeat(2, 1fr)",
                    "components": [
                        {"type": "kpi", "title": "Entity ID", "span": 1,
                         "config": {"column": "entity_id", "aggregation": "count"}},
                        {"type": "kpi", "title": "Status", "span": 1,
                         "config": {"column": "status", "aggregation": "count"}},

                        {"type": "chart", "title": "Performance Over Time", "span": 1,
                         "config": {"chart_type": "line", "columns": ["date", "score"],
                                    "aggregation": "mean", "group_by": ["date"]}},

                        {"type": "chart", "title": "Category Breakdown", "span": 1,
                         "config": {"chart_type": "bar",
                                    "columns": ["category", "count"],
                                    "aggregation": "count",
                                    "group_by": ["category"]}},

                        {"type": "table", "title": "Recent Activity", "span": 2,
                         "config": {"columns": ["date", "event", "details", "impact"]}}
                    ]
                },
                "style_guide": (
                    "Entity dashboards provide deep-dive analysis across multiple dimensions."
                )
            }
        }

    @property
    def db(self):
        """Lazy database initialization to avoid None during startup"""
        if self._db is None:
            self._db = get_database()
        return self._db

    # ---------------------------------------------------------
    # MAIN ENTRY: DESIGN DASHBOARD
    # ---------------------------------------------------------
    async def design_intelligent_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        design_preference: Optional[str] = None
    ) -> Dict[str, Any]:

        try:
            # Safe ObjectId handling
            try:
                dataset_oid = ObjectId(dataset_id)
                query = {"_id": dataset_oid, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            dataset_doc = await self.db.datasets.find_one(query)

            if not dataset_doc or not dataset_doc.get("metadata"):
                raise RuntimeError("Dataset metadata missing — cannot design dashboard.")

            metadata = dataset_doc["metadata"]

            # 1. choose pattern
            best_pattern = await self._analyze_dataset_for_pattern(metadata, design_preference)
            pattern = self.design_patterns.get(best_pattern) or next(iter(self.design_patterns.values()))

            # 2. build prompt
            prompt = self._create_designer_prompt(metadata, pattern)

            # 3. call LLM via router (OpenRouter or Ollama)
            try:
                ai_output = await llm_router.call(
                    prompt, model_role="layout_designer", expect_json=True
                )
                logger.info(f"AI Designer LLM Response: {json.dumps(ai_output, indent=2)[:500]}")
            except Exception as e:
                logger.exception(f"LLM call failed: {e}; falling back to pattern blueprint")
                ai_output = {"dashboard": pattern["blueprint"], "reasoning": "fallback LLM failure"}

            # 4. repair
            blueprint = self._validate_and_enhance_design(
                ai_output.get("dashboard", {}), metadata, pattern
            )

            # 5. persist
            design_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "design_pattern": best_pattern,
                "blueprint": blueprint,
                "created_at": datetime.utcnow(),
                "is_default": True
            }
            await self.db.dashboards.insert_one(design_doc)

            return {
                "dashboard_blueprint": blueprint,
                "design_pattern": best_pattern,
                "pattern_name": pattern.get("name"),
                "reasoning": ai_output.get("reasoning", "AI-generated blueprint")
            }

        except Exception as e:
            logger.exception("AI Designer error")
            raise RuntimeError(f"Failed to design dashboard: {e}") from e

    # ---------------------------------------------------------
    # Pattern selection
    # ---------------------------------------------------------
    async def _analyze_dataset_for_pattern(self, metadata: Dict, preference: Optional[str]) -> str:
        if preference in self.design_patterns:
            return preference

        colmeta = metadata.get("column_metadata", [])
        overview = metadata.get("dataset_overview", {})

        total_rows = overview.get("total_rows", 0)

        numeric = sum(1 for c in colmeta if c.get("type") in ("numeric", "integer", "float", "int"))
        categorical = sum(1 for c in colmeta if c.get("type") in ("string", "categorical", "utf8"))
        temporal = sum(1 for c in colmeta if c.get("type") in ("date", "datetime", "timestamp"))

        if temporal > 0 and numeric >= 2:
            return "executive_kpi_trend"
        if categorical >= 2 and numeric >= 1:
            return "comparative_analysis"
        if total_rows < 1000 and categorical >= 1:
            return "entity_breakdown"

        return "executive_kpi_trend"

    # ---------------------------------------------------------
    # Prompt generation
    # ---------------------------------------------------------
    def _create_designer_prompt(self, metadata: Dict, selected_pattern: Dict) -> str:
        context = self._create_dataset_context_string(metadata)
        example_blueprint = json.dumps(selected_pattern["blueprint"], indent=2)

        return f"""
You are DataSage Designer, a world-class dashboard layout architect.

DATASET CONTEXT:
{context}

EXAMPLE BLUEPRINT (use this structure):
{example_blueprint}

CRITICAL INSTRUCTIONS:
1. Return ONLY raw JSON (no markdown, no code blocks, no explanations)
2. Use the EXACT structure from the example blueprint
3. Replace column names with ACTUAL columns from the dataset
4. Start your response with {{ and end with }}
5. Ensure all JSON is valid (proper quotes, commas, brackets)

REQUIRED JSON FORMAT:
{{
  "dashboard": {{
      "layout_grid": "repeat(4, 1fr)",
      "components": [
        {{
          "type": "kpi",
          "title": "Total Records",
          "span": 1,
          "config": {{"column": "actual_column_name", "aggregation": "sum"}}
        }}
      ]
  }},
  "reasoning": "Brief explanation of design choices"
}}

RESPOND NOW WITH ONLY THE JSON:
"""

    # ---------------------------------------------------------
    # Blueprint validation / repair
    # ---------------------------------------------------------
    def _validate_and_enhance_design(self, blueprint: Dict, metadata: Dict, pattern: Dict) -> Dict:
        if not blueprint or "components" not in blueprint:
            logger.warning(f"Invalid AI blueprint. Blueprint keys: {list(blueprint.keys()) if blueprint else 'None'}. Using fallback pattern.")
            return pattern["blueprint"]

        components = blueprint.get("components", [])
        types = [c.get("type") for c in components]

        # ensure KPI exists
        if "kpi" not in types:
            components.insert(0, {
                "type": "kpi",
                "title": "Total Records",
                "span": 1,
                "config": {"column": "id", "aggregation": "count"}
            })

        # ensure chart exists
        if "chart" not in types:
            first_col = (metadata.get("column_metadata") or [{}])[0].get("name", "value")
            components.insert(1, {
                "type": "chart",
                "title": "Overview",
                "span": 2,
                "config": {"chart_type": "bar", "columns": [first_col], "aggregation": "sum"}
            })

        # ensure layout_grid
        if "layout_grid" not in blueprint:
            blueprint["layout_grid"] = "repeat(4, 1fr)"

        return blueprint

    # ---------------------------------------------------------
    # Context builder
    # ---------------------------------------------------------
    def _create_dataset_context_string(self, metadata: Dict) -> str:
        overview = metadata.get("dataset_overview", {})
        colmeta = metadata.get("column_metadata", [])

        cols = [f"{c.get('name')} ({c.get('type')})" for c in colmeta[:15]]

        context = (
            f"Rows: {overview.get('total_rows', 'N/A')}, "
            f"Columns: {overview.get('total_columns', 'N/A')}\n"
            f"Columns: {', '.join(cols)}"
        )

        if len(colmeta) > 15:
            context += f"\n... +{len(colmeta) - 15} more columns"

        return context

    # ---------------------------------------------------------
    async def get_available_patterns(self) -> Dict[str, Any]:
        return {
            "patterns": [
                {"id": pid, "name": p["name"], "use_cases": p["use_cases"]}
                for pid, p in self.design_patterns.items()
            ]
        }


# Singleton instance
ai_designer_service = AIDesignerService()
