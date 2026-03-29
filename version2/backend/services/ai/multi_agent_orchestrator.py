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
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from services.llm_router import llm_router
from services.analysis.insight_interpreter import insight_interpreter
from core.prompts import (
    PromptFactory,
    PromptType,
    ChartGeneratorResponse,
    extract_and_validate,
)
from core.prompt_templates import (
    get_chart_recommendation_prompt,
    get_kpi_suggestion_prompt,
    get_chart_explanation_prompt,
    get_insight_generation_prompt,
    get_deep_reasoning_prompt,
    get_self_critique_prompt,
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
        conversation_summary: Optional[str] = None,
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

        # ── Inject pre-computed QUIS findings ──
        # These are statistically validated (FDR-corrected, ranked by effect size × novelty).
        # Injecting them prevents the LLM from guessing patterns already proven by the engine.
        quis_block = self._format_quis_findings(metadata)
        if quis_block:
            enriched_context = (
                f"COMPUTED FINDINGS (pre-validated, FDR-corrected — treat these as ground truth):\n"
                f"{quis_block}\n\n"
                f"{enriched_context}"
            )
            logger.info("📊 Injected pre-computed QUIS findings into pipeline context")

        try:
            # Stage 0: Deep Reasoning (The Data Scientist Phase)
            logger.info("🧠 Stage 0: Performing Deep Reasoning analysis")
            reasoning_trace = await self._agent_deep_reasoning(
                enriched_context, metadata
            )

            # Enrich context for downstream agents with the reasoning insights
            if reasoning_trace:
                # Extract hidden_insights_to_explore fields correctly:
                # prompt returns: columns, hypothesis, why_valuable, chart_type_recommendation
                hidden = reasoning_trace.get("hidden_insights_to_explore", [])
                hidden_lines = []
                for h in hidden[:3]:
                    cols = " × ".join(h.get("columns", []))
                    hyp = h.get("hypothesis", "")
                    rec = h.get("chart_type_recommendation", "")
                    if cols and hyp:
                        hidden_lines.append(f"  • {cols}: {hyp} → suggest {rec}")
                hidden_text = (
                    "\n".join(hidden_lines) if hidden_lines else "None identified"
                )

                watchouts = reasoning_trace.get("data_watchouts", [])
                watchout_text = (
                    "\n".join(f"  ⚠ {w}" for w in watchouts[:3]) if watchouts else ""
                )

                priority = reasoning_trace.get("priority_signals", [{}])
                priority_text = ""
                if priority and isinstance(priority, list) and len(priority) > 0:
                    p = priority[0]
                    priority_text = (
                        f"- Priority signal: {p.get('signal', '')} "
                        f"(evidence: {p.get('evidence', '')})"
                        f"\n- Hero chart: {p.get('recommended_hero_chart', '')}"
                    )

                enriched_context = (
                    f"STAGE 0 ANALYTICAL STRATEGY (use this — do not re-derive):\n"
                    f"- Governing thought: {reasoning_trace.get('analytical_strategy', '')}\n"
                    f"- Business questions: {', '.join(reasoning_trace.get('business_questions', []))}\n"
                    f"- Non-obvious patterns to visualize:\n{hidden_text}\n"
                    f"{priority_text}\n"
                    f"- Data watchouts (avoid these mistakes):\n{watchout_text}\n\n"
                    f"{enriched_context}"
                )
                logger.info(
                    "✓ Stage 0 output correctly enriched into chart_rec context"
                )

            # Stage 1: Parallel execution for independent tasks
            logger.info(
                "📊 Stage 1: Running Chart Recommendation + KPI Suggestion in parallel"
            )
            chart_recommendations, kpi_suggestions = await self._stage_1_parallel(
                enriched_context, metadata
            )

            has_charts = bool(chart_recommendations.get("charts"))
            has_kpis = bool(kpi_suggestions.get("kpis"))

            if not has_charts and not has_kpis:
                logger.warning(
                    "⚠️ Stage 1 produced no charts or KPIs; skipping stages 2 and 3"
                )
                chart_explanations = []
                insights = {"insights": [], "summary": ""}
            else:
                # Stage 2: Chart Explanations are lazy-loaded by the frontend.
                logger.info("📝 Stage 2: Skipped (Chart explanations are lazy-loaded)")
                chart_explanations = []

                # Stage 3: Insight Generation (synthesize everything)
                logger.info("💡 Stage 3: Generating insights from analysis")
                insights = await self._stage_3_insights(
                    chart_recommendations, kpi_suggestions, dataset_context, metadata
                )

            # Combine results into final dashboard blueprint
            blueprint = await self._assemble_dashboard(
                chart_recommendations,
                kpi_suggestions,
                chart_explanations,
                insights,
                metadata,
            )

            # Phase 4: Self-Critique (Enterprise Quality Assurance)
            # This is where we verify the HYDRATED logic (clones, 1970 bugs, etc)
            logger.info("🛡️ Stage 4: Running Self-Critique on generated dashboard")
            # We pass the blueprint - in a real scenario we'd pass calculated summaries too
            # For now, we'll simulate the "Critique" process
            critique = await self._agent_self_critique(blueprint, dataset_context)

            if not critique.get("is_valid", True):
                # Apply fixes from critique["errors"]
                for error in critique.get("errors", []):
                    if error.get("auto_fixable"):
                        blueprint = self._apply_critique_fix(blueprint, error)
                logger.info(f"Applied {len(critique.get('errors', []))} critique fixes")

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
                    "agents_used": ["qwen_235b", "hermes_405b"],
                },
            }

        except Exception as e:
            logger.error(f"❌ Multi-agent pipeline failed: {e}", exc_info=True)
            raise

    async def generate_chart_with_explanation(
        self,
        dataset_context: str,
        user_query: str,
        metadata: Dict[str, Any],
        conversation_summary: Optional[str] = None,
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
                f"CONVERSATION CONTEXT:\n{conversation_summary}\n\n{dataset_context}"
            )

        try:
            # Step 1: Get chart recommendation
            chart_config = await self._agent_chart_recommendation(
                enriched_context, user_query=user_query, metadata=metadata
            )

            # Step 2: Generate explanation
            explanation = await self._agent_chart_explanation(
                chart_config, enriched_context, metadata
            )

            return {
                "success": True,
                "chart_config": chart_config,
                "explanation": explanation,
                "agent": "qwen_235b + hermes_405b",
            }

        except Exception as e:
            logger.error(f"❌ Chart generation with explanation failed: {e}")
            raise

    # -----------------------------------------------------------
    # STAGE 1: PARALLEL EXECUTION (Chart Recommendation + KPI)
    # -----------------------------------------------------------

    async def _stage_1_parallel(
        self, dataset_context: str, metadata: Dict[str, Any]
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
            return_exceptions=True,  # Don't fail if one agent fails
        )

        # Unpack results with error handling
        chart_recommendations = (
            results[0]
            if not isinstance(results[0], Exception)
            else {"error": str(results[0]), "charts": []}
        )

        kpi_suggestions = (
            results[1]
            if not isinstance(results[1], Exception)
            else {"error": str(results[1]), "kpis": []}
        )

        return chart_recommendations, kpi_suggestions

    # -----------------------------------------------------------
    # STAGE 2: CHART EXPLANATION (Sequential)
    # -----------------------------------------------------------

    async def _stage_2_explanations(
        self,
        chart_recommendations: Dict[str, Any],
        dataset_context: str,
        metadata: Optional[Dict[str, Any]] = None,
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

        # Generate explanations for all charts (with semaphore protection)
        sem = asyncio.Semaphore(3)  # Max 3 concurrent explanation calls

        async def safe_explain(chart):
            async with sem:
                return await self._agent_chart_explanation(
                    chart, dataset_context, metadata
                )

        explanation_tasks = [safe_explain(chart) for chart in charts]

        explanations = await asyncio.gather(*explanation_tasks, return_exceptions=True)

        # Filter out errors
        valid_explanations = [
            exp for exp in explanations if not isinstance(exp, Exception)
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
        metadata: Dict[str, Any],
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
            chart_recommendations, kpi_suggestions, dataset_context, metadata
        )

    # -----------------------------------------------------------
    # INDIVIDUAL AGENTS
    # -----------------------------------------------------------

    async def _agent_chart_recommendation(
        self,
        dataset_context: str,
        user_query: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Chart Recommendation Agent (Qwen3-235B)

        Analyzes data and recommends optimal chart types.
        Uses enriched dataset context with cardinality, correlations, and domain info
        to make data-aware chart decisions.
        Returns ChartGeneratorResponse format with 7-layer enterprise chart specs.
        """
        prompt = get_chart_recommendation_prompt(
            dataset_context, user_query, include_context=False
        )

        raw_response = None
        try:
            raw_response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_recommendation",
                expect_json=True,
                temperature=0.4,
                max_tokens=8000,
                context=dataset_context,
            )

            result = extract_and_validate(raw_response, ChartGeneratorResponse)
            charts = [k.model_dump() for k in result.charts]

            logger.info(
                f"✓ Chart recommendation generated: {len(charts)} charts (archetype: {result.dashboard_story[:50]}...)"
            )
            return {
                "charts": charts,
                "dashboard_story": result.dashboard_story,
                "chart_order_rationale": result.chart_order_rationale,
            }

        except Exception as e:
            logger.warning(f"Chart recommendation strict validation failed: {e} — attempting partial recovery")
            return self._recover_partial_charts(raw_response or "")

    def _recover_partial_charts(self, raw_response) -> dict:
        """
        Fallback: when strict Pydantic validation fails, salvage any chart objects
        from the raw LLM response.  Accepts dicts, lists, or raw JSON strings.
        Returns a partial result rather than an empty array so the pipeline can
        continue with whatever charts were generated.
        """
        import json, re

        # Normalise to a plain Python object
        if isinstance(raw_response, dict):
            data = raw_response
        elif isinstance(raw_response, str):
            try:
                data = json.loads(raw_response)
            except Exception:
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                try:
                    data = json.loads(match.group()) if match else {}
                except Exception:
                    data = {}
        else:
            data = {}

        raw_charts = data.get("charts", [])

        # Minimal per-chart validation: must have at least type + x/y columns
        REQUIRED = {"type", "x", "y"}
        valid = []
        for c in raw_charts:
            if isinstance(c, dict) and REQUIRED.issubset(c.keys()):
                valid.append(c)

        logger.info(f"Partial chart recovery: salvaged {len(valid)} / {len(raw_charts)} charts")

        if not valid:
            logger.error("Chart recommendation agent failed and recovery produced 0 charts")
            return {"error": "chart_generation_failed", "charts": []}

        return {
            "charts": valid,
            "dashboard_story": data.get("dashboard_story", ""),
            "chart_order_rationale": data.get("chart_order_rationale", ""),
        }

    async def _agent_kpi_suggestion(
        self, dataset_context: str, metadata: Dict[str, Any]
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
            kpi_hints.append(
                f"Domain-identified key metrics: {', '.join(domain_intel['key_metrics'][:6])}"
            )
        if domain_intel.get("measures"):
            kpi_hints.append(
                f"Numeric columns suitable for aggregation: {', '.join(domain_intel['measures'][:8])}"
            )
        if data_profile.get("id_columns"):
            kpi_hints.append(
                f"ID columns (DO NOT use for KPIs): {', '.join(data_profile['id_columns'][:6])}"
            )

        kpi_context = "\n".join(kpi_hints) if kpi_hints else ""

        prompt = get_kpi_suggestion_prompt(
            dataset_context, kpi_context, include_context=False
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="kpi_suggestion",
                expect_json=True,
                temperature=0.3,  # Lower temperature for structured output
                max_tokens=1200,
                context=dataset_context,
            )

            logger.info(
                f"✓ KPI suggestions generated: {len(response.get('kpis', []))} KPIs"
            )
            return response

        except Exception as e:
            logger.error(f"KPI suggestion agent failed: {e}")
            return {"error": str(e), "kpis": []}

    async def _agent_chart_explanation(
        self,
        chart_config: Dict[str, Any],
        dataset_context: str,
        metadata: Optional[Dict[str, Any]] = None,
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
            f"Type: {chart_type}, X-axis: {x_col}, Y-axis: {y_col}, Title: {title}"
        )

        # Build data stats from metadata so the LLM can reference real numbers
        data_stats = ""
        if metadata:
            stat_parts = []
            col_metadata = {
                c.get("name"): c for c in metadata.get("column_metadata", [])
            }
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
                                parts.append(
                                    f"    {k}={v:.2f}"
                                    if isinstance(v, float)
                                    else f"    {k}={v}"
                                )
                        stat_parts.append("\n".join(parts))
                    elif col_info:
                        sample = col_info.get("sample_value", "")
                        dtype = col_info.get("type", "")
                        stat_parts.append(
                            f"  {col_name}: type={dtype}, sample={sample}"
                        )

            # Add relevant correlations involving these columns
            for corr in enhanced.get("correlations", [])[:8]:
                c1, c2 = corr.get("column1", ""), corr.get("column2", "")
                if c1 in (x_col, y_col) or c2 in (x_col, y_col):
                    r = corr.get("correlation", 0)
                    strength = corr.get("strength", "")
                    stat_parts.append(
                        f"  Correlation: {c1} ↔ {c2}: r={r:.3f} ({strength})"
                    )

            # Add relevant distributions
            for dist in enhanced.get("distributions", [])[:6]:
                if dist.get("column") in (x_col, y_col):
                    skew = dist.get("skewness", 0)
                    dtype = dist.get("distribution_type", "")
                    stat_parts.append(
                        f"  Distribution of {dist['column']}: {dtype}, skewness={skew:.2f}"
                    )

            # Add cardinality info for categorical columns
            cardinality = data_profile.get("cardinality", {})
            for col_name in [x_col, y_col]:
                if col_name and col_name in cardinality:
                    card = cardinality[col_name]
                    unique = card.get("unique_count", "")
                    top_vals = card.get("top_values", [])
                    if top_vals:
                        top_str = ", ".join(
                            f"{v.get('value')}={v.get('count')}" for v in top_vals[:5]
                        )
                        stat_parts.append(f"  {col_name} categories (top): {top_str}")
                    elif unique:
                        stat_parts.append(f"  {col_name}: {unique} unique values")

            if stat_parts:
                data_stats = "\n".join(stat_parts)

        prompt = get_chart_explanation_prompt(
            chart_summary, dataset_context, data_stats, include_context=False
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="chart_explanation",
                expect_json=True,
                temperature=0.4,
                max_tokens=500,
                context=dataset_context,
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
        metadata: Dict[str, Any],
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
        charts_text = (
            "\n".join(chart_summary_lines)
            if chart_summary_lines
            else "No charts recommended"
        )

        kpi_summary_lines = []
        for k in kpi_suggestions.get("kpis", [])[:6]:
            kpi_summary_lines.append(
                f"  • {k.get('title', '')}: {k.get('aggregation', 'sum')}({k.get('column', '')})"
            )
        kpis_text = (
            "\n".join(kpi_summary_lines) if kpi_summary_lines else "No KPIs suggested"
        )

        # Pull executive summary from metadata if available
        deep_analysis = metadata.get("deep_analysis", {})
        exec_summary = deep_analysis.get("executive_summary", "")
        exec_text = ""
        if exec_summary and isinstance(exec_summary, str) and len(exec_summary) > 20:
            truncated = (
                exec_summary[:400].rsplit(".", 1)[0] + "."
                if len(exec_summary) > 400
                else exec_summary
            )
            exec_text = f"\nPRE-COMPUTED EXECUTIVE SUMMARY:\n{truncated}"

        prompt = get_insight_generation_prompt(
            dataset_context, charts_text, kpis_text, exec_text, include_context=False
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="insight_generation",
                expect_json=True,
                temperature=0.6,  # Keep insights useful but reduce verbosity/latency
                max_tokens=900,
                context=dataset_context,
            )

            logger.info(
                f"✓ Insights generated: {len(response.get('insights', []))} insights"
            )
            return response

        except Exception as e:
            logger.error(f"Insight generation agent failed: {e}")
            return {"error": str(e), "insights": []}

    async def _agent_deep_reasoning(
        self, dataset_context: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep Reasoning Agent (Phase 0)

        Analyzes metadata to identify critical business questions and hidden insights
        before the dashboard design phase begins.
        """
        prompt = get_deep_reasoning_prompt(dataset_context, include_context=False)

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="insight_generation",  # Use high-reasoning role
                expect_json=True,
                temperature=0.7,
                max_tokens=1500,
                context=dataset_context,
            )
            logger.info("✓ Deep reasoning completed")
            return response
        except Exception as e:
            logger.error(f"Deep reasoning agent failed: {e}")
            return {}

    async def _agent_self_critique(
        self, blueprint: Dict[str, Any], dataset_context: str
    ) -> Dict[str, Any]:
        """
        Self-Critique Agent (Phase 4)

        Reviews the final hydrated dashboard for "shocking" errors or redundancy.
        """
        # Build a compact summary of what we generated
        blueprint_json = json.dumps(blueprint, indent=2)
        prompt = get_self_critique_prompt(
            blueprint_json, "Analysis pending final hydration"
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role="validation",  # Mistral Small — no reasoning needed for checklist
                expect_json=True,
                temperature=0.2,
                max_tokens=1200,
                context=dataset_context,
            )
            logger.info("✓ Self-critique completed")
            return response
        except Exception as e:
            logger.error(f"Self-critique agent failed: {e}")
            return {
                "is_valid": True,  # Don't block the pipeline
                "errors": [],
                "warnings": [f"Self-critique unavailable: {str(e)}"],
                "skipped": True
            }

    # -----------------------------------------------------------
    # ASSEMBLY - Combine Results into Dashboard Blueprint
    # -----------------------------------------------------------

    async def _assemble_dashboard(
        self,
        chart_recommendations: Dict[str, Any],
        kpi_suggestions: Dict[str, Any],
        chart_explanations: List[Dict[str, Any]],
        insights: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assemble all agent outputs into a cohesive dashboard blueprint.

        Returns:
            Complete dashboard blueprint ready for frontend rendering
        """
        components = []

        # Pre-build a column → stats lookup from metadata so KPI enrichment is O(1)
        data_profile = metadata.get("data_profile", {})
        summary_stats = data_profile.get("summary_statistics", {})

        AGG_TO_STAT = {
            "mean": "mean", "avg": "mean", "average": "mean",
            "median": "median", "sum": "sum",
            "min": "min", "max": "max", "count": "count",
        }

        def _kpi_benchmark(column: str, aggregation: str) -> dict:
            """Compute value from summary_stats and enrich with median comparison + range."""
            col_stats = summary_stats.get(column, {})
            if not col_stats:
                return {}
            stat_key = AGG_TO_STAT.get(aggregation.lower(), "mean")
            value = col_stats.get(stat_key)
            median = col_stats.get("median") or col_stats.get("50%")
            col_min = col_stats.get("min")
            col_max = col_stats.get("max")
            if value is None or median is None:
                return {}
            try:
                value_f = float(value)
                median_f = float(median)
                delta_pct = round(((value_f - median_f) / abs(median_f)) * 100, 1) if median_f != 0 else None
                direction = "above" if value_f >= median_f else "below"
                benchmark = f"{direction} dataset median of {median_f:,.1f}"
                if col_min is not None and col_max is not None:
                    benchmark += f"  ·  range {float(col_min):,.1f}–{float(col_max):,.1f}"
                return {
                    "value": value_f,
                    "comparison_value": median_f,
                    "comparison_label": "vs dataset median",
                    "delta_percent": delta_pct,
                    "delta_direction": "up" if (delta_pct or 0) > 0 else "down" if (delta_pct or 0) < 0 else "neutral",
                    "benchmarkText": benchmark,
                }
            except (TypeError, ValueError):
                return {}

        # Add KPIs first
        for kpi in kpi_suggestions.get("kpis", [])[:8]:  # Max 8 KPIs
            col = kpi.get("column")
            agg = kpi.get("aggregation", "mean")
            enrichment = _kpi_benchmark(col, agg) if col else {}
            components.append(
                {
                    "type": "kpi",
                    "title": kpi.get("title", "KPI"),
                    "span": 1,
                    "value": enrichment.get("value"),
                    "config": {
                        "column": col,
                        "aggregation": kpi.get("aggregation", "sum"),
                    },
                    "metadata": {"reasoning": kpi.get("reasoning", "")},
                    **enrichment,
                }
            )

        # Deduplicate charts by diversity_role and by (type, x, y) to prevent identical charts.
        # The LLM is instructed to enforce uniqueness but often ignores it.
        seen_roles: set = set()
        seen_axes: set = set()
        deduped_charts = []
        for chart in chart_recommendations.get("charts", [])[:12]:
            role = (chart.get("diversity_role") or "").upper()
            axes_key = (chart.get("type", ""), chart.get("x", ""), chart.get("y", ""))
            if role and role in seen_roles:
                logger.info(f"Dedup: dropping chart with duplicate diversity_role={role}")
                continue
            if axes_key in seen_axes:
                logger.info(f"Dedup: dropping chart with duplicate axes {axes_key}")
                continue
            if role:
                seen_roles.add(role)
            seen_axes.add(axes_key)
            deduped_charts.append(chart)

        # Guard: drop scatter charts where either axis looks like an ID / row-index column.
        # These produce meaningless blobs of dots that destroy dashboard credibility.
        ID_PATTERNS = {"id", "_id", "index", "row", "num", "number", "no", "seq", "serial", "key", "code"}

        def _is_id_column(col_name: str) -> bool:
            if not col_name:
                return False
            lower = col_name.lower().replace(" ", "_")
            return any(lower == p or lower.endswith(f"_{p}") or lower.startswith(f"{p}_") for p in ID_PATTERNS)

        safe_charts = []
        for chart in deduped_charts:
            if chart.get("type") == "scatter":
                x_col = chart.get("x", "")
                y_col = chart.get("y", "")
                if _is_id_column(x_col) or _is_id_column(y_col):
                    logger.info(f"Guard: dropping scatter with ID column (x={x_col}, y={y_col})")
                    continue
            safe_charts.append(chart)

        # Add charts
        for i, chart in enumerate(safe_charts):
            # The AI field is title_insight (from ChartItemV2 schema), not title.
            # model_dump() serialises it as title_insight, so we must read that key.
            ai_title = chart.get("title_insight") or chart.get("title", "")

            # Find matching explanation — also keyed on title_insight
            explanation = next(
                (
                    exp
                    for exp in chart_explanations
                    if exp.get("chart_id") in (ai_title, chart.get("title_insight"), chart.get("title"))
                ),
                {},
            )

            # Use AI title if it's a real insight headline; otherwise build from columns
            raw_title = ai_title
            if not raw_title or raw_title.lower().startswith("chart"):
                x_col = chart.get("x") or ""
                y_col = chart.get("y") or ""
                chart_type_name = chart.get("type", "bar")
                x_label = x_col.replace("_", " ").title() if x_col else ""
                y_label = y_col.replace("_", " ").title() if y_col else ""
                if x_label and y_label:
                    raw_title = f"{y_label} by {x_label}"
                elif x_label:
                    raw_title = f"{x_label} Distribution"
                elif y_label:
                    raw_title = f"{y_label} Overview"
                else:
                    raw_title = f"{chart_type_name.replace('_', ' ').title()} {i + 1}"

            components.append(
                {
                    "type": "chart",
                    "title": raw_title,
                    "span": 2,
                    "config": {
                        "chart_type": chart.get("type", "bar"),
                        "x": chart.get("x"),
                        "y": chart.get("y"),
                        "columns": [chart.get("x"), chart.get("y")],
                    },
                    "metadata": {
                        "reasoning": chart.get("reasoning", ""),
                        "explanation": explanation.get("explanation", ""),
                        "key_insights": explanation.get("key_insights", []),
                        "reading_guide": explanation.get("reading_guide", ""),
                    },
                }
            )

        # Add a data table component using the first columns from metadata
        colmeta = metadata.get("column_metadata", [])
        table_columns = [c.get("name", "") for c in colmeta[:6] if c.get("name")]
        if table_columns:
            components.append(
                {
                    "type": "table",
                    "title": "Data Overview",
                    "span": 4,
                    "config": {"columns": table_columns, "limit": 200},
                }
            )

        blueprint = {
            "layout_grid": "repeat(4, 1fr)",
            "components": components,
            "insights": insights.get("insights", []),
            "summary": insights.get("summary", ""),
            "generated_by": "multi_agent_pipeline",
            "agents": {
                "chart_recommendation": "deepseek_v32",
                "kpi_suggestion": "deepseek_v32",
                "chart_explanation": "mistral_small_32",
                "insight_generation": "deepseek_v32",
            },
        }

        # Apply validation and auto-fix
        blueprint = await self._apply_validation_and_fix(blueprint, metadata)

        return blueprint

    async def _apply_validation_and_fix(
        self, blueprint: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply validation and auto-fix to the blueprint.

        This ensures the dashboard meets quality standards before being returned.
        """
        try:
            from services.ai.dashboard_validator import dashboard_validator

            # Run validation
            validation_result = await dashboard_validator.validate_dashboard(blueprint, None, metadata)

            if validation_result["issues"]:
                logger.info(
                    f"Validation found {len(validation_result['issues'])} issues, "
                    f"applied {len(validation_result['auto_fixes'])} fixes"
                )

            # Return validated blueprint
            return validation_result.get("validated_blueprint", blueprint)

        except ImportError:
            logger.warning("Dashboard validator not available, skipping validation")
            return blueprint
        except Exception as e:
            logger.warning(f"Validation failed: {e}, returning original blueprint")
            return blueprint

    def _apply_critique_fix(
        self, blueprint: Dict[str, Any], error: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply auto-fixes from self-critique."""
        issue_type = error.get("type", "")
        component_id = error.get("component_id")

        if issue_type == "duplicate_chart" and component_id:
            # Remove the duplicate chart by title
            blueprint["components"] = [
                c for c in blueprint.get("components", []) 
                if c.get("title") != component_id
            ]
        elif issue_type == "missing_labels":
            for c in blueprint.get("components", []):
                if c.get("title") == component_id and "config" in c:
                    # Provide default labels if missing
                    c["config"]["x_label"] = c["config"].get("x", "X Axis")
                    c["config"]["y_label"] = c["config"].get("y", "Y Axis")
        elif issue_type == "incorrect_aggregation":
            for c in blueprint.get("components", []):
                if c.get("title") == component_id and "config" in c:
                    # Default payload aggregation fallback
                    c["config"]["aggregation"] = error.get("suggested_fix", "sum")
                    
        return blueprint

    # -----------------------------------------------------------
    # PRIVATE HELPERS
    # -----------------------------------------------------------

    def _format_quis_findings(self, metadata: Dict[str, Any]) -> str:
        """
        Extract pre-computed QUIS top_insights from metadata and format them
        as a structured text block for injection into the LLM prompt context.

        Returns empty string if no QUIS findings are available.
        """
        deep_analysis = metadata.get("deep_analysis", {})
        if not deep_analysis:
            return ""

        quis = deep_analysis.get("quis_insights", {})
        top_insights = quis.get("top_insights", [])
        if not top_insights:
            return ""

        type_labels = {
            "correlation": "CORRELATION",
            "comparison": "GROUP COMPARISON",
            "subspace": "SUBSPACE PATTERN",
            "trend": "TREND",
            "anomaly": "ANOMALY",
            "simpson_paradox": "SIMPSON'S PARADOX ⚠",
        }

        lines = []
        for i, finding in enumerate(top_insights[:8], 1):
            p_val = finding.get("p_value")
            effect = finding.get("effect_size", 0)
            effect_interp = finding.get("effect_interpretation", "")
            insight_type = finding.get("insight_type", "insight")
            description = finding.get("description", "")
            columns = finding.get("columns", [])
            score = finding.get("overall_score", 0)

            # Skip statistically insignificant findings
            if p_val is not None and p_val > 0.05:
                continue

            label = type_labels.get(insight_type, insight_type.upper())
            cols_str = " × ".join(columns) if columns else ""
            p_str = f"p={p_val:.4f}" if p_val is not None else ""
            effect_str = (
                f"effect={effect:.3f} ({effect_interp})" if effect else ""
            )
            stat_str = " · ".join(filter(None, [p_str, effect_str]))

            business_sentence = insight_interpreter.interpret_quis_finding_business(finding)

            lines.append(
                f"  [{i}] {label} | columns: {cols_str} | {stat_str}\n"
                f"      Statistical: {description}\n"
                f"      Business: {business_sentence}"
            )

        if not lines:
            return ""

        summary = quis.get("summary", {})
        header = (
            f"({summary.get('significant_insights', len(lines))} statistically significant "
            f"findings after FDR correction, ranked by effect × novelty)"
        )
        return header + "\n" + "\n".join(lines)


# Singleton instance
multi_agent_orchestrator = MultiAgentOrchestrator()
