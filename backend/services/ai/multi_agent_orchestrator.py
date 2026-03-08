"""
Multi-Agent Orchestrator for Dashboard AI Pipeline
---------------------------------------------------
Coordinates multiple specialized LLMs for:
1. Chart Recommendation (Qwen3-235B)
2. KPI Suggestion (Hermes 3 405B)
3. Chart Explanation (Hermes 3 405B)
4. Insight Generation (Qwen3-235B / DeepSeek)

Architecture:
- Parallel execution: Chart Recommendation + KPI Suggestion
- Sequential execution: Chart Explanation → Insight Generation
- Draft/Review/Refine pattern: Small model drafts, large model refines
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from services.llm_router import llm_router
from core.prompts import PromptFactory, PromptType
from core.prompt_templates import (
    get_chart_recommendation_prompt,
    get_kpi_suggestion_prompt,
    get_chart_explanation_prompt,
    get_insight_generation_prompt
)

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    Orchestrates multiple specialized AI agents for dashboard generation.
    """
    
    def __init__(self):
        self.llm_router = llm_router
    
    # -----------------------------------------------------------
    # PUBLIC API - Main Orchestration Methods
    # -----------------------------------------------------------
    
    async def design_dashboard_multi_agent(
        self,
        dataset_context: str,
        metadata: Dict[str, Any],
        design_preference: Optional[str] = None,
        conversation_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete dashboard design using multiple specialized agents.
        
        Pipeline:
        1. [Parallel] Chart Recommendation + KPI Suggestion
        2. [Sequential] Chart Explanation
        3. [Sequential] Insight Generation
        
        Args:
            dataset_context: String representation of dataset metadata
            metadata: Full dataset metadata dict
            design_preference: Optional user preference for design pattern
            
        Returns:
            Complete dashboard design with components, explanations, and insights
        """
        logger.info("🚀 Starting multi-agent dashboard design pipeline")
        start_time = datetime.now()
        
        # Enrich dataset context with conversation history if available
        enriched_context = dataset_context
        if conversation_summary:
            enriched_context = (
                f"CONVERSATION CONTEXT (what the user has been analyzing):\n"
                f"{conversation_summary}\n\n"
                f"{dataset_context}"
            )
            logger.info("📝 Dashboard agents enriched with conversation context")
        
        try:
            # Stage 1: Parallel execution for independent tasks
            logger.info("📊 Stage 1: Running Chart Recommendation + KPI Suggestion in parallel")
            chart_recommendations, kpi_suggestions = await self._stage_1_parallel(
                enriched_context, metadata
            )

            has_charts = bool(chart_recommendations.get("charts"))
            has_kpis = bool(kpi_suggestions.get("kpis"))

            if not has_charts and not has_kpis:
                logger.warning("⚠️ Stage 1 produced no charts or KPIs; skipping stages 2 and 3")
                chart_explanations = []
                insights = {"insights": [], "summary": ""}
            else:
                # Stage 2: Chart Explanation (depends on chart recommendations)
                logger.info("📝 Stage 2: Generating chart explanations")
                chart_explanations = await self._stage_2_explanations(
                    chart_recommendations, dataset_context, metadata
                )
                
                # Stage 3: Insight Generation (synthesize everything)
                logger.info("💡 Stage 3: Generating insights from analysis")
                insights = await self._stage_3_insights(
                    chart_recommendations, kpi_suggestions, dataset_context, metadata
                )
            
            # Combine results into final dashboard blueprint
            blueprint = self._assemble_dashboard(
                chart_recommendations,
                kpi_suggestions,
                chart_explanations,
                insights,
                metadata
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Multi-agent pipeline completed in {duration:.2f}s")
            
            return {
                "success": True,
                "blueprint": blueprint,
                "metadata": {
                    "pipeline_duration_seconds": duration,
                    "chart_count": len(chart_recommendations.get("charts", [])),
                    "kpi_count": len(kpi_suggestions.get("kpis", [])),
                    "insight_count": len(insights.get("insights", [])),
                    "agents_used": ["qwen_235b", "hermes_405b"]
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Multi-agent pipeline failed: {e}", exc_info=True)
            raise
    
    async def generate_chart_with_explanation(
        self,
        dataset_context: str,
        user_query: str,
        metadata: Dict[str, Any],
        conversation_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single chart with explanation for chat-based requests.
        
        Uses:
        1. Chart Recommendation agent (Qwen3-235B)
        2. Chart Explanation agent (Hermes 3 405B)
        
        Args:
            dataset_context: Dataset metadata string
            user_query: User's natural language query
            metadata: Full dataset metadata
            
        Returns:
            Chart config with detailed explanation
        """
        logger.info("💬 Chat mode: Generating chart with explanation")
        
        # Enrich context with conversation history if available
        enriched_context = dataset_context
        if conversation_summary:
            enriched_context = (
                f"CONVERSATION CONTEXT:\n{conversation_summary}\n\n"
                f"{dataset_context}"
            )
        
        try:
            # Step 1: Get chart recommendation
            chart_config = await self._agent_chart_recommendation(
                enriched_context, 
                user_query=user_query,
                metadata=metadata
            )
            
            # Step 2: Generate explanation
            explanation = await self._agent_chart_explanation(
                chart_config, 
                enriched_context,
                metadata
            )
            
            return {
                "success": True,
                "chart_config": chart_config,
                "explanation": explanation,
                "agent": "qwen_235b + hermes_405b"
            }
            
        except Exception as e:
            logger.error(f"❌ Chart generation with explanation failed: {e}")
            raise
    
    # -----------------------------------------------------------
    # STAGE 1: PARALLEL EXECUTION (Chart Recommendation + KPI)
    # -----------------------------------------------------------
    
    async def _stage_1_parallel(
        self,
        dataset_context: str,
        metadata: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Run Chart Recommendation and KPI Suggestion in parallel.
        
        Returns:
            Tuple of (chart_recommendations, kpi_suggestions)
        """
        # Run both tasks concurrently
        results = await asyncio.gather(
            self._agent_chart_recommendation(dataset_context, metadata=metadata),
            self._agent_kpi_suggestion(dataset_context, metadata),
            return_exceptions=True  # Don't fail if one agent fails
        )
        
        # Unpack results with error handling
        chart_recommendations = results[0] if not isinstance(results[0], Exception) else {
            "error": str(results[0]),
            "charts": []
        }
        
        kpi_suggestions = results[1] if not isinstance(results[1], Exception) else {
            "error": str(results[1]),
            "kpis": []
        }
        
        return chart_recommendations, kpi_suggestions
    
    # -----------------------------------------------------------
    # STAGE 2: CHART EXPLANATION (Sequential)
    # -----------------------------------------------------------
    
    async def _stage_2_explanations(
        self,
        chart_recommendations: Dict[str, Any],
        dataset_context: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate explanations for each recommended chart.
        
        Returns:
            List of chart explanations
        """
        charts = chart_recommendations.get("charts", [])
        
        if not charts:
            logger.warning("No charts to explain")
            return []
        
        # Generate explanations for all charts (can be done in parallel if needed)
        explanation_tasks = [
            self._agent_chart_explanation(chart, dataset_context, metadata)
            for chart in charts
        ]
        
        explanations = await asyncio.gather(*explanation_tasks, return_exceptions=True)
        
        # Filter out errors
        valid_explanations = [
            exp for exp in explanations 
            if not isinstance(exp, Exception)
        ]
        
        return valid_explanations
    
    # -----------------------------------------------------------
    # STAGE 3: INSIGHT GENERATION (Sequential)
    # -----------------------------------------------------------
    
    async def _stage_3_insights(
        self,
        chart_recommendations: Dict[str, Any],
        kpi_suggestions: Dict[str, Any],
        dataset_context: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate high-level insights based on all previous analysis.
        
        Returns:
            Insights dict with key findings
        """
        if not chart_recommendations.get("charts") and not kpi_suggestions.get("kpis"):
            logger.warning("No charts or KPIs available for insight generation")
            return {"insights": [], "summary": ""}

        return await self._agent_insight_generation(
            chart_recommendations,
            kpi_suggestions,
            dataset_context,
            metadata
        )
    
    # -----------------------------------------------------------
    # INDIVIDUAL AGENTS
    # -----------------------------------------------------------
    
    async def _agent_chart_recommendation(
        self,
        dataset_context: str,
        user_query: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Chart Recommendation Agent (Qwen3-235B)
        
        Analyzes data and recommends optimal chart types.
        Uses enriched dataset context with cardinality, correlations, and domain info
        to make data-aware chart decisions.
        """
        prompt = get_chart_recommendation_prompt(dataset_context, user_query)
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_recommendation",
                expect_json=True,
                temperature=0.4,
                max_tokens=2500
            )
            
            logger.info(f"✓ Chart recommendation generated: {len(response.get('charts', []))} charts")
            return response
            
        except Exception as e:
            logger.error(f"Chart recommendation agent failed: {e}")
            return {"error": str(e), "charts": []}
    
    async def _agent_kpi_suggestion(
        self,
        dataset_context: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        KPI Suggestion Agent (Hermes 3 405B)
        
        Identifies key performance indicators from the data.
        Uses domain intelligence and data profile for smarter KPI selection.
        """
        # Build extra domain context for KPI-specific intelligence
        domain_intel = metadata.get("domain_intelligence", {})
        data_profile = metadata.get("data_profile", {})

        kpi_hints = []
        if domain_intel.get("key_metrics"):
            kpi_hints.append(f"Domain-identified key metrics: {', '.join(domain_intel['key_metrics'][:6])}")
        if domain_intel.get("measures"):
            kpi_hints.append(f"Numeric columns suitable for aggregation: {', '.join(domain_intel['measures'][:8])}")
        if data_profile.get("id_columns"):
            kpi_hints.append(f"ID columns (DO NOT use for KPIs): {', '.join(data_profile['id_columns'][:6])}")

        kpi_context = "\n".join(kpi_hints) if kpi_hints else ""

        prompt = get_kpi_suggestion_prompt(dataset_context, kpi_context)
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="kpi_suggestion",
                expect_json=True,
                temperature=0.3,  # Lower temperature for structured output
                max_tokens=1200
            )
            
            logger.info(f"✓ KPI suggestions generated: {len(response.get('kpis', []))} KPIs")
            return response
            
        except Exception as e:
            logger.error(f"KPI suggestion agent failed: {e}")
            return {"error": str(e), "kpis": []}
    
    async def _agent_chart_explanation(
        self,
        chart_config: Dict[str, Any],
        dataset_context: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Chart Explanation Agent
        
        Generates clear, data-specific explanations for each chart.
        References actual numbers and patterns, not generic chart-reading advice.
        """
        chart_type = chart_config.get("type", "bar")
        x_col = chart_config.get("x", "N/A")
        y_col = chart_config.get("y", "N/A")
        title = chart_config.get("title", "Chart")

        # Build a compact chart summary
        chart_summary = (
            f"Type: {chart_type}, "
            f"X-axis: {x_col}, "
            f"Y-axis: {y_col}, "
            f"Title: {title}"
        )

        # Build data stats from metadata so the LLM can reference real numbers
        data_stats = ""
        if metadata:
            stat_parts = []
            col_metadata = {c.get("name"): c for c in metadata.get("column_metadata", [])}
            deep = metadata.get("deep_analysis", {})
            enhanced = deep.get("enhanced_analysis", {})
            data_profile = metadata.get("data_profile", {})
            summary_stats = data_profile.get("summary_statistics", {})

            # Add specific stats for the columns used in this chart
            for col_name in [x_col, y_col]:
                if col_name and col_name != "N/A":
                    col_info = col_metadata.get(col_name, {})
                    col_stats = summary_stats.get(col_name, {})
                    if col_stats:
                        parts = [f"  {col_name}:"]
                        for k in ("mean", "median", "min", "max", "std"):
                            if k in col_stats:
                                v = col_stats[k]
                                parts.append(f"    {k}={v:.2f}" if isinstance(v, float) else f"    {k}={v}")
                        stat_parts.append("\n".join(parts))
                    elif col_info:
                        sample = col_info.get("sample_value", "")
                        dtype = col_info.get("type", "")
                        stat_parts.append(f"  {col_name}: type={dtype}, sample={sample}")

            # Add relevant correlations involving these columns
            for corr in enhanced.get("correlations", [])[:8]:
                c1, c2 = corr.get("column1", ""), corr.get("column2", "")
                if c1 in (x_col, y_col) or c2 in (x_col, y_col):
                    r = corr.get("correlation", 0)
                    strength = corr.get("strength", "")
                    stat_parts.append(f"  Correlation: {c1} ↔ {c2}: r={r:.3f} ({strength})")

            # Add relevant distributions
            for dist in enhanced.get("distributions", [])[:6]:
                if dist.get("column") in (x_col, y_col):
                    skew = dist.get("skewness", 0)
                    dtype = dist.get("distribution_type", "")
                    stat_parts.append(f"  Distribution of {dist['column']}: {dtype}, skewness={skew:.2f}")

            # Add cardinality info for categorical columns
            cardinality = data_profile.get("cardinality", {})
            for col_name in [x_col, y_col]:
                if col_name and col_name in cardinality:
                    card = cardinality[col_name]
                    unique = card.get("unique_count", "")
                    top_vals = card.get("top_values", [])
                    if top_vals:
                        top_str = ", ".join(f"{v.get('value')}={v.get('count')}" for v in top_vals[:5])
                        stat_parts.append(f"  {col_name} categories (top): {top_str}")
                    elif unique:
                        stat_parts.append(f"  {col_name}: {unique} unique values")

            if stat_parts:
                data_stats = "\n".join(stat_parts)

        prompt = get_chart_explanation_prompt(chart_summary, dataset_context, data_stats)
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_explanation",
                expect_json=True,
                temperature=0.4,
                max_tokens=500
            )
            
            logger.info(f"✓ Chart explanation generated for: {title}")
            return response
            
        except Exception as e:
            logger.error(f"Chart explanation agent failed: {e}")
            return {"error": str(e), "explanation": ""}
    
    async def _agent_insight_generation(
        self,
        chart_recommendations: Dict[str, Any],
        kpi_suggestions: Dict[str, Any],
        dataset_context: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Insight Generation Agent (Qwen3-235B)
        
        Synthesizes deep, actionable insights from all analysis.
        Uses structured summaries instead of raw dict dumps to save tokens.
        """
        # Build compact structured summaries instead of dumping raw dicts
        chart_summary_lines = []
        for c in chart_recommendations.get("charts", [])[:5]:
            chart_summary_lines.append(
                f"  • {c.get('type', 'bar')}: {c.get('title', '')} "
                f"({c.get('x', '')} vs {c.get('y', '')})"
            )
        charts_text = "\n".join(chart_summary_lines) if chart_summary_lines else "No charts recommended"

        kpi_summary_lines = []
        for k in kpi_suggestions.get("kpis", [])[:6]:
            kpi_summary_lines.append(
                f"  • {k.get('title', '')}: {k.get('aggregation', 'sum')}({k.get('column', '')})"
            )
        kpis_text = "\n".join(kpi_summary_lines) if kpi_summary_lines else "No KPIs suggested"

        # Pull executive summary from metadata if available
        deep_analysis = metadata.get("deep_analysis", {})
        exec_summary = deep_analysis.get("executive_summary", "")
        exec_text = ""
        if exec_summary and isinstance(exec_summary, str) and len(exec_summary) > 20:
            truncated = exec_summary[:400].rsplit(".", 1)[0] + "." if len(exec_summary) > 400 else exec_summary
            exec_text = f"\nPRE-COMPUTED EXECUTIVE SUMMARY:\n{truncated}"

        prompt = get_insight_generation_prompt(
            dataset_context,
            charts_text,
            kpis_text,
            exec_text
        )
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="insight_generation",
                expect_json=True,
                temperature=0.6,  # Keep insights useful but reduce verbosity/latency
                max_tokens=900
            )
            
            logger.info(f"✓ Insights generated: {len(response.get('insights', []))} insights")
            return response
            
        except Exception as e:
            logger.error(f"Insight generation agent failed: {e}")
            return {"error": str(e), "insights": []}
    
    # -----------------------------------------------------------
    # ASSEMBLY - Combine Results into Dashboard Blueprint
    # -----------------------------------------------------------
    
    def _assemble_dashboard(
        self,
        chart_recommendations: Dict[str, Any],
        kpi_suggestions: Dict[str, Any],
        chart_explanations: List[Dict[str, Any]],
        insights: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assemble all agent outputs into a cohesive dashboard blueprint.
        
        Returns:
            Complete dashboard blueprint ready for frontend rendering
        """
        components = []
        
        # Add KPIs first
        for kpi in kpi_suggestions.get("kpis", [])[:8]:  # Max 8 KPIs
            components.append({
                "type": "kpi",
                "title": kpi.get("title", "KPI"),
                "span": 1,
                "config": {
                    "column": kpi.get("column"),
                    "aggregation": kpi.get("aggregation", "sum")
                },
                "metadata": {
                    "reasoning": kpi.get("reasoning", "")
                }
            })
        
        # Add charts
        for i, chart in enumerate(chart_recommendations.get("charts", [])[:8]):  # Max 8 charts
            # Find matching explanation
            explanation = next(
                (exp for exp in chart_explanations if exp.get("chart_id") == chart.get("title")),
                {}
            )
            
            components.append({
                "type": "chart",
                "title": chart.get("title", f"Chart {i+1}"),
                "span": 2,
                "config": {
                    "chart_type": chart.get("type", "bar"),
                    "x": chart.get("x"),
                    "y": chart.get("y"),
                    "columns": [chart.get("x"), chart.get("y")]
                },
                "metadata": {
                    "reasoning": chart.get("reasoning", ""),
                    "explanation": explanation.get("explanation", ""),
                    "key_insights": explanation.get("key_insights", []),
                    "reading_guide": explanation.get("reading_guide", "")
                }
            })
        
        # Add a data table component using the first columns from metadata
        colmeta = metadata.get("column_metadata", [])
        table_columns = [c.get("name", "") for c in colmeta[:6] if c.get("name")]
        if table_columns:
            components.append({
                "type": "table",
                "title": "Data Overview",
                "span": 4,
                "config": {
                    "columns": table_columns,
                    "limit": 200
                }
            })
        
        return {
            "layout_grid": "repeat(4, 1fr)",
            "components": components,
            "insights": insights.get("insights", []),
            "summary": insights.get("summary", ""),
            "generated_by": "multi_agent_pipeline",
            "agents": {
                "chart_recommendation": "deepseek_v32",
                "kpi_suggestion": "deepseek_v32",
                "chart_explanation": "mistral_small_32",
                "insight_generation": "deepseek_v32"
            }
        }


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
