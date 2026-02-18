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
        
        # Detect domain from metadata
        domain = metadata.get("domain_intelligence", {}).get("domain") or dataset.get("domain")
        
        # Generate intelligent, context-aware KPIs with full metadata
        intelligent_kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
            df=df,
            domain=domain,
            max_kpis=4,
            dataset_metadata=metadata,
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
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        metadata = dataset.get("metadata", {})
        deep_analysis = metadata.get("deep_analysis", {})

        insights = []

        # ── If deep_analysis was pre-computed at upload (pipeline v3.0+) ──
        if deep_analysis and deep_analysis.get("analysis_version"):
            enhanced = deep_analysis.get("enhanced_analysis", {})
            quis = deep_analysis.get("quis_insights", {})
            executive_summary = deep_analysis.get("executive_summary", "")

            # Top QUIS insights (beam-search validated, FDR-corrected)
            for i, finding in enumerate(quis.get("top_insights", [])[:6]):
                insight_type = finding.get("insight_type", "insight")
                desc = finding.get("description", "")
                p_val = finding.get("p_value")
                effect = finding.get("effect_size")
                effect_interp = finding.get("effect_interpretation", "")
                ci = finding.get("confidence_interval")

                # Build rich description
                stat_parts = [desc]
                if p_val is not None and p_val < 1.0:
                    stat_parts.append(f"p={p_val:.4f}")
                if effect is not None and effect > 0:
                    stat_parts.append(f"effect size={effect:.3f} ({effect_interp})" if effect_interp else f"effect={effect:.3f}")
                if ci:
                    stat_parts.append(f"95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]")

                type_map = {
                    "correlation": "info",
                    "comparison": "warning",
                    "subspace": "success",
                    "trend": "info",
                    "anomaly": "warning",
                    "simpson_paradox": "success",
                }

                confidence = max(10, int((1 - (p_val or 0.5)) * 100))

                insights.append({
                    "id": f"quis_{i}",
                    "type": type_map.get(insight_type, "info"),
                    "title": insight_type.replace("_", " ").title(),
                    "description": ". ".join(stat_parts),
                    "confidence": min(confidence, 99),
                    "p_value": p_val,
                    "effect_size": effect,
                    "is_simpson_paradox": finding.get("is_simpson_paradox", False),
                })

            # Strong correlations from enhanced analysis
            for i, corr in enumerate(enhanced.get("correlations", [])[:4]):
                if abs(corr.get("correlation", 0)) >= 0.5 and len(insights) < 10:
                    r = corr["correlation"]
                    col1 = corr.get("column1", "?")
                    col2 = corr.get("column2", "?")
                    method = corr.get("method", "pearson")
                    p = corr.get("p_value")
                    ci = corr.get("confidence_interval")

                    desc = f"{corr.get('strength', 'Notable')} {method} correlation (r={r:.3f}"
                    if p is not None:
                        desc += f", p={p:.4f}"
                    desc += f") between {col1} and {col2}"
                    if ci:
                        desc += f". 95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]"

                    insights.append({
                        "id": f"corr_{i}",
                        "type": "info",
                        "title": f"Correlation: {col1} ↔ {col2}",
                        "description": desc,
                        "confidence": max(10, int((1 - (p or 0.5)) * 100)),
                        "p_value": p,
                        "effect_size": abs(r),
                    })

            # Distribution anomalies
            for i, dist in enumerate(enhanced.get("distributions", [])[:3]):
                skew = dist.get("skewness", 0)
                if abs(skew) > 1.0 and len(insights) < 12:
                    col = dist.get("column", "?")
                    norm_p = dist.get("normality_p_value")
                    dist_type = dist.get("distribution_type", "unknown")

                    desc = f"{col} follows a {dist_type} distribution (skewness={skew:.2f}, kurtosis={dist.get('kurtosis', 0):.2f})"
                    if norm_p is not None:
                        desc += f". Normality test: p={norm_p:.4f}"

                    insights.append({
                        "id": f"dist_{i}",
                        "type": "warning" if abs(skew) > 2 else "info",
                        "title": f"Distribution: {col}",
                        "description": desc,
                        "confidence": 90,
                    })

            # Executive summary as first insight if available
            if executive_summary:
                insights.insert(0, {
                    "id": "executive_summary",
                    "type": "success",
                    "title": "Executive Summary",
                    "description": executive_summary,
                    "confidence": 100,
                })

        else:
            # ── Fallback for datasets processed before v3.0 ──
            df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
            quis_results = analysis_service.run_quis_analysis(df, dataset_id=dataset_id)

            for finding in quis_results.get("deep_insights", [])[:4]:
                insights.append({
                    "id": f"deep_{len(insights)}",
                    "type": "success",
                    "title": finding.get("type", "Deep Insight").replace("_", " ").title(),
                    "description": f"A strong pattern was found in the subspace: {finding.get('subspace', 'N/A')}",
                    "confidence": 95,
                })

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
