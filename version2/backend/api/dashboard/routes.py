import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request

from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_kpis(dataset: dict) -> list[dict]:
    row_count = dataset.get("row_count") or 0
    column_count = dataset.get("column_count") or 0
    quality = dataset.get("metadata", {}).get("data_quality", {})
    completeness = quality.get("completeness")

    kpis = [
        {
            "id": "rows",
            "title": "Rows",
            "value": row_count,
            "format": "number",
        },
        {
            "id": "columns",
            "title": "Columns",
            "value": column_count,
            "format": "number",
        },
    ]

    if completeness is not None:
        kpis.append(
            {
                "id": "completeness",
                "title": "Data Completeness",
                "value": completeness,
                "format": "percent",
            }
        )

    return kpis


@router.get("/{dataset_id}/overview")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_overview(
    request: Request,
    dataset_id: str,
    period: str = Query("all"),
    current_user: dict = Depends(get_current_user),
):
    from services.pipeline.on_demand import ensure_kpis

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)

    # ── Intelligent KPIs (lazy — computed on first access, cached thereafter) ─
    intelligent_kpis = await ensure_kpis(dataset_id, user_id)
    kpi_source = "intelligent" if intelligent_kpis else "basic"

    # ── Fallback: basic structural KPIs if no intelligent KPIs ───────────────
    kpis = intelligent_kpis or _build_kpis(dataset)

    # ── Signal: record KPI views (fire-and-forget, non-blocking) ────────────
    from services.learning.signal_collector import signal_collector
    import asyncio as _asyncio

    _asyncio.ensure_future(
        signal_collector.record_kpi_view_bulk(
            user_id=user_id,
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            kpis=kpis,
            source="dashboard",
        )
    )

    return {
        "dataset": {
            "id": dataset.get("id") or dataset_id,
            "name": dataset.get("name"),
            "row_count": dataset.get("row_count", 0),
            "column_count": dataset.get("column_count", 0),
            "processing_status": dataset.get("processing_status"),
        },
        "kpis": kpis,
        "kpi_source": kpi_source,
        "period": period,
        "available_periods": ["all"],
    }


@router.get("/{dataset_id}/charts")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_charts(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    from db.database import get_database

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)
    db = get_database()

    # First, try to get the dashboard blueprint from the dashboards collection
    dashboard = await db.dashboards.find_one(
        {"dataset_id": dataset_id, "user_id": user_id, "is_default": True}
    )

    charts = []
    if dashboard and dashboard.get("blueprint"):
        blueprint = dashboard["blueprint"]
        components = blueprint.get("components", [])
        # Extract all chart components from the blueprint
        charts = [comp for comp in components if comp.get("type") == "chart"]

    # Fallback to analytics if no dashboard found
    if not charts:
        combined = await enhanced_dataset_service.get_full_dataset_with_analytics(
            dataset_id,
            user_id,
        )
        analytics = combined.get("analytics") or {}
        metadata = combined.get("metadata") or {}
        charts = (
            analytics.get("chart_recommendations") or metadata.get("chart_recommendations") or []
        )

    # Last resort: generate chart recommendations on demand
    if not charts:
        try:
            from services.pipeline.on_demand import ensure_chart_recommendations

            charts = await ensure_chart_recommendations(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"[Dashboard] On-demand chart recommendations failed: {e}")

    # ── Signal: record chart views (fire-and-forget) ────────────────────────
    from services.learning.signal_collector import signal_collector
    import asyncio as _asyncio

    for chart in charts:
        chart_config = chart.get("config", {})
        _asyncio.ensure_future(
            signal_collector.record_chart_view(
                user_id=user_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                chart_id=chart.get("id", "") or chart.get("title", ""),
                chart_metadata={
                    "chart_type": chart_config.get("chart_type", ""),
                    "columns": chart_config.get("columns", []),
                    "title": chart.get("title", ""),
                    "aggregation": chart_config.get("aggregation", "sum"),
                    "group_by": chart_config.get("group_by"),
                },
                source="dashboard",
            )
        )

    return {
        "charts": charts,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }


@router.get("/{dataset_id}/insights")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_insights(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    from services.pipeline.on_demand import ensure_deep_analysis

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)

    # Lazily compute deep analysis on first access
    deep_analysis = await ensure_deep_analysis(dataset_id, user_id)
    summary = deep_analysis.get("executive_summary") or ""

    insights_raw = (
        deep_analysis.get("quis_insights", {}).get("top_insights")
        or deep_analysis.get("quis_insights", {}).get("insights")
        or []
    )

    insights = []
    for idx, item in enumerate(insights_raw):
        insights.append(
            {
                "id": item.get("id") or f"insight_{idx}",
                "title": item.get("title") or item.get("question") or "Insight",
                "description": item.get("description")
                or item.get("insight")
                or item.get("finding")
                or "",
                "type": item.get("type") or "insight",
                "confidence": item.get("confidence"),
                "effect_size": item.get("effect_size"),
                "p_value": item.get("p_value"),
                "columns": item.get("columns") or [],
            }
        )

    # ── Signal: record insight views (fire-and-forget) ──────────────────────
    from services.learning.signal_collector import signal_collector
    import asyncio as _asyncio

    for insight in insights[:10]:  # Only track top 10 to avoid noise
        _asyncio.ensure_future(
            signal_collector.record_insight_view(
                user_id=user_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                insight_id=insight.get("id", ""),
                insight_metadata={
                    "title": insight.get("title", ""),
                    "columns": insight.get("columns", []),
                    "type": insight.get("type", ""),
                },
                source="dashboard",
            )
        )

    return {
        "summary": summary,
        "insights": insights,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }


@router.get("/{dataset_id}/config")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dashboard_config(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get the complete AI-generated dashboard configuration (blueprint with all components).

    Lazily triggers dashboard design on first access if not cached.
    """
    from services.pipeline.on_demand import ensure_dashboard_design

    # Lazy dashboard design — generates on first access if not cached,
    # returns cached blueprint on subsequent calls.
    blueprint = await ensure_dashboard_design(dataset_id, current_user["id"])

    if not blueprint or not blueprint.get("components"):
        return {
            "dashboard_blueprint": None,
            "design_pattern": None,
            "components": [],
            "reasoning": "Dashboard design not yet available",
            "cached": False,
        }

    return {
        "dashboard_blueprint": blueprint,
        "design_pattern": blueprint.get("design_pattern"),
        "pattern_name": blueprint.get("pattern_name"),
        "components": blueprint.get("components", []),
        "summary": blueprint.get("summary"),
        "reasoning": blueprint.get("reasoning"),
        "cached": True,
        "created_at": blueprint.get("created_at"),
    }
