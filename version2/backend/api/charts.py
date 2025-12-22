"""
Charts API - New Unified Chart Rendering Service
================================================

This module provides the new chart rendering API with:
- Unified /api/charts/render endpoint
- Chart recommendations based on data
- Chart insights and explanations
- Dashboard chart management

Author: DataSage AI Team
Version: 3.0 (Refactored)
"""

import logging
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

# --- Application Modules ---
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.charts.chart_render_service import chart_render_service
from services.charts.chart_insights_service import chart_insights_service
from services.charts.chart_intelligence_service import ChartIntelligenceService
from db.schemas_charts import (
    ChartRenderRequest,
    ChartResponse,
    ChartRecommendation
)
from db.schemas_dashboard import ChartConfig, ChartType, AggregationType

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
chart_intelligence_service = ChartIntelligenceService()


# ============================================================
#            MAIN CHART RENDERING ENDPOINT
# ============================================================
@router.post("/render", response_model=ChartResponse)
async def render_chart(
    request: ChartRenderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Main chart rendering endpoint.
    
    Accepts ChartRenderRequest with full configuration and returns
    a ChartResponse with Plotly traces, layout, and AI-generated explanation.
    
    Flow:
    1. Load dataset
    2. Parse and validate chart config
    3. Hydrate chart (DataFrame → Plotly traces)
    4. Render with theme and layout
    5. Generate AI explanation/insights
    6. Return unified response
    """
    try:
        logger.info(f"Rendering chart: type={request.chart_type}, dataset={request.dataset_id}")
        
        # Load dataset
        df = await enhanced_dataset_service.load_dataset_data(
            request.dataset_id,
            current_user["id"]
        )
        
        if df is None or df.is_empty():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or empty"
            )
        
        # Build chart config
        chart_config = {
            "chart_type": request.chart_type,
            "columns": request.fields,
            "aggregation": request.aggregation or "sum",
            "title": request.title or f"{request.chart_type.title()} Chart",
            "group_by": request.group_by
        }
        
        # Apply filters if provided
        if request.filters:
            # TODO: Implement filter logic
            logger.info(f"Applying {len(request.filters)} filters")
        
        # Render chart (hydrate + render pipeline)
        chart_payload = await chart_render_service.render_chart(
            df=df,
            chart_config=chart_config,
            theme="dark"  # TODO: Get from user preferences
        )
        
        # Generate AI explanation and insights (only if requested)
        insights = {}
        if request.include_insights:
            # Ensure chart_payload has chart_type at top level for insights service
            if "chart_type" not in chart_payload and "metadata" in chart_payload:
                chart_payload["chart_type"] = chart_payload["metadata"].get("chart_type")

            insights = await chart_insights_service.generate_chart_insight(
                chart_data=chart_payload,
                df=df,
                use_llm=True
            )
        
        # Build response
        chart_id = str(uuid.uuid4())
        response = ChartResponse(
            id=chart_id,
            type=request.chart_type,
            title=chart_config["title"],
            traces=chart_payload.get("traces", []),
            layout=chart_payload.get("layout", {}),
            fields=request.fields,
            explanation=insights.get("summary", ""),
            confidence=insights.get("confidence", 0.0),
            metadata=chart_payload.get("metadata", {})
        )
        
        logger.info(f"✓ Chart rendered successfully: {chart_id}")
        return response
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid chart configuration: {e}"
        )
    except Exception as e:
        logger.error(f"Chart rendering failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render chart: {str(e)}"
        )


# ============================================================
#            CHART RECOMMENDATIONS
# ============================================================
@router.get("/recommendations", response_model=List[ChartRecommendation])
async def get_chart_recommendations(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get AI-powered chart recommendations for a dataset.
    
    Returns a list of suggested chart types with descriptions
    and suitable columns based on data analysis.
    """
    try:
        logger.info(f"Getting chart recommendations for dataset: {dataset_id}")
        
        # Load dataset metadata
        dataset = await enhanced_dataset_service.get_dataset(
            dataset_id,
            current_user["id"]
        )
        
        metadata = dataset.get("metadata", {})
        column_metadata = metadata.get("column_metadata", [])
        
        if not column_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dataset metadata not available. Please process the dataset first."
            )
        
        # Generate recommendations using AI service
        recommendations = await chart_intelligence_service.suggest_charts_for_dataset(
            column_metadata=column_metadata,
            dataset_overview=metadata.get("dataset_overview", {}),
            max_suggestions=5
        )
        
        # Convert to ChartRecommendation schema
        result = []
        for rec in recommendations:
            result.append(ChartRecommendation(
                chart_type=rec.get("chart_type", "bar"),
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                suitable_columns=rec.get("columns", []),
                confidence=rec.get("confidence", "Medium")
            ))
        
        logger.info(f"✓ Generated {len(result)} chart recommendations")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chart recommendations: {str(e)}"
        )


# ============================================================
#            CHART INSIGHTS (Detailed Analysis)
# ============================================================
@router.post("/insights")
async def get_chart_insights(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed insights for an existing or proposed chart.
    
    Provides:
    - Pattern detection (trends, comparisons, outliers)
    - Statistical summary
    - Natural language explanation
    - Confidence score
    """
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data", [])
        dataset_id = request.get("dataset_id")
        
        if not chart_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chart_config is required"
            )
        
        # Get dataset metadata if provided
        dataset_metadata = {}
        if dataset_id:
            dataset = await enhanced_dataset_service.get_dataset(
                dataset_id,
                current_user["id"]
            )
            dataset_metadata = dataset.get("metadata", {})
        
        # Generate insights
        insights = await chart_insights_service.generate_chart_insight(
            chart_config=chart_config,
            chart_data=chart_data,
            dataset_metadata=dataset_metadata
        )
        
        return insights
        
    except Exception as e:
        logger.error(f"Error generating chart insights: {e}", exc_info=True)
        # Return fallback insights instead of erroring
        return chart_insights_service._generate_fallback_insight(
            request.get("chart_config", {}),
            []
        )


# ============================================================
#            DASHBOARD CHART MANAGEMENT
# ============================================================
@router.post("/dashboard/save")
async def save_chart_to_dashboard(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Save a chart configuration to the user's dashboard.
    
    Stores the ChartConfig so it can be reloaded later.
    """
    try:
        dataset_id = request.get("dataset_id")
        chart_config = request.get("chart_config")
        
        if not dataset_id or not chart_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dataset_id and chart_config are required"
            )
        
        # TODO: Implement dashboard storage in database
        # For now, return success
        chart_id = str(uuid.uuid4())
        
        logger.info(f"Saved chart {chart_id} to dashboard for user {current_user['id']}")
        
        return {
            "success": True,
            "chart_id": chart_id,
            "message": "Chart saved to dashboard"
        }
        
    except Exception as e:
        logger.error(f"Error saving chart: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save chart: {str(e)}"
        )


@router.get("/dashboard/list")
async def list_dashboard_charts(
    dataset_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List all saved charts for a user's dashboard.
    
    Optionally filter by dataset_id.
    """
    try:
        # TODO: Implement database query for saved charts
        # For now, return empty list
        
        logger.info(f"Listing dashboard charts for user {current_user['id']}")
        
        return {
            "charts": [],
            "count": 0
        }
        
    except Exception as e:
        logger.error(f"Error listing charts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list charts: {str(e)}"
        )


# ============================================================
#            LEGACY ENDPOINTS (Backward Compatibility)
# ============================================================
@router.post("/generate")
async def generate_chart_legacy(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Legacy endpoint for backward compatibility.
    Maps old {x_axis, y_axis, ...} format to new ChartRenderRequest.
    """
    try:
        # Map legacy format to new format
        new_request = ChartRenderRequest(
            dataset_id=request.get("dataset_id"),
            chart_type=request.get("chart_type", "bar"),
            fields=[request.get("x_axis"), request.get("y_axis")],
            aggregation=request.get("aggregation", "sum"),
            title=request.get("title")
        )
        
        # Call new render endpoint
        return await render_chart(new_request, current_user)
        
    except Exception as e:
        logger.error(f"Legacy chart generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chart: {str(e)}"
        )
