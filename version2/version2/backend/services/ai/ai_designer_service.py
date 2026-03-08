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
    # UTILITY: GET EXISTING DASHBOARD
    # ---------------------------------------------------------
    async def get_existing_dashboard(self, dataset_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch existing dashboard for a dataset without regenerating.
        
        Returns:
            Dashboard data if exists, None otherwise
        """
        try:
            dashboard = await self.db.dashboards.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id,
                "is_default": True
            })
            
            if dashboard:
                return {
                    "dashboard_blueprint": dashboard.get("blueprint"),
                    "design_pattern": dashboard.get("design_pattern"),
                    "pattern_name": self.design_patterns.get(dashboard.get("design_pattern"), {}).get("name"),
                    "reasoning": "Loaded from cache",
                    "cached": True,
                    "created_at": dashboard.get("created_at")
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching existing dashboard: {e}")
            return None

    # ---------------------------------------------------------
    # MAIN ENTRY: DESIGN DASHBOARD
    # ---------------------------------------------------------
    async def design_intelligent_dashboard(
        self,
        dataset_id: str,
        user_id: str,
        design_preference: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Design an intelligent dashboard for a dataset.
        
        Args:
            dataset_id: Dataset identifier
            user_id: User identifier
            design_preference: Optional pattern preference
            force_regenerate: If True, regenerate even if dashboard exists. If False (default), return cached dashboard.
        
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

            dataset_doc = await self.db.datasets.find_one(query)

            if not dataset_doc or not dataset_doc.get("metadata"):
                raise RuntimeError("Dataset metadata missing — cannot design dashboard.")
            
            # CHECK FOR EXISTING DASHBOARD (unless force_regenerate is True)
            if not force_regenerate:
                existing_dashboard = await self.db.dashboards.find_one({
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "is_default": True
                })
                
                if existing_dashboard:
                    logger.info(f"Found existing dashboard for dataset {dataset_id}, returning cached version")
                    return {
                        "dashboard_blueprint": existing_dashboard.get("blueprint"),
                        "design_pattern": existing_dashboard.get("design_pattern"),
                        "pattern_name": self.design_patterns.get(existing_dashboard.get("design_pattern"), {}).get("name"),
                        "reasoning": "Loaded from cache (previously generated)",
                        "cached": True,
                        "created_at": existing_dashboard.get("created_at")
                    }
                else:
                    logger.info(f"No existing dashboard found for dataset {dataset_id}, generating new one")

            metadata = dataset_doc["metadata"]

            # 1. choose pattern
            best_pattern = await self._analyze_dataset_for_pattern(metadata, design_preference)
            pattern = self.design_patterns.get(best_pattern) or next(iter(self.design_patterns.values()))

            # 2. Build dataset context for AI
            dataset_context = self._create_dataset_context_string(metadata)

            # 3. Generate dashboard using Multi-Agent Pipeline (NEW!)
            # Uses 5 specialized OpenRouter models for better quality
            ai_reasoning = "AI-generated blueprint"  # Default reasoning
            
            try:
                from services.ai.multi_agent_orchestrator import multi_agent_orchestrator
                
                logger.info("🤖 Using Multi-Agent Pipeline for dashboard design (5 specialized models)")
                
                result = await multi_agent_orchestrator.design_dashboard_multi_agent(
                    dataset_context=dataset_context,
                    metadata=metadata,
                    design_preference=best_pattern
                )
                
                if result.get("success"):
                    blueprint = result["blueprint"]
                    ai_metadata = result.get("metadata", {})
                    component_count = len((blueprint or {}).get("components", []))
                    if component_count == 0:
                        raise RuntimeError("Multi-agent pipeline returned empty blueprint")
                    ai_reasoning = f"Multi-agent pipeline: {ai_metadata.get('chart_count', 0)} charts, {ai_metadata.get('kpi_count', 0)} KPIs in {ai_metadata.get('pipeline_duration_seconds', 0):.1f}s"
                    logger.info(f"✅ Multi-agent pipeline completed in {ai_metadata.get('pipeline_duration_seconds', 0):.2f}s")
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
                    logger.warning("🔐 OpenRouter auth issue detected; using deterministic pattern fallback")
                    blueprint = json.loads(json.dumps(pattern["blueprint"]))
                    ai_reasoning = "Pattern fallback (OpenRouter authentication failure)"
                else:
                    logger.info("↩️ Falling back to single-model approach")
                
                    prompt = self._create_designer_prompt(metadata, pattern)
                    
                    try:
                        ai_output = await llm_router.call(
                            prompt, model_role="layout_designer", expect_json=True
                        )
                        full_response = json.dumps(ai_output, indent=2)
                        logger.info(f"AI Designer LLM Response (first 800 chars): {full_response[:800]}")
                        if len(full_response) > 800:
                            logger.info(f"AI Designer LLM Response (remaining): {full_response[800:]}")
                    except Exception as e:
                        logger.exception(f"LLM call failed: {e}; falling back to pattern blueprint")
                        ai_output = {"dashboard": pattern["blueprint"], "reasoning": "fallback LLM failure"}

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
                "is_default": True
            }
            
            # Use update_one with upsert to replace existing or create new
            await self.db.dashboards.update_one(
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                {"$set": design_doc},
                upsert=True
            )
            
            logger.info(f"{'Regenerated' if force_regenerate else 'Created'} dashboard for dataset {dataset_id}")

            return {
                "dashboard_blueprint": blueprint,
                "design_pattern": best_pattern,
                "pattern_name": pattern.get("name"),
                "reasoning": ai_reasoning,
                "cached": False,
                "created_at": design_doc["created_at"]
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
You are DataSage Designer, a world-class dashboard layout architect specializing in data storytelling for non-technical users.

DATASET CONTEXT:
{context}

EXAMPLE BLUEPRINT (use this structure, but adapt columns and chart types based on the dataset):
{example_blueprint}

DESIGN RULES:
- Use LOW-CARD columns for pie charts and bar chart x-axes (few unique values = readable charts)
- NEVER use HIGH-CARD or ID columns for pie charts or bar charts (too many categories)
- Skip ID columns entirely — they are not useful for visualization
- Use time columns for line charts (show trends)
- Use correlated columns together in scatter plots
- KPI titles must be business-friendly ("Total Revenue" not "sum_revenue_col")
- Chart titles should describe the INSIGHT, not just the axes ("Revenue Concentration by Region" not "Region vs Revenue")

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
        # Handle nested structure (some LLMs return {dashboard: {components: [...]}})
        if blueprint and "dashboard" in blueprint and isinstance(blueprint["dashboard"], dict):
            logger.info("Detected nested 'dashboard' key, extracting inner blueprint")
            blueprint = blueprint["dashboard"]
        
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
    # Context builder (enriched with pre-computed metadata)
    # ---------------------------------------------------------
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
        cardinality = data_profile.get("cardinality", {})

        # --- Section 1: Overview ---
        sections.append(
            f"OVERVIEW: {overview.get('total_rows', 'N/A'):,} rows × "
            f"{overview.get('total_columns', 'N/A')} columns"
        )

        # --- Section 2: Domain Intelligence ---
        if domain_intel and domain_intel.get("domain", "general") != "general":
            domain_parts = [f"DOMAIN: {domain_intel['domain']} (confidence: {domain_intel.get('confidence', 0):.0%})"]
            if domain_intel.get("key_metrics"):
                domain_parts.append(f"  Key metrics: {', '.join(domain_intel['key_metrics'][:6])}")
            if domain_intel.get("measures"):
                domain_parts.append(f"  Measures (numeric for aggregation): {', '.join(domain_intel['measures'][:8])}")
            if domain_intel.get("dimensions"):
                domain_parts.append(f"  Dimensions (categorical for grouping): {', '.join(domain_intel['dimensions'][:8])}")
            if domain_intel.get("time_columns"):
                domain_parts.append(f"  Time columns: {', '.join(domain_intel['time_columns'][:4])}")
            sections.append("\n".join(domain_parts))

        # --- Section 3: Columns with cardinality context ---
        col_lines = []
        for c in colmeta[:30]:  # Cap at 30 columns
            col_name = c.get("name", "")
            col_type = c.get("type", "")
            sample_val = c.get("sample_value", "")
            # Truncate sample value
            if isinstance(sample_val, str) and len(sample_val) > 40:
                sample_val = sample_val[:40] + "…"

            # Add cardinality context if available
            card_info = cardinality.get(col_name, {})
            card_level = card_info.get("cardinality_level", "")
            unique_count = card_info.get("unique_count", "")

            card_tag = ""
            if card_level == "low":
                card_tag = f" [LOW-CARD: {unique_count} unique — good for grouping/pie]"
            elif card_level == "very_high":
                card_tag = f" [HIGH-CARD: {unique_count} unique — ID-like, skip for charts]"
            elif card_level == "high":
                card_tag = f" [HIGH-CARD: {unique_count} unique — bad for pie/bar]"
            elif card_level == "medium":
                card_tag = f" [MED-CARD: {unique_count} unique]"

            col_lines.append(f"  • {col_name} ({col_type}){card_tag} — e.g. {sample_val}")

        sections.append("COLUMNS:\n" + "\n".join(col_lines))
        if len(colmeta) > 30:
            sections.append(f"  ... +{len(colmeta) - 30} more columns")

        # --- Section 4: ID columns to skip ---
        id_cols = data_profile.get("id_columns", [])
        if id_cols:
            sections.append(f"SKIP COLUMNS (IDs, not useful for charts/KPIs): {', '.join(id_cols[:10])}")

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
            skewed = [d for d in distributions if abs(d.get("skewness", 0)) > 1.5]
            if skewed:
                skew_names = [f"{d.get('column', '')} (skew={d.get('skewness', 0):.1f})" for d in skewed[:5]]
                sections.append(f"SKEWED COLUMNS (consider log scale or median instead of mean): {', '.join(skew_names)}")

        # --- Section 7: Statistical findings ---
        outlier_info = statistical_findings.get("outliers", [])
        if outlier_info:
            outlier_cols = [o.get("column", "") for o in outlier_info[:5] if o.get("column")]
            if outlier_cols:
                sections.append(f"OUTLIER COLUMNS (consider filtering or box plots): {', '.join(outlier_cols)}")

        # --- Section 8: Executive summary (from deep analysis) ---
        exec_summary = deep_analysis.get("executive_summary", "")
        if exec_summary and isinstance(exec_summary, str) and len(exec_summary) > 20:
            # Truncate to ~200 chars to keep prompt compact
            truncated = exec_summary[:300].rsplit(".", 1)[0] + "." if len(exec_summary) > 300 else exec_summary
            sections.append(f"EXECUTIVE SUMMARY: {truncated}")

        # --- Section 9: Pre-computed chart recommendations (from upload pipeline) ---
        chart_recs = metadata.get("chart_recommendations", [])
        if chart_recs:
            rec_lines = ["PRE-COMPUTED CHART SUGGESTIONS (from statistical analysis):"]
            for rec in chart_recs[:5]:
                chart_type = rec.get("chart_type", rec.get("type", ""))
                title = rec.get("title", "")
                cols = rec.get("columns", [])
                rec_lines.append(f"  • {chart_type}: {title} — columns: {', '.join(cols) if isinstance(cols, list) else cols}")
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
