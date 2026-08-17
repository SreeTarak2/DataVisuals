"""
Chart Generation & Rendering API
==================================
Endpoints for rendering charts from dataset data.

Endpoints:
  POST /render     — Render a chart from dataset config (primary)
  POST /render-preview — Quick preview without full AI insights
  GET  /recommendations — Get AI-powered chart recommendations
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.rate_limiter import limiter, RateLimits
from db.database import get_database
from db.schemas_charts import ChartRenderRequest, ChartResponse
from services.auth_service import get_current_user
from services.charts.chart_render_service import chart_render_service
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/render")
@limiter.limit(RateLimits.CHART_RENDER)
async def render_chart(
    request: Request,
    body: ChartRenderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Render a chart from dataset data with full configuration.

    Accepts chart type, column fields, aggregation, filters, date ranges,
    and grouping. Returns Plotly-compatible traces and layout.
    """
    try:
        user_id = current_user["id"]
        dataset_id = body.dataset_id

        # Verify dataset ownership
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        if not dataset.get("is_processed"):
            raise HTTPException(
                status_code=202,
                detail="Dataset still processing — try again shortly",
            )

        # Load data
        df = await enhanced_dataset_service.load_dataset_data(
            dataset_id, user_id, max_rows=body.limit
        )
        if df is None or df.is_empty():
            raise HTTPException(status_code=422, detail="Dataset is empty")

        # Build config for render service
        config: Dict[str, Any] = {
            "chart_type": body.chart_type,
            "columns": body.fields,
            "aggregation": body.aggregation or "sum",
            "title": body.title or f"{' vs '.join(body.fields)}",
            "include_insights": body.include_insights,
        }

        if body.group_by:
            config["group_by"] = body.group_by
        if body.filters:
            config["filters"] = body.filters
        if body.from_date:
            config["from"] = body.from_date
        if body.to_date:
            config["to"] = body.to_date
        if body.granularity:
            config["granularity"] = body.granularity

        # Render
        chart_payload = await chart_render_service.render_chart(df, config)

        # Build response
        traces = chart_payload.get("traces", [])
        layout = chart_payload.get("layout", {})
        metadata = chart_payload.get("metadata", {})

        # Try to get explanation from point_intelligence if no AI insights
        explanation = None
        point_intel = chart_payload.get("point_intelligence")
        if point_intel:
            explanation = (
                f"Showing {point_intel.get('y_label', 'value')} by "
                f"{point_intel.get('x_label', 'category')}. "
                f"Based on {point_intel.get('total_records', 0):,} records."
            )

        return {
            "traces": traces,
            "layout": layout,
            "explanation": explanation or "",
            "fields": body.fields,
            "chart_type": body.chart_type,
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart render failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chart rendering failed: {str(e)}")


@router.post("/render-preview")
@limiter.limit(RateLimits.CHART_RENDER)
async def render_chart_preview(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Quick chart preview — accepts a chart_config with embedded data or a
    dataset_id + config, and returns Plotly traces without AI insights.
    """
    try:
        user_id = current_user["id"]
        dataset_id = body.get("dataset_id") or body.get("chart_config", {}).get("dataset_id")

        if not dataset_id:
            raise HTTPException(status_code=400, detail="dataset_id is required")

        # Verify ownership
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Load data (preview limit)
        limit = body.get("limit", 200)
        df = await enhanced_dataset_service.load_dataset_data(
            dataset_id, user_id, max_rows=limit
        )
        if df is None or df.is_empty():
            raise HTTPException(status_code=422, detail="Dataset is empty")

        # Build config from body
        chart_config = body.get("chart_config", body)
        config = {
            "chart_type": chart_config.get("chart_type", "bar"),
            "columns": chart_config.get("columns", chart_config.get("fields", [])),
            "aggregation": chart_config.get("aggregation", "sum"),
            "title": chart_config.get("title", "Preview"),
        }

        chart_payload = await chart_render_service.render_chart(df, config)

        return {
            "traces": chart_payload.get("traces", []),
            "layout": chart_payload.get("layout", {}),
            "fields": config["columns"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chart preview failed: {str(e)}")


@router.get("/recommendations")
@limiter.limit(RateLimits.CHART_RECOMMENDATIONS)
async def get_chart_recommendations(
    request: Request,
    dataset_id: str = Query(..., description="Dataset ID"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get AI-powered chart recommendations for a dataset.

    Returns suggested chart types, column pairings, and confidence scores.
    """
    try:
        user_id = current_user["id"]

        # Verify dataset ownership
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        columns = dataset.get("columns", dataset.get("metadata", {}).get("column_metadata", []))
        numeric_cols = [
            c.get("name", c) if isinstance(c, dict) else c
            for c in columns
            if (isinstance(c, dict) and c.get("is_numeric")) or not isinstance(c, dict)
        ]
        categorical_cols = [
            c.get("name", c) if isinstance(c, dict) else c
            for c in columns
            if (isinstance(c, dict) and c.get("is_categorical")) or not isinstance(c, dict)
        ]

        # Build smart recommendations
        recommendations = []

        if numeric_cols and categorical_cols:
            cat = categorical_cols[0]
            num = numeric_cols[0]
            recommendations.append({
                "chart_type": "bar",
                "title": f"{num} by {cat}",
                "description": f"Compare {num} across different {cat} values",
                "fields": [cat, num],
                "confidence": "High",
            })
            if len(numeric_cols) >= 2:
                recommendations.append({
                    "chart_type": "scatter",
                    "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
                    "description": f"Explore relationship between {numeric_cols[0]} and {numeric_cols[1]}",
                    "fields": [numeric_cols[0], numeric_cols[1]],
                    "confidence": "High",
                })

        if len(numeric_cols) >= 1 and len(categorical_cols) >= 1:
            recommendations.append({
                "chart_type": "pie",
                "title": f"Distribution of {numeric_cols[0]} by {categorical_cols[0]}",
                "description": f"See how {numeric_cols[0]} is distributed across {categorical_cols[0]}",
                "fields": [categorical_cols[0], numeric_cols[0]],
                "confidence": "Medium",
            })

        # Time-based recommendations
        temporal_cols = [
            c.get("name", c) if isinstance(c, dict) else c
            for c in columns
            if (isinstance(c, dict) and c.get("is_temporal")) or not isinstance(c, dict)
        ]
        if temporal_cols and numeric_cols:
            recommendations.append({
                "chart_type": "line",
                "title": f"{numeric_cols[0]} over {temporal_cols[0]}",
                "description": f"Track {numeric_cols[0]} trends over time",
                "fields": [temporal_cols[0], numeric_cols[0]],
                "confidence": "High",
            })

        return {"recommendations": recommendations}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart recommendations failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
