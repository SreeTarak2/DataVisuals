"""
AnalystAgent — strategic data analyst agent.

Uses a ReAct loop (Reason → Act → Observe → Loop) to:
1. Profile the dataset to understand its structure
2. Run statistical analysis (correlations, anomalies, distributions)
3. Generate strategic KPI recommendations tailored to user intent
4. Retrieve historical context via RAG
5. Check novelty against the user's belief store
6. Synthesize a strategic, executive-facing recommendation

Tool interface (all injected via constructor):
    profiler       — profile_dataframe(df, domain_signal, domain_confidence) → DatasetProfile
    stats_engine   — callable(df) → dict {correlations, anomalies, distributions}
    kpi_strategy   — callable(df, domain, max_kpis, dataset_metadata) → list[KPI dicts]
    rag            — faiss_vector_service.search_similar_queries(...)
    memory         — belief_store (BeliefStore instance)

Designed to be used standalone or integrated into the chat / pipeline orchestrator.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import polars as pl

from agents.base_agent import AgentContext, BaseAgent, ToolResult

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """
    Strategic data analyst — thinks like a senior data analyst, not a dashboard generator.

    The ReAct loop naturally sequences: profile → stats → KPIs → novelty check,
    where each step informs the next. The _synthesize method produces an
    executive-facing strategic recommendation tailored to the user's intent.
    """

    MAX_ITERATIONS = 6

    def _select_tools(self) -> list[str]:
        return ["profiler", "stats_engine", "kpi_strategy", "rag", "memory"]

    async def _process_result(
        self, observations: list[ToolResult], context: AgentContext
    ) -> dict[str, Any]:
        """
        Assemble all successful observations into a structured result dict.

        Downstream consumers (dashboard, chat) can read:
            result["profile"]              – DatasetProfile
            result["statistical_findings"] – correlations / anomalies / distributions
            result["kpi_recommendations"]  – list of generated KPI dicts
            result["novelty_check"]        – {surprisal_score, is_novel, finding}
        """
        profile = None
        stats_findings = {}
        kpi_recommendations = []
        novelty = {}
        rag_docs = []

        for obs in observations:
            if not obs.success:
                continue
            result = obs.result or {}
            if obs.tool == "profiler" and "profile" in result:
                profile = result["profile"]
            elif obs.tool == "stats_engine" and "findings" in result:
                stats_findings = result["findings"]
            elif obs.tool == "kpi_strategy" and "recommendations" in result:
                kpi_recommendations = result["recommendations"]
            elif obs.tool == "memory":
                novelty = result
            elif obs.tool == "rag" and "documents" in result:
                rag_docs = result["documents"]

        return {
            "profile": profile,
            "statistical_findings": stats_findings,
            "kpi_recommendations": kpi_recommendations,
            "novelty_check": novelty,
            "rag_context": rag_docs,
            "analysis_intent": context.query,
        }

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    async def _act(
        self,
        tool_name: str,
        observations: list[ToolResult],
        context: AgentContext,
    ) -> ToolResult:
        """
        Override _act to allow internally-handled tools that don't need
        a registered tool (e.g. stats_engine, kpi_strategy use lazy imports).
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            # Check if this tool has a dedicated handler — if so, call it
            # even if the tool isn't in the registry
            handler_name = f"_handle_{tool_name}"
            handler = getattr(self, handler_name, None)
            if handler is not None:
                tool = self._tools.get(tool_name)  # May be None — handler accepts it
                result, reasoning_summary = await handler(tool, observations, context)
                return ToolResult(
                    tool=tool_name,
                    success=True,
                    timestamp=timestamp,
                    result=result,
                    reasoning_summary=reasoning_summary,
                )

            # Fall through to normal _act logic for registered tools
            return await super()._act(tool_name, observations, context)

        except Exception as e:
            logger.error(
                f"[ACT] {self.__class__.__name__}/{tool_name} failed: {e}",
                exc_info=True,
            )
            return ToolResult(
                tool=tool_name,
                success=False,
                timestamp=timestamp,
                error=str(e),
                result={},
                reasoning_summary=f"Tool '{tool_name}' execution exception: {str(e)[:100]}",
            )

    async def _call_tool(
        self,
        tool_name: str,
        tool: Any,
        observations: list[ToolResult],
        context: AgentContext,
    ) -> tuple[dict[str, Any], str]:
        """Route to the matching _handle_{tool_name} method."""
        handler_name = f"_handle_{tool_name}"
        handler = getattr(self, handler_name, None)
        if handler is not None:
            return await handler(tool, observations, context)
        return await super()._call_tool(tool_name, tool, observations, context)

    # ── Tool: profiler ─────────────────────────────────────────────────────────

    async def _handle_profiler(
        self, profiler_fn: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        """Profile the full DataFrame to understand its structure."""
        df = context.df
        if df is None:
            return {"error": "No DataFrame"}, "Profiler requires a DataFrame"

        try:
            profile = profiler_fn(
                df=df,
                domain_signal=context.domain_signal,
                domain_confidence=context.domain_confidence,
            )
            return (
                {"profile": profile},
                f"Profiled {len(df)} rows × {len(df.columns)} columns "
                f"(domain: {context.domain_signal}, "
                f"confidence: {context.domain_confidence:.2f})",
            )
        except Exception as e:
            logger.error("[AnalystAgent] profiler failed: %s", e, exc_info=True)
            return {"error": str(e)}, f"Profiling failed: {e}"

    # ── Tool: stats_engine ─────────────────────────────────────────────────────

    async def _handle_stats_engine(
        self, stats_tool: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        """
        Run statistical analysis on the full dataset.

        Produces:
        - Pairwise correlations for numeric columns (up to 5 cols)
        - Z-score anomaly detection per numeric column
        - Distribution analysis (skewness, normality) per numeric column
        """
        df = context.df
        if df is None:
            return {"findings": {}}, "Stats engine requires a DataFrame"

        from services.analysis.advanced_stats import (
            AnomalyDetector,
            CorrelationAnalyzer,
            DistributionAnalyzer,
        )

        numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
        if not numeric_cols:
            return {"findings": {}}, "No numeric columns to analyze"

        # Limit to first 8 columns for performance
        analysis_cols = numeric_cols[:8]
        findings: dict[str, Any] = {}

        # ── Correlations ──
        correlations = []
        analyzer = CorrelationAnalyzer()
        for i, col1 in enumerate(analysis_cols):
            for col2 in analysis_cols[i + 1 :]:
                try:
                    corr = analyzer.analyze_correlation(
                        df[col1].to_numpy(),
                        df[col2].to_numpy(),
                        col1,
                        col2,
                        method="pearson",
                    )
                    if corr.is_significant and abs(corr.correlation) > 0.3:
                        correlations.append(corr.to_dict())
                except Exception:
                    continue

        if correlations:
            correlations.sort(key=lambda c: abs(c["correlation"]), reverse=True)
        findings["correlations"] = correlations[:10]  # Top 10

        # ── Anomalies ──
        detector = AnomalyDetector()
        anomalies = {}
        for col in analysis_cols[:5]:
            try:
                result = detector.detect_zscore(df[col].to_numpy(), col, threshold=3.0)
                anomalies[col] = result.to_dict()
            except Exception:
                continue
        findings["anomalies"] = anomalies

        # ── Distributions ──
        dist_analyzer = DistributionAnalyzer()
        distributions = {}
        for col in analysis_cols[:5]:
            try:
                dist = dist_analyzer.analyze_full(df[col].to_numpy(), col)
                distributions[col] = dist.to_dict()
            except Exception:
                continue
        findings["distributions"] = distributions

        # ── Summary ──
        anomaly_count = sum(
            v.get("outlier_count", 0) for v in anomalies.values() if isinstance(v, dict)
        )
        summary = (
            f"Stats analysis: {len(correlations)} significant correlations, "
            f"{anomaly_count} anomaly data points across "
            f"{len(distributions)} distribution profiles"
        )

        return {"findings": findings}, summary

    # ── Tool: kpi_strategy ─────────────────────────────────────────────────────

    async def _handle_kpi_strategy(
        self, kpi_tool: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        """
        Generate KPI recommendations tailored to the user's intent.

        Uses IntelligentKPIGenerator with enriched metadata (profile + stats)
        and adapts KPI count / focus based on intent:
            performance → 6 KPIs, trend-focused
            anomalies   → 4 KPIs, monitoring-focused
            segments    → 5 KPIs, comparison-focused
            drivers     → 5 KPIs, correlation-focused
            explore     → 6 KPIs, broad discovery
        """
        from services.ai.intelligent_kpi_generator import intelligent_kpi_generator

        df = context.df
        if df is None:
            return {"recommendations": []}, "No DataFrame for KPI generation"

        user_intent = context.query or "explore"

        # Gather observations to build enriched metadata
        stats = {}
        for obs in reversed(observations):
            if obs.success:
                result = obs.result or {}
                if obs.tool == "stats_engine" and "findings" in result:
                    stats = result["findings"]

        # ── Intent-driven configuration ──
        intent_config = {
            "performance": {"count": 6, "focus": "trend-focused tracking KPIs"},
            "anomalies": {"count": 4, "focus": "anomaly monitoring and alert KPIs"},
            "segments": {"count": 5, "focus": "segmentation and cohort comparison KPIs"},
            "drivers": {"count": 5, "focus": "driver analysis and correlation KPIs"},
            "explore": {"count": 6, "focus": "broad discovery and surprising KPIs"},
        }
        cfg = intent_config.get(user_intent, intent_config["explore"])

        # Enrich metadata with findings + intent
        dataset_metadata = {
            "domain_intelligence": {
                "domain": context.domain_signal,
                "confidence": context.domain_confidence,
            },
            "analysis_intent": user_intent,
            "statistical_findings": stats,
            "focus_instruction": cfg["focus"],
        }

        try:
            kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
                df=df,
                domain=context.domain_signal,
                max_kpis=cfg["count"],
                dataset_metadata=dataset_metadata,
            )

            return (
                {"recommendations": kpis},
                f"Generated {len(kpis)} KPIs "
                f"(intent={user_intent}, count={cfg['count']})",
            )
        except Exception as e:
            logger.error("[AnalystAgent] KPI generation failed: %s", e, exc_info=True)
            return {"recommendations": [], "error": str(e)}, f"KPI strategy failed: {e}"

    # ── Tool: rag ──────────────────────────────────────────────────────────────

    async def _handle_rag(
        self, rag_tool: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        """Retrieve historical context for this dataset/user from the vector store."""
        search_text = context.query or "understand dataset"

        try:
            documents = await rag_tool.search_similar_queries(
                query=search_text,
                user_id=context.user_id,
                k=5,
            )
            return (
                {"documents": documents},
                f"Retrieved {len(documents)} historical documents",
            )
        except Exception as e:
            logger.error("[AnalystAgent] RAG retrieval failed: %s", e, exc_info=True)
            return {"documents": []}, f"RAG retrieval failed: {e}"

    # ── Tool: memory ───────────────────────────────────────────────────────────

    async def _handle_memory(
        self, memory_tool: Any, observations: list[ToolResult], context: AgentContext
    ) -> tuple[dict[str, Any], str]:
        """
        Check novelty of the latest finding and store it in the user's belief store.

        Uses the BeliefStore's calculate_semantic_surprisal to determine
        whether this finding is genuinely new or already known.
        """
        # Extract the most recent meaningful finding
        finding_text = ""
        for obs in reversed(observations):
            if obs.success:
                summary = obs.reasoning_summary or ""
                if summary:
                    finding_text = summary
                    break

        if not finding_text:
            return {"note": "No finding to check"}, "Memory check skipped"

        try:
            surprisal, similar = await memory_tool.calculate_semantic_surprisal(
                context.user_id, finding_text
            )

            # Store this finding as a candidate belief for future novelty checks
            await memory_tool.add_belief(
                user_id=context.user_id,
                belief_text=finding_text,
                dataset_id=context.dataset_id,
            )

            is_novel = surprisal > 0.7
            return (
                {
                    "surprisal_score": surprisal,
                    "is_novel": is_novel,
                    "finding": finding_text,
                    "similar_beliefs": similar[:3] if similar else [],
                },
                f"Novelty: surprisal={surprisal:.2f} "
                f"({'novel' if is_novel else 'familiar'})",
            )
        except Exception as e:
            logger.error("[AnalystAgent] memory check failed: %s", e, exc_info=True)
            return {"error": str(e)}, f"Memory check failed: {e}"

    # ── Synthesis ──────────────────────────────────────────────────────────────

    async def _synthesize(
        self, query: str, observations: list[ToolResult], context: AgentContext
    ) -> str:
        """
        Produce a concise, executive-facing strategic summary.

        The prompt positions the LLM as a senior data analyst presenting
        findings to a decision-maker, not as a chatbot.
        """
        if not observations:
            return "No analysis could be performed on this dataset."

        snippets = self._build_synthesis_snippets(observations)
        user_intent = query or "explore"
        df_rows = len(context.df) if context.df is not None else "?"
        df_cols = len(context.df.columns) if context.df is not None else "?"

        prompt = (
            "You are a senior data analyst presenting strategic findings.\n\n"
            f"User's focus: {user_intent}\n"
            f"Dataset: {df_rows} rows × {df_cols} columns, domain: {context.domain_signal}\n\n"
            "Analysis observations:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, executive-facing summary that:\n"
            "1. States what the data contains (domain, size, key columns)\n"
            "2. Highlights the most important statistical findings\n"
            "3. Recommends which KPIs to track and why\n"
            "4. Suggests 1-2 specific next analytical steps\n\n"
            "Be direct, specific, and actionable. Avoid generic statements. "
            "Use numbers where possible."
        )

        try:
            from services.llm_router import llm_router

            resp = await llm_router.call(
                prompt=prompt,
                model_role="narrative_story",
                user_id=context.user_id,
                expect_json=False,
                max_tokens=768,
            )
            return resp.get("text") if isinstance(resp, dict) else str(resp)
        except Exception as e:
            logger.error("[AnalystAgent] synthesize failed: %s", e, exc_info=True)
            return "Failed to produce strategic summary."

    async def _synthesize_streaming(
        self, query: str, observations: list[ToolResult], context: AgentContext
    ):
        if not observations:
            yield {"type": "error", "content": "No analysis to summarize."}
            return

        snippets = self._build_synthesis_snippets(observations)
        user_intent = query or "explore"
        df_rows = len(context.df) if context.df is not None else "?"
        df_cols = len(context.df.columns) if context.df is not None else "?"

        prompt = (
            "You are a senior data analyst presenting strategic findings.\n\n"
            f"User's focus: {user_intent}\n"
            f"Dataset: {df_rows} rows × {df_cols} columns, domain: {context.domain_signal}\n\n"
            "Analysis observations:\n"
            + "\n".join(snippets)
            + "\n\nProvide a concise, executive-facing summary that:\n"
            "1. States what the data contains (domain, size, key columns)\n"
            "2. Highlights the most important statistical findings\n"
            "3. Recommends which KPIs to track and why\n"
            "4. Suggests 1-2 specific next analytical steps\n\n"
            "Be direct, specific, and actionable. Avoid generic statements. "
            "Use numbers where possible."
        )

        full = ""
        from services.llm_router import llm_router
        from services.retries.async_utils import retry_async

        async def call_stream():
            return llm_router.call_streaming(
                prompt=prompt,
                model_role="narrative_story",
                is_conversational=False,
                user_id=context.user_id,
            )

        try:
            stream_gen = await retry_async(call_stream, attempts=3, base_delay=0.5)
            async for chunk in stream_gen:
                if chunk.get("type") == "token":
                    token = chunk.get("content", "")
                    full += token
                    yield {"type": "token", "content": token}
                elif chunk.get("type") == "error":
                    yield {"type": "error", "content": chunk.get("content", "")}
                    return
                elif chunk.get("type") == "done":
                    yield {"type": "response_complete", "full_response": full}
                    return
        except Exception as e:
            logger.error("[AnalystAgent] stream synthesis failed: %s", e, exc_info=True)
            yield {"type": "error", "content": "Failed to stream strategic summary."}
