from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
import uuid
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import settings
from database import connect_to_mongo, close_mongo_connection, get_collection
from models import (
    DatasetInfo, VisualizationRecommendation, LLMRequest, LLMResponse,
    DashboardTemplate, HealthCheck, UserCreate, UserLogin, 
    UserResponse, Token
)
from services.data_profiler import DataProfiler
from services.llm_service import LLMService
from services.chat_service import ChatService
from services.auth_service import auth_service, get_current_user
from services.dynamic_drilldown_service import DynamicDrillDownService
from services.metadata_service import MetadataService
from services.rag_service import RAGService
from services.chart_validation_service import ChartValidationService
from services.enhanced_llm_service import EnhancedLLMService

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
enhanced_llm_service = EnhancedLLMService(llm_service)
metadata_service = MetadataService()
rag_service = RAGService()
chart_validation_service = ChartValidationService()
dynamic_drilldown_service = DynamicDrillDownService()
chat_service = ChatService(llm_service)


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


# Authentication Routes
@app.post("/auth/register", response_model=UserResponse, tags=["Authentication"])
async def register_user(user_create: UserCreate):
    """Register a new user."""
    try:
        user = await auth_service.create_user(user_create)
        logger.info(f"New user registered: {user.email}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during registration"
        )


@app.post("/auth/login", response_model=dict, tags=["Authentication"])
async def login_user(user_login: UserLogin):
    """Login a user and return access token."""
    try:
        result = await auth_service.login_user(user_login)
        logger.info(f"User logged in: {user_login.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during login"
        )


@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@app.post("/auth/logout", tags=["Authentication"])
async def logout_user(current_user = Depends(get_current_user)):
    """Logout user (client should discard token)."""
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Successfully logged out"}


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
            "_id": file_id,  # Use UUID as MongoDB _id
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


# LLM Endpoints
@app.post("/llm/explain", response_model=LLMResponse, tags=["LLM"])
async def explain_dataset(
    dataset_id: str = Query(..., description="ID of the dataset to explain")
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
        explanation = await llm_service.explain_dataset(profile)
        
        return explanation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/visualize", response_model=LLMResponse, tags=["LLM"])
async def recommend_visualization_llm(
    dataset_id: str = Query(..., description="ID of the dataset"),
    query: str = Query(..., description="Natural language query for visualization")
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
        recommendation = await llm_service.recommend_visualization(profile, query)
        
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


@app.post("/datasets/{dataset_id}/analyze", response_model=LLMResponse, tags=["Analysis"])
async def analyze_dataset(
    dataset_id: str
):
    """Perform comprehensive analysis of a dataset."""
    try:
        # Get dataset from database
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Get dataset profile
        profile = dataset.get('profile', {})
        
        if not profile:
            raise HTTPException(status_code=400, detail="Dataset profile not available. Please reprocess the dataset.")
        
        # Perform analysis using LLM service
        response = await llm_service.explain_dataset(profile)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing dataset: {e}")
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
                features={"simplified_labels": True, "business_insights": True, "statistical_details": True, "confidence_intervals": True}
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
                features={"simple_explanations": True, "key_insights": True, "statistical_tests": True, "advanced_metrics": True}
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
                features={"trend_explanation": True, "business_impact": True, "model_parameters": True, "confidence_intervals": True}
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


# Chat Endpoints
@app.post("/chat/message", tags=["Chat"])
async def send_chat_message(
    dataset_id: str = Query(..., description="ID of the dataset"),
    message: str = Body(..., description="User's chat message")
):
    """Send a chat message and get AI response with visualization."""
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Process chat message
        response = await chat_service.process_chat_message(message, dataset_id, dataset_data)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dynamic Drill-Down Endpoints
@app.get("/datasets/{dataset_id}/dynamic-analysis", tags=["Dynamic Drill-Down"])
async def analyze_dataset_for_drilldown(dataset_id: str):
    """
    Analyze any dataset to detect drill-down hierarchies and opportunities.
    Works with ANY data structure and column names.
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Analyze dataset for drill-down opportunities
        analysis_result = await dynamic_drilldown_service.analyze_dataset_for_drilldown(dataset_data)
        
        return {
            "dataset_id": dataset_id,
            "analysis": analysis_result,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing dataset for drill-down: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/datasets/{dataset_id}/dynamic-drilldown", tags=["Dynamic Drill-Down"])
async def execute_dynamic_drilldown(
    dataset_id: str,
    hierarchy: Dict[str, Any] = Body(..., description="Hierarchy configuration"),
    current_level: int = Body(..., description="Current drill-down level"),
    filters: Dict[str, Any] = Body({}, description="Current filters")
):
    """
    Execute drill-down operation for any dataset and hierarchy.
    Works with any data structure automatically detected.
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Execute drill-down
        result = await dynamic_drilldown_service.execute_drilldown(
            dataset_data, hierarchy, current_level, filters
        )
        
        return {
            "dataset_id": dataset_id,
            "drilldown_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing dynamic drill-down: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Enhanced LLM Endpoints with Three Critical Strategies
@app.post("/llm/enhanced/query", tags=["Enhanced LLM"])
async def enhanced_dataset_query(
    dataset_id: str = Body(..., description="ID of the dataset"),
    query: str = Body(..., description="Natural language query")
):
    """
    Process dataset query using three critical strategies:
    1. Never feed raw rows → only metadata, samples, summaries
    2. Use RAG to fetch relevant slices
    3. Always validate AI chart choice with datatype rules
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Process with enhanced LLM service
        result = await enhanced_llm_service.process_dataset_query(
            query, dataset_id, dataset_data
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing enhanced query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/enhanced/visualize", tags=["Enhanced LLM"])
async def enhanced_visualization_recommendation(
    dataset_id: str = Body(..., description="ID of the dataset"),
    query: str = Body(..., description="Visualization query")
):
    """
    Get enhanced visualization recommendation with validation.
    Uses metadata-only approach and RAG for relevant data slices.
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Generate metadata package
        metadata_package = await metadata_service.generate_llm_metadata_package(
            dataset_data, dataset_id
        )
        
        # Get enhanced recommendation
        result = await enhanced_llm_service.recommend_visualization(
            query, metadata_package, dataset_data
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced visualization recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/datasets/{dataset_id}/metadata", tags=["Metadata"])
async def get_dataset_metadata(dataset_id: str):
    """
    Get comprehensive metadata package for LLM consumption.
    NEVER includes raw data rows - only metadata, samples, summaries.
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Generate metadata package
        metadata_package = await metadata_service.generate_llm_metadata_package(
            dataset_data, dataset_id
        )
        
        return {
            "dataset_id": dataset_id,
            "metadata_package": metadata_package,
            "raw_data_excluded": True,
            "llm_ready": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/retrieve", tags=["RAG"])
async def retrieve_relevant_slices(
    dataset_id: str = Body(..., description="ID of the dataset"),
    query: str = Body(..., description="Query for data retrieval"),
    max_slices: int = Body(5, description="Maximum number of slices to return")
):
    """
    Use RAG to retrieve relevant data slices based on query.
    Returns only relevant portions, never full dataset.
    """
    try:
        # Get dataset data
        collection = get_collection("datasets")
        dataset = await collection.find_one({"_id": dataset_id})
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        dataset_data = await _load_dataset_data(dataset)
        
        # Generate metadata package
        metadata_package = await metadata_service.generate_llm_metadata_package(
            dataset_data, dataset_id
        )
        
        # Use RAG to retrieve relevant slices
        result = await rag_service.retrieve_relevant_slices(
            query, metadata_package, dataset_data, max_slices
        )
        
        return {
            "dataset_id": dataset_id,
            "query": query,
            "rag_result": result,
            "raw_data_excluded": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving relevant slices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/charts/validate", tags=["Chart Validation"])
async def validate_chart_recommendation(
    chart_type: str = Body(..., description="Chart type to validate"),
    columns: List[str] = Body(..., description="Columns to use"),
    data: List[Dict] = Body(..., description="Sample data for validation"),
    dataset_metadata: Dict[str, Any] = Body({}, description="Dataset metadata")
):
    """
    Validate AI chart recommendation against datatype rules.
    Ensures chart choice is appropriate for the data.
    """
    try:
        # Validate chart recommendation
        validation_result = chart_validation_service.validate_chart_recommendation(
            chart_type, columns, data, dataset_metadata
        )
        
        return {
            "chart_type": chart_type,
            "validation_result": validation_result,
            "validated": True
        }
        
    except Exception as e:
        logger.error(f"Error validating chart recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _load_dataset_data(dataset: Dict[str, Any]) -> List[Dict]:
    """Load actual dataset data from file."""
    try:
        file_path = dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            # Fallback to sample data if file not found
            profile = dataset.get('profile', {})
            return _generate_sample_data_from_profile(profile)
        
        # Load the actual dataset
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            # Fallback to sample data for unsupported formats
            profile = dataset.get('profile', {})
            return _generate_sample_data_from_profile(profile)
        
        # Convert to list of dictionaries
        return df.to_dict('records')
        
    except Exception as e:
        logger.error(f"Error loading dataset data: {e}")
        # Fallback to sample data
        profile = dataset.get('profile', {})
        return _generate_sample_data_from_profile(profile)

def _generate_sample_data_from_profile(profile: Dict[str, Any]) -> List[Dict]:
    """Generate sample data from dataset profile for analysis."""
    columns = profile.get('columns', [])
    row_count = profile.get('row_count', 100)
    summary_stats = profile.get('summary_stats', {})
    strong_correlations = summary_stats.get('strong_correlations', [])
    
    # Create a DataFrame to preserve correlations
    df = pd.DataFrame()
    
    # Generate numeric columns first
    numeric_cols = [col for col in columns if col.get('is_numeric')]
    for col in numeric_cols:
        min_val = col.get('min', 0)
        max_val = col.get('max', 100)
        df[col['name']] = np.random.uniform(min_val, max_val, min(row_count, 1000))
    
    # Apply correlations if they exist
    for corr in strong_correlations:
        col1 = corr['column1']
        col2 = corr['column2']
        correlation = corr['correlation']
        
        if col1 in df.columns and col2 in df.columns:
            # Generate correlated data
            df[col2] = df[col1] * correlation + np.random.normal(0, 0.1, len(df[col1]))
    
    # Generate categorical columns
    for col in columns:
        if not col.get('is_numeric'):
            values = col.get('sample_values', ['A', 'B', 'C'])
            df[col['name']] = np.random.choice(values, min(row_count, 1000))
    
    return df.to_dict('records')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        reload=settings.debug
    )

