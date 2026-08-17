"""
AI API routes - provides endpoints for AI-generated dashboard configs and design endpoints.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from services.auth_service import get_current_user
from core.rate_limiter import limiter, RateLimits
from services.ai.ai_designer_service import ai_designer_service

logger = logging.getLogger(__name__)

router = APIRouter()


class _SkipPersistence(Exception):
    """Internal sentinel: skip blueprint persistence (used for transient views)."""


def _resolve_chart_config(component: dict) -> Optional[dict]:
    """
    Extract a renderable chart config from a dashboard component dict.

    Returns None when the component isn't a chart or lacks chart_type/columns
    (callers treat this as "skip / not a chart").
    """
    if not isinstance(component, dict):
        return None
    chart_config = component.get("config", {})
    if not chart_config:
        chart_config = {
            "type": "chart",
            "title": component.get("title", "Chart"),
            "chart_type": component.get("chart_type", "bar"),
            "columns": component.get("columns", []),
            "aggregation": component.get("aggregation", "sum"),
        }
    if not chart_config.get("chart_type") and not chart_config.get("columns"):
        return None
    return chart_config


def _find_blueprint_component_index(components: List[dict], component: dict) -> Optional[int]:
    """
    Locate a blueprint chart component matching the incoming component.

    Matching order: id → title (case-insensitive) → chart_type + columns.
    Returns the list index or None when nothing matches.
    """
    for idx, comp in enumerate(components):
        if not isinstance(comp, dict) or comp.get("type") != "chart":
            continue

        if component.get("id") and comp.get("id") == component.get("id"):
            return idx

        incoming_title = (component.get("title") or "").strip().lower()
        existing_title = (comp.get("title") or "").strip().lower()
        if incoming_title and incoming_title == existing_title:
            return idx

        incoming_cfg = component.get("config") or {}
        existing_cfg = comp.get("config") or {}
        if incoming_cfg.get("chart_type") == existing_cfg.get("chart_type") and (
            incoming_cfg.get("columns") or []
        ) == (existing_cfg.get("columns") or []):
            return idx
    return None


class DashboardDesignRequest(BaseModel):
    design_preference: Optional[str] = None
    force_regenerate: bool = False
    conversation_summary: Optional[str] = None
    redesign_mode: str = "layout"  # "layout" = rearrange existing, "full" = re-compute everything
    selected_columns: Optional[List[str]] = None
    user_intent: Optional[str] = None


@router.get("/{dataset_id}/dashboard")
@limiter.limit(RateLimits.DATASET_GET)
async def get_ai_dashboard(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get the complete AI-generated dashboard configuration (blueprint with all components).
    Frontend endpoint: Used by useDashboardGeneration hook to fetch the full dashboard config.

    Returns dashboard blueprint with:
    - components (KPIs + Charts with layout info)
    - design pattern
    - summary
    - reasoning
    """
    from db.database import get_database

    db = get_database()

    # Fetch the dashboard blueprint from the dashboards collection
    dashboard = await db.dashboards.find_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True}
    )

    if not dashboard:
        # No dashboard found - return empty config
        return {
            "dashboard_blueprint": None,
            "design_pattern": None,
            "components": [],
            "summary": None,
            "reasoning": "No AI-generated dashboard found yet",
            "cached": False,
            "created_at": None,
        }

    blueprint = dashboard.get("blueprint", {})

    return {
        "dashboard_blueprint": blueprint,
        "design_pattern": dashboard.get("design_pattern"),
        "pattern_name": dashboard.get("pattern_name"),
        "components": blueprint.get("components", []),
        "summary": blueprint.get("summary") or blueprint.get("description"),
        "reasoning": dashboard.get("reasoning"),
        "cached": True,
        "created_at": dashboard.get("created_at"),
    }


@router.post("/{dataset_id}/design-dashboard")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def design_dashboard(
    request: Request,
    dataset_id: str,
    body: DashboardDesignRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate or regenerate the AI dashboard blueprint for a dataset.
    Frontend endpoint: Used by the dashboard Redesign/Regenerate action.
    """
    body = body or DashboardDesignRequest()
    try:
        return await ai_designer_service.design_intelligent_dashboard(
            dataset_id=dataset_id,
            user_id=current_user["id"],
            design_preference=body.design_preference,
            force_regenerate=body.force_regenerate,
            conversation_summary=body.conversation_summary,
            redesign_mode=body.redesign_mode,
            selected_columns=body.selected_columns,
            user_intent=body.user_intent,
            workspace_id=current_user.get("workspace_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{dataset_id}/generate-dashboard")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def generate_dashboard(
    request: Request,
    dataset_id: str,
    force_regenerate: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """
    Legacy dashboard generation alias kept for older frontend fallback code.
    """
    try:
        return await ai_designer_service.design_intelligent_dashboard(
            dataset_id=dataset_id,
            user_id=current_user["id"],
            force_regenerate=force_regenerate,
            workspace_id=current_user.get("workspace_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── CHART RETRY ──────────────────────────────────────────────────────────────
# Hydrates a dashboard chart component with rendered chart_data on demand.
# Re-enabled: the Dashboard chart grid relies on this endpoint to auto-fill
# chart data for blueprint components (which carry config, not traces).


@router.post("/{dataset_id}/retry-chart")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def retry_chart(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retry rendering a failed chart component.

    Request body:
    - component: The dashboard component object with config (chart_type, columns, ...)

    Returns rendered chart_data (traces + layout) and the resolved config.
    """
    from db.database import get_database
    from services.charts.chart_render_service import chart_render_service
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    db = get_database()

    body = await request.json()
    component = body.get("component", {})

    if not component:
        raise HTTPException(status_code=400, detail="component is required")

    # Extract + validate chart config from component
    chart_config = _resolve_chart_config(component)
    if chart_config is None:
        raise HTTPException(
            status_code=400, detail="component must have chart_type or columns"
        )

    try:
        df = await enhanced_dataset_service.load_dataset_data(
            dataset_id,
            current_user["id"],
            max_rows=body.get("max_rows", 10000),
        )

        if df is None or df.is_empty():
            raise HTTPException(status_code=400, detail="Dataset is empty or not found")

        # Cross-filter: apply {field, value} filters before rendering so the
        # chart re-aggregates over only the filtered rows (Power BI-style).
        from core.chart_filter import apply_df_filters

        df = apply_df_filters(df, body.get("filters"))
        if df.is_empty():
            chart_data = {
                "data": [],
                "layout": {},
                "metadata": {"empty_filtered": True, "filtered_out": True},
            }
            return {
                "success": True,
                "chart_data": chart_data,
                "updated_config": chart_config,
            }

        chart_payload = await chart_render_service.render_chart(
            df,
            chart_config,
            theme=body.get("theme", "dark"),
        )

        chart_data = {
            "data": chart_payload.get("data") or chart_payload.get("traces", []),
            "layout": chart_payload.get("layout", {}),
            # Sampling metadata (LTTB / category caps) powers the frontend's
            # "shown of total" honesty badge on the chart card.
            "metadata": chart_payload.get("metadata", {}),
        }

        # Persist retried chart into the default dashboard blueprint so it survives relogin.
        dashboard = await db.dashboards.find_one(
            {
                "dataset_id": dataset_id,
                "user_id": current_user["id"],
                "is_default": True,
            }
        )

        if dashboard and isinstance(dashboard.get("blueprint"), dict):
            blueprint = dashboard.get("blueprint") or {}
            components = blueprint.get("components") or []

            target_idx = _find_blueprint_component_index(components, component)

            if target_idx is not None:
                existing = components[target_idx]
                existing_cfg = existing.get("config") or {}
                components[target_idx] = {
                    **existing,
                    "chart_data": chart_data,
                    "config": {
                        **existing_cfg,
                        **chart_config,
                    },
                }

                blueprint["components"] = components
                await db.dashboards.update_one(
                    {"_id": dashboard["_id"]},
                    {"$set": {"blueprint": blueprint, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
                )

        return {
            "success": True,
            "chart_data": chart_data,
            "updated_config": chart_config,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to retry chart: {str(exc)}"
        )


@router.post("/{dataset_id}/hydrate-charts")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def hydrate_charts(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Bulk-render every config-only chart component in a single request.

    Replaces the N-per-chart `retry-chart` calls the dashboard used to fire
    (Tradeoff #1 from CHART_PRODUCTION_READINESS.md). Loads the dataset ONCE,
    renders all charts in parallel server-side, persists successes into the
    default dashboard blueprint in a single write, and returns per-component
    results.

    Request body:
    - components: list of dashboard chart component dicts (each with config)
    - theme: "light" | "dark" (default "dark")
    - max_rows: optional row cap (default 10000)

    Returns:
    {
        "hydrated": int,   # charts successfully rendered
        "total": int,      # charts requested & renderable
        "results": [
            {
                "index": int,          # position in the requested components array
                "id": str | None,
                "title": str | None,
                "success": bool,
                "chart_data": {...} | None,
                "updated_config": {...} | None,
                "error": str | None,
            }
        ]
    }
    """
    from db.database import get_database
    from services.charts.chart_render_service import chart_render_service
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    db = get_database()

    body = await request.json()
    components = body.get("components") or []
    if not isinstance(components, list) or not components:
        return {"hydrated": 0, "total": 0, "results": []}

    # Resolve renderable chart configs (skip non-chart / invalid components).
    targets = []  # (index_in_request, component, chart_config)
    for idx, comp in enumerate(components):
        chart_config = _resolve_chart_config(comp)
        if chart_config:
            targets.append((idx, comp, chart_config))

    if not targets:
        return {"hydrated": 0, "total": 0, "results": []}

    try:
        df = await enhanced_dataset_service.load_dataset_data(
            dataset_id,
            current_user["id"],
            max_rows=body.get("max_rows", 10000),
        )
        if df is None or df.is_empty():
            raise HTTPException(status_code=400, detail="Dataset is empty or not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(exc)}")

    # Cross-filter: apply the shared filter context to the loaded frame ONCE
    # so every hydrated chart re-aggregates over the same filtered rows.
    filters = body.get("filters")
    if filters:
        from core.chart_filter import apply_df_filters

        df = apply_df_filters(df, filters)

    # Filter excluded every row → every chart renders the honest empty state.
    if df.is_empty():
        empty_results = []
        for idx, comp, chart_config in targets:
            empty_results.append(
                {
                    "index": idx,
                    "id": comp.get("id"),
                    "title": comp.get("title"),
                    "success": True,
                    "chart_data": {
                        "data": [],
                        "layout": {},
                        "metadata": {"empty_filtered": True, "filtered_out": True},
                    },
                    "updated_config": chart_config,
                    "error": None,
                }
            )
        return {
            "hydrated": len(empty_results),
            "total": len(targets),
            "results": empty_results,
        }

    theme = body.get("theme", "dark")

    async def _render_one(idx: int, comp: dict, chart_config: dict):
        """Render one chart; never raises — failures become error results."""
        try:
            chart_payload = await chart_render_service.render_chart(
                df,
                chart_config,
                theme=theme,
            )
            chart_data = {
                "data": chart_payload.get("data") or chart_payload.get("traces", []),
                "layout": chart_payload.get("layout", {}),
                "metadata": chart_payload.get("metadata", {}),
            }
            return {
                "index": idx,
                "id": comp.get("id"),
                "title": comp.get("title"),
                "success": True,
                "chart_data": chart_data,
                "updated_config": chart_config,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[hydrate-charts] component {idx} failed: {exc}")
            return {
                "index": idx,
                "id": comp.get("id"),
                "title": comp.get("title"),
                "success": False,
                "chart_data": None,
                "updated_config": None,
                "error": str(exc)[:300],
            }

    # ── Parallel server-side rendering (one dataset load, many charts) ──
    results = await asyncio.gather(
        *(_render_one(idx, comp, cfg) for idx, comp, cfg in targets)
    )

    # ── Persist successful renders into the default blueprint (single write) ──
    # Cross-filter results (filters active) are NEVER persisted — they are
    # transient filtered views; persisting them would permanently overwrite
    # the full-data blueprint with a filtered slice.
    try:
        if filters:
            raise _SkipPersistence()
        dashboard = await db.dashboards.find_one(
            {
                "dataset_id": dataset_id,
                "user_id": current_user["id"],
                "is_default": True,
            }
        )
        if dashboard and isinstance(dashboard.get("blueprint"), dict):
            blueprint = dashboard.get("blueprint") or {}
            bp_components = blueprint.get("components") or []
            changed = False

            for r in results:
                if not r.get("success"):
                    continue
                comp = components[r["index"]]
                target_idx = _find_blueprint_component_index(bp_components, comp)
                if target_idx is None:
                    continue
                existing = bp_components[target_idx]
                existing_cfg = existing.get("config") or {}
                bp_components[target_idx] = {
                    **existing,
                    "chart_data": r["chart_data"],
                    "config": {
                        **existing_cfg,
                        **r["updated_config"],
                    },
                }
                changed = True

            if changed:
                blueprint["components"] = bp_components
                await db.dashboards.update_one(
                    {"_id": dashboard["_id"]},
                    {
                        "$set": {
                            "blueprint": blueprint,
                            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                        }
                    },
                )
    except _SkipPersistence:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[hydrate-charts] blueprint persistence skipped: {exc}")

    return {
        "hydrated": sum(1 for r in results if r.get("success")),
        "total": len(targets),
        "results": results,
    }



# ── DASHBOARD STORY ENDPOINT DISABLED ────────────────────────────────────────────
# The get_dashboard_story endpoint served the auto-generated narrative card that
# has been removed from the frontend. Professional dashboards (Stripe, Grafana,
# Vercel, Linear) don't use narrative text — they use KPI stat cards with sparklines.
# The _generate_dashboard_story function is preserved for internal KPI pipeline use.
#
# @router.get("/{dataset_id}/dashboard-story")
# @limiter.limit(RateLimits.DATASET_GET)
# async def get_dashboard_story(...):
#     ...
#
# def _fmt_kpi_value(kpi: dict) -> str:
#     ...


@router.post("/{dataset_id}/suggest-columns")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def suggest_columns(
    request: Request,
    dataset_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Suggest columns relevant to the user's intent using an LLM.

    Sends column metadata (name, type, cardinality, sample values) plus
    the user's natural language intent to a cheap model, and returns a
    ranked list of column names that would be useful for the analysis.

    Body:
    {
        "user_intent": str,
        "max_columns": int | None  (optional, default 20)
    }

    Returns:
    {
        "suggested_columns": [str],
        "reasoning": str | None
    }
    """
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service
    from llm.router import llm_router

    user_intent = (body.get("user_intent") or "").strip()
    if not user_intent:
        return {"suggested_columns": [], "reasoning": None}

    max_columns = body.get("max_columns", 20)

    # ── Fetch dataset metadata ─────────────────────────────────
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    meta = dataset.get("metadata", {})
    column_metadata = meta.get("column_metadata", [])
    domain = meta.get("domain_intelligence", {}).get("domain", "general")

    # Build a compact column summary for the LLM prompt
    col_summaries = []
    for col in column_metadata[:50]:  # Limit to 50 columns to keep prompt compact
        name = col.get("name", "?")
        dtype = col.get("type", "unknown")
        null_pct = col.get("null_percentage", 0)
        unique = col.get("unique_count", 0)
        col_summaries.append(f"  {name}: {dtype} (null={null_pct}%, unique={unique})")

    col_context = "\n".join(col_summaries) if col_summaries else "(no columns)"

    # ── Build the prompt ───────────────────────────────────────
    prompt = (
        f"Dataset domain: {domain}\n\n"
        f"Available columns:\n{col_context}\n\n"
        f"User wants to: {user_intent}\n\n"
        "Which columns from the list above are most relevant to the user's analysis?\n"
        "Return ONLY valid JSON with no markdown fences:\n"
        '{\n'
        '  "columns": ["col1", "col2", ...],\n'
        '  "reasoning": "Brief one-sentence explanation"\n'
        "}\n\n"
        "Rules:\n"
        "- Include columns the user explicitly mentioned or clearly implied.\n"
        "- Include at least 1 measure/numeric column and 1 group-by column.\n"
        "- Limit to at most 12 columns — the most essential ones.\n"
        "- Order by relevance, most important first.\n"
        "- Only use column names that exist in the list above.\n"
        "- If the intent is too vague, return all numeric + time columns."
    )

    try:
        response = await llm_router.call(
            prompt=prompt,
            model_role="column_suggestion",
            expect_json=True,
            temperature=0.1,
            max_tokens=512,
            user_id=current_user["id"],
        )

        if isinstance(response, dict):
            columns = response.get("columns", [])
            reasoning = response.get("reasoning", "")

            # Validate: only return columns that actually exist in the dataset
            existing_names = {c.get("name", "") for c in column_metadata}
            valid_columns = [c for c in columns if c in existing_names][:max_columns]

            return {
                "suggested_columns": valid_columns,
                "reasoning": reasoning or None,
            }
        elif isinstance(response, list):
            # Handle models that return an array directly
            columns = response[:max_columns]
            existing_names = {c.get("name", "") for c in column_metadata}
            valid_columns = [c for c in columns if isinstance(c, str) and c in existing_names]
            return {
                "suggested_columns": valid_columns,
                "reasoning": None,
            }
        else:
            logger.warning(
                "[SuggestColumns] Unexpected response type: %s", type(response)
            )
            return {"suggested_columns": [], "reasoning": None}

    except Exception as e:
        logger.warning("[SuggestColumns] LLM call failed: %s", e)
        return {"suggested_columns": [], "reasoning": None}


@router.get("/design-patterns")
@limiter.limit(RateLimits.DATASET_GET)
async def get_design_patterns(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await ai_designer_service.get_available_patterns()
