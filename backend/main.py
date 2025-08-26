from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional

from config import settings
from database import connect_to_mongo, close_mongo_connection, get_collection
from models import (
    DatasetInfo, VisualizationRecommendation, LLMRequest, LLMResponse,
    DashboardTemplate, HealthCheck, PersonaType
)
from services.data_profiler import DataProfiler
from services.visualization_recommender import VisualizationRecommender
from services.llm_service import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DataSage AI",
    description="AI-powered data visualization and analysis platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
llm_service = LLMService()


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    await connect_to_mongo()
    logger.info("DataSage AI started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown."""
    await close_mongo_connection()
    logger.info("DataSage AI shutdown complete")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to DataSage AI",
        "version": "1.0.0",
        "description": "AI-powered data visualization and analysis platform",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        db = get_collection("health_check")
        await db.find_one()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check LLM service
    try:
        # Simple test call
        test_response = await llm_service.explain_dataset(
            {"row_count": 100, "column_count": 5, "columns": []}, 
            PersonaType.NORMAL
        )
        llm_status = "healthy" if test_response else "unhealthy"
    except Exception as e:
        logger.error(f"OpenAI service health check failed: {e}")
        llm_status = "unhealthy"
    
    return HealthCheck(
        status="healthy" if db_status == "healthy" and llm_status == "healthy" else "degraded",
        timestamp=datetime.utcnow(),
        database=db_status,
        llm_service=llm_status
    )


# Dataset Management Endpoints
@app.post("/datasets/upload", response_model=DatasetInfo, tags=["Datasets"])
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and profile a dataset."""
    try:
        # Validate file type
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(settings.upload_dir, f"{file_id}{file_extension}")
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Profile dataset
        profile = await DataProfiler.profile_dataset(file_path)
        
        # Create dataset info
        dataset_info = DatasetInfo(
            id=file_id,
            filename=file.filename,
            size=len(content),
            row_count=profile['row_count'],
            column_count=profile['column_count'],
            upload_date=datetime.utcnow(),
            columns=profile['columns'],
            summary_stats=profile['summary_stats']
        )
        
        # Store in database
        collection = get_collection("datasets")
        await collection.insert_one({
            **dataset_info.dict(),
            "file_path": file_path,
            "profile": profile
        })
        
        logger.info(f"Dataset uploaded successfully: {file_id}")
        return dataset_info
        
    except Exception as e:
        logger.error(f"Error uploading dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/datasets", response_model=List[DatasetInfo], tags=["Datasets"])
async def list_datasets():
    """List all uploaded datasets."""
    try:
        collection = get_collection("datasets")
        datasets = await collection.find({}, {"file_path": 0, "profile": 0}).to_list(length=100)
        
        # Convert to DatasetInfo models
        dataset_list = []
        for dataset in datasets:
            dataset['id'] = str(dataset['_id'])
            del dataset['_id']
            dataset_list.append(DatasetInfo(**dataset))
        
        return dataset_list
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/datasets/{dataset_id}", response_model=DatasetInfo, tags=["Datasets"])
async def get_dataset(dataset_id: str):
    """Get specific dataset information."""
    try:
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        dataset['id'] = str(dataset['_id'])
        del dataset['_id']
        return DatasetInfo(**dataset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/datasets/{dataset_id}", tags=["Datasets"])
async def delete_dataset(dataset_id: str):
    """Delete a dataset."""
    try:
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Delete file
        if 'file_path' in dataset and os.path.exists(dataset['file_path']):
            os.remove(dataset['file_path'])
        
        # Delete from database
        await collection.delete_one({"_id": dataset_id})
        
        logger.info(f"Dataset deleted successfully: {dataset_id}")
        return {"message": "Dataset deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Visualization Endpoints
@app.get("/visualization/chart-types", response_model=List[VisualizationRecommendation], tags=["Visualization"])
async def recommend_charts(
    dataset_id: str = Query(..., description="ID of the dataset to analyze"),
    persona: PersonaType = Query(PersonaType.NORMAL, description="User persona for recommendations")
):
    """Get visualization recommendations for a dataset."""
    try:
        # Get dataset profile
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        profile = dataset.get('profile', {})
        
        # Get recommendations
        recommendations = await VisualizationRecommender.recommend_visualizations(profile, persona)
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recommending charts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/visualization/fields", tags=["Visualization"])
async def get_available_fields(dataset_id: str = Query(..., description="ID of the dataset")):
    """Get available fields and their characteristics for a dataset."""
    try:
        # Get dataset profile
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        profile = dataset.get('profile', {})
        
        # Get field information
        fields = await VisualizationRecommender.get_available_fields(profile)
        
        return {"dataset_id": dataset_id, "fields": fields}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fields: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# LLM Endpoints
@app.post("/llm/explain", response_model=LLMResponse, tags=["LLM"])
async def explain_dataset(
    dataset_id: str = Query(..., description="ID of the dataset to explain"),
    persona: PersonaType = Query(PersonaType.NORMAL, description="User persona for explanation")
):
    """Get AI-powered explanation of a dataset."""
    try:
        # Get dataset profile
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        profile = dataset.get('profile', {})
        
        # Get LLM explanation
        explanation = await llm_service.explain_dataset(profile, persona)
        
        return explanation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/visualize", response_model=LLMResponse, tags=["LLM"])
async def recommend_visualization_llm(
    dataset_id: str = Query(..., description="ID of the dataset"),
    query: str = Query(..., description="Natural language query for visualization"),
    persona: PersonaType = Query(PersonaType.NORMAL, description="User persona")
):
    """Get AI-powered visualization recommendations based on natural language query."""
    try:
        # Get dataset profile
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        profile = dataset.get('profile', {})
        
        # Get LLM recommendation
        recommendation = await llm_service.recommend_visualization(profile, query, persona)
        
        return recommendation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM visualization recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/query", response_model=LLMResponse, tags=["LLM"])
async def query_dataset(request: LLMRequest):
    """Answer natural language queries about a dataset."""
    try:
        # Get LLM response
        response = await llm_service.answer_query(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard Template Endpoints
@app.get("/dashboard/templates", response_model=List[DashboardTemplate], tags=["Dashboards"])
async def get_dashboard_templates():
    """Get available dashboard templates."""
    try:
        # Predefined templates
        templates = [
            DashboardTemplate(
                id="kpi",
                name="KPI Dashboard",
                description="Key performance indicators and metrics overview",
                template_type="kpi",
                layout=[
                    {"type": "metric", "title": "Total Sales", "position": {"x": 0, "y": 0, "w": 3, "h": 2}},
                    {"type": "line_chart", "title": "Sales Trend", "position": {"x": 3, "y": 0, "w": 9, "h": 4}},
                    {"type": "bar_chart", "title": "Sales by Category", "position": {"x": 0, "y": 2, "w": 6, "h": 4}},
                    {"type": "pie_chart", "title": "Market Share", "position": {"x": 6, "y": 2, "w": 6, "h": 4}}
                ],
                recommended_datasets=["sales_data", "product_data"],
                persona_adaptations={
                    PersonaType.NORMAL: {"simplified_labels": True, "business_insights": True},
                    PersonaType.EXPERT: {"statistical_details": True, "confidence_intervals": True}
                }
            ),
            DashboardTemplate(
                id="exploration",
                name="Data Exploration",
                description="Interactive data exploration and analysis",
                template_type="exploration",
                layout=[
                    {"type": "scatter_plot", "title": "Correlation Analysis", "position": {"x": 0, "y": 0, "w": 6, "h": 4}},
                    {"type": "histogram", "title": "Distribution Analysis", "position": {"x": 6, "y": 0, "w": 6, "h": 4}},
                    {"type": "heatmap", "title": "Correlation Matrix", "position": {"x": 0, "y": 4, "w": 12, "h": 4}},
                    {"type": "box_plot", "title": "Outlier Detection", "position": {"x": 0, "y": 8, "w": 12, "h": 4}}
                ],
                recommended_datasets=["analytical_data"],
                persona_adaptations={
                    PersonaType.NORMAL: {"simple_explanations": True, "key_insights": True},
                    PersonaType.EXPERT: {"statistical_tests": True, "advanced_metrics": True}
                }
            ),
            DashboardTemplate(
                id="forecast",
                name="Forecasting Dashboard",
                description="Time series analysis and predictions",
                template_type="forecast",
                layout=[
                    {"type": "line_chart", "title": "Historical Data", "position": {"x": 0, "y": 0, "w": 12, "h": 4}},
                    {"type": "line_chart", "title": "Forecast", "position": {"x": 0, "y": 4, "w": 8, "h": 4}},
                    {"type": "metric", "title": "Forecast Accuracy", "position": {"x": 8, "y": 4, "w": 4, "h": 2}},
                    {"type": "bar_chart", "title": "Seasonal Patterns", "position": {"x": 8, "y": 6, "w": 4, "h": 2}}
                ],
                recommended_datasets=["time_series_data"],
                persona_adaptations={
                    PersonaType.NORMAL: {"trend_explanation": True, "business_impact": True},
                    PersonaType.EXPERT: {"model_parameters": True, "confidence_intervals": True}
                }
            )
        ]
        
        return templates
        
    except Exception as e:
        logger.error(f"Error getting dashboard templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/templates/{template_id}", response_model=DashboardTemplate, tags=["Dashboards"])
async def get_dashboard_template(template_id: str):
    """Get specific dashboard template."""
    try:
        templates = await get_dashboard_templates()
        
        for template in templates:
            if template.id == template_id:
                return template
        
        raise HTTPException(status_code=404, detail="Template not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
