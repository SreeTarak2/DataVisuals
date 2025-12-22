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

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()


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
    Creates an intelligent dashboard design using the AI Designer service.
    
    By default, returns cached dashboard if it exists. To regenerate, pass force_regenerate=true.
    
    Request body (optional):
    {
        "design_preference": "executive_kpi_trend",  // Optional pattern preference
        "force_regenerate": false                     // Set to true to regenerate existing dashboard
    }
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

@router.post("/analysis/run")
async def run_analysis(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Runs a specific, targeted statistical analysis (e.g., correlation, outlier detection)
    from the computational engine.
    """
    try:
        dataset_id = request.get("dataset_id")
        analysis_type = request.get("analysis_type")
        if not dataset_id or not analysis_type:
            raise HTTPException(status_code=400, detail="Dataset ID and analysis type are required")

        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        
        analysis_func = getattr(analysis_service, analysis_type, None)
        if not callable(analysis_func):
             # A more robust check for available methods in analysis_service
            if analysis_type == "correlation":
                results = analysis_service.find_strong_correlations(df)
            elif analysis_type == "outlier":
                results = analysis_service.detect_outliers_iqr(df)
            elif analysis_type == "distribution":
                results = analysis_service.analyze_distribution(df)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")
        else:
             results = analysis_func(df)

        return {"results": results, "analysis_type": analysis_type}
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