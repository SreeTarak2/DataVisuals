"""
AI API routes - provides endpoints for AI-generated dashboard configs and design endpoints.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from services.auth_service import get_current_user
from core.rate_limiter import limiter, RateLimits
from services.ai.ai_designer_service import ai_designer_service

router = APIRouter()


class DashboardDesignRequest(BaseModel):
    design_preference: Optional[str] = None
    force_regenerate: bool = False
    conversation_summary: Optional[str] = None
    redesign_mode: str = "layout"  # "layout" = rearrange existing, "full" = re-compute everything


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
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{dataset_id}/retry-chart")
@limiter.limit(RateLimits.CHART_RETRY)
async def retry_chart(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retry rendering a failed chart component.
    Frontend endpoint: Used when a chart fails to render, to attempt re-rendering.

    Request body should contain:
    - component: The dashboard component object with config
    """
    from db.database import get_database
    from services.charts.chart_render_service import chart_render_service
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    db = get_database()

    body = await request.json()
    component = body.get("component", {})

    if not component:
        raise HTTPException(status_code=400, detail="component is required")

    # Extract chart config from component
    chart_config = component.get("config", {})
    if not chart_config:
        # Fallback: build chart config from component fields
        chart_config = {
            "type": "chart",
            "title": component.get("title", "Chart"),
            "chart_type": component.get("chart_type", "bar"),
            "columns": component.get("columns", []),
            "aggregation": component.get("aggregation", "sum"),
        }

    # Validate component has required fields BEFORE the try block
    if not chart_config.get("chart_type") and not chart_config.get("columns"):
        raise HTTPException(status_code=400, detail="component must have chart_type or columns")

    # Check for missing y column (common issue with old dashboards)
    chart_type = chart_config.get("type", "").lower()
    requires_y = chart_type in [
        "bar",
        "line",
        "grouped_bar",
        "stacked_bar",
        "multi_line",
        "stacked_area",
        "scatter",
        "area",
    ]
    has_y = bool(chart_config.get("y") or chart_config.get("y_axis"))

    if requires_y and not has_y:
        raise HTTPException(
            status_code=400,
            detail=f"Chart type '{chart_type}' requires a 'y' column. Missing in config. Regenerate dashboard to fix.",
        )

    try:
        # Load dataset
        df = await enhanced_dataset_service.load_dataset_data(
            dataset_id,
            current_user["id"],
        )

        if df is None or df.is_empty():
            raise HTTPException(status_code=400, detail="Dataset is empty or not found")

        # Render the chart
        chart_payload = await chart_render_service.render_chart(
            df,
            chart_config,
            theme=body.get("theme", "dark"),
        )

        # Transform to frontend format: traces -> data
        chart_data = {
            "data": chart_payload.get("data") or chart_payload.get("traces", []),
            "layout": chart_payload.get("layout", {}),
        }

        # Persist retried chart into default dashboard blueprint so it survives relogin.
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

            target_idx = None
            for idx, comp in enumerate(components):
                if not isinstance(comp, dict) or comp.get("type") != "chart":
                    continue

                # Prefer id match; fallback to title/config signature.
                if component.get("id") and comp.get("id") == component.get("id"):
                    target_idx = idx
                    break

                incoming_title = (component.get("title") or "").strip().lower()
                existing_title = (comp.get("title") or "").strip().lower()
                if incoming_title and incoming_title == existing_title:
                    target_idx = idx
                    break

                incoming_cfg = component.get("config") or {}
                existing_cfg = comp.get("config") or {}
                if incoming_cfg.get("chart_type") == existing_cfg.get("chart_type") and (
                    incoming_cfg.get("columns") or []
                ) == (existing_cfg.get("columns") or []):
                    target_idx = idx
                    break

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
                    {"$set": {"blueprint": blueprint, "updated_at": datetime.utcnow()}},
                )

        return {
            "success": True,
            "chart_data": chart_data,
            "updated_config": chart_config,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        error_msg = str(exc)
        error_category = "render_error"
        if "aggregation" in error_msg.lower():
            error_category = "aggregation_error"
            error_msg = f"Aggregation error: {error_msg}. Try changing the aggregation type (mean, sum, count, median)."
        elif "column" in error_msg.lower() or "missing" in error_msg.lower():
            error_category = "column_error"
            error_msg = (
                f"Column error: {error_msg}. The specified column may not exist in the dataset."
            )
        elif "empty" in error_msg.lower() or "no data" in error_msg.lower():
            error_category = "data_error"
            error_msg = f"No data available: {error_msg}. Try adjusting filters or selecting different columns."
        elif "type" in error_msg.lower() or "numeric" in error_msg.lower():
            error_category = "type_error"
            error_msg = f"Data type error: {error_msg}. This aggregation requires numeric data."
        else:
            error_msg = f"Chart rendering failed: {error_msg}"

        raise HTTPException(
            status_code=500,
            detail={
                "message": error_msg,
                "category": error_category,
                "suggestion": _get_error_suggestion(error_category, chart_config),
            },
        )
    except Exception as exc:
        error_msg = str(exc)
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to retry chart: {error_msg}",
                "category": "unknown_error",
                "suggestion": "Try regenerating the dashboard or selecting a different chart type.",
            },
        )


def _get_error_suggestion(category: str, chart_config: dict) -> str:
    """Get user-friendly suggestion based on error category."""
    suggestions = {
        "aggregation_error": "Try changing aggregation to 'mean', 'sum', 'count', or 'median'. Some aggregations require numeric data.",
        "column_error": "Check that the column names in the chart config match the dataset columns exactly.",
        "data_error": "The filtered data may be empty. Try removing filters or selecting a different date range.",
        "type_error": "Switch to 'count' or 'nunique' aggregation for categorical data, or select numeric columns.",
        "render_error": "Try a simpler chart type like 'bar' or 'line' with fewer columns.",
        "unknown_error": "Try regenerating the dashboard or selecting a different chart type.",
    }
    return suggestions.get(category, "Try regenerating the dashboard.")


@router.get("/design-patterns")
@limiter.limit(RateLimits.DATASET_GET)
async def get_design_patterns(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return await ai_designer_service.get_available_patterns()
