# backend/api/dashboard.py

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query

import polars as pl

# --- Application Modules ---
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.charts.chart_render_service import chart_render_service
from services.charts.chart_insights_service import chart_insights_service
from services.ai.ai_service import ai_service
from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
from services.analysis.analysis_service import analysis_service
from services.dashboard_cache_service import dashboard_cache_service

# --- Config ---
logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================
#                 DASHBOARD OVERVIEW
# ============================================================
@router.get("/{dataset_id}/overview")
async def get_dashboard_overview(
    dataset_id: str, 
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force regeneration, ignoring cache")
):
    try:
        user_id = current_user["id"]
        
        # CHECK CACHE FIRST (unless force_refresh)
        if not force_refresh:
            cached_kpis = await dashboard_cache_service.get_cached_kpis(dataset_id, user_id)
            if cached_kpis is not None:
                # Get basic dataset info (fast, no AI call)
                dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
                overview = dataset.get("metadata", {}).get("dataset_overview", {})
                
                logger.info(f"✅ Returning cached KPIs for dataset {dataset_id}")
                return {
                    "dataset": {
                        "id": dataset.get("id"),
                        "name": dataset.get("name"),
                        "row_count": overview.get("total_rows", 0),
                        "column_count": overview.get("total_columns", 0),
                    },
                    "kpis": cached_kpis,
                    "cached": True
                }
        
        # CACHE MISS - Generate KPIs
        logger.info(f"🔄 Generating fresh KPIs for dataset {dataset_id}")
        
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        metadata = dataset.get("metadata", {})

        overview = metadata.get("dataset_overview", {})
        quality = metadata.get("data_quality", {})

        if not overview:
            raise HTTPException(status_code=409, detail="Dataset metadata is not available. Please reprocess the dataset.")

        # Load actual dataframe for intelligent KPI generation
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
        
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
            if isinstance(value, dict):
                # Structured values (e.g. range: {"min": x, "max": y})
                if "min" in value and "max" in value:
                    formatted_value = f"{value['min']:,.2f} – {value['max']:,.2f}"
                else:
                    formatted_value = str(value)
            elif isinstance(value, (int, float)):
                if value >= 1_000_000:
                    formatted_value = f"{value/1_000_000:.2f}M"
                elif value >= 1_000:
                    formatted_value = f"{value/1_000:.2f}K"
                else:
                    formatted_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
            elif value is None:
                formatted_value = "N/A"
            else:
                formatted_value = str(value)
            
            # Normalize sparkline: backend may return dict or list
            raw_sparkline = kpi.get("sparkline_data", [])
            if isinstance(raw_sparkline, dict):
                sparkline_data = raw_sparkline.get("data", [])
            else:
                sparkline_data = raw_sparkline

            kpis.append({
                "title": kpi["title"],
                "value": formatted_value,
                "subtitle": kpi.get("subtitle", ""),
                "raw_value": value,
                # Enterprise KPI fields
                "format": kpi.get("format", "number"),
                "comparison_value": kpi.get("comparison_value"),
                "comparison_label": kpi.get("comparison_label", "vs last period"),
                "delta_percent": kpi.get("delta_percent"),
                "delta_direction": kpi.get("delta_direction"),
                "target_value": kpi.get("target_value"),
                "target_label": kpi.get("target_label"),
                "sparkline_data": sparkline_data,
                "context": kpi.get("context", ""),
                "column": kpi.get("column", ""),
                "aggregation": kpi.get("aggregation", "")
            })

        # CACHE THE RESULT
        await dashboard_cache_service.cache_kpis(dataset_id, user_id, kpis)

        return {
            "dataset": {
                "id": dataset.get("id"),
                "name": dataset.get("name"),
                "row_count": overview.get("total_rows", 0),
                "column_count": overview.get("total_columns", 0),
            },
            "kpis": kpis,
            "cached": False
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
async def get_dashboard_insights(
    dataset_id: str, 
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force regeneration, ignoring cache")
):
    try:
        user_id = current_user["id"]
        
        # CHECK CACHE FIRST (unless force_refresh)
        if not force_refresh:
            cached_insights = await dashboard_cache_service.get_cached_insights(dataset_id, user_id)
            if cached_insights is not None:
                # Verify user still has access to this dataset
                await enhanced_dataset_service.get_dataset(dataset_id, user_id)
                logger.info(f"✅ Returning cached insights for dataset {dataset_id}")
                return {"insights": cached_insights, "cached": True}
        
        logger.info(f"🔄 Generating fresh insights for dataset {dataset_id}")
        
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        metadata = dataset.get("metadata", {})
        deep_analysis = metadata.get("deep_analysis", {})

        insights = []

        # ── Helper: generate human-readable titles & descriptions ──
        def _humanize_correlation(col1: str, col2: str, r: float, effect_interp: str = "") -> tuple[str, str]:
            """Return (title, description) in plain English for a correlation insight."""
            direction = "increases with" if r > 0 else "decreases as"
            strength = effect_interp or ("strongly" if abs(r) >= 0.7 else "moderately" if abs(r) >= 0.4 else "weakly")
            # Make column names readable
            c1 = col1.replace("_", " ").title()
            c2 = col2.replace("_", " ").title()
            title = f"{c1} {direction} {c2}" if abs(r) < 0.7 else f"Strong link: {c1} ↔ {c2}"
            desc = f"{c1} and {c2} are {strength} correlated — when one changes, the other tends to follow {'in the same' if r > 0 else 'the opposite'} direction."
            return title, desc

        def _humanize_comparison(desc: str, finding: dict) -> tuple[str, str]:
            """Return (title, description) for a group comparison insight."""
            columns = finding.get("columns", [])
            col_names = [c.replace("_", " ").title() for c in columns] if columns else []
            if len(col_names) >= 2:
                title = f"{col_names[0]} varies across {col_names[1]} groups"
            else:
                title = f"Significant difference found across groups"
            effect_interp = finding.get("effect_interpretation", "notable")
            human_desc = f"There's a {effect_interp} difference in {col_names[0] if col_names else 'values'} when comparing different groups — this pattern is statistically significant and worth investigating."
            return title, human_desc

        def _humanize_subspace(desc: str, finding: dict) -> tuple[str, str]:
            """Return (title, description) for a subspace/hidden pattern insight."""
            subspace = finding.get("subspace", {})
            columns = finding.get("columns", [])
            if subspace:
                filters = [f"{k}={v}" for k, v in subspace.items()]
                title = f"Hidden pattern in {', '.join(filters[:2])}"
                human_desc = f"When filtering to {' and '.join(filters[:2])}, an unexpected pattern emerges that isn't visible in the overall data."
            elif columns:
                col_names = [c.replace("_", " ").title() for c in columns[:2]]
                title = f"Hidden pattern in {' & '.join(col_names)}"
                human_desc = f"A surprising pattern was found in {' and '.join(col_names)} that only appears in a specific subset of the data."
            else:
                title = "Hidden pattern discovered"
                human_desc = desc or "A non-obvious pattern was detected in a data subset — this could reveal insights not visible in summary statistics."
            return title, human_desc

        def _is_trivial_correlation(col1: str, col2: str, r: float) -> bool:
            """Detect obviously redundant column pairs (Close↔Adj Close, etc.)."""
            if abs(r) > 0.98:
                return True
            # Common trivially correlated pairs (case-insensitive substrings)
            c1, c2 = col1.lower(), col2.lower()
            trivial_pairs = [
                ("close", "adj_close"), ("close", "adj close"), ("close", "adjusted_close"),
                ("open", "high"), ("low", "close"),
                ("price", "adj_price"), ("amount", "total_amount"),
            ]
            for a, b in trivial_pairs:
                if (a in c1 and b in c2) or (a in c2 and b in c1):
                    return True
            return False

        # ── If deep_analysis was pre-computed at upload (pipeline v3.0+) ──
        if deep_analysis and deep_analysis.get("analysis_version"):
            enhanced = deep_analysis.get("enhanced_analysis", {})
            quis = deep_analysis.get("quis_insights", {})
            executive_summary = deep_analysis.get("executive_summary", "")

            type_map = {
                "correlation": "info",
                "comparison": "warning",
                "subspace": "success",
                "trend": "trend",
                "anomaly": "warning",
                "simpson_paradox": "success",
            }

            # Track seen column pairs to avoid duplicates
            seen_pairs = set()

            # Top QUIS insights (beam-search validated, FDR-corrected)
            for i, finding in enumerate(quis.get("top_insights", [])[:8]):
                insight_type = finding.get("insight_type", "insight")
                desc = finding.get("description", "")
                p_val = finding.get("p_value")
                effect = finding.get("effect_size")
                effect_interp = finding.get("effect_interpretation", "")
                columns = finding.get("columns", [])

                # Skip statistically insignificant insights
                if p_val is not None and p_val > 0.05:
                    continue

                # Skip trivial correlations
                if insight_type == "correlation" and len(columns) >= 2:
                    pair = tuple(sorted([columns[0].lower(), columns[1].lower()]))
                    if pair in seen_pairs or _is_trivial_correlation(columns[0], columns[1], effect or 0):
                        continue
                    seen_pairs.add(pair)

                # Generate human-readable title & description
                if insight_type == "correlation" and len(columns) >= 2:
                    title, human_desc = _humanize_correlation(columns[0], columns[1], effect or 0, effect_interp)
                elif insight_type in ("comparison", "group_comparison"):
                    title, human_desc = _humanize_comparison(desc, finding)
                elif insight_type == "subspace":
                    title, human_desc = _humanize_subspace(desc, finding)
                elif insight_type == "simpson_paradox":
                    title = "⚠️ Simpson's Paradox detected"
                    human_desc = desc or "A trend that appears in the overall data reverses when the data is split into groups — be cautious drawing conclusions from aggregated numbers."
                else:
                    # trend, anomaly, or unknown — keep original desc but clean up title
                    title = insight_type.replace("_", " ").title()
                    human_desc = desc

                confidence = max(10, int((1 - (p_val or 0.5)) * 100))

                insights.append({
                    "id": f"quis_{i}",
                    "type": type_map.get(insight_type, "info"),
                    "title": title,
                    "description": human_desc,
                    "confidence": min(confidence, 99),
                    "p_value": p_val,
                    "effect_size": effect,
                    "is_simpson_paradox": finding.get("is_simpson_paradox", False),
                    "columns": columns,
                })

            # Strong correlations from enhanced analysis (only if not already covered by QUIS)
            for i, corr in enumerate(enhanced.get("correlations", [])[:4]):
                r = corr.get("correlation", 0)
                if abs(r) < 0.5 or len(insights) >= 8:
                    continue

                col1 = corr.get("column1", "?")
                col2 = corr.get("column2", "?")
                p = corr.get("p_value")

                # Skip insignificant, trivial, or already-seen pairs
                if p is not None and p > 0.05:
                    continue
                pair = tuple(sorted([col1.lower(), col2.lower()]))
                if pair in seen_pairs or _is_trivial_correlation(col1, col2, r):
                    continue
                seen_pairs.add(pair)

                strength = corr.get("strength", "notable")
                title, human_desc = _humanize_correlation(col1, col2, r, strength)

                insights.append({
                    "id": f"corr_{i}",
                    "type": "info",
                    "title": title,
                    "description": human_desc,
                    "confidence": max(10, int((1 - (p or 0.5)) * 100)),
                    "p_value": p,
                    "effect_size": abs(r),
                    "columns": [col1, col2],
                })

            # Distribution anomalies (only genuinely skewed ones)
            for i, dist in enumerate(enhanced.get("distributions", [])[:3]):
                skew = dist.get("skewness", 0)
                if abs(skew) > 1.5 and len(insights) < 8:
                    col = dist.get("column", "?")
                    col_name = col.replace("_", " ").title()
                    dist_type = dist.get("distribution_type", "skewed")
                    direction = "right" if skew > 0 else "left"

                    title = f"{col_name} is heavily {direction}-skewed"
                    human_desc = (
                        f"The distribution of {col_name} is not bell-shaped — it's skewed to the {direction}, "
                        f"meaning {'most values cluster low with a few extreme highs' if skew > 0 else 'most values cluster high with a few extreme lows'}. "
                        f"Consider using median instead of mean for this column."
                    )

                    insights.append({
                        "id": f"dist_{i}",
                        "type": "warning" if abs(skew) > 2 else "info",
                        "title": title,
                        "description": human_desc,
                        "confidence": 90,
                        "columns": [col],
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

        # CACHE THE RESULT
        await dashboard_cache_service.cache_insights(dataset_id, user_id, insights)

        return {"insights": insights, "cached": False}

    except Exception as e:
        logger.error(f"Error getting dashboard insights for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get dashboard insights.")


# ============================================================
#                 DEFAULT DASHBOARD CHARTS
# ============================================================
@router.get("/{dataset_id}/charts")
async def get_dashboard_charts(
    dataset_id: str, 
    current_user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force regeneration, ignoring cache")
):
    try:
        user_id = current_user["id"]
        
        # CHECK CACHE FIRST (unless force_refresh)
        if not force_refresh:
            cached_charts = await dashboard_cache_service.get_cached_charts(dataset_id, user_id)
            if cached_charts is not None:
                # Verify user still has access to this dataset
                await enhanced_dataset_service.get_dataset(dataset_id, user_id)
                logger.info(f"✅ Returning cached charts for dataset {dataset_id}")
                return {"charts": cached_charts, "cached": True}
        
        logger.info(f"🔄 Generating fresh charts for dataset {dataset_id}")
        
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)

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

        # CACHE THE RESULT
        await dashboard_cache_service.cache_charts(dataset_id, user_id, charts)

        return {"charts": charts, "cached": False}

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


# ============================================================
#                CACHE STATUS & MANAGEMENT
# ============================================================
@router.get("/{dataset_id}/cache-status")
async def get_cache_status(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Get dashboard cache status for a dataset."""
    try:
        status = await dashboard_cache_service.get_cache_status(dataset_id, current_user["id"])
        return {"success": True, "cache_status": status}
    except Exception as e:
        logger.error(f"Error getting cache status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get cache status.")


@router.delete("/{dataset_id}/cache")
async def invalidate_dashboard_cache(
    dataset_id: str, 
    current_user: dict = Depends(get_current_user),
    cache_keys: str = Query(None, description="Comma-separated keys to invalidate (kpis,charts,insights). If empty, invalidates all.")
):
    """Invalidate dashboard cache for a dataset. Use when forcing refresh."""
    try:
        keys = [k.strip() for k in cache_keys.split(",") if k.strip()] if cache_keys else None
        if keys is not None and len(keys) == 0:
            keys = None
        success = await dashboard_cache_service.invalidate_cache(dataset_id, current_user["id"], keys)
        return {"success": success, "invalidated_keys": keys or ["all"]}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to invalidate cache.")
