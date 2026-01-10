# backend/api/dashboard.py

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

import polars as pl

# --- Application Modules ---
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.charts.chart_render_service import chart_render_service
from services.charts.chart_insights_service import chart_insights_service
from services.ai.ai_service import ai_service
from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
from services.analysis.analysis_service import analysis_service

# --- Config ---
logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================
#                 DASHBOARD OVERVIEW
# ============================================================
@router.get("/{dataset_id}/overview")
async def get_dashboard_overview(dataset_id: str, current_user: dict = Depends(get_current_user)):
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        metadata = dataset.get("metadata", {})

        overview = metadata.get("dataset_overview", {})
        quality = metadata.get("data_quality", {})

        if not overview:
            raise HTTPException(status_code=409, detail="Dataset metadata is not available. Please reprocess the dataset.")

        # Load actual dataframe for intelligent KPI generation
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        
        # Detect domain from metadata if available
        domain = metadata.get("dataset_overview", {}).get("domain")
        
        # Generate intelligent, context-aware KPIs
        intelligent_kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
            df=df,
            domain=domain,
            max_kpis=4
        )
        
        # Format KPIs for frontend with enterprise data
        kpis = []
        for kpi in intelligent_kpis:
            value = kpi["value"]
            # Format large numbers for display
            if isinstance(value, (int, float)):
                if value >= 1_000_000:
                    formatted_value = f"{value/1_000_000:.2f}M"
                elif value >= 1_000:
                    formatted_value = f"{value/1_000:.2f}K"
                else:
                    formatted_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
            else:
                formatted_value = str(value)
            
            kpis.append({
                "title": kpi["title"],
                "value": formatted_value,
                "subtitle": kpi.get("subtitle", ""),
                "raw_value": value,
                # Enterprise KPI fields
                "format": kpi.get("format", "number"),
                "comparison_value": kpi.get("comparison_value"),
                "comparison_label": kpi.get("comparison_label", "vs last period"),
                "target_value": kpi.get("target_value"),
                "target_label": kpi.get("target_label"),
                "sparkline_data": kpi.get("sparkline_data", []),
                "context": kpi.get("context", ""),
                "column": kpi.get("column", ""),
                "aggregation": kpi.get("aggregation", "")
            })

        return {
            "dataset": {
                "id": dataset.get("id"),
                "name": dataset.get("name"),
                "row_count": overview.get("total_rows", 0),
                "column_count": overview.get("total_columns", 0),
            },
            "kpis": kpis,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard overview for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get dashboard overview.")


# ============================================================
#                 DASHBOARD INSIGHTS
# ============================================================
@router.get("/{dataset_id}/insights")
async def get_dashboard_insights(dataset_id: str, current_user: dict = Depends(get_current_user)):
    try:
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        quis_results = analysis_service.run_quis_analysis(df, dataset_id=dataset_id)

        insights = []

        # Deep insights
        for finding in quis_results.get("deep_insights", [])[:4]:
            insights.append({
                "id": f"deep_{len(insights)}",
                "type": "success",
                "title": finding.get("type", "Deep Insight").replace("_", " ").title(),
                "description": f"A strong pattern was found in the subspace: {finding.get('subspace', 'N/A')}",
                "confidence": 95,
            })

        # Basic insights
        for finding in quis_results.get("basic_insights", [])[:4 - len(insights)]:
            if finding.get("type") in ["correlation", "outlier"]:
                insights.append({
                    "id": f"basic_{len(insights)}",
                    "type": "warning" if finding.get("type") == "outlier" else "info",
                    "title": finding.get("type", "Insight").title(),
                    "description": f"Column '{finding.get('column', finding.get('columns'))}' shows notable {finding.get('type')}.",
                    "confidence": 85,
                })

        if not insights:
            insights.append({
                "id": "default",
                "type": "info",
                "title": "Analysis Complete",
                "description": "The dataset has been analyzed. No high-significance automated insights were found.",
                "confidence": 100,
            })

        return {"insights": insights}

    except Exception as e:
        logger.error(f"Error getting dashboard insights for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get dashboard insights.")


# ============================================================
#                 DEFAULT DASHBOARD CHARTS
# ============================================================
@router.get("/{dataset_id}/charts")
async def get_dashboard_charts(dataset_id: str, current_user: dict = Depends(get_current_user)):
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])

        charts = {}

        numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
        categorical_cols = df.select(pl.col(pl.Utf8, pl.Categorical)).columns

        if numeric_cols and categorical_cols:
            # Use render_chart directly with the dataframe instead of render_chart_from_config
            charts["sales_by_category"] = await chart_render_service.render_chart(
                df,
                {"chart_type": "bar", "columns": [categorical_cols[0], numeric_cols[0]], "aggregation": "sum"}
            )

            charts["traffic_source"] = await chart_render_service.render_chart(
                df,
                {"chart_type": "pie", "columns": [categorical_cols[0], numeric_cols[0]], "aggregation": "count"}
            )

        return {"charts": charts}

    except Exception as e:
        logger.error(f"Error getting dashboard charts for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get dashboard charts.")


# ============================================================
#            AI-GENERATED DASHBOARD LAYOUT
# ============================================================
@router.get("/{dataset_id}/ai-layout")
async def get_ai_dashboard_layout(dataset_id: str, current_user: dict = Depends(get_current_user)):
    try:
        layout = await ai_service.generate_ai_dashboard(dataset_id, current_user["id"])
        return {"success": True, "layout": layout}

    except Exception as e:
        logger.error(f"Error generating AI dashboard layout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate AI dashboard layout.")


# ============================================================
#            ANALYTICS STUDIO (CUSTOM CHARTS)
# ============================================================
@router.post("/analytics/generate-chart")
async def generate_analytics_chart(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    try:
        dataset_id = request.get("dataset_id")
        chart_config = {
            "chart_type": request.get("chart_type", "bar"),
            "columns": [request.get("x_axis"), request.get("y_axis")],
            "aggregation": request.get("aggregation", "sum"),
        }

        if not dataset_id or not chart_config["columns"][0]:
            raise HTTPException(status_code=400, detail="dataset_id and x_axis are required.")

        return await chart_render_service.render_chart(chart_config, dataset_id, current_user["id"])

    except Exception as e:
        logger.error(f"Error generating analytics chart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate chart data: {e}")


# ============================================================
#                 PREVIEW RENDERING
# ============================================================
@router.post("/charts/render-preview")
async def render_chart_preview(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    try:
        chart_config = request.get("chart_config")
        dataset_id = request.get("dataset_id")

        if not chart_config or not dataset_id:
            raise HTTPException(status_code=400, detail="chart_config and dataset_id are required.")

        return await chart_render_service.render_chart(chart_config, dataset_id, current_user["id"])

    except Exception as e:
        logger.error(f"Chart rendering error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to render chart.")


# ============================================================
#                 AI CHART INSIGHTS
# ============================================================
@router.post("/charts/insights")
async def generate_chart_insights(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data", [])
        dataset_id = request.get("dataset_id")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])

        return await chart_insights_service.generate_chart_insight(
            chart_config, chart_data, dataset.get("metadata", {})
        )

    except Exception as e:
        logger.error(f"Error generating chart insights: {e}", exc_info=True)
        return chart_insights_service._generate_fallback_insight(chart_config, [])


# ============================================================
#                CACHED CHARTS
# ============================================================
@router.get("/{dataset_id}/cached-charts")
async def get_cached_charts(dataset_id: str, current_user: dict = Depends(get_current_user)):
    return await chart_insights_service.get_dataset_cached_charts(dataset_id, current_user["id"])
