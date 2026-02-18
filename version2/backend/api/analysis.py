# backend/api/analysis.py

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

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
                comp["value"] = result.get("value", 0) if isinstance(result, dict) else result

            elif ctype == "chart":
                columns = cfg.get("columns", [])
                if isinstance(columns, str):
                    columns = [columns]
                # Filter to columns that actually exist in the dataframe
                safe_columns = [c for c in columns if c in df.columns]
                if not safe_columns:
                    logger.warning(f"Chart '{comp.get('title')}' has no valid columns. Skipping hydration.")
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
    """
    try:
        force_regenerate = request.get("force_regenerate", False)
        design_preference = request.get("design_preference")
        
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