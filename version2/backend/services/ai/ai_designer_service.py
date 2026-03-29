# backend/services/ai/ai_designer_service.py

import logging
import json
import re
import inspect
import concurrent.futures
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

from db.database import get_database
from services.llm_router import llm_router
from core.prompt_templates import get_dashboard_designer_prompt

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

    def __init__(self, sync_db=None):
        """
        Initialize AIDesignerService.

        Args:
            sync_db: Optional sync MongoDB database instance. If provided (e.g., from Celery worker),
                     uses this directly. Otherwise, uses async get_database() (for FastAPI).
        """
        self._db = sync_db  # Use provided sync DB if in Celery context

        # --- FEW-SHOT DESIGN PATTERNS ---
        self.design_patterns = {
            "executive_kpi_trend": {
                "name": "Executive KPI & Trend Dashboard",
                "use_cases": ["sales", "marketing", "finance", "performance"],
                "blueprint": {
                    "layout_grid": "repeat(4, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total Revenue",
                            "span": 1,
                            "config": {"column": "revenue", "aggregation": "sum"},
                        },
                        {
                            "type": "kpi",
                            "title": "Total Customers",
                            "span": 1,
                            "config": {"column": "customer_id", "aggregation": "count"},
                        },
                        {
                            "type": "kpi",
                            "title": "Average Order",
                            "span": 1,
                            "config": {"column": "order_value", "aggregation": "mean"},
                        },
                        {
                            "type": "kpi",
                            "title": "Growth Rate",
                            "span": 1,
                            "config": {"column": "growth", "aggregation": "mean"},
                        },
                        {
                            "type": "chart",
                            "title": "Revenue Trend Over Time",
                            "span": 3,
                            "config": {
                                "chart_type": "line",
                                "columns": ["date", "revenue"],
                                "aggregation": "sum",
                                "group_by": ["date"],
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Revenue by Category",
                            "span": 1,
                            "config": {
                                "chart_type": "pie",
                                "columns": ["category", "revenue"],
                                "aggregation": "sum",
                                "group_by": ["category"],
                            },
                        },
                        {
                            "type": "table",
                            "title": "Recent Transactions",
                            "span": 4,
                            "config": {
                                "columns": [
                                    "id",
                                    "customer",
                                    "date",
                                    "amount",
                                    "status",
                                ]
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Executive dashboards prioritize KPIs, trend analysis and summary insights. "
                    "Lead with metrics, tell the story with time series, and provide detail in tables."
                ),
            },
            "comparative_analysis": {
                "name": "Comparative Analysis Dashboard",
                "use_cases": [
                    "logistics",
                    "inventory",
                    "product_comparison",
                    "regional_analysis",
                ],
                "blueprint": {
                    "layout_grid": "repeat(3, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total Items",
                            "span": 1,
                            "config": {"column": "item_count", "aggregation": "count"},
                        },
                        {
                            "type": "kpi",
                            "title": "Average Performance",
                            "span": 1,
                            "config": {"column": "performance", "aggregation": "mean"},
                        },
                        {
                            "type": "kpi",
                            "title": "Top Performer",
                            "span": 1,
                            "config": {"column": "top_score", "aggregation": "first"},
                        },
                        {
                            "type": "chart",
                            "title": "Performance by Category",
                            "span": 2,
                            "config": {
                                "chart_type": "grouped_bar",
                                "columns": ["category", "performance"],
                                "aggregation": "mean",
                                "group_by": ["category"],
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Distribution",
                            "span": 1,
                            "config": {
                                "chart_type": "histogram",
                                "columns": ["performance"],
                                "aggregation": "none",
                            },
                        },
                        {
                            "type": "table",
                            "title": "Detailed Comparison",
                            "span": 3,
                            "config": {
                                "columns": [
                                    "item",
                                    "category",
                                    "performance",
                                    "rank",
                                    "change",
                                ]
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Comparative dashboards focus on relative performance. "
                    "Use grouped bars for comparison, histograms for distributions, "
                    "and ranking tables for details."
                ),
            },
            "entity_breakdown": {
                "name": "Entity Breakdown Dashboard",
                "use_cases": [
                    "student_profile",
                    "product_details",
                    "campaign_analysis",
                    "customer_profile",
                ],
                "blueprint": {
                    "layout_grid": "repeat(2, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Entity ID",
                            "span": 1,
                            "config": {"column": "entity_id", "aggregation": "count"},
                        },
                        {
                            "type": "kpi",
                            "title": "Status",
                            "span": 1,
                            "config": {"column": "status", "aggregation": "count"},
                        },
                        {
                            "type": "chart",
                            "title": "Performance Over Time",
                            "span": 1,
                            "config": {
                                "chart_type": "line",
                                "columns": ["date", "score"],
                                "aggregation": "mean",
                                "group_by": ["date"],
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Category Breakdown",
                            "span": 1,
                            "config": {
                                "chart_type": "bar",
                                "columns": ["category", "count"],
                                "aggregation": "count",
                                "group_by": ["category"],
                            },
                        },
                        {
                            "type": "table",
                            "title": "Recent Activity",
                            "span": 2,
                            "config": {
                                "columns": ["date", "event", "details", "impact"]
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Entity dashboards provide deep-dive analysis across multiple dimensions."
                ),
            },
            # ─────────────────────────────────────────────────────────────────────
            # UNIVERSAL META-PATTERNS
            # These patterns work for ANY dataset regardless of domain
            # Selected based on data fingerprint (temporal, categorical, numeric)
            # ─────────────────────────────────────────────────────────────────────
            "temporal_overview": {
                "name": "Temporal Overview Dashboard",
                "use_cases": ["universal", "any_dataset_with_time"],
                "is_universal": True,
                "trigger_conditions": ["has_temporal", "complexity >= 4"],
                "blueprint": {
                    "layout_grid": "repeat(4, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total Records",
                            "span": 1,
                            "config": {"column": "id", "aggregation": "count"},
                        },
                        {
                            "type": "kpi",
                            "title": "First Value",
                            "span": 1,
                            "config": {"column": None, "aggregation": "first_numeric"},
                        },
                        {
                            "type": "kpi",
                            "title": "Latest Value",
                            "span": 1,
                            "config": {"column": None, "aggregation": "last_numeric"},
                        },
                        {
                            "type": "kpi",
                            "title": "Change",
                            "span": 1,
                            "config": {"column": None, "aggregation": "change_pct"},
                        },
                        {
                            "type": "chart",
                            "title": "Trend Over Time",
                            "span": 4,
                            "config": {
                                "chart_type": "line",
                                "columns": ["temporal_column", "numeric_column"],
                                "aggregation": "sum",
                                "group_by": ["temporal_column"],
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Distribution",
                            "span": 2,
                            "config": {
                                "chart_type": "histogram",
                                "columns": ["numeric_column"],
                                "aggregation": "none",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Breakdown",
                            "span": 2,
                            "config": {
                                "chart_type": "bar",
                                "columns": ["categorical_column", "numeric_column"],
                                "aggregation": "mean",
                                "group_by": ["categorical_column"],
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Temporal dashboards show how metrics evolve over time. "
                    "Use line charts for trends, histograms for distributions, "
                    "and KPIs to highlight key measurements."
                ),
            },
            "trend_comparison": {
                "name": "Trend & Comparison Dashboard",
                "use_cases": ["universal", "time_series_with_segments"],
                "is_universal": True,
                "trigger_conditions": ["has_temporal", "has_categorical"],
                "blueprint": {
                    "layout_grid": "repeat(4, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total",
                            "span": 1,
                            "config": {"column": None, "aggregation": "sum"},
                        },
                        {
                            "type": "kpi",
                            "title": "Average",
                            "span": 1,
                            "config": {"column": None, "aggregation": "mean"},
                        },
                        {
                            "type": "kpi",
                            "title": "Segments",
                            "span": 1,
                            "config": {
                                "column": "categorical_column",
                                "aggregation": "count_unique",
                            },
                        },
                        {
                            "type": "kpi",
                            "title": "Trend",
                            "span": 1,
                            "config": {
                                "column": None,
                                "aggregation": "trend_direction",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Overall Trend",
                            "span": 2,
                            "config": {
                                "chart_type": "line",
                                "columns": ["temporal_column", "numeric_column"],
                                "aggregation": "sum",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "By Segment",
                            "span": 2,
                            "config": {
                                "chart_type": "line",
                                "columns": [
                                    "temporal_column",
                                    "categorical_column",
                                    "numeric_column",
                                ],
                                "aggregation": "sum",
                                "group_by": ["categorical_column"],
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Segment Comparison",
                            "span": 4,
                            "config": {
                                "chart_type": "grouped_bar",
                                "columns": ["categorical_column", "numeric_column"],
                                "aggregation": "mean",
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Combine time trends with segment comparisons. "
                    "Use line charts for temporal analysis, grouped bars for segment comparison."
                ),
            },
            "segmentation_dashboard": {
                "name": "Segmentation Dashboard",
                "use_cases": ["universal", "categorical_data"],
                "is_universal": True,
                "trigger_conditions": ["has_categorical", "low_cardinality"],
                "blueprint": {
                    "layout_grid": "repeat(3, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total Segments",
                            "span": 1,
                            "config": {
                                "column": "categorical_column",
                                "aggregation": "count_unique",
                            },
                        },
                        {
                            "type": "kpi",
                            "title": "Largest Segment",
                            "span": 1,
                            "config": {
                                "column": "categorical_column",
                                "aggregation": "mode",
                            },
                        },
                        {
                            "type": "kpi",
                            "title": "Avg Per Segment",
                            "span": 1,
                            "config": {
                                "column": "numeric_column",
                                "aggregation": "mean",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Segment Distribution",
                            "span": 2,
                            "config": {
                                "chart_type": "bar",
                                "columns": ["categorical_column"],
                                "aggregation": "count",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Segment Performance",
                            "span": 1,
                            "config": {
                                "chart_type": "pie",
                                "columns": ["categorical_column", "numeric_column"],
                                "aggregation": "sum",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Segment Details",
                            "span": 3,
                            "config": {
                                "chart_type": "grouped_bar",
                                "columns": ["categorical_column", "numeric_column"],
                                "aggregation": "mean",
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Segmentation dashboards highlight how data is distributed across categories. "
                    "Use bar charts for counts, pie charts for composition, "
                    "and grouped bars for segment comparison."
                ),
            },
            "multivariate_analysis": {
                "name": "Multivariate Analysis Dashboard",
                "use_cases": ["universal", "complex_numeric"],
                "is_universal": True,
                "trigger_conditions": ["numeric_count >= 3", "complexity >= 5"],
                "blueprint": {
                    "layout_grid": "repeat(3, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Correlation",
                            "span": 1,
                            "config": {
                                "column": "numeric_column_1",
                                "aggregation": "correlation",
                            },
                        },
                        {
                            "type": "kpi",
                            "title": "Variables",
                            "span": 1,
                            "config": {
                                "column": "numeric_column_1",
                                "aggregation": "count",
                            },
                        },
                        {
                            "type": "kpi",
                            "title": "Outliers",
                            "span": 1,
                            "config": {
                                "column": "numeric_column_1",
                                "aggregation": "outlier_count",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Correlation Matrix",
                            "span": 3,
                            "config": {
                                "chart_type": "heatmap",
                                "columns": ["numeric_columns"],
                                "aggregation": "correlation",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Relationship",
                            "span": 2,
                            "config": {
                                "chart_type": "scatter",
                                "columns": ["numeric_column_1", "numeric_column_2"],
                                "aggregation": "none",
                            },
                        },
                        {
                            "type": "chart",
                            "title": "Distribution",
                            "span": 1,
                            "config": {
                                "chart_type": "box",
                                "columns": ["numeric_column_1"],
                                "aggregation": "none",
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Multivariate dashboards explore relationships between multiple numeric variables. "
                    "Use scatter plots for relationships, heatmaps for correlations, "
                    "and box plots for distributions."
                ),
            },
            "simple_overview": {
                "name": "Simple Overview Dashboard",
                "use_cases": ["universal", "any_simple_dataset"],
                "is_universal": True,
                "trigger_conditions": ["complexity <= 3", "any_basic_data"],
                "blueprint": {
                    "layout_grid": "repeat(2, 1fr)",
                    "components": [
                        {
                            "type": "kpi",
                            "title": "Total Records",
                            "span": 1,
                            "config": {"column": "id", "aggregation": "count"},
                        },
                        {
                            "type": "kpi",
                            "title": "Key Metric",
                            "span": 1,
                            "config": {"column": None, "aggregation": "sum"},
                        },
                        {
                            "type": "chart",
                            "title": "Overview",
                            "span": 2,
                            "config": {
                                "chart_type": "bar",
                                "columns": ["categorical_column", "numeric_column"],
                                "aggregation": "sum",
                            },
                        },
                    ],
                },
                "style_guide": (
                    "Simple dashboards provide a basic overview of the data. "
                    "Use KPIs for key metrics and a single bar chart for distribution."
                ),
            },
        }

    @property
    def db(self):
        """Lazy database initialization to avoid None during startup"""
        if self._db is None:
            self._db = get_database()
        return self._db

    @property
    def _is_async_db(self) -> bool:
        """Check if db is async (Motor) vs sync (PyMongo)."""
        db = self._db if self._db is not None else get_database()
        if db is None:
            return True
        db_type = type(db).__name__
        return (
            "Async" in db_type
            or hasattr(db, "find_one")
            and inspect.iscoroutinefunction(db.find_one)
        )

    async def _db_op(self, operation, *args, **kwargs):
        """
        Bridge method that handles both sync and async DB operations.

        In Celery workers with sync DB (PyMongo), runs sync code directly.
        In FastAPI with async DB (Motor), awaits async operations.
        """
        if self._is_async_db:
            return await operation(*args, **kwargs)
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(operation, *args, **kwargs)
                return future.result()

    # ---------------------------------------------------------
    # UTILITY: GET EXISTING DASHBOARD
    # ---------------------------------------------------------
    async def get_existing_dashboard(
        self, dataset_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch existing dashboard for a dataset without regenerating.

        Returns:
            Dashboard data if exists, None otherwise
        """
        try:
            dashboard = await self._db_op(
                self.db.dashboards.find_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
            )

            if dashboard:
                return {
                    "dashboard_blueprint": dashboard.get("blueprint"),
                    "design_pattern": dashboard.get("design_pattern"),
                    "pattern_name": self.design_patterns.get(
                        dashboard.get("design_pattern"), {}
                    ).get("name"),
                    "reasoning": "Loaded from cache",
                    "cached": True,
                    "created_at": dashboard.get("created_at"),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching existing dashboard: {e}")
            return None

    # ---------------------------------------------------------
    # UTILITY: UPDATE COMPONENT CONFIG
    # ---------------------------------------------------------
    async def update_dashboard_component(
        self,
        dataset_id: str,
        user_id: str,
        component_title: str,
        updated_config: Dict[str, Any],
    ) -> bool:
        """
        Update a single component's configuration in the existing dashboard.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier
            component_title: Title of the component to update
            updated_config: The new configuration dictionary

        Returns:
            bool: Success status
        """
        try:
            dashboard = await self._db_op(
                self.db.dashboards.find_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
            )

            if not dashboard or "blueprint" not in dashboard:
                logger.warning(
                    f"Cannot update component: No dashboard found for dataset {dataset_id}"
                )
                return False

            blueprint = dashboard["blueprint"]
            components = blueprint.get("components", [])

            updated = False
            for comp in components:
                if comp.get("title") == component_title:
                    comp["config"] = updated_config
                    updated = True
                    break

            if not updated:
                logger.warning(
                    f"Component '{component_title}' not found in dashboard for dataset {dataset_id}"
                )
                return False

            await self._db_op(
                self.db.dashboards.update_one,
                {"_id": dashboard["_id"]},
                {"$set": {"blueprint": blueprint, "updated_at": datetime.utcnow()}},
            )

            logger.info(
                f"Updated component '{component_title}' in dashboard for dataset {dataset_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Error updating component '{component_title}': {e}")
            return False

    # ---------------------------------------------------------
    # MAIN ENTRY: DESIGN DASHBOARD
    # ---------------------------------------------------------
    async def design_intelligent_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        design_preference: Optional[str] = None,
        force_regenerate: bool = False,
        conversation_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Design an intelligent dashboard for a dataset.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier
            design_preference: Optional pattern preference
            force_regenerate: If True, regenerate even if dashboard exists. If False (default), return cached dashboard.
            conversation_summary: Optional summary of prior conversation for context-aware design

        Returns:
            Dashboard blueprint with pattern info
        """
        try:
            # Safe ObjectId handling
            try:
                dataset_oid = ObjectId(dataset_id)
                query = {"_id": dataset_oid, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            dataset_doc = await self._db_op(self.db.uploads.find_one, query)

            if not dataset_doc or not dataset_doc.get("metadata"):
                raise RuntimeError(
                    "Dataset metadata missing — cannot design dashboard."
                )

            # CHECK FOR EXISTING DASHBOARD (unless force_regenerate is True)
            if not force_regenerate:
                existing_dashboard = await self._db_op(
                    self.db.dashboards.find_one,
                    {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                )

                if existing_dashboard:
                    logger.info(
                        f"Found existing dashboard for dataset {dataset_id}, returning cached version"
                    )
                    return {
                        "dashboard_blueprint": existing_dashboard.get("blueprint"),
                        "design_pattern": existing_dashboard.get("design_pattern"),
                        "pattern_name": self.design_patterns.get(
                            existing_dashboard.get("design_pattern"), {}
                        ).get("name"),
                        "reasoning": "Loaded from cache (previously generated)",
                        "cached": True,
                        "created_at": existing_dashboard.get("created_at"),
                    }
                else:
                    logger.info(
                        f"No existing dashboard found for dataset {dataset_id}, generating new one"
                    )

            metadata = dataset_doc["metadata"]

            # 1. choose pattern
            best_pattern = await self._analyze_dataset_for_pattern(
                metadata, design_preference
            )
            pattern = self.design_patterns.get(best_pattern) or next(
                iter(self.design_patterns.values())
            )

            # 2. Build dataset context for AI
            dataset_context = self._create_dataset_context_string(metadata)

            # 3. Generate dashboard using Multi-Agent Pipeline (NEW!)
            # Uses 5 specialized OpenRouter models for better quality
            ai_reasoning = "AI-generated blueprint"  # Default reasoning

            try:
                from services.ai.multi_agent_orchestrator import (
                    multi_agent_orchestrator,
                )

                logger.info(
                    "🤖 Using Multi-Agent Pipeline for dashboard design (5 specialized models)"
                )

                result = await multi_agent_orchestrator.design_dashboard_multi_agent(
                    dataset_context=dataset_context,
                    metadata=metadata,
                    design_preference=best_pattern,
                    conversation_summary=conversation_summary,
                )

                if result.get("success"):
                    raw_blueprint = result["blueprint"]

                    # 4. Rigorous validation of the multi-agent blueprint
                    blueprint = self._validate_and_enhance_design(
                        raw_blueprint, metadata, pattern
                    )

                    ai_metadata = result.get("metadata", {})
                    component_count = len((blueprint or {}).get("components", []))
                    if component_count == 0:
                        raise RuntimeError(
                            "Multi-agent pipeline returned empty blueprint after validation"
                        )
                    ai_reasoning = f"Multi-agent pipeline: {ai_metadata.get('chart_count', 0)} charts, {ai_metadata.get('kpi_count', 0)} KPIs in {ai_metadata.get('pipeline_duration_seconds', 0):.1f}s"
                    logger.info(
                        f"✅ Multi-agent pipeline completed in {ai_metadata.get('pipeline_duration_seconds', 0):.2f}s"
                    )
                    logger.info(
                        f"📊 Generated {ai_metadata.get('chart_count', 0)} charts, "
                        f"{ai_metadata.get('kpi_count', 0)} KPIs, {component_count} components"
                    )
                else:
                    raise Exception("Multi-agent pipeline returned unsuccessful result")

            except Exception as multi_agent_error:
                logger.warning(f"⚠️ Multi-agent pipeline failed: {multi_agent_error}")
                error_text = str(multi_agent_error).lower()
                is_auth_error = (
                    "401" in error_text
                    or "403" in error_text
                    or "authentication failed" in error_text
                    or "openrouter authentication" in error_text
                )

                if is_auth_error:
                    logger.warning(
                        "🔐 OpenRouter auth issue detected; using data-aware pattern fallback"
                    )
                    blueprint = self._adapt_pattern_to_data(
                        pattern["blueprint"], metadata
                    )
                    ai_reasoning = "Pattern fallback (OpenRouter authentication failure) — columns adapted to dataset"
                else:
                    logger.info("↩️ Falling back to single-model approach")

                    prompt = self._create_designer_prompt(metadata, pattern)

                    try:
                        ai_output = await llm_router.call(
                            prompt, model_role="layout_designer", expect_json=True
                        )
                        full_response = json.dumps(ai_output, indent=2)
                        logger.info(
                            f"AI Designer LLM Response (first 800 chars): {full_response[:800]}"
                        )
                        if len(full_response) > 800:
                            logger.info(
                                f"AI Designer LLM Response (remaining): {full_response[800:]}"
                            )
                    except Exception as e:
                        logger.exception(
                            f"LLM call failed: {e}; falling back to pattern blueprint"
                        )
                        ai_output = {
                            "dashboard": pattern["blueprint"],
                            "reasoning": "fallback LLM failure",
                        }

                    # 4. repair
                    blueprint = self._validate_and_enhance_design(
                        ai_output.get("dashboard", {}), metadata, pattern
                    )

            # 5. persist (use upsert to avoid duplicates on regeneration)
            design_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "design_pattern": best_pattern,
                "blueprint": blueprint,
                "created_at": datetime.utcnow(),
                "is_default": True,
            }

            # Use update_one with upsert to replace existing or create new
            await self._db_op(
                self.db.dashboards.update_one,
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                {"$set": design_doc},
                upsert=True,
            )

            # --- FIX: Update artifact_status in datasets collection so frontend knows we are ready ---
            try:
                await self._db_op(
                    self.db.uploads.update_one,
                    query,
                    {
                        "$set": {
                            "artifact_status.dashboard_design": "ready",
                            "artifact_status.dashboard_generated_at": datetime.utcnow(),
                        }
                    },
                )
                logger.info(
                    f"Updated artifact_status to 'ready' for dataset {dataset_id}"
                )
            except Exception as status_err:
                logger.warning(
                    f"Failed to update artifact_status (non-fatal): {status_err}"
                )

            logger.info(
                f"{'Regenerated' if force_regenerate else 'Created'} dashboard for dataset {dataset_id}"
            )

            return {
                "dashboard_blueprint": blueprint,
                "design_pattern": best_pattern,
                "pattern_name": pattern.get("name"),
                "reasoning": ai_reasoning,
                "cached": False,
                "created_at": design_doc["created_at"],
            }

        except Exception as e:
            logger.exception("AI Designer error")
            raise RuntimeError(f"Failed to design dashboard: {e}") from e

    # ---------------------------------------------------------
    # Pattern selection
    # ---------------------------------------------------------
    async def _analyze_dataset_for_pattern(
        self, metadata: Dict, preference: Optional[str]
    ) -> str:
        """
        Select the best pattern for the dataset.

        Priority:
        1. User preference (if valid)
        2. Universal patterns (based on data fingerprint)
        3. Domain-specific patterns (fallback)
        """
        if preference in self.design_patterns:
            return preference

        colmeta = metadata.get("column_metadata", [])
        overview = metadata.get("dataset_overview", {})
        data_profile = metadata.get("data_profile", {})

        total_rows = overview.get("total_rows", 0)

        numeric = sum(
            1
            for c in colmeta
            if c.get("type") in ("numeric", "integer", "float", "int")
        )
        categorical = sum(
            1 for c in colmeta if c.get("type") in ("string", "categorical", "utf8")
        )
        temporal = sum(
            1 for c in colmeta if c.get("type") in ("date", "datetime", "timestamp")
        )

        # Calculate complexity score
        complexity = 0
        if numeric >= 3:
            complexity += 3
        elif numeric >= 1:
            complexity += 1
        if categorical >= 2:
            complexity += 2
        if temporal >= 1:
            complexity += 2
        if total_rows > 10000:
            complexity += 2
        elif total_rows > 1000:
            complexity += 1

        # Check for low cardinality categorical columns (good for grouping)
        low_cardinality_cols = data_profile.get("low_cardinality_dims", [])
        has_grouping = len(low_cardinality_cols) > 0

        # ─────────────────────────────────────────────────────────────────────
        # UNIVERSAL PATTERN SELECTION (preferred for any dataset)
        # ─────────────────────────────────────────────────────────────────────

        # Universal Pattern 1: Temporal Overview
        if temporal > 0 and complexity >= 4:
            logger.info(
                f"Pattern selected: temporal_overview (temporal={temporal}, complexity={complexity})"
            )
            return "temporal_overview"

        # Universal Pattern 2: Trend & Comparison
        if temporal > 0 and (categorical >= 1 or has_grouping):
            logger.info(
                f"Pattern selected: trend_comparison (temporal={temporal}, categorical={categorical})"
            )
            return "trend_comparison"

        # Universal Pattern 3: Segmentation Dashboard
        if has_grouping and categorical >= 1:
            logger.info(
                f"Pattern selected: segmentation_dashboard (has_grouping={has_grouping})"
            )
            return "segmentation_dashboard"

        # Universal Pattern 4: Multivariate Analysis
        if numeric >= 3 and complexity >= 5:
            logger.info(
                f"Pattern selected: multivariate_analysis (numeric={numeric}, complexity={complexity})"
            )
            return "multivariate_analysis"

        # Universal Pattern 5: Simple Overview
        if complexity <= 3:
            logger.info(f"Pattern selected: simple_overview (complexity={complexity})")
            return "simple_overview"

        # ─────────────────────────────────────────────────────────────────────
        # LEGACY DOMAIN-SPECIFIC PATTERNS (fallback)
        # ─────────────────────────────────────────────────────────────────────
        if temporal > 0 and numeric >= 2:
            return "executive_kpi_trend"
        if categorical >= 2 and numeric >= 1:
            return "comparative_analysis"
        if total_rows < 1000 and categorical >= 1:
            return "entity_breakdown"

        # Ultimate fallback
        return "simple_overview"

    # ---------------------------------------------------------
    # Prompt generation
    # ---------------------------------------------------------
    def _create_designer_prompt(self, metadata: Dict, selected_pattern: Dict) -> str:
        context = self._create_dataset_context_string(metadata)
        example_blueprint = json.dumps(selected_pattern["blueprint"], indent=2)
        return get_dashboard_designer_prompt(context, example_blueprint)

    # ---------------------------------------------------------
    # Blueprint validation / repair
    # ---------------------------------------------------------
    def _validate_and_enhance_design(
        self, blueprint: Dict, metadata: Dict, pattern: Dict
    ) -> Dict:
        """
        Validates the structure of the blueprint and then passes it through
        a rigorous data-aware validation layer to remove hallucinated columns
        and enforce cardinality limits.
        """
        # Handle nested structure (some LLMs return {dashboard: {components: [...]}})
        if (
            blueprint
            and "dashboard" in blueprint
            and isinstance(blueprint["dashboard"], dict)
        ):
            logger.info("Detected nested 'dashboard' key, extracting inner blueprint")
            blueprint = blueprint["dashboard"]

        if not blueprint or "components" not in blueprint:
            logger.warning(
                f"Invalid AI blueprint. Blueprint keys: {list(blueprint.keys()) if blueprint else 'None'}. Using fallback pattern."
            )
            blueprint = json.loads(json.dumps(pattern["blueprint"]))

        components = blueprint.get("components", [])

        # Rigorous Data-Aware Validation Pass
        valid_components = []
        for comp in components:
            validated_comp = self._validate_blueprint_component_with_data_stats(
                comp, metadata
            )
            if validated_comp:
                valid_components.append(validated_comp)

        blueprint["components"] = valid_components

        types = [c.get("type") for c in valid_components]

        # ensure KPI exists
        if "kpi" not in types:
            blueprint["components"].insert(
                0,
                {
                    "type": "kpi",
                    "title": "Total Records",
                    "span": 1,
                    "config": {"column": "id", "aggregation": "count"},
                    "_fallbackReason": "Added fallback KPI because none were found.",
                },
            )

        # ensure chart exists
        if "chart" not in types:
            first_col = (metadata.get("column_metadata") or [{}])[0].get(
                "name", "value"
            )
            blueprint["components"].insert(
                1,
                {
                    "type": "chart",
                    "title": "Overview",
                    "span": 2,
                    "config": {
                        "chart_type": "bar",
                        "columns": [first_col],
                        "aggregation": "sum",
                    },
                    "_fallbackReason": "Added fallback Chart because none were found.",
                },
            )

        # ensure layout_grid
        if "layout_grid" not in blueprint:
            blueprint["layout_grid"] = "repeat(4, 1fr)"

        return blueprint

    def _validate_blueprint_component_with_data_stats(
        self, comp: Dict, metadata: Dict
    ) -> Optional[Dict]:
        """
        Deep validation for a single dashboard component.
        - Resolves fuzzy/hallucinated column names to EXACT dataset column names.
        - Enforces cardinality restrictions (e.g. no pie chart on a highly cardinal column).
        - Attaches `_fallbackReason` when changing the AI's intent.

        Returns the validated component, or None if it's completely unrecoverable.
        """
        colmeta = metadata.get("column_metadata", [])
        valid_col_names = [c["name"] for c in colmeta if c.get("name")]
        valid_col_names_lower = {name.lower().strip(): name for name in valid_col_names}

        def resolve_column(requested_col: str) -> Optional[str]:
            if not requested_col:
                return None
            req_lower = str(requested_col).lower().strip()
            # 1. Exact match (case insensitive)
            if req_lower in valid_col_names_lower:
                return valid_col_names_lower[req_lower]
            # 2. Substring match
            for valid_lower, actual_name in valid_col_names_lower.items():
                if req_lower in valid_lower or valid_lower in req_lower:
                    return actual_name
            return None

        ctype = comp.get("type", "")
        cfg = comp.get("config", {})

        fallback_reasons = []

        if ctype == "kpi":
            req_col = cfg.get("column")
            actual_col = resolve_column(req_col)
            if not actual_col:
                return None  # Drop KPI if the column doesn't exist at all
            if actual_col != req_col:
                fallback_reasons.append(
                    f"Mapped hallucinated column '{req_col}' to '{actual_col}'."
                )
            cfg["column"] = actual_col

        elif ctype == "chart":
            chart_type = cfg.get("chart_type", "bar")
            requested_cols = cfg.get("columns", [])

            # Resolve all columns
            actual_cols = []
            for c in requested_cols:
                resolved = resolve_column(c)
                if resolved:
                    actual_cols.append(resolved)
                else:
                    fallback_reasons.append(f"Dropped hallucinated column '{c}'.")

            if not actual_cols:
                return None  # Unrecoverable chart

            cfg["columns"] = actual_cols
            cfg["x"] = resolve_column(cfg.get("x")) or (
                actual_cols[0] if len(actual_cols) > 0 else None
            )
            cfg["y"] = resolve_column(cfg.get("y")) or (
                actual_cols[1] if len(actual_cols) > 1 else None
            )

            if cfg.get("group_by"):
                resolved_group = [resolve_column(g) for g in cfg["group_by"]]
                cfg["group_by"] = [g for g in resolved_group if g]

            # Enforce Cardinality Limits for Pie Charts
            if chart_type in ["pie", "pie_chart", "donut"]:
                data_profile = metadata.get("data_profile", {})
                cardinality_map = data_profile.get("cardinality", {})

                # Check the grouping column (usually x)
                group_col = cfg.get("x") or cfg["columns"][0]
                if group_col in cardinality_map:
                    unique_count = cardinality_map[group_col].get("unique_count", 0)
                    if unique_count > 15:
                        cfg["chart_type"] = "bar"
                        fallback_reasons.append(
                            f"Pie chart changed to Bar chart because '{group_col}' has high cardinality ({unique_count} > 15)."
                        )

        comp["config"] = cfg
        if fallback_reasons:
            comp["_fallbackReason"] = " | ".join(fallback_reasons)

        return comp

    # ---------------------------------------------------------
    # Context builder (enriched with pre-computed metadata)
    # ---------------------------------------------------------
    def _adapt_pattern_to_data(self, pattern_blueprint: Dict, metadata: Dict) -> Dict:
        """
        Substitute real dataset column names into a canned pattern blueprint.

        The pattern blueprints use generic column names like 'revenue', 'category',
        'date' which won't match real datasets. This method replaces them with
        actual column names from the dataset metadata.
        """
        blueprint = json.loads(json.dumps(pattern_blueprint))  # Deep copy

        colmeta = metadata.get("column_metadata", [])
        if not colmeta:
            return blueprint

        # Classify columns by type
        numeric_cols = [
            c["name"]
            for c in colmeta
            if c.get("type") in ("numeric", "integer", "float", "int")
            and "id" not in c.get("name", "").lower()
        ]
        categorical_cols = [
            c["name"]
            for c in colmeta
            if c.get("type") in ("string", "categorical", "utf8")
            and "id" not in c.get("name", "").lower()
        ]
        temporal_cols = [
            c["name"]
            for c in colmeta
            if c.get("type") in ("date", "datetime", "timestamp")
        ]
        all_cols = [c["name"] for c in colmeta[:6] if c.get("name")]

        # Use domain intelligence if available for better column choices
        domain = metadata.get("domain_intelligence", {})
        measures = domain.get("measures", numeric_cols[:6])
        dimensions = domain.get("dimensions", categorical_cols[:4])
        time_cols = domain.get("time_columns", temporal_cols[:2])

        ni = 0  # numeric index
        ci = 0  # categorical index

        for comp in blueprint.get("components", []):
            cfg = comp.get("config", {})
            ctype = comp.get("type", "")

            if ctype == "kpi":
                # Assign real numeric column for aggregation
                if ni < len(measures):
                    cfg["column"] = measures[ni]
                    ni += 1
                elif numeric_cols:
                    cfg["column"] = numeric_cols[0]

            elif ctype == "chart":
                chart_type = cfg.get("chart_type", "bar")

                if chart_type in ("line", "area") and time_cols:
                    # Time-series charts → use time column on x-axis
                    cfg["columns"] = [
                        time_cols[0],
                        measures[min(ni, len(measures) - 1)]
                        if measures
                        else numeric_cols[0]
                        if numeric_cols
                        else all_cols[0],
                    ]
                    cfg["group_by"] = [time_cols[0]]
                    ni = min(ni + 1, len(measures) - 1)
                elif chart_type in ("pie",) and dimensions:
                    cfg["columns"] = [
                        dimensions[min(ci, len(dimensions) - 1)],
                        measures[0] if measures else all_cols[0],
                    ]
                    cfg["group_by"] = [dimensions[min(ci, len(dimensions) - 1)]]
                    ci = min(ci + 1, len(dimensions) - 1)
                elif chart_type in ("histogram", "box_plot", "violin") and measures:
                    cfg["columns"] = [measures[min(ni, len(measures) - 1)]]
                    ni = min(ni + 1, len(measures) - 1)
                elif dimensions and measures:
                    # Bar / grouped_bar / scatter
                    cfg["columns"] = [
                        dimensions[min(ci, len(dimensions) - 1)],
                        measures[min(ni, len(measures) - 1)],
                    ]
                    cfg["group_by"] = [dimensions[min(ci, len(dimensions) - 1)]]
                    ci = min(ci + 1, len(dimensions) - 1)
                    ni = min(ni + 1, len(measures) - 1)

            elif ctype == "table":
                cfg["columns"] = all_cols

        return blueprint

    def _create_dataset_context_string(self, metadata: Dict) -> str:
        """
        Build a rich but compact dataset context string for LLM prompts.
        Uses all the metadata already computed during the upload pipeline:
        domain_intelligence, data_profile, deep_analysis, statistical_findings,
        chart_recommendations, and sample_data — so the LLM can make intelligent
        dashboard decisions without ever seeing raw data rows.

        Approximate token budget: ~400-800 tokens (well within any model's limit).
        """
        sections = []
        overview = metadata.get("dataset_overview", {})
        colmeta = metadata.get("column_metadata", [])
        domain_intel = metadata.get("domain_intelligence", {})
        data_profile = metadata.get("data_profile", {})
        deep_analysis = metadata.get("deep_analysis", {})
        statistical_findings = metadata.get("statistical_findings", {})
        if isinstance(statistical_findings, list):
            statistical_findings = {"findings": statistical_findings}
        cardinality = data_profile.get("cardinality", {})

        # --- Section 1: Overview ---
        sections.append(
            f"OVERVIEW: {overview.get('total_rows', 'N/A'):,} rows × "
            f"{overview.get('total_columns', 'N/A')} columns"
        )

        # --- Section 2: Domain Intelligence ---
        if domain_intel and domain_intel.get("domain", "general") != "general":
            domain_parts = [
                f"DOMAIN: {domain_intel['domain']} (confidence: {domain_intel.get('confidence', 0):.0%})"
            ]
            if domain_intel.get("key_metrics"):
                domain_parts.append(
                    f"  Key metrics: {', '.join(domain_intel['key_metrics'][:6])}"
                )
            if domain_intel.get("measures"):
                domain_parts.append(
                    f"  Measures (numeric for aggregation): {', '.join(domain_intel['measures'][:8])}"
                )
            if domain_intel.get("dimensions"):
                domain_parts.append(
                    f"  Dimensions (categorical for grouping): {', '.join(domain_intel['dimensions'][:8])}"
                )
            if domain_intel.get("time_columns"):
                domain_parts.append(
                    f"  Time columns: {', '.join(domain_intel['time_columns'][:4])}"
                )
            sections.append("\n".join(domain_parts))

        # --- Section 3: Columns with cardinality context ---
        def _fmt_num(v):
            if v is None:
                return "?"
            return str(int(v)) if float(v) == int(float(v)) else f"{v:.1f}"

        col_lines = []
        for c in colmeta[:30]:  # Cap at 30 columns
            col_name = c.get("name", "")
            col_type = c.get("type", "")
            sample_val = c.get("sample_value", "")
            if isinstance(sample_val, str) and len(sample_val) > 40:
                sample_val = sample_val[:40] + "…"

            card_info = cardinality.get(col_name, {})
            card_level = card_info.get("cardinality_level", "")
            unique_count = card_info.get("unique_count", c.get("unique_count", ""))

            # Build cardinality tag
            if card_level == "low":
                card_tag = f" [LOW-CARD: {unique_count} unique — good for grouping/pie]"
            elif card_level == "very_high":
                card_tag = (
                    f" [HIGH-CARD: {unique_count} unique — ID-like, skip for charts]"
                )
            elif card_level == "high":
                card_tag = f" [HIGH-CARD: {unique_count} unique — bad for pie/bar]"
            elif card_level == "medium":
                card_tag = f" [MED-CARD: {unique_count} unique]"
            else:
                card_tag = ""

            # Numeric columns: show range + mean (critical for binning decisions)
            num_summary = c.get("numeric_summary", {})
            if num_summary:
                lo = num_summary.get("min")
                hi = num_summary.get("max")
                mean = num_summary.get("mean")
                range_str = (
                    f" range={_fmt_num(lo)}–{_fmt_num(hi)}, mean={_fmt_num(mean)}"
                )
                # Flag continuous numeric (needs binning if used as x-axis)
                n_uniq = unique_count if isinstance(unique_count, int) else 0
                if n_uniq > 15:
                    range_str += " [CONTINUOUS — use line/area, not bar, as x-axis]"
                col_lines.append(f"  • {col_name} ({col_type}){card_tag}{range_str}")
                continue

            # Categorical/boolean: show actual unique values for low-cardinality columns
            top_values = c.get("top_values", [])
            if top_values and (
                card_level in ("low", "")
                or (isinstance(unique_count, int) and unique_count <= 15)
            ):
                vals = [str(v["value"]) for v in top_values[:8]]
                vals_str = f" values: {', '.join(vals)}"
                col_lines.append(f"  • {col_name} ({col_type}){card_tag}{vals_str}")
                continue

            col_lines.append(
                f"  • {col_name} ({col_type}){card_tag} — e.g. {sample_val}"
            )

        sections.append("COLUMNS:\n" + "\n".join(col_lines))
        if len(colmeta) > 30:
            sections.append(f"  ... +{len(colmeta) - 30} more columns")

        # --- Section 4: ID columns to skip ---
        id_cols = data_profile.get("id_columns", [])
        if id_cols:
            sections.append(
                f"SKIP COLUMNS (IDs, not useful for charts/KPIs): {', '.join(id_cols[:10])}"
            )

        # --- Section 5: Top correlations ---
        enhanced = deep_analysis.get("enhanced_analysis", {})
        correlations = enhanced.get("correlations", [])
        if correlations:
            corr_lines = ["KEY CORRELATIONS (use for scatter plots or related KPIs):"]
            for c in correlations[:5]:
                col1 = c.get("column1", "")
                col2 = c.get("column2", "")
                r = c.get("correlation", 0)
                strength = c.get("strength", "")
                corr_lines.append(f"  • {col1} ↔ {col2}: r={r:.3f} ({strength})")
            sections.append("\n".join(corr_lines))

        # --- Section 6: Distribution highlights ---
        distributions = enhanced.get("distributions", [])
        if distributions:
            skewed = [
                d
                for d in distributions
                if d.get("skewness") is not None and abs(d["skewness"]) > 1.5
            ]
            if skewed:
                skew_names = [
                    f"{d.get('column', '')} (skew={d.get('skewness', 0):.1f})"
                    for d in skewed[:5]
                ]
                sections.append(
                    f"SKEWED COLUMNS (consider log scale or median instead of mean): {', '.join(skew_names)}"
                )

        # --- Section 7: Statistical findings ---
        outlier_info = statistical_findings.get("outliers", [])
        if outlier_info:
            outlier_cols = [
                o.get("column", "") for o in outlier_info[:5] if o.get("column")
            ]
            if outlier_cols:
                sections.append(
                    f"OUTLIER COLUMNS (consider filtering or box plots): {', '.join(outlier_cols)}"
                )

        # --- Section 8: Executive summary (from deep analysis) ---
        exec_summary = deep_analysis.get("executive_summary", "")
        if exec_summary and isinstance(exec_summary, str) and len(exec_summary) > 20:
            # Truncate to ~200 chars to keep prompt compact
            truncated = (
                exec_summary[:300].rsplit(".", 1)[0] + "."
                if len(exec_summary) > 300
                else exec_summary
            )
            sections.append(f"EXECUTIVE SUMMARY: {truncated}")

        # --- Section 9: Pre-computed chart recommendations (from upload pipeline) ---
        chart_recs = metadata.get("chart_recommendations", [])
        if chart_recs:
            rec_lines = ["PRE-COMPUTED CHART SUGGESTIONS (from statistical analysis):"]
            for rec in chart_recs[:5]:
                chart_type = rec.get("chart_type", rec.get("type", ""))
                title = rec.get("title", "")
                cols = rec.get("columns", [])
                rec_lines.append(
                    f"  • {chart_type}: {title} — columns: {', '.join(cols) if isinstance(cols, list) else cols}"
                )
            sections.append("\n".join(rec_lines))

        return "\n\n".join(sections)

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
