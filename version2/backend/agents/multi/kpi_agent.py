"""
KPICAgent — deterministic KPI pipeline agent.

NOT a BaseAgent subclass — runs a fixed pipeline:
  profile + candidate_specs → plan → compute → critic → narrate → intelligent_kpis

Designed for the data scientist mindset: deterministic selection + optional LLM enrichment.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import polars as pl

from agents.multi.orchestrator import PipelineContext

logger = logging.getLogger(__name__)

_kpi_generator_instance: Any = None


def _dedup_kpis_by_slug(
    cards: List[Dict[str, Any]],
    intelligent_kpis: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge ctx.cards (from narrator pipeline) and ctx.intelligent_kpis
    (from IntelligentKPIGenerator) into a single deduplicated list.

    Deduplication key is "slug" — derived from the KPI's ``column`` field
    (lowercased, stripped). When a card and an intelligent KPI share the
    same slug, the intelligent KPI wins (it has richer computed fields).
    """
    result: List[Dict[str, Any]] = []
    seen_slugs: set = set()

    def _get_slug(k: Any) -> str:
        if isinstance(k, dict):
            col = k.get("column") or k.get("title") or ""
            return str(col).lower().strip()
        if hasattr(k, "column"):
            return str(k.column).lower().strip()
        if hasattr(k, "title"):
            return str(k.title).lower().strip()
        return ""

    # Intelligent KPIs first (they have richer computed fields)
    for k in intelligent_kpis:
        slug = _get_slug(k)
        if slug and slug not in seen_slugs:
            # Convert to dict if it's a Pydantic model or dataclass
            if hasattr(k, "model_dump"):
                result.append(k.model_dump())
            elif hasattr(k, "to_dict"):
                result.append(k.to_dict())
            else:
                result.append(dict(k) if not isinstance(k, dict) else k)
            seen_slugs.add(slug)

    # Cards fill remaining slots (skip duplicates)
    for c in cards:
        slug = _get_slug(c)
        if slug and slug not in seen_slugs:
            if hasattr(c, "model_dump"):
                result.append(c.model_dump())
            elif hasattr(c, "to_dict"):
                result.append(c.to_dict())
            else:
                result.append(dict(c) if not isinstance(c, dict) else c)
            seen_slugs.add(slug)

    return result


class KPICAgent:
    """
    KPI pipeline agent — orchestrates plan/compute/critic/narrate/intelligent_kpis.

    Implements the PipelineAgent protocol so the orchestrator can call run_pipeline(ctx).
    """

    async def run_pipeline(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run the full KPI pipeline: plan → compute → critic → narrate + intelligent KPIs.

        All inputs come from ctx (profile, specs, df). All outputs are written back to ctx.
        Safe to call with empty or partial ctx — falls back gracefully.
        """
        if ctx.df is None or ctx.df.is_empty():
            logger.warning("[KPICAgent] No DataFrame in context — skipping KPI pipeline")
            ctx.errors.append("KPICAgent: no DataFrame provided")
            ctx.partial_failure = True
            return ctx

        if ctx.profile is None:
            logger.warning("[KPICAgent] No profile in context — skipping plan stage")
        elif not ctx.specs:
            logger.warning("[KPICAgent] No specs in context — skipping to intelligent KPIs")
        else:
            try:
                from services.pipeline.planner import plan

                ctx.specs = await plan(ctx.profile, ctx.specs)
                logger.info(f"[KPICAgent] Plan: {len(ctx.specs)} specs confirmed")
            except Exception as e:
                logger.warning(f"[KPICAgent] plan failed ({e}) — continuing with candidates")
                ctx.errors.append(f"plan: {e}")

        try:
            from services.pipeline.compute import compute_all

            ctx.compute_results = await compute_all(ctx.specs, ctx.df)
            logger.info(f"[KPICAgent] Compute: {len(ctx.compute_results)} results")
        except Exception as e:
            logger.warning(f"[KPICAgent] compute_all failed ({e})")
            ctx.errors.append(f"compute: {e}")

        if ctx.compute_results:
            try:
                from services.pipeline.critic import check_all

                ctx.compute_results = check_all(ctx.compute_results)
                logger.info(f"[KPICAgent] Critic: checked {len(ctx.compute_results)} results")
            except Exception as e:
                logger.warning(f"[KPICAgent] check_all failed ({e})")
                ctx.errors.append(f"critic: {e}")

        if ctx.compute_results and ctx.specs:
            try:
                from services.pipeline.narrator import narrate

                ctx.cards = await narrate(ctx.compute_results, ctx.specs)
                logger.info(f"[KPICAgent] Narrate: {len(ctx.cards)} cards")
            except Exception as e:
                logger.warning(f"[KPICAgent] narrate failed ({e})")
                ctx.errors.append(f"narrate: {e}")

        try:
            from services.ai.intelligent_kpi_generator import IntelligentKPIGenerator

            global _kpi_generator_instance
            if _kpi_generator_instance is None:
                _kpi_generator_instance = IntelligentKPIGenerator()

            df_for_kpi: pl.DataFrame = ctx.df
            if not isinstance(df_for_kpi, pl.DataFrame):
                logger.warning(
                    "[KPICAgent] df is not a Polars DataFrame — skipping intelligent KPIs"
                )
            else:
                dataset_metadata = {
                    "domain_intelligence": {
                        "domain": ctx.domain_signal,
                        "confidence": ctx.domain_confidence,
                    }
                }
                ctx.intelligent_kpis = await _kpi_generator_instance.generate_intelligent_kpis(
                    df=df_for_kpi,
                    domain=ctx.domain_signal,
                    max_kpis=6,
                    dataset_metadata=dataset_metadata,
                )
                logger.info(f"[KPICAgent] Intelligent KPIs: {len(ctx.intelligent_kpis)} generated")
        except Exception as e:
            logger.warning(f"[KPICAgent] intelligent_kpis failed ({e})")
            ctx.errors.append(f"intelligent_kpis: {e}")

        # ── Deduplicate: merge ctx.cards and ctx.intelligent_kpis by slug ────
        try:
            merged = _dedup_kpis_by_slug(ctx.cards, ctx.intelligent_kpis)
            ctx.intelligent_kpis = merged
            logger.info(
                f"[KPICAgent] Dedup: merged {len(ctx.cards)} cards + "
                f"{len(ctx.intelligent_kpis)} intelligent KPIs → {len(merged)} unique"
            )
        except Exception as e:
            logger.warning(f"[KPICAgent] Dedup failed: {e}")

        return ctx
