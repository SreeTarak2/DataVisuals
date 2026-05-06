from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core.rate_limiter import RateLimits, limiter
from services.auth_service import get_current_user
from services.charts.chart_render_service import chart_render_service
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

router = APIRouter()


class MultiSeriesRenderRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    x_column: str = Field(..., min_length=1)
    metric_columns: List[str] = Field(..., min_items=2)
    title: Optional[str] = None
    analysis_intent: Optional[str] = None  # trend|comparison|composition|diagnosis
    time_indexed: bool = False
    limit: int = Field(10000, ge=1, le=1_000_000)
    theme: str = "dark"


CHART_TYPE_ALIASES = {
    "bar_chart": "bar",
    "line_chart": "line",
    "pie_chart": "pie",
    "donut": "pie",
    "donut_chart": "pie",
    "scatter_plot": "scatter",
    "box": "box_plot",
    "area_chart": "area",
}


class ChartRenderRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    chart_type: str = "bar"
    fields: Optional[List[str]] = None
    columns: Optional[List[str]] = None
    aggregation: str = "sum"
    title: Optional[str] = None
    group_by: Optional[Any] = None
    include_insights: bool = True
    limit: int = Field(10000, ge=1, le=1_000_000)
    theme: str = "dark"
    colorscale: Optional[str] = None


def _normalise_chart_config(body: ChartRenderRequest) -> Dict[str, Any]:
    columns = body.columns or body.fields or []
    if not columns:
        raise HTTPException(status_code=400, detail="fields or columns are required")

    chart_type = CHART_TYPE_ALIASES.get(body.chart_type.lower(), body.chart_type.lower())

    group_by = body.group_by
    if isinstance(group_by, str):
        group_by = [group_by] if group_by else None

    return {
        "type": "chart",
        "title": body.title or "Chart",
        "chart_type": chart_type,
        "columns": columns,
        "aggregation": body.aggregation,
        "group_by": group_by,
        "colorscale": body.colorscale,
        "span": 2,
    }


@router.post("/render")
@limiter.limit(RateLimits.DATASET_GET)
async def render_chart(
    request: Request,
    body: ChartRenderRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        df = await enhanced_dataset_service.load_dataset_data(
            body.dataset_id,
            current_user["id"],
        )
        if body.limit and len(df) > body.limit:
            df = df.head(body.limit)

        chart_config = _normalise_chart_config(body)
        return await chart_render_service.render_chart(
            df,
            chart_config,
            theme=body.theme,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render chart: {exc}")


@router.post("/multi-series")
@limiter.limit(RateLimits.DATASET_GET)
async def render_multi_series_chart(
    request: Request,
    body: MultiSeriesRenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Smart multi-series chart rendering.

    Automatically detects patterns in the data (trends, correlations, anomalies,
    scale mismatches, seasonality) and selects the best visualization strategy:
    overlay / dual_axis / facet / combo / grouped / stacked.

    Returns the Plotly chart dict plus detected patterns and the strategy chosen.
    """
    try:
        df = await enhanced_dataset_service.load_dataset_data(
            body.dataset_id,
            current_user["id"],
        )
        if body.limit and len(df) > body.limit:
            df = df.head(body.limit)

        return await chart_render_service.render_multi_series(
            df=df,
            metric_columns=body.metric_columns,
            x_column=body.x_column,
            title=body.title or f"{', '.join(body.metric_columns)} over {body.x_column}",
            analysis_intent=body.analysis_intent,
            time_indexed=body.time_indexed,
            theme=body.theme,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Multi-series render failed: {exc}")


@router.post("/render-preview")
@limiter.limit(RateLimits.DATASET_GET)
async def render_chart_preview(
    request: Request,
    body: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    chart_config = body.get("chart_config") or {}
    dataset_id = body.get("dataset_id") or chart_config.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required")

    try:
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        return await chart_render_service.render_chart(df.head(1000), chart_config, theme="dark")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render chart preview: {exc}")


@router.get("/recommendations")
@limiter.limit(RateLimits.DATASET_GET)
async def get_chart_recommendations(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    combined = await enhanced_dataset_service.get_full_dataset_with_analytics(
        dataset_id,
        current_user["id"],
    )
    analytics = combined.get("analytics") or {}
    metadata = combined.get("metadata") or {}
    recommendations = (
        analytics.get("chart_recommendations")
        or metadata.get("chart_recommendations")
        or []
    )
    return {"recommendations": recommendations}
