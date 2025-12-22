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
        design_preference: Optional[str] = None
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
        
        try:
            # Stage 1: Parallel execution for independent tasks
            logger.info("📊 Stage 1: Running Chart Recommendation + KPI Suggestion in parallel")
            chart_recommendations, kpi_suggestions = await self._stage_1_parallel(
                dataset_context, metadata
            )
            
            # Stage 2: Chart Explanation (depends on chart recommendations)
            logger.info("📝 Stage 2: Generating chart explanations")
            chart_explanations = await self._stage_2_explanations(
                chart_recommendations, dataset_context
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
        metadata: Dict[str, Any]
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
        
        try:
            # Step 1: Get chart recommendation
            chart_config = await self._agent_chart_recommendation(
                dataset_context, 
                user_query=user_query
            )
            
            # Step 2: Generate explanation
            explanation = await self._agent_chart_explanation(
                chart_config, 
                dataset_context
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
            self._agent_chart_recommendation(dataset_context),
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
        dataset_context: str
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
            self._agent_chart_explanation(chart, dataset_context)
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
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Chart Recommendation Agent (Qwen3-235B)
        
        Analyzes data and recommends optimal chart types.
        """
        prompt = f"""Analyze this dataset and recommend the best chart visualizations.

DATASET:
{dataset_context}

{f"USER REQUEST: {user_query}" if user_query else ""}

Recommend 3-5 charts that best visualize this data. For each chart, specify:
1. Chart type - MUST be EXACTLY one of: "bar", "line", "pie", "scatter", "histogram", "heatmap" (lowercase only!)
2. X-axis column - MUST be an EXACT column name from the dataset above
3. Y-axis column - MUST be an EXACT column name (null for pie charts)
4. Title - Descriptive chart title
5. Reasoning - Why this chart is appropriate

CRITICAL: Use ONLY the exact column names shown in DATASET above. Do NOT invent columns!

Return ONLY valid JSON in this format:
{{
  "charts": [
    {{
      "type": "bar",
      "x": "column_name",
      "y": "column_name",
      "title": "Chart Title",
      "reasoning": "Why this chart"
    }}
  ]
}}
"""
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_recommendation",
                expect_json=True,
                temperature=0.7
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
        """
        prompt = f"""Analyze this dataset and suggest the most important KPIs (Key Performance Indicators).

DATASET:
{dataset_context}

Suggest 3-6 KPIs that provide the most valuable insights. For each KPI:
1. Title (user-friendly name)
2. Column to aggregate
3. Aggregation type (sum, mean, count, max, min)
4. Why this KPI matters

Return ONLY valid JSON:
{{
  "kpis": [
    {{
      "title": "Total Revenue",
      "column": "revenue",
      "aggregation": "sum",
      "reasoning": "Shows overall performance"
    }}
  ]
}}
"""
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="kpi_suggestion",
                expect_json=True,
                temperature=0.5  # Lower temperature for structured output
            )
            
            logger.info(f"✓ KPI suggestions generated: {len(response.get('kpis', []))} KPIs")
            return response
            
        except Exception as e:
            logger.error(f"KPI suggestion agent failed: {e}")
            return {"error": str(e), "kpis": []}
    
    async def _agent_chart_explanation(
        self,
        chart_config: Dict[str, Any],
        dataset_context: str
    ) -> Dict[str, Any]:
        """
        Chart Explanation Agent (Hermes 3 405B)
        
        Generates clear explanations for why a chart was chosen.
        """
        prompt = f"""Explain this chart visualization choice.

CHART CONFIG:
{chart_config}

DATASET:
{dataset_context}

Provide a clear explanation covering:
1. What the chart shows
2. Why this chart type is appropriate
3. Key insights viewers should notice
4. Who benefits most from this view

Return ONLY valid JSON:
{{
  "chart_id": "{chart_config.get('title', 'chart')}",
  "explanation": "Full explanation text",
  "key_insights": ["insight 1", "insight 2"],
  "target_audience": "who this helps"
}}
"""
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_explanation",
                expect_json=True,
                temperature=0.7
            )
            
            logger.info(f"✓ Chart explanation generated for: {chart_config.get('title', 'chart')}")
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
        
        Synthesizes deep insights from all analysis.
        """
        prompt = f"""Generate strategic insights from this data analysis.

DATASET:
{dataset_context}

RECOMMENDED CHARTS:
{chart_recommendations}

SUGGESTED KPIs:
{kpi_suggestions}

Provide 3-5 high-level insights that:
1. Identify patterns or trends
2. Suggest actionable recommendations
3. Highlight potential opportunities or risks

Return ONLY valid JSON:
{{
  "insights": [
    {{
      "title": "Key Finding",
      "description": "Detailed insight",
      "impact": "high|medium|low",
      "action": "Recommended next step"
    }}
  ],
  "summary": "Overall analysis summary"
}}
"""
        
        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="insight_generation",
                expect_json=True,
                temperature=0.8  # Higher temperature for creative insights
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
        for kpi in kpi_suggestions.get("kpis", [])[:6]:  # Max 6 KPIs
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
        for i, chart in enumerate(chart_recommendations.get("charts", [])[:4]):  # Max 4 charts
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
                    "type": chart.get("type", "bar"),
                    "x": chart.get("x"),
                    "y": chart.get("y"),
                    "columns": [chart.get("x"), chart.get("y")]
                },
                "metadata": {
                    "reasoning": chart.get("reasoning", ""),
                    "explanation": explanation.get("explanation", ""),
                    "key_insights": explanation.get("key_insights", [])
                }
            })
        
        return {
            "layout_grid": "repeat(4, 1fr)",
            "components": components,
            "insights": insights.get("insights", []),
            "summary": insights.get("summary", ""),
            "generated_by": "multi_agent_pipeline",
            "agents": {
                "chart_recommendation": "qwen_235b",
                "kpi_suggestion": "hermes_405b",
                "chart_explanation": "hermes_405b",
                "insight_generation": "qwen_235b"
            }
        }


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
