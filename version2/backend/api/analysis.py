# backend/api/analysis.py

import asyncio
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
import polars as pl

# --- Application Modules ---
from services.auth_service import get_current_user
from services.ai.ai_service import ai_service
from services.ai.ai_designer_service import ai_designer_service
from services.analysis.analysis_service import analysis_service
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.datasets.dataset_loader import load_dataset
from services.charts.hydrate import hydrate_chart, hydrate_kpi, hydrate_table
from db.schemas_dashboard import ChartConfig, KpiConfig, TableConfig, ComponentType
from db.database import get_database
from bson import ObjectId

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dashboard generation deduplication lock ---
# Prevents concurrent design-dashboard calls for the same dataset
_dashboard_generation_locks: Dict[str, asyncio.Lock] = {}
_dashboard_generation_futures: Dict[str, asyncio.Task] = {}


# ---------------------------------------------------------
# Hydrate a raw blueprint dict with actual data from the dataset
# ---------------------------------------------------------
async def _hydrate_blueprint(blueprint: Dict[str, Any], dataset_id: str, user_id: str) -> Dict[str, Any]:
    """
    Take a designer-produced blueprint (column names + chart types only)
    and hydrate every component with real Plotly traces / KPI values / table rows.
    """
    components = blueprint.get("components", [])
    if not components:
        return blueprint

    # Load the dataset file
    db = get_database()
    try:
        dataset_oid = ObjectId(dataset_id)
    except Exception:
        dataset_oid = dataset_id
    dataset_doc = await db.datasets.find_one({"_id": dataset_oid, "user_id": user_id})
    if not dataset_doc or not dataset_doc.get("file_path"):
        logger.warning(f"Cannot hydrate blueprint — dataset {dataset_id} not found or has no file_path")
        return blueprint

    try:
        df = await load_dataset(dataset_doc["file_path"])
    except Exception as e:
        logger.error(f"Failed to load dataset for hydration: {e}")
        return blueprint

    hydrated = []
    for comp in components:
        ctype = comp.get("type", "")
        cfg = comp.get("config", {})

        try:
            if ctype == "kpi":
                kpi_cfg = KpiConfig(
                    title=cfg.get("title", comp.get("title", "KPI")),
                    span=comp.get("span", 1),
                    column=cfg.get("column", "__all__"),
                    aggregation=cfg.get("aggregation", "count"),
                    icon=cfg.get("icon"),
                    color=cfg.get("color"),
                )
                result = hydrate_kpi(df, kpi_cfg)
                if isinstance(result, dict):
                    comp["value"] = result.get("value", 0)
                    # Pass through all enrichment fields
                    for key in ("sparkline_data", "comparison_value", "comparison_label",
                                "delta_percent", "format", "min_value", "max_value",
                                "record_count", "top_values"):
                        if key in result:
                            comp[key] = result[key]
                else:
                    comp["value"] = result

            elif ctype == "chart":
                columns = cfg.get("columns", [])
                if isinstance(columns, str):
                    columns = [columns]
                # Filter to columns that actually exist in the dataframe
                safe_columns = [c for c in columns if c in df.columns]
                # Fuzzy fallback: if LLM gave a slightly wrong column name, try to match
                if len(safe_columns) < len(columns):
                    df_cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}
                    for orig_col in columns:
                        if orig_col in df.columns:
                            continue
                        normalized = orig_col.lower().replace(" ", "_")
                        if normalized in df_cols_lower:
                            safe_columns.append(df_cols_lower[normalized])
                            logger.info(f"Fuzzy-matched column '{orig_col}' → '{df_cols_lower[normalized]}'")
                    safe_columns = list(dict.fromkeys(safe_columns))  # dedupe preserving order
                if not safe_columns:
                    logger.warning(f"Chart '{comp.get('title')}' has no valid columns. Skipping hydration.")
                    comp["chart_data"] = {"data": [], "layout": {}}
                    hydrated.append(comp)
                    continue

                # Pre-check: some chart types need at least 2 columns
                chart_type_str = cfg.get("chart_type", "bar")
                # pie with 1 col = categorical distribution; histogram with 1 col = fine
                min_2_types = {"bar", "line", "scatter", "grouped_bar", "area", "waterfall", "funnel", "box_plot", "box", "violin", "bubble", "heatmap"}
                if chart_type_str in min_2_types and len(safe_columns) < 2:
                    # Try to auto-add a complementary column before giving up
                    if len(safe_columns) == 1:
                        existing = safe_columns[0]
                        is_numeric = df[existing].dtype in pl.NUMERIC_DTYPES
                        if is_numeric:
                            # Have numeric → need a categorical for x-axis
                            cat_cols = [c for c in df.columns if df[c].dtype in {pl.Utf8, pl.Categorical, pl.Boolean} and c != existing and "id" not in c.lower()]
                            if cat_cols:
                                safe_columns = [cat_cols[0], existing]
                                logger.info(f"Auto-added categorical '{cat_cols[0]}' for chart '{comp.get('title')}'")
                        else:
                            # Have categorical → need a numeric for y-axis
                            num_cols = [c for c in df.columns if df[c].dtype in pl.NUMERIC_DTYPES and c != existing and "id" not in c.lower()]
                            if num_cols:
                                safe_columns = [existing, num_cols[0]]
                                logger.info(f"Auto-added numeric '{num_cols[0]}' for chart '{comp.get('title')}'")
                    if len(safe_columns) < 2:
                        logger.warning(f"Chart '{comp.get('title')}' needs ≥2 columns for {chart_type_str}, only has {safe_columns}. Skipping.")
                        comp["chart_data"] = {"data": [], "layout": {}}
                        hydrated.append(comp)
                        continue

                chart_cfg = ChartConfig(
                    title=cfg.get("title", comp.get("title", "Chart")),
                    span=comp.get("span", 2),
                    chart_type=cfg.get("chart_type", "bar"),
                    columns=safe_columns,
                    aggregation=cfg.get("aggregation", "sum"),
                    group_by=cfg.get("group_by"),
                )
                traces, rows_used = hydrate_chart(df, chart_cfg)
                comp["chart_data"] = {
                    "data": traces,
                    "layout": {"title": comp.get("title", "Chart")},
                    "rows_used": rows_used,
                }

            elif ctype == "table":
                columns = cfg.get("columns", [])
                safe_columns = [c for c in columns if c in df.columns]
                if not safe_columns:
                    safe_columns = list(df.columns[:6])
                table_cfg = TableConfig(
                    title=cfg.get("title", comp.get("title", "Table")),
                    span=comp.get("span", 4),
                    columns=safe_columns,
                    limit=cfg.get("limit", 200),
                )
                comp["table_data"] = hydrate_table(df, table_cfg)

        except Exception as e:
            logger.error(f"Hydration failed for component '{comp.get('title')}' ({ctype}): {e}")
            if ctype == "chart":
                comp["chart_data"] = {"data": [], "layout": {}}
            elif ctype == "kpi":
                comp["value"] = "N/A"
            elif ctype == "table":
                comp["table_data"] = []

        hydrated.append(comp)

    blueprint["components"] = hydrated
    return blueprint


# --- AI-Powered Dashboard and Story Generation ---


# ---------------------------------------------------------
# Per-chart re-hydration endpoint
# ---------------------------------------------------------
@router.post("/{dataset_id}/retry-chart")
async def retry_single_chart(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Re-hydrate a single chart component without regenerating the entire dashboard.
    Accepts the chart's component config and returns fresh chart_data (Plotly traces).
    """
    try:
        user_id = current_user["id"]
        component = request.get("component", {})
        cfg = component.get("config", {})

        if not cfg:
            raise HTTPException(status_code=400, detail="Missing chart config in request body.")

        # Load the dataset
        db = get_database()
        try:
            dataset_oid = ObjectId(dataset_id)
        except Exception:
            dataset_oid = dataset_id
        dataset_doc = await db.datasets.find_one({"_id": dataset_oid, "user_id": user_id})
        if not dataset_doc or not dataset_doc.get("file_path"):
            raise HTTPException(status_code=404, detail="Dataset not found.")

        df = await load_dataset(dataset_doc["file_path"])

        # Same hydration logic as _hydrate_blueprint but for a single chart
        columns = cfg.get("columns", [])
        if isinstance(columns, str):
            columns = [columns]
        safe_columns = [c for c in columns if c in df.columns]

        chart_type_str = cfg.get("chart_type", "bar")

        # Auto-add complementary column if only 1 is provided
        min_2_types = {"bar", "line", "scatter", "grouped_bar", "area", "waterfall", "funnel", "box_plot", "violin", "bubble"}
        if chart_type_str in min_2_types and len(safe_columns) < 2:
            if len(safe_columns) == 1:
                existing = safe_columns[0]
                is_numeric = df[existing].dtype in pl.NUMERIC_DTYPES
                if is_numeric:
                    cat_cols = [c for c in df.columns if df[c].dtype in {pl.Utf8, pl.Categorical, pl.Boolean} and c != existing and "id" not in c.lower()]
                    if cat_cols:
                        safe_columns = [cat_cols[0], existing]
                else:
                    num_cols = [c for c in df.columns if df[c].dtype in pl.NUMERIC_DTYPES and c != existing and "id" not in c.lower()]
                    if num_cols:
                        safe_columns = [existing, num_cols[0]]

        # Chart types that can work with fewer than 2 columns:
        # pie/donut: 1 col → value_counts, heatmap: falls back to correlation, histogram: 1 col
        flexible_types = {"pie", "pie_chart", "donut", "histogram", "heatmap", "treemap"}
        if chart_type_str not in flexible_types and len(safe_columns) < 2:
            raise HTTPException(status_code=400, detail=f"Chart type '{chart_type_str}' needs at least 2 valid columns, but only found: {safe_columns}")

        if not safe_columns:
            raise HTTPException(status_code=400, detail="No valid columns found in the dataset for this chart.")

        chart_cfg = ChartConfig(
            title=cfg.get("title", component.get("title", "Chart")),
            span=component.get("span", 2),
            chart_type=chart_type_str,
            columns=safe_columns,
            aggregation=cfg.get("aggregation", "sum"),
            group_by=cfg.get("group_by"),
        )
        traces, rows_used = hydrate_chart(df, chart_cfg)

        return {
            "success": True,
            "chart_data": {
                "data": traces,
                "layout": {"title": component.get("title", "Chart")},
                "rows_used": rows_used,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry chart failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to re-hydrate chart: {str(e)}")


@router.post("/{dataset_id}/generate-dashboard")
async def generate_ai_dashboard(
    dataset_id: str,
    force_regenerate: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    (Legacy Method) Triggers the AI to design and populate a full dashboard layout.
    This method uses the core AIService for generation.
    """
    return await ai_service.generate_ai_dashboard(dataset_id, current_user["id"], force_regenerate)

@router.post("/{dataset_id}/design-dashboard")
async def design_intelligent_dashboard(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Creates an intelligent dashboard design using the AI Designer service,
    then hydrates each component with real data (Plotly traces, KPI values, table rows).
    
    Includes deduplication: concurrent calls for the same dataset will share
    a single generation pipeline instead of running 4x in parallel.
    """
    try:
        force_regenerate = request.get("force_regenerate", False)
        design_preference = request.get("design_preference")
        lock_key = f"{dataset_id}:{current_user['id']}"

        # Get or create a per-dataset lock to prevent concurrent generation
        if lock_key not in _dashboard_generation_locks:
            _dashboard_generation_locks[lock_key] = asyncio.Lock()
        lock = _dashboard_generation_locks[lock_key]

        # If another call is already generating, wait for it instead of starting a new one
        if lock.locked() and not force_regenerate:
            logger.info(f"Dashboard generation already in-flight for {lock_key}, waiting for result...")
            async with lock:
                # The first call finished — fetch the cached result
                existing = await ai_designer_service.get_existing_dashboard(
                    dataset_id=dataset_id,
                    user_id=current_user["id"]
                )
                if existing:
                    return existing
                # If somehow no cached result, fall through to generate

        async with lock:
            response = await ai_designer_service.design_intelligent_dashboard(
                dataset_id=dataset_id,
                user_id=current_user["id"],
                design_preference=design_preference,
                force_regenerate=force_regenerate
            )

            # Hydrate the blueprint with actual data
            blueprint = response.get("dashboard_blueprint")
            if blueprint and isinstance(blueprint, dict):
                logger.info(f"Hydrating designer blueprint for dataset {dataset_id}...")
                response["dashboard_blueprint"] = await _hydrate_blueprint(
                    blueprint, dataset_id, current_user["id"]
                )
                logger.info(f"Blueprint hydration complete.")

                # Passive belief ingestion: KPI values → candidate beliefs (fire-and-forget)
                try:
                    from services.agents.belief_store import get_belief_store, PassiveBeliefIngestion
                    _bs = get_belief_store()
                    components = blueprint.get("components", [])
                    asyncio.create_task(
                        PassiveBeliefIngestion.ingest_dashboard_kpis(
                            _bs, current_user["id"], components, dataset_id
                        )
                    )
                except Exception as _e:
                    logger.debug(f"Dashboard belief ingestion skipped: {_e}")

            return response
    except Exception as e:
        logger.error(f"AI Designer error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to design dashboard.")

@router.get("/{dataset_id}/dashboard")
async def get_existing_dashboard(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves existing dashboard for a dataset without regenerating.
    Returns 404 if no dashboard exists yet.
    """
    try:
        dashboard = await ai_designer_service.get_existing_dashboard(
            dataset_id=dataset_id,
            user_id=current_user["id"]
        )
        
        if not dashboard:
            raise HTTPException(status_code=404, detail="No dashboard found for this dataset. Generate one first.")
        
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard")

@router.get("/design-patterns")
async def get_design_patterns(current_user: dict = Depends(get_current_user)):
    """
    Retrieves the list of available design patterns for AI dashboard creation.
    """
    return await ai_designer_service.get_available_patterns()

@router.post("/{dataset_id}/generate-story")
async def generate_data_story(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Generates a compelling data narrative or "story" from the dataset.
    """
    try:
        story_type = request.get("story_type", "business_impact")
        return await ai_service.generate_data_story(dataset_id, current_user["id"], story_type)
    except Exception as e:
        logger.error(f"Error generating data story: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate data story.")


# --- AI-Powered Insight Generation ---

@router.post("/generate-quis-insights")
async def generate_quis_insights(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Generates high-level, proactive insights using the QUIS methodology.
    """
    try:
        dataset_metadata = request.get("dataset_metadata", {})
        dataset_name = request.get("dataset_name", "Unknown Dataset")
        return await ai_service.generate_quis_insights(dataset_metadata, dataset_name)
    except Exception as e:
        logger.error(f"Error generating QUIS insights: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate QUIS insights.")

@router.post("/{dataset_id}/explain-chart")
async def explain_chart(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Provides a comprehensive, AI-generated explanation of a chart's configuration and data.
    """
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data")
        return await ai_service.explain_chart(dataset_id, current_user["id"], chart_config, chart_data)
    except Exception as e:
        logger.error(f"Error explaining chart: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to explain chart.")

@router.post("/{dataset_id}/business-insights")
async def generate_business_insights(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Generates business-focused insights with actionable recommendations.
    """
    try:
        business_context = request.get("business_context")
        return await ai_service.generate_business_insights(dataset_id, current_user["id"], business_context)
    except Exception as e:
        logger.error(f"Error generating business insights: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate business insights.")


# --- Direct Computational Analysis Endpoints ---

# Whitelist of allowed analysis types - prevents arbitrary method execution
ALLOWED_ANALYSIS_TYPES = {
    "correlation": "find_strong_correlations",
    "outlier": "detect_outliers_iqr",
    "distribution": "analyze_distribution",
    "summary": "get_summary_statistics",
}

@router.post("/analysis/run")
async def run_analysis(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Runs a specific, targeted statistical analysis (e.g., correlation, outlier detection)
    from the computational engine.
    
    Allowed analysis types: correlation, outlier, distribution, summary
    """
    try:
        dataset_id = request.get("dataset_id")
        analysis_type = request.get("analysis_type")
        if not dataset_id or not analysis_type:
            raise HTTPException(status_code=400, detail="Dataset ID and analysis type are required")
        
        # Validate analysis type against whitelist
        if analysis_type not in ALLOWED_ANALYSIS_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown analysis type: '{analysis_type}'. Allowed types: {', '.join(ALLOWED_ANALYSIS_TYPES.keys())}"
            )

        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        
        # Get the method name from whitelist and call it
        method_name = ALLOWED_ANALYSIS_TYPES[analysis_type]
        analysis_func = getattr(analysis_service, method_name, None)
        
        if not callable(analysis_func):
            logger.error(f"Analysis method '{method_name}' not found on analysis_service")
            raise HTTPException(status_code=500, detail="Analysis method not available")
        
        results = analysis_func(df)

        return {"results": results, "analysis_type": analysis_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run analysis.")


@router.post("/run-quis")
async def run_quis_analysis(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Runs the comprehensive QUIS analysis, including subspace search for deep insights.
    """
    try:
        dataset_id = request.get("dataset_id")
        if not dataset_id:
            raise HTTPException(status_code=400, detail="Dataset ID is required")
            
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        quis_results = analysis_service.run_quis_analysis(df, dataset_id=dataset_id)
        
        return {"quis_analysis": quis_results}
    except Exception as e:
        logger.error(f"Error running QUIS analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run QUIS analysis.")