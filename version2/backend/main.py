# backend/main.py

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from datetime import datetime
import logging
import polars as pl

# --- NEW, CLEANED IMPORTS ---
# Core application components
from database import connect_to_mongo, close_mongo_connection
from models.schemas import *

# Correctly imported services
from services.auth_service import auth_service, get_current_user
from services.enhanced_dataset_service import enhanced_dataset_service
from services.dynamic_drilldown_service import drilldown_service
from services.ai_service import ai_service
from services.analysis_service import analysis_service
from services.chart_render_service import chart_render_service
from services.ai_designer_service import ai_designer_service
from services.faiss_vector_service import faiss_vector_service

# For background task status polling
from celery.result import AsyncResult
from tasks import celery_app
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DataSage AI API v3.0",
    description="Refactored AI-powered data visualization and analysis platform",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- LIFECYCLE EVENTS (remain the same) ---
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    # Properly shutdown the httpx client in the AI service
    await ai_service.http_client.aclose()
    await close_mongo_connection()

# --- AUTH & HEALTHCHECK ENDPOINTS (remain the same, no changes needed) ---

@app.post("/api/auth/register", response_model=User)
async def register_user(user_data: UserCreate):
    return await auth_service.create_user(user_data)

@app.post("/api/auth/login", response_model=LoginResponse)
async def login_user(login_data: UserLogin):
    return await auth_service.login_user(login_data)

@app.get("/health")
async def health_check():
    """Health check endpoint for debugging"""
    return {
        "status": "healthy",
        "message": "Backend is running",
        "cors_origins": settings.ALLOWED_ORIGINS,
        "version": "3.0.0"
    }

@app.get("/api/models/status")
async def get_model_status():
    """Get the health status of all AI models"""
    try:
        status = await ai_service.get_model_status()
        return {
            "status": "success",
            "models": status,
            "fallback_enabled": settings.MODEL_FALLBACK_ENABLED
        }
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        return {
            "status": "error",
            "message": "Failed to get model status",
            "error": str(e)
        }

@app.get("/api/auth/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/api/test-ai")
async def test_ai_services():
    """Test AI service connectivity"""
    try:
        # Test a simple AI call
        test_response = await ai_service._call_ollama(
            "Hello, can you respond with just 'AI service working'?", 
            "chat_engine", 
            expect_json=False
        )
        
        return {
            "status": "success",
            "ai_service": "connected",
            "test_response": test_response[:100] + "..." if len(test_response) > 100 else test_response
        }
    except Exception as e:
        return {
            "status": "error", 
            "ai_service": "unavailable",
            "error": str(e),
            "message": "AI services are not available. Please check your Ollama installation or configuration."
        }

# --- DATASET MANAGEMENT ENDPOINTS (remain the same, correctly use enhanced_dataset_service) ---

@app.post("/api/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Uploads a new dataset and starts a background processing task."""
    return await enhanced_dataset_service.upload_dataset(file, current_user["id"], name, description)

@app.get("/api/datasets")
async def list_datasets(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    datasets = await enhanced_dataset_service.get_user_datasets(current_user["id"], skip, limit)
    return {"datasets": datasets}

@app.get("/api/datasets/{dataset_id}")
async def get_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    return await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])

@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    await enhanced_dataset_service.delete_dataset(dataset_id, current_user["id"])
    return {"message": "Dataset deleted successfully"}

@app.get("/api/datasets/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: str, page: int = 1, page_size: int = 100, current_user: dict = Depends(get_current_user)
):
    return await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page, page_size)

@app.get("/api/datasets/{dataset_id}/preview")
async def get_dataset_preview(
    dataset_id: str, limit: int = 10, current_user: dict = Depends(get_current_user)
):
    """
    Get a preview of the dataset (first few rows) for dashboard display.
    """
    try:
        # Get the first page with limited rows
        result = await enhanced_dataset_service.get_dataset_data(
            dataset_id, current_user["id"], page=1, page_size=limit
        )
        
        return {
            "success": True,
            "rows": result.get("data", []),
            "total_rows": result.get("total_rows", 0),
            "columns": result.get("columns", []),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting dataset preview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset preview")

@app.get("/api/datasets/{dataset_id}/columns")
async def get_dataset_columns(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get dataset columns with their data types for chart configuration.
    """
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
        
        # Get column information
        columns = []
        for col in df.columns:
            dtype = df[col].dtype
            is_numeric = dtype in pl.NUMERIC_DTYPES
            is_categorical = dtype in [pl.Utf8, pl.Categorical]
            is_temporal = dtype in [pl.Date, pl.Datetime]
            
            columns.append({
                "name": col,
                "type": str(dtype),
                "is_numeric": is_numeric,
                "is_categorical": is_categorical,
                "is_temporal": is_temporal,
                "sample_values": df[col].head(5).to_list() if len(df) > 0 else []
            })
        
        return {
            "success": True,
            "columns": columns,
            "dataset_info": {
                "name": dataset["name"],
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dataset columns: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset columns")

# --- NEW AND REFACTORED AI & ANALYSIS ENDPOINTS ---

@app.post("/api/datasets/{dataset_id}/chat")
async def process_chat(
    dataset_id: str, 
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    mode: str = Query("learning", description="Chat mode: learning, quick, deep, or forecast")
):
    # Validate mode parameter
    valid_modes = ["learning", "quick", "deep", "forecast"]
    if mode not in valid_modes:
        raise HTTPException(status_code=422, detail=f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}")
    """
    Enhanced conversational chat with pedagogical approach, RAG integration, and validation.
    The frontend must pass back the `conversation_id` on subsequent messages in the same chat thread.
    
    Modes:
    - "learning": Enhanced pedagogical approach with analogies and learning arcs
    - "quick": Fast responses for simple queries
    - "deep": Comprehensive analysis for complex queries
    - "forecast": Predictive analysis mode
    """
    try:
        # Use enhanced AI service for chat processing
        response = await ai_service.process_chat_message_enhanced(
            query=request.message,
            dataset_id=dataset_id,
            user_id=current_user["id"],
            conversation_id=request.conversation_id,
            mode=mode
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/conversations")
async def get_chat_conversations(current_user: dict = Depends(get_current_user)):
    """Get all chat conversations for the current user"""
    try:
        conversations = await ai_service.get_user_conversations(current_user["id"])
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat conversations")

@app.get("/api/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Get a specific conversation by ID"""
    try:
        conversation = await ai_service.get_conversation(conversation_id, current_user["id"])
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"conversation": conversation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")

@app.delete("/api/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific conversation"""
    try:
        success = await ai_service.delete_conversation(conversation_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

@app.get("/api/datasets/{dataset_id}/cached-charts")
async def get_cached_charts(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all cached charts for a dataset"""
    try:
        from services.chart_insights_service import chart_insights_service
        cached_charts = await chart_insights_service.get_dataset_cached_charts(dataset_id, current_user["id"])
        return {"cached_charts": cached_charts}
    except Exception as e:
        logger.error(f"Failed to get cached charts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cached charts")

@app.post("/api/datasets/{dataset_id}/generate-chart-insight")
async def generate_chart_insight(
    dataset_id: str,
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Generate AI insights for a specific chart"""
    try:
        from services.chart_insights_service import chart_insights_service
        
        # Get dataset metadata
        dataset_doc = await ai_service.db.datasets.find_one({"_id": ObjectId(dataset_id), "user_id": current_user["id"]})
        if not dataset_doc or not dataset_doc.get("metadata"):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data", [])
        
        insight = await chart_insights_service.generate_chart_insight(
            chart_config, chart_data, dataset_doc["metadata"]
        )
        
        return {"insight": insight}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate chart insight: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate chart insight")


@app.post("/api/ai/generate-quis-insights")
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
        logger.error(f"Error generating QUIS insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate QUIS insights.")

@app.post("/api/ai/{dataset_id}/generate-dashboard")
async def generate_ai_dashboard(
    dataset_id: str, 
    force_regenerate: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Triggers the AI to design and populate a full dashboard layout
    based on the dataset's content.
    
    Args:
        force_regenerate: If True, deletes existing dashboard and creates a new one
    """
    return await ai_service.generate_ai_dashboard(dataset_id, current_user["id"], force_regenerate)

@app.post("/api/ai/{dataset_id}/design-dashboard")
async def design_intelligent_dashboard(
    dataset_id: str, 
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Creates an intelligent dashboard design using AI Designer service with design patterns.
    This is the new "AI Designer" approach using few-shot learning.
    """
    try:
        design_preference = request.get("design_preference")
        
        response = await ai_designer_service.design_intelligent_dashboard(
            dataset_id=dataset_id,
            user_id=current_user["id"],
            design_preference=design_preference
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI Designer error: {e}")
        raise HTTPException(status_code=500, detail="Failed to design dashboard.")

@app.get("/api/ai/design-patterns")
async def get_design_patterns(current_user: dict = Depends(get_current_user)):
    """
    Get available design patterns for dashboard creation.
    """
    try:
        patterns = await ai_designer_service.get_available_patterns()
        return patterns
    except Exception as e:
        logger.error(f"Error getting design patterns: {e}")
        raise HTTPException(status_code=500, detail="Failed to get design patterns.")

# --- NEW STORYTELLING AND CHART EXPLANATION ENDPOINTS ---

@app.post("/api/ai/{dataset_id}/generate-story")
async def generate_data_story(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Generate compelling data narratives using enhanced storytelling capabilities.
    """
    try:
        story_type = request.get("story_type", "business_impact")
        response = await ai_service.generate_data_story(dataset_id, current_user["id"], story_type)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating data story: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate data story.")

@app.post("/api/ai/{dataset_id}/explain-chart")
async def explain_chart(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Provide comprehensive explanations of charts and visualizations.
    """
    try:
        chart_config = request.get("chart_config", {})
        chart_data = request.get("chart_data")
        response = await ai_service.explain_chart(dataset_id, current_user["id"], chart_config, chart_data)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining chart: {e}")
        raise HTTPException(status_code=500, detail="Failed to explain chart.")

@app.post("/api/ai/{dataset_id}/business-insights")
async def generate_business_insights(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Generate business-focused insights with actionable recommendations.
    """
    try:
        business_context = request.get("business_context")
        response = await ai_service.generate_business_insights(dataset_id, current_user["id"], business_context)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating business insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate business insights.")

# --- VECTOR DATABASE ENDPOINTS ---

@app.post("/api/vector/datasets/{dataset_id}/index")
async def index_dataset_to_vector_db(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Index a dataset to the vector database for semantic search.
    """
    try:
        # Get dataset metadata
        dataset_doc = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        if not dataset_doc or not dataset_doc.get("metadata"):
            raise HTTPException(status_code=404, detail="Dataset not found or not processed")
        
        # Add to vector database using Celery task
        from tasks import index_dataset_to_vector_db
        vector_task = index_dataset_to_vector_db.delay(
            dataset_id=dataset_id,
            dataset_metadata=dataset_doc["metadata"],
            user_id=current_user["id"]
        )
        
        return {
            "message": "Dataset indexing started", 
            "dataset_id": dataset_id,
            "task_id": vector_task.id,
            "status": "processing"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dataset indexing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to index dataset")

@app.post("/api/vector/search/datasets")
async def search_similar_datasets(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Search for datasets similar to the query using semantic similarity.
    """
    try:
        query = request.get("query", "")
        limit = request.get("limit", 5)
        
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query is required")
        
        similar_datasets = await faiss_vector_service.search_similar_datasets(
            query=query,
            user_id=current_user["id"],
            limit=limit
        )
        
        return {
            "query": query,
            "results": similar_datasets,
            "total_found": len(similar_datasets)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail="Failed to search datasets")

@app.post("/api/vector/rag/{dataset_id}/enhanced")
async def enhanced_rag_search(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Enhanced RAG search combining vector similarity with dataset context.
    """
    try:
        query = request.get("query", "")
        
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Add query to history using Celery task
        from tasks import add_query_to_vector_history
        add_query_to_vector_history.delay(
            query=query,
            dataset_id=dataset_id,
            user_id=current_user["id"]
        )
        
        # Perform enhanced RAG search
        rag_result = await faiss_vector_service.enhanced_rag_search(
            query=query,
            dataset_id=dataset_id,
            user_id=current_user["id"]
        )
        
        return rag_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced RAG error: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform enhanced RAG search")

@app.get("/api/vector/stats")
async def get_vector_db_stats(current_user: dict = Depends(get_current_user)):
    """
    Get statistics about the vector database for the current user.
    """
    try:
        stats = await faiss_vector_service.get_vector_db_stats(current_user["id"])
        return stats
        
    except Exception as e:
        logger.error(f"Vector stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get vector database stats")

@app.delete("/api/vector/reset")
async def reset_vector_db(current_user: dict = Depends(get_current_user)):
    """
    Reset the vector database for the current user.
    """
    try:
        success = await faiss_vector_service.reset_vector_db(current_user["id"])
        
        if success:
            return {"message": "Vector database reset successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset vector database")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector reset error: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset vector database")

@app.post("/api/charts/render-preview")
async def render_chart_preview(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Dedicated endpoint for deterministic chart rendering.
    Takes a chart configuration and returns Plotly-ready data.
    This endpoint is separate from AI reasoning and focuses purely on rendering.
    """
    try:
        chart_config = request.get("chart_config")
        dataset_id = request.get("dataset_id")
        
        if not chart_config or not dataset_id:
            raise HTTPException(status_code=400, detail="chart_config and dataset_id are required")
        
        response = await chart_render_service.render_chart(
            chart_config=chart_config,
            dataset_id=dataset_id,
            user_id=current_user["id"]
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart rendering error: {e}")
        raise HTTPException(status_code=500, detail="Failed to render chart.")

@app.post("/api/analysis/run")
async def run_analysis(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Runs a specific, targeted statistical analysis from the computational engine.
    This endpoint no longer contains any analysis logic itself.
    """
    try:
        dataset_id = request.get("dataset_id")
        analysis_type = request.get("analysis_type") # e.g., "correlation", "outlier"
        
        if not dataset_id or not analysis_type:
            raise HTTPException(status_code=400, detail="Dataset ID and analysis type are required")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset or not dataset.get("file_path"):
            raise HTTPException(status_code=404, detail="Dataset file not found.")

        # Load data using Polars for performance
        df = pl.read_csv(dataset["file_path"]) # Add logic for other file types if needed
        
        # Route to the correct method in analysis_service
        if analysis_type == "correlation":
            results = analysis_service.find_strong_correlations(df)
        elif analysis_type == "outlier":
            results = analysis_service.detect_outliers_iqr(df)
        elif analysis_type == "distribution":
            results = analysis_service.analyze_distribution(df)
        # Add more routes here as needed...
        else:
            raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")
            
        return {
            "results": results,
            "analysis_type": analysis_type,
            "dataset_name": dataset.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run analysis.")

@app.post("/api/analysis/run-quis")
async def run_quis_analysis(request: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """
    Runs the comprehensive QUIS analysis including subspace search for deep insights.
    This implements the full QUIS methodology for discovering hidden patterns.
    """
    try:
        dataset_id = request.get("dataset_id")
        max_depth = request.get("max_depth", 2)  # Default to 2-level subspace search
        
        if not dataset_id:
            raise HTTPException(status_code=400, detail="Dataset ID is required")

        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset or not dataset.get("file_path"):
            raise HTTPException(status_code=404, detail="Dataset file not found.")

        # Load data using Polars for performance
        df = pl.read_csv(dataset["file_path"])  # Add logic for other file types if needed
        
        # Run comprehensive QUIS analysis
        quis_results = analysis_service.run_quis_analysis(df)
        
        # Add query to history for future RAG enhancement using Celery task
        from tasks import add_query_to_vector_history
        add_query_to_vector_history.delay(
            query="QUIS comprehensive analysis",
            dataset_id=dataset_id,
            user_id=current_user["id"]
        )
        
        return {
            "quis_analysis": quis_results,
            "dataset_name": dataset.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running QUIS analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run QUIS analysis.")

# --- DRILLDOWN ENDPOINTS (remain the same, correctly use drilldown_service) ---
@app.post("/api/datasets/{dataset_id}/reprocess")
async def reprocess_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Reprocess a dataset to regenerate metadata."""
    try:
        # Get the dataset to ensure it exists and user owns it
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Dispatch a new processing task
        from tasks import process_dataset_task
        task = process_dataset_task.delay(dataset_id, dataset["file_path"])
        
        return {
            "message": "Dataset reprocessing started",
            "task_id": task.id,
            "dataset_id": dataset_id
        }
    except Exception as e:
        logger.error(f"Error reprocessing dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess dataset")


@app.post("/api/datasets/{dataset_id}/drill-down")
async def drill_down(
    dataset_id: str, request: DrillDownRequest, current_user: dict = Depends(get_current_user)
):
    dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page_size=20000)
    return await drilldown_service.execute_drilldown(
        dataset_data.data, request.hierarchy, request.current_level, request.filters
    )

# --- NEW BACKGROUND TASK STATUS ENDPOINT ---
@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """Polls the status of a Celery background task."""
    task_result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "state": task_result.state, "info": {}}
    if task_result.state == 'PROGRESS':
        response["info"] = task_result.info
    elif task_result.state == 'SUCCESS':
        response["info"] = task_result.result
    elif task_result.state == 'FAILURE':
        response["info"] = {'error': str(task_result.info)}
    return response

# --- DASHBOARD ENDPOINTS ---

@app.get("/api/dashboard/{dataset_id}/overview")
async def get_dashboard_overview(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Get dashboard overview with KPIs and basic statistics"""
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
        
        # Calculate basic statistics
        numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
        categorical_cols = df.select(pl.col([pl.Utf8, pl.Categorical])).columns
        
        # Generate KPIs based on actual data
        kpis = []
        
        if numeric_cols:
            # Use first numeric column for primary KPI
            primary_col = numeric_cols[0]
            total_value = df[primary_col].sum()
            mean_value = df[primary_col].mean()
            
            # Only add dollar signs for actual financial/currency columns
            is_currency = any(keyword in primary_col.lower() for keyword in ["price", "revenue", "sales", "cost", "amount", "dollar", "currency", "money"])
            
            kpis.append({
                "title": f"Total {primary_col}",
                "value": f"${total_value:,.2f}" if is_currency else f"{total_value:,.0f}",
                "change": 0,  # Would need historical data for real change
                "color": "success",
                "trendData": []  # Would need time series data
            })
            
            kpis.append({
                "title": f"Average {primary_col}",
                "value": f"${mean_value:,.2f}" if is_currency else f"{mean_value:,.0f}",
                "change": 0,
                "color": "info",
                "trendData": []
            })
        
        # Row count KPI
        kpis.append({
            "title": "Total Records",
            "value": f"{len(df):,}",
            "change": 0,
            "color": "success",
            "trendData": []
        })
        
        # Column count KPI
        kpis.append({
            "title": "Data Columns",
            "value": f"{len(df.columns)}",
            "change": 0,
            "color": "info",
            "trendData": []
        })
        
        return {
            "dataset": {
                "id": dataset["id"],
                "name": dataset["name"],
                "row_count": len(df),
                "column_count": len(df.columns)
            },
            "kpis": kpis,
            "data_types": {
                "numeric": len(numeric_cols),
                "categorical": len(categorical_cols),
                "total": len(df.columns)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard overview")

@app.get("/api/dashboard/{dataset_id}/insights")
async def get_dashboard_insights(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Get AI-generated insights for dashboard"""
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
        
        # Run QUIS analysis to get real insights
        quis_results = analysis_service.run_quis_analysis(df)
        
        # Debug: Log the structure of insights returned
        logger.info(f"QUIS results structure: {list(quis_results.keys())}")
        if quis_results.get("basic_insights"):
            logger.info(f"Basic insights count: {len(quis_results['basic_insights'])}")
            if quis_results["basic_insights"]:
                logger.info(f"First insight structure: {list(quis_results['basic_insights'][0].keys())}")
        
        # Convert QUIS results to dashboard insights format
        insights = []
        
        # Process basic insights
        basic_insights = quis_results.get("basic_insights", [])
        for insight in basic_insights[:3]:  # Limit to top 3
            # Skip insights without a type field
            if not insight.get("type"):
                continue
                
            if insight["type"] == "correlation":
                strength = insight.get("strength", "moderate")
                method = insight.get("method", "correlation")
                columns = insight.get("columns", ["unknown", "unknown"])
                value = insight.get("value", 0)
                
                insights.append({
                    "id": len(insights) + 1,
                    "type": "info",
                    "title": f"Strong {method} correlation found",
                    "description": f"Columns '{columns[0]}' and '{columns[1]}' show {strength} correlation ({value})",
                    "confidence": 85,
                    "icon": "TrendingUp",
                    "color": "text-blue-400",
                    "bgColor": "bg-blue-500/10",
                    "borderColor": "border-blue-500/30"
                })
            elif insight["type"] == "outlier":
                insights.append({
                    "id": len(insights) + 1,
                    "type": "warning",
                    "title": "Outliers detected",
                    "description": f"Column '{insight['column']}' has {insight['percentage']}% outliers that may need attention",
                    "confidence": 90,
                    "icon": "AlertTriangle",
                    "color": "text-yellow-400",
                    "bgColor": "bg-yellow-500/10",
                    "borderColor": "border-yellow-500/30"
                })
        
        # Process deep insights (QUIS subspace search results)
        for insight in quis_results["deep_insights"][:2]:  # Limit to top 2
            if insight["type"] == "subspace_correlation":
                insights.append({
                    "id": len(insights) + 1,
                    "type": "success",
                    "title": "Hidden pattern discovered",
                    "description": f"Correlation between '{insight['base_insight']['columns'][0]}' and '{insight['base_insight']['columns'][1]}' is much stronger ({insight['subspace_correlation']}) in {insight['subspace']}",
                    "confidence": 95,
                    "icon": "Lightbulb",
                    "color": "text-green-400",
                    "bgColor": "bg-green-500/10",
                    "borderColor": "border-green-500/30"
                })
            elif insight["type"] == "category_specific_pattern":
                insights.append({
                    "id": len(insights) + 1,
                    "type": "info",
                    "title": "Category-specific pattern",
                    "description": f"Category '{insight['category_value']}' shows significantly different behavior in '{insight['numeric_column']}' (deviation: {insight['deviation']})",
                    "confidence": 88,
                    "icon": "CheckCircle",
                    "color": "text-blue-400",
                    "bgColor": "bg-blue-500/10",
                    "borderColor": "border-blue-500/30"
                })
        
        # If no insights found, add a default one
        if not insights:
            insights.append({
                "id": 1,
                "type": "info",
                "title": "Dataset analysis complete",
                "description": f"Successfully analyzed {len(df)} records with {len(df.columns)} columns. No significant patterns detected.",
                "confidence": 100,
                "icon": "CheckCircle",
                "color": "text-blue-400",
                "bgColor": "bg-blue-500/10",
                "borderColor": "border-blue-500/30"
            })
        
        return {
            "insights": insights,
            "summary": {
                "total_insights": len(insights),
                "high_confidence": len([i for i in insights if i["confidence"] > 90]),
                "quis_insights": len(quis_results["deep_insights"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard insights")

@app.post("/api/analytics/generate-chart")
async def generate_analytics_chart(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Generate chart data for analytics studio using upgraded Plotly-compatible renderer"""
    try:
        dataset_id = request.get("dataset_id")
        chart_type = request.get("chart_type", "bar")
        x_axis = request.get("x_axis")
        y_axis = request.get("y_axis")
        aggregation = request.get("aggregation", "sum")
        
        if not dataset_id or not x_axis:
            raise HTTPException(status_code=400, detail="dataset_id and x_axis are required")
        
        # For charts that require y_axis, validate it
        charts_requiring_y = ["bar", "line", "pie", "scatter", "area", "timeseries", "bubble", "heatmap"]
        if chart_type in charts_requiring_y and not y_axis:
            raise HTTPException(status_code=400, detail=f"y_axis is required for {chart_type} charts")
        
        # Get dataset
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
        
        # Validate that the requested columns exist
        if x_axis not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{x_axis}' not found in dataset")
        if y_axis and y_axis not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{y_axis}' not found in dataset")
        
        # Check data types for better error messages
        x_dtype = df[x_axis].dtype
        y_dtype = df[y_axis].dtype if y_axis else None
        
        # Warn about potential issues
        if y_dtype and y_dtype not in pl.NUMERIC_DTYPES and aggregation != "count":
            logger.warning(f"Y-axis column '{y_axis}' is not numeric, aggregation '{aggregation}' may not work as expected")
        
        # Log column types for debugging
        logger.info(f"Chart generation - X-axis: {x_axis} (type: {df[x_axis].dtype}), Y-axis: {y_axis} (type: {df[y_axis].dtype if y_axis else 'N/A'})")
        
        # Prepare chart configuration for the new service
        # Note: columns[0] should be the value column (Y-axis), group_by should be the category column (X-axis)
        
        chart_config = {
            "chart_type": chart_type,
            "columns": [y_axis] if y_axis else [x_axis],  # Value column (Y-axis)
            "group_by": x_axis,  # Category column (X-axis)
            "aggregation": aggregation  # Use the requested aggregation
        }
        
        logger.info(f"Using {aggregation} aggregation for {chart_type} chart")
        
        # Generate chart data using the new service
        chart_data = await chart_render_service.render_chart_from_config(chart_config, dataset["file_path"])
        
        return {
            "chart_data": chart_data,
            "chart_type": chart_type,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "aggregation": aggregation,
            "dataset_info": {
                "name": dataset["name"],
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating analytics chart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate chart data: {str(e)}")

# --- DRILL-DOWN API ENDPOINTS ---

@app.post("/api/drilldown/{dataset_id}/analyze")
async def analyze_dataset_for_drilldown(
    dataset_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze dataset to discover possible drill-down hierarchies.
    Frontend calls this once after uploading or selecting a dataset.
    """
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data using the file_path
        file_path = dataset.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="Dataset file not found")
        
        # Read the file based on its extension
        file_ext = file_path.split('.')[-1].lower()
        if file_ext == 'csv':
            df = pl.read_csv(file_path, infer_schema_length=10000)
        elif file_ext in ['xlsx', 'xls']:
            df = pl.read_excel(file_path)
        elif file_ext == 'json':
            df = pl.read_json(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
        
        dataset_data = df.to_dicts()
        
        # Analyze for drill-down hierarchies
        result = await drilldown_service.analyze_dataset_for_drilldown(dataset_data)
        
        return {
            "status": "success",
            "dataset_id": dataset_id,
            "analysis": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing dataset for drill-down: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze dataset: {str(e)}")

@app.post("/api/drilldown/{dataset_id}/execute")
async def execute_drilldown(
    dataset_id: str,
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """
    Execute a specific drill-down level based on user interaction.
    Frontend calls this each time a chart point is clicked.
    """
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data using the file_path
        file_path = dataset.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="Dataset file not found")
        
        # Read the file based on its extension
        file_ext = file_path.split('.')[-1].lower()
        if file_ext == 'csv':
            df = pl.read_csv(file_path, infer_schema_length=10000)
        elif file_ext in ['xlsx', 'xls']:
            df = pl.read_excel(file_path)
        elif file_ext == 'json':
            df = pl.read_json(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
        
        dataset_data = df.to_dicts()
        
        # Extract request parameters
        hierarchy = request.get("hierarchy", {})
        current_level = request.get("current_level", 1)
        filters = request.get("filters", {})
        
        # Execute drill-down
        result = await drilldown_service.execute_drilldown(
            dataset_data=dataset_data,
            hierarchy=hierarchy,
            current_level=current_level,
            filters=filters
        )
        
        return {
            "status": "success",
            "dataset_id": dataset_id,
            "drilldown_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error executing drill-down: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute drill-down: {str(e)}")

@app.get("/api/dashboard/{dataset_id}/charts")
async def get_dashboard_charts(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Get chart data for dashboard"""
    try:
        # Get dataset info
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load dataset data
        df = await enhanced_dataset_service.load_dataset_data(dataset_id, current_user["id"])
        if df is None:
            raise HTTPException(status_code=404, detail="Dataset data not found")
        
        charts = {}
        
        # Generate revenue/time chart - improved logic
        numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
        temporal_cols = df.select(pl.col([pl.Date, pl.Datetime])).columns
        
        # Also check for string columns that might be dates
        string_cols = df.select(pl.col([pl.Utf8, pl.Categorical])).columns
        potential_date_cols = [col for col in string_cols if any(keyword in col.lower() for keyword in ['date', 'time', 'created', 'updated', 'invoice'])]
        
        logger.info(f"Found numeric cols: {numeric_cols}")
        logger.info(f"Found temporal cols: {temporal_cols}")
        logger.info(f"Found potential date cols: {potential_date_cols}")
        
        # Try to generate revenue chart with different approaches
        revenue_data = None
        
        if numeric_cols:
            # Use first numeric column for revenue
            num_col = numeric_cols[0]
            
            if temporal_cols:
                # Use proper temporal column
                temp_col = temporal_cols[0]
                try:
                    revenue_data = df.group_by_dynamic(temp_col, every="1mo").agg([
                        pl.col(num_col).sum().alias("revenue")
                    ]).sort(temp_col).to_dicts()
                except Exception as e:
                    logger.warning(f"Dynamic grouping failed: {e}")
                    revenue_data = None
            
            if not revenue_data and potential_date_cols:
                # Try with string date column
                temp_col = potential_date_cols[0]
                try:
                    # Try to parse the string dates and group
                    df_with_parsed_dates = df.with_columns([
                        pl.col(temp_col).str.to_date("%Y-%m-%d", strict=False).alias("parsed_date")
                    ]).filter(pl.col("parsed_date").is_not_null())
                    
                    if len(df_with_parsed_dates) > 0:
                        revenue_data = df_with_parsed_dates.group_by_dynamic("parsed_date", every="1mo").agg([
                            pl.col(num_col).sum().alias("revenue")
                        ]).sort("parsed_date").to_dicts()
                except Exception as e:
                    logger.warning(f"String date parsing failed: {e}")
            
            # Fallback: group by row index if no temporal data
            if not revenue_data:
                try:
                    # Create a simple time series based on row order
                    sample_size = min(12, len(df))  # Limit to 12 data points
                    step = len(df) // sample_size
                    
                    revenue_data = []
                    for i in range(sample_size):
                        start_idx = i * step
                        end_idx = min((i + 1) * step, len(df))
                        subset = df.slice(start_idx, end_idx - start_idx)
                        revenue_sum = subset[num_col].sum()
                        
                        revenue_data.append({
                            "month": f"Period {i+1}",
                            "revenue": float(revenue_sum) if revenue_sum is not None else 0
                        })
                except Exception as e:
                    logger.warning(f"Fallback grouping failed: {e}")
            
            # Format the data
            if revenue_data:
                charts["revenue_over_time"] = []
                for row in revenue_data:
                    # Extract month name or use period
                    if "parsed_date" in row:
                        month_str = row["parsed_date"].strftime("%b %Y") if hasattr(row["parsed_date"], 'strftime') else str(row["parsed_date"])
                    elif any(key in row for key in temporal_cols):
                        temp_key = next(key for key in temporal_cols if key in row)
                        month_str = row[temp_key].strftime("%b %Y") if hasattr(row[temp_key], 'strftime') else str(row[temp_key])
                    else:
                        month_str = row.get("month", "Unknown")
                    
                    charts["revenue_over_time"].append({
                        "month": month_str,
                        "revenue": float(row["revenue"]) if row["revenue"] is not None else 0
                    })
                
                logger.info(f"Generated {len(charts['revenue_over_time'])} revenue data points")
        
        # Generate category distribution if we have categorical columns
        categorical_cols = df.select(pl.col([pl.Utf8, pl.Categorical])).columns
        if categorical_cols and numeric_cols:
            cat_col = categorical_cols[0]
            num_col = numeric_cols[0]
            
            # Group by category and sum numeric values
            category_data = df.group_by(cat_col).agg([
                pl.col(num_col).sum().alias("value")
            ]).sort("value", descending=True).limit(5).to_dicts()
            
            charts["sales_by_category"] = [
                {
                    "name": str(row[cat_col]) if row[cat_col] is not None else "Unknown",
                    "value": float(row["value"]) if row["value"] is not None else 0
                }
                for row in category_data
            ]
        
        # Generate dynamic user activity chart
        if numeric_cols and len(df) > 0:
            # Use second numeric column for users, or create meaningful data
            user_col = numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0]
            user_data = None  # Initialize user_data
            
            # If we have temporal data, use it; otherwise create meaningful periods
            if temporal_cols or potential_date_cols:
                # Use the same temporal logic as revenue chart
                if temporal_cols:
                    temp_col = temporal_cols[0]
                    try:
                        user_data = df.group_by_dynamic(temp_col, every="1mo").agg([
                            pl.col(user_col).count().alias("users")  # Count records as "users"
                        ]).sort(temp_col).to_dicts()
                    except Exception as e:
                        logger.warning(f"Dynamic user grouping failed: {e}")
                        user_data = None
                
                if not user_data and potential_date_cols:
                    temp_col = potential_date_cols[0]
                    try:
                        df_with_parsed_dates = df.with_columns([
                            pl.col(temp_col).str.to_date("%Y-%m-%d", strict=False).alias("parsed_date")
                        ]).filter(pl.col("parsed_date").is_not_null())
                        
                        if len(df_with_parsed_dates) > 0:
                            user_data = df_with_parsed_dates.group_by_dynamic("parsed_date", every="1mo").agg([
                                pl.count().alias("users")
                            ]).sort("parsed_date").to_dicts()
                    except Exception as e:
                        logger.warning(f"String date user parsing failed: {e}")
                        user_data = None
                
                if user_data:
                    charts["monthly_active_users"] = []
                    for row in user_data:
                        if "parsed_date" in row:
                            month_str = row["parsed_date"].strftime("%b %Y") if hasattr(row["parsed_date"], 'strftime') else str(row["parsed_date"])
                        elif any(key in row for key in temporal_cols):
                            temp_key = next(key for key in temporal_cols if key in row)
                            month_str = row[temp_key].strftime("%b %Y") if hasattr(row[temp_key], 'strftime') else str(row[temp_key])
                        else:
                            month_str = "Unknown"
                        
                        charts["monthly_active_users"].append({
                            "month": month_str,
                            "users": int(row["users"]) if row["users"] is not None else 0
                        })
            
            # Fallback: create meaningful periods based on data
            if "monthly_active_users" not in charts:
                try:
                    sample_size = min(6, len(df))
                    step = len(df) // sample_size
                    
                    mau_data = []
                    for i in range(sample_size):
                        start_idx = i * step
                        end_idx = min((i + 1) * step, len(df))
                        subset = df.slice(start_idx, end_idx - start_idx)
                        user_count = len(subset)
                        
                        mau_data.append({
                            "month": f"Period {i+1}",
                            "users": user_count
                        })
                    charts["monthly_active_users"] = mau_data
                except Exception as e:
                    logger.warning(f"Fallback user data generation failed: {e}")
                    # Final fallback
                    charts["monthly_active_users"] = [
                        {"month": "Period 1", "users": len(df)}
                    ]
        
        # Generate dynamic traffic source pie chart from categorical data
        if categorical_cols:
            # Use a categorical column to create meaningful segments
            traffic_col = categorical_cols[1] if len(categorical_cols) > 1 else categorical_cols[0]
            
            # Count occurrences of each category
            traffic_data = df.group_by(traffic_col).agg([
                pl.count().alias("value")
            ]).sort("value", descending=True).limit(4).to_dicts()
            
            if traffic_data:
                charts["traffic_source"] = []
                for row in traffic_data:
                    charts["traffic_source"].append({
                        "name": str(row[traffic_col]) if row[traffic_col] is not None else "Unknown",
                        "value": int(row["value"]) if row["value"] is not None else 0
                    })
        
        # Fallback traffic source if no categorical data
        if "traffic_source" not in charts:
            charts["traffic_source"] = [
                {"name": "Data Records", "value": len(df)},
                {"name": "Columns", "value": len(df.columns)},
                {"name": "Categories", "value": len(categorical_cols) if categorical_cols else 1}
            ]
        
        return {
            "charts": charts,
            "dataset_info": {
                "name": dataset["name"],
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard charts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard charts")

@app.get("/api/dashboard/{dataset_id}/ai-layout")
async def get_ai_dashboard_layout(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Generate AI-driven dashboard layout using the dashboard_designer prompt.
    """
    try:
        # Use service layer for consistent dataset access
        dataset_doc = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset_doc or not dataset_doc.get("metadata"):
            raise HTTPException(status_code=404, detail="Dataset not found or not ready")
        
        # Use AI service to generate dashboard layout
        ai_layout = await ai_service.generate_ai_dashboard(dataset_id, current_user["id"])
        
        return {
            "success": True,
            "layout": ai_layout,
            "dataset_info": {
                "name": dataset_doc.get("name", "Unknown Dataset"),
                "row_count": dataset_doc.get("metadata", {}).get("dataset_overview", {}).get("total_rows", 0),
                "column_count": dataset_doc.get("metadata", {}).get("dataset_overview", {}).get("total_columns", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating AI dashboard layout: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI dashboard layout")

@app.get("/api/debug/ollama-status")
async def debug_ollama_status(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check Ollama connection status."""
    try:
        from services.ai_service import ai_service
        
        # Test both URLs
        llama_status = await ai_service.test_ollama_connection("https://09acb44ee9fa.ngrok-free.app")
        llava_status = await ai_service.test_ollama_connection("https://wilber-unremarried-reversibly.ngrok-free.dev")
        
        return {
            "llama_status": llama_status,
            "llava_status": llava_status,
            "model_configs": {
                "llama_url": "https://09acb44ee9fa.ngrok-free.app",
                "llava_url": "https://wilber-unremarried-reversibly.ngrok-free.dev"
            }
        }
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return {"error": str(e)}

@app.get("/api/debug/test-ngrok")
async def test_ngrok():
    """Simple test to check if ngrok URL is accessible."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://09acb44ee9fa.ngrok-free.app/api/tags")
            return {
                "status": "success",
                "status_code": response.status_code,
                "response": response.text[:500] if response.text else "No response body"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

@app.get("/api/datasets/{dataset_id}/column-importance")
async def get_column_importance(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get column importance analysis using QUIS system.
    Uses the existing QUIS subspace search to identify important columns.
    """
    try:
        from services.ai_service import ai_service
        
        # Get dataset
        dataset_doc = await db.datasets.find_one({"_id": dataset_id, "user_id": current_user["_id"]})
        if not dataset_doc:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Use QUIS to analyze column importance
        query = "What are the most important columns in this dataset and why are they crucial for analysis?"
        
        # Call QUIS analysis
        quis_response = await ai_service.analyze_with_quis(
            query=query,
            dataset_doc=dataset_doc,
            current_user=current_user
        )
        
        return {
            "analysis": quis_response.get("response_text", "Analysis completed"),
            "insights": quis_response.get("insights", []),
            "method": "QUIS Subspace Search",
            "recommendation": "Use QUIS Q&A system to ask specific questions about column importance and relationships."
        }
        
    except Exception as e:
        logger.error(f"Error analyzing column importance with QUIS: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze column importance: {str(e)}")

@app.get("/api/debug/test-dashboard-generation")
async def test_dashboard_generation(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """Test dashboard generation step by step."""
    try:
        from services.ai_service import ai_service
        from core.prompts import PromptFactory, PromptType
        
        # Get dataset
        dataset_doc = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        if not dataset_doc or not dataset_doc.get("metadata"):
            return {"error": "Dataset not found or not ready"}
        
        # Test context creation
        context_str = ai_service._create_enhanced_llm_context(dataset_doc["metadata"], dataset_doc["file_path"])
        
        # Test prompt creation
        chart_ids = [chart['id'] for chart in ai_service.chart_definitions.values()]
        factory = PromptFactory(dataset_context=context_str)
        prompt = factory.get_prompt(PromptType.DASHBOARD_DESIGNER, chart_options=chart_ids, max_components=12)
        
        # Test AI call
        logger.info("Testing dashboard generation AI call...")
        layout_response = await ai_service._call_ollama(prompt, model_role="visualization_engine", expect_json=True)
        
        return {
            "context_length": len(context_str),
            "chart_options_count": len(chart_ids),
            "prompt_length": len(prompt),
            "ai_response": layout_response,
            "has_dashboard": "dashboard" in layout_response,
            "has_components": "components" in layout_response.get("dashboard", {})
        }
    except Exception as e:
        logger.error(f"Dashboard generation test failed: {e}")
        return {"error": str(e), "error_type": type(e).__name__}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)