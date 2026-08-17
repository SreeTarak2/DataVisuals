"""
On-Demand Pipeline Stages — Tier 2 / Tier 3
=============================================

Each function in this module follows the same pattern:

1. **Check** if the data is already cached (MongoDB, Redis, or dashboard cache)
2. **Return immediately** if cached
3. **Compute** on-demand if not cached
4. **Cache** the result for subsequent calls
5. **Log** what happened for observability

This allows the API endpoints to call ``ensure_*`` functions without worrying
about whether the data exists yet — they get back the data either way.

Usage (in API routes)::

    from services.pipeline.on_demand import ensure_kpis

    kpis = await ensure_kpis(dataset_id, user_id)
    return {"kpis": kpis}
"""

import logging
from typing import Any

import polars as pl

from services.cache.dashboard_cache_service import dashboard_cache_service
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from db.database import get_database

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# TIER 2 — On-Demand (runs when user opens a specific tab)
# ═══════════════════════════════════════════════════════════════════════════


async def ensure_kpis(
    dataset_id: str,
    user_id: str,
    df: pl.DataFrame | None = None,
    force_refresh: bool = False,
) -> list[dict]:
    """
    Ensure intelligent KPI cards are computed for this dataset.

    Checks the dashboard cache first. Falls back to on-demand generation
    with the ``IntelligentKPIGenerator``. Returns cached or freshly
    generated KPIs.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.
        df:         Optional pre-loaded DataFrame (avoids redundant I/O).
        force_refresh: If True, bypass cache and regenerate.

    Returns:
        List of KPI card dicts (or empty list if generation fails).
    """
    # ── 1. Check cache ──────────────────────────────────────────────────
    if not force_refresh:
        try:
            cached = await dashboard_cache_service.get_cached_kpis(dataset_id, user_id)
            if cached:
                kpis = cached if isinstance(cached, list) else cached.get("kpis", [])
                if kpis:
                    logger.debug(f"[OnDemand] KPIs cache hit for {dataset_id[:8]}")
                    return kpis
        except Exception:
            pass

    # ── 2. Load DataFrame if not provided ────────────────────────────────
    if df is None:
        try:
            df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"[OnDemand] Failed to load DataFrame for KPIs: {e}")
            return []

    if df is None or (hasattr(df, "is_empty") and df.is_empty()):
        return []

    # ── 3. Generate KPIs ────────────────────────────────────────────────
    try:
        from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
        from db.database import get_database as _get_db

        db = _get_db()
        datasets_collection = db.uploads
        doc = await datasets_collection.find_one(
            {"_id": dataset_id}, {"metadata.domain_intelligence": 1}
        )
        domain = "general"
        metadata = {}
        if doc:
            domain_intel = doc.get("metadata", {}).get("domain_intelligence", {})
            domain = domain_intel.get("domain", "general")
            metadata = doc.get("metadata", {})

        kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
            df=df,
            domain=domain,
            max_kpis=6,
            dataset_metadata=metadata or {},
            dataset_id=dataset_id,
        )

        # Cache for subsequent calls
        if kpis:
            try:
                await dashboard_cache_service.cache_kpis(dataset_id, user_id, kpis)
            except Exception as e:
                logger.warning(f"[OnDemand] KPI cache write failed: {e}")

        logger.info(f"[OnDemand] Generated {len(kpis)} KPIs for {dataset_id[:8]}")
        return kpis

    except Exception as e:
        logger.error(f"[OnDemand] KPI generation failed: {e}", exc_info=True)
        return []


async def ensure_deep_analysis(
    dataset_id: str,
    user_id: str,
    df: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Ensure deep statistical analysis is computed for this dataset.

    Includes: enhanced analysis (distributions, correlations, outliers)
    and QUIS subspace analysis.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.
        df:         Optional pre-loaded DataFrame.

    Returns:
        Dict with keys ``enhanced_analysis``, ``quis_insights``,
        ``executive_summary``, and ``analysis_version``.
    """
    # ── 1. Check if already stored (workspace-scoped read) ───────────────
    try:
        doc = await enhanced_dataset_service.get_dataset_analytics(
            dataset_id, user_id
        )
        if doc and doc.get("deep_analysis"):
            logger.debug(f"[OnDemand] Deep analysis cache hit for {dataset_id[:8]}")
            return doc["deep_analysis"]
    except Exception:
        pass

    # ── 2. Load DataFrame ───────────────────────────────────────────────
    if df is None:
        try:
            df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"[OnDemand] Failed to load DataFrame for analysis: {e}")
            return _empty_deep_analysis()

    if df is None or (hasattr(df, "is_empty") and df.is_empty()):
        return _empty_deep_analysis()

    # ── 3. Run analysis ─────────────────────────────────────────────────
    try:
        from services.analysis.analysis_service import analysis_service
        from services.analysis.insight_interpreter import insight_interpreter

        enhanced_results = analysis_service.run_enhanced_analysis(df, depth="standard")

        quis_results = analysis_service.run_enhanced_quis_sync(df, dataset_id=dataset_id)

        try:
            executive_summary = insight_interpreter.generate_summary(enhanced_results)
        except Exception:
            executive_summary = ""

        try:
            statistical_findings = analysis_service.run_all_statistical_checks(df)
        except Exception:
            statistical_findings = {
                "correlations": [],
                "outliers": [],
                "distributions": {},
            }

        deep_analysis = {
            "enhanced_analysis": enhanced_results,
            "quis_insights": quis_results,
            "executive_summary": executive_summary,
            "analysis_version": "2.0",
        }

        # Persist to dataset_analytics
        try:
            await _upsert_analytics(dataset_id, user_id, {"deep_analysis": deep_analysis})
        except Exception as e:
            logger.warning(f"[OnDemand] Analysis persist failed: {e}")

        logger.info(
            f"[OnDemand] Deep analysis complete for {dataset_id[:8]}: "
            f"{len(quis_results.get('top_insights', []))} insights"
        )
        return deep_analysis

    except Exception as e:
        logger.error(f"[OnDemand] Deep analysis failed: {e}", exc_info=True)
        return _empty_deep_analysis()


async def ensure_chart_recommendations(
    dataset_id: str,
    user_id: str,
    df: pl.DataFrame | None = None,
) -> list[dict]:
    """
    Ensure chart recommendations are computed for this dataset.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.
        df:         Optional pre-loaded DataFrame.

    Returns:
        List of chart recommendation dicts.
    """
    # ── 1. Check if already stored (workspace-scoped read) ───────────────
    try:
        doc = await enhanced_dataset_service.get_dataset_analytics(
            dataset_id, user_id
        )
        if doc and doc.get("chart_recommendations"):
            logger.debug(f"[OnDemand] Chart recs cache hit for {dataset_id[:8]}")
            return doc["chart_recommendations"]
    except Exception:
        pass

    # ── 2. Fallback to metadata ─────────────────────────────────────────
    try:
        ds = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        meta = ds.get("metadata", {})
        stored = meta.get("chart_recommendations")
        if stored:
            logger.debug(f"[OnDemand] Chart recs from metadata for {dataset_id[:8]}")
            return stored
    except Exception:
        pass

    # ── 3. Load DataFrame ───────────────────────────────────────────────
    if df is None:
        try:
            df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"[OnDemand] Failed to load DataFrame for charts: {e}")
            return []

    if df is None or (hasattr(df, "is_empty") and df.is_empty()):
        return []

    # ── 4. Generate recommendations ─────────────────────────────────────
    try:
        from services.charts.chart_recommender import chart_recommender

        # Fetch column metadata and domain from the stored dataset doc
        ds = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        meta = ds.get("metadata", {})
        column_metadata = meta.get("column_metadata", [])
        domain_intel = meta.get("domain_intelligence", {})
        data_profile = meta.get("data_profile", {})

        # Read unified profile from separate collection (with legacy fallback)
        unified_profile = (
            await enhanced_dataset_service.get_dataset_profile(dataset_id, user_id) or {}
        )

        raw_cardinality = data_profile.get("cardinality", {}) or {}
        if not raw_cardinality:
            raw_cardinality = {
                c.get("name"): c.get("cardinality", {}).get("cardinality_level", "medium")
                for c in unified_profile.get("columns", [])
            }
        cardinality = {
            col: (val if isinstance(val, dict) else {"cardinality_level": val, "unique_count": 0})
            for col, val in raw_cardinality.items()
        }

        recommendations = chart_recommender.recommend_charts(
            df=df,
            column_metadata=column_metadata or [],
            domain=domain_intel.get("domain", "general"),
            cardinality=cardinality,
            time_columns=domain_intel.get("time_columns", []),
        )

        # Persist to dataset_analytics
        if recommendations:
            try:
                await _upsert_analytics(
                    dataset_id, user_id, {"chart_recommendations": recommendations}
                )
            except Exception as e:
                logger.warning(f"[OnDemand] Chart recs persist failed: {e}")

        logger.info(f"[OnDemand] Generated {len(recommendations)} chart recommendations")
        return recommendations

    except Exception as e:
        logger.error(f"[OnDemand] Chart recommendations failed: {e}", exc_info=True)
        return []


async def ensure_dashboard_design(
    dataset_id: str,
    user_id: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Ensure a dashboard design blueprint exists for this dataset.

    Triggers the AI Designer Service if no design is cached.
    Returns the dashboard config or None.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.
        force_refresh: Regenerate even if cached.

    Returns:
        Dashboard config dict or empty dict if not available.
    """
    # ── 1. Check if already designed ────────────────────────────────────
    if not force_refresh:
        try:
            db = get_database()
            dashboard = await db.dashboards.find_one(
                {"dataset_id": dataset_id, "user_id": user_id, "is_default": True},
                {"blueprint": 1},
            )
            if dashboard and dashboard.get("blueprint"):
                logger.debug(f"[OnDemand] Dashboard cache hit for {dataset_id[:8]}")
                return dashboard["blueprint"]
        except Exception:
            pass

    # ── 2. Generate dashboard ───────────────────────────────────────────
    try:
        from services.ai.ai_designer_service import AIDesignerService
        from db.database import get_database as _get_db
        from services.workspace import workspace_service

        db = _get_db()
        designer = AIDesignerService(sync_db=db)
        wid = await workspace_service.resolve_effective_workspace_id(None, user_id)
        result = await designer.design_intelligent_dashboard(
            dataset_id=dataset_id,
            user_id=user_id,
            force_regenerate=force_refresh,
            workspace_id=wid,
        )
        logger.info(f"[OnDemand] Dashboard designed for {dataset_id[:8]}")
        return result or {}

    except Exception as e:
        logger.error(f"[OnDemand] Dashboard design failed: {e}", exc_info=True)
        return {}


async def ensure_data_quality_report(
    dataset_id: str,
    user_id: str,
    column_metadata: list[dict] | None = None,
    sample_rows: list[dict] | None = None,
    row_count: int | None = None,
) -> dict[str, Any]:
    """
    Ensure the LLM-powered data quality report is computed.

    This is Tier 2 — only runs when the user opens the Quality tab.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.
        column_metadata: Column metadata from the stored doc.
        sample_rows: Sample rows for spot-checking.
        row_count: Total row count.

    Returns:
        DataQualityAgent report dict.
    """
    # ── 1. Check if already stored (workspace-scoped read) ───────────────
    try:
        doc = await enhanced_dataset_service.get_dataset_analytics(
            dataset_id, user_id
        )
        if doc and doc.get("data_quality_agent"):
            return doc["data_quality_agent"]
    except Exception:
        pass

    # ── 2. Fetch metadata if not provided ───────────────────────────────
    if not column_metadata or not sample_rows:
        try:
            ds = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
            meta = ds.get("metadata", {})
            column_metadata = column_metadata or meta.get("column_metadata", [])
            sample_rows = sample_rows or meta.get("sample_data", [])
            row_count = row_count or ds.get("row_count", 0)
        except Exception:
            pass

    if not column_metadata:
        return {}

    # ── 3. Run quality agent ────────────────────────────────────────────
    try:
        from services.data_quality import DataQualityAgent

        quality_agent = DataQualityAgent()
        quality_report = await quality_agent.run_quality_check(
            columns=column_metadata,
            sample_rows=sample_rows[:5] if sample_rows else None,
            row_count=row_count or 0,
            dataset_id=dataset_id,
        )

        report = {
            "overall_score": quality_report.overall_score,
            "issues": quality_report.issues[:50],
            "completeness": quality_report.completeness,
            "consistency": quality_report.consistency,
            "distribution_drift": quality_report.distribution_drift[:10],
            "schema_changes": quality_report.schema_changes,
            "passed_checks": quality_report.passed_checks,
            "failed_checks": quality_report.failed_checks,
        }

        # Persist
        try:
            await _upsert_analytics(dataset_id, user_id, {"data_quality_agent": report})
        except Exception:
            pass

        logger.info(f"[OnDemand] Data quality report computed for {dataset_id[:8]}")
        return report

    except Exception as e:
        logger.warning(f"[OnDemand] Data quality report failed: {e}")
        return {}


async def ensure_entity_discovery(
    dataset_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """
    Ensure entity discovery (knowledge graph) is computed for this dataset.

    Most callers should use ``GET /datasets/{id}/understanding`` instead,
    which already builds the full understanding report on-demand from the
    unified profile. This function is a fallback for when the understanding
    endpoint's inline discovery fails.

    Args:
        dataset_id: Dataset identifier.
        user_id:    Owner.

    Returns:
        Entity discovery report dict or None.
    """
    # ── 1. Check metadata ───────────────────────────────────────────────
    try:
        ds = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        meta = ds.get("metadata", {})
        stored = meta.get("entity_discovery")
        if stored:
            return stored
    except Exception:
        pass

    # ── 2. Build from unified profile (the understanding endpoint already
    #    does this on-demand, so this is a lightweight pass-through).
    #    Return None and let the caller fall through to the understanding endpoint.
    return None


# ═══════════════════════════════════════════════════════════════════════════
# TIER 3 — Explicit (only when user clicks a button)
# ═══════════════════════════════════════════════════════════════════════════


async def ensure_deep_reasoning(
    dataset_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Ensure deep reasoning / analytical strategy is computed.

    Tier 3 — only runs when the user explicitly requests strategic advice.
    """
    try:
        from prompts.sql import get_deep_reasoning_prompt
        from llm.router import llm_router
        from services.ai.ai_designer_service import AIDesignerService

        db = get_database()
        designer = AIDesignerService(sync_db=db)
        ds = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        meta = ds.get("metadata", {})

        dataset_context_string = designer._create_dataset_context_string(meta)
        reasoning_prompt = get_deep_reasoning_prompt(dataset_context_string)

        strategy_json = await llm_router.call(
            reasoning_prompt,
            model_role="insight_generation",
            expect_json=True,
            temperature=0.7,
        )

        result = {
            "analytical_strategy": strategy_json.get("analytical_strategy", ""),
            "priority_signals": strategy_json.get("priority_signals", []),
        }

        # Persist to dataset doc (workspace-scoped write)
        try:
            from db.tenant_guard import tenant_scope_query
            from services.workspace import workspace_service

            wid = await workspace_service.resolve_effective_workspace_id(None, user_id)
            db.uploads.update_one(
                tenant_scope_query("uploads", {"_id": dataset_id}, wid, user_id),
                {
                    "$set": {
                        "metadata.analytical_strategy": result["analytical_strategy"],
                        "metadata.priority_signals": result["priority_signals"],
                    }
                },
            )
        except Exception as e:
            logger.warning(f"[OnDemand] Deep reasoning persist failed: {e}")

        logger.info(f"[OnDemand] Deep reasoning complete for {dataset_id[:8]}")
        return result

    except Exception as e:
        logger.error(f"[OnDemand] Deep reasoning failed: {e}", exc_info=True)
        return {"analytical_strategy": "", "priority_signals": []}


# ═══════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════


async def _upsert_analytics(dataset_id: str, user_id: str, fields: dict[str, Any]) -> None:
    """Upsert fields into the dataset_analytics collection.

    All field values are sanitized via ``convert_types_for_json`` before
    the MongoDB write to prevent crashes from numpy scalars (np.int64,
    np.float64, np.bool_), numpy arrays, Polars Series, or NaN/Inf floats
    that MongoDB rejects.

    Tenant isolation: writes are pinned to the caller's effective workspace
    (explicit or personal) and every doc is tagged with ``workspace_id`` so
    the strict workspace-scoped reads and composite indexes apply.
    """
    from datetime import datetime, timezone
    from db.tenant_guard import enforce_workspace_filter
    from services.pipeline.helpers import convert_types_for_json
    from services.workspace import workspace_service

    db = get_database()
    wid = await workspace_service.resolve_effective_workspace_id(None, user_id)
    analytics_filter: dict = {"dataset_id": dataset_id, "workspace_id": wid}
    # Fail-closed: the write must be pinned to the caller's workspace.
    enforce_workspace_filter("dataset_analytics", analytics_filter, wid, "write")

    set_fields = {
        **fields,
        "dataset_id": dataset_id,
        "user_id": user_id,
        "workspace_id": wid,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    # On first insert, also set computed_at
    set_fields.setdefault("computed_at", datetime.now(timezone.utc).replace(tzinfo=None))
    # Set pipeline_version if not already present
    set_fields.setdefault("pipeline_version", "3.0-tier2")

    # ── Sanitize ALL field values for MongoDB compatibility ───────────────
    # This is the central fix for the recurring numpy→MongoDB serialization
    # crash that was silently dropping analysis results.
    set_fields = convert_types_for_json(set_fields)

    await db.dataset_analytics.update_one(
        analytics_filter,
        {"$set": set_fields},
        upsert=True,
    )


def _empty_deep_analysis() -> dict[str, Any]:
    """Return an empty deep analysis structure."""
    return {
        "enhanced_analysis": {
            "depth": "not_computed",
            "row_count": 0,
            "column_count": 0,
            "distributions": [],
            "correlations": [],
        },
        "quis_insights": {
            "summary": {"total_questions": 0, "significant_insights": 0},
            "insights": [],
            "top_insights": [],
        },
        "executive_summary": "",
        "analysis_version": "2.0",
    }
