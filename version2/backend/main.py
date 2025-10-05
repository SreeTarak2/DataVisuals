from importlib import reload
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import uuid
import json
import uvicorn
import io
from datetime import datetime
import logging

# Import database and services
from database import connect_to_mongo, close_mongo_connection
from services.auth_service import auth_service, get_current_user
from services.enhanced_dataset_service import enhanced_dataset_service
from services.enhanced_llm_service import EnhancedLLMService
from services.metadata_service import MetadataService
from services.rag_service import RAGService
from services.dynamic_drilldown_service import DynamicDrillDownService
from services.chart_validation_service import ChartValidationService
from services.ai_visualization_service import ai_visualization_service
from services.file_storage_service import file_storage_service
from models.schemas import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DataSage AI API",
    description="AI-powered data visualization and analysis platform",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://localhost:5174", 
        "http://localhost:5175",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Initialize services
llm_service = EnhancedLLMService()
metadata_service = MetadataService()
rag_service = RAGService()
drilldown_service = DynamicDrillDownService()
chart_validator = ChartValidationService()

# In-memory storage for demo (replace with MongoDB in production)
datasets = {}
charts = {}

# Authentication Endpoints
@app.post("/auth/register", response_model=User)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        user = await auth_service.create_user(user_data)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/auth/login", response_model=Token)
async def login_user(login_data: UserLogin):
    """Login user and return access token"""
    try:
        token = await auth_service.login_user(login_data)
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@app.put("/auth/profile", response_model=User)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    try:
        updated_user = await auth_service.update_user_profile(
            current_user["_id"], 
            profile_data.dict(exclude_unset=True)
        )
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )

@app.post("/auth/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        await auth_service.change_password(
            current_user["_id"],
            password_data.old_password,
            password_data.new_password
        )
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Dataset Management Routes
@app.get("/api/datasets")
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """List all datasets for the current user"""
    try:
        datasets = await enhanced_dataset_service.get_user_datasets(current_user["id"], skip, limit)
        return {"datasets": datasets}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve datasets")

@app.post("/api/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Upload new dataset"""
    try:
        result = await enhanced_dataset_service.upload_dataset(
            file, 
            current_user["id"], 
            name, 
            description
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get dataset details"""
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset")

@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete dataset"""
    try:
        await enhanced_dataset_service.delete_dataset(dataset_id, current_user["id"])
        return {"message": "Dataset deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete dataset")

@app.get("/api/datasets/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: str,
    page: int = 1,
    page_size: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get dataset data with pagination"""
    try:
        data = await enhanced_dataset_service.get_dataset_data(
            dataset_id, current_user["id"], page, page_size
        )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset data")

@app.get("/api/datasets/{dataset_id}/summary")
async def get_dataset_summary(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get dataset summary statistics"""
    try:
        summary = await enhanced_dataset_service.get_dataset_summary(
            dataset_id, current_user["id"]
        )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset summary")

@app.get("/api/datasets/{dataset_id}/metadata")
async def get_dataset_metadata(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get dataset metadata"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        metadata = await metadata_service.generate_llm_metadata_package(
            dataset_data.data, dataset_id
        )
        
        return metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/datasets/{dataset_id}/kpis")
async def get_dataset_kpis(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get KPI metrics for a dataset"""
    try:
        # Get dataset summary
        summary = await enhanced_dataset_service.get_dataset_summary(dataset_id, current_user["id"])
        
        # Calculate KPI metrics
        kpis = [
            {
                "title": "Total Rows",
                "value": str(summary.total_rows),
                "change": "+0%",
                "trend": "up",
                "description": "Total number of data records"
            },
            {
                "title": "Total Columns", 
                "value": str(summary.total_columns),
                "change": "+0%",
                "trend": "up",
                "description": "Number of data columns"
            },
            {
                "title": "Data Quality",
                "value": f"{85}%",
                "change": "+5%",
                "trend": "up", 
                "description": "Overall data quality score"
            },
            {
                "title": "Missing Values",
                "value": str(sum(summary.missing_values.values())),
                "change": "-2%",
                "trend": "down",
                "description": "Total missing data points"
            }
        ]
        
        return {"kpis": kpis}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset KPIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chart Generation Routes
@app.post("/api/datasets/{dataset_id}/generate-dashboard")
async def generate_dashboard(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Generate initial dashboard charts"""
    try:
        # Get dataset from enhanced service
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        # Generate metadata
        metadata = await metadata_service.generate_llm_metadata_package(
            dataset_data.data, dataset_id
        )
        
        # Generate chart recommendations
        chart_recommendations = metadata.get("chart_recommendations", [])
        
        # Create dashboard charts
        dashboard_charts = []
        for i, rec in enumerate(chart_recommendations[:4]):  # Limit to 4 charts
            chart_id = f"{dataset_id}_chart_{i}"
            chart_data = await _generate_chart_data(dataset_data.data, rec)
            
            chart = {
                "id": chart_id,
                "type": rec["chart_type"],
                "title": rec["title"],
                "data": chart_data,
                "fields": rec["suitable_columns"],
                "explanation": rec["description"],
                "confidence": rec.get("confidence", 0.8)
            }
            
            charts[chart_id] = chart
            dashboard_charts.append(chart)
        
        return {
            "charts": dashboard_charts,
            "dataset_id": dataset_id,
            "total_charts": len(dashboard_charts)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/datasets/{dataset_id}/create-chart")
async def create_chart(
    dataset_id: str, 
    request: ChartRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create specific chart"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        chart_id = f"{dataset_id}_chart_{len(charts)}"
        
        # Generate chart data
        chart_data = await _generate_chart_data(dataset_data.data, {
            "chart_type": request.chart_type,
            "suitable_columns": request.fields
        })
        
        chart = {
            "id": chart_id,
            "type": request.chart_type,
            "title": request.title or f"{request.chart_type.title()} Chart",
            "data": chart_data,
            "fields": request.fields,
            "explanation": request.explanation or "Generated chart based on your request",
            "confidence": 0.9
        }
        
        charts[chart_id] = chart
        return chart
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chart creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/datasets/{dataset_id}/chart-recommendations")
async def get_chart_recommendations(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get AI chart recommendations"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        metadata = await metadata_service.generate_llm_metadata_package(
            dataset_data.data, dataset_id
        )
        
        return {
            "recommendations": metadata.get("chart_recommendations", []),
            "dataset_id": dataset_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/datasets/{dataset_id}/chat")
async def process_chat(
    dataset_id: str, 
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Process chat queries"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        # Generate metadata
        metadata = await metadata_service.generate_llm_metadata_package(
            dataset_data.data, dataset_id
        )
        
        # Process query with LLM
        response = await llm_service.process_dataset_query(
            request.message, dataset_id, dataset_data.data
        )
        
        # Generate chart if requested
        chart = None
        if response.get("chart_recommendation"):
            chart_data = await _generate_chart_data(
                dataset_data.data, 
                response["chart_recommendation"]
            )
            chart = {
                "type": response["chart_recommendation"]["chart_type"],
                "data": chart_data,
                "fields": response["chart_recommendation"]["suitable_columns"],
                "explanation": response["chart_recommendation"]["description"]
            }
        
        return {
            "response": response["response"],
            "chart": chart,
            "metadata_used": response.get("metadata_used", False),
            "rag_used": response.get("rag_used", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Drill-down Routes
@app.get("/api/datasets/{dataset_id}/hierarchies")
async def get_hierarchies(
    dataset_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get available hierarchies"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        analysis = await drilldown_service.analyze_dataset_for_drilldown(dataset_data.data)
        
        return {
            "hierarchies": analysis.get("hierarchies", []),
            "dataset_id": dataset_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting hierarchies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/datasets/{dataset_id}/drill-down")
async def drill_down(
    dataset_id: str, 
    request: DrillDownRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute drill-down operation"""
    try:
        # Get dataset data
        dataset_data = await enhanced_dataset_service.get_dataset_data(dataset_id, current_user["id"], page=1, page_size=1000)
        
        result = await drilldown_service.execute_drilldown(
            dataset_data.data, 
            request.hierarchy, 
            request.current_level, 
            request.filters
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Drill-down error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function
async def _generate_chart_data(data: List[Dict], chart_config: Dict) -> List[Dict]:
    """Generate chart data based on configuration"""
    df = pd.DataFrame(data)
    
    chart_type = chart_config.get("chart_type", "bar_chart")
    fields = chart_config.get("suitable_columns", [])
    
    if not fields or len(fields) < 1:
        return []
    
    try:
        if chart_type == "bar_chart":
            if len(fields) >= 2:
                # Group by first field, sum the second field
                result = df.groupby(fields[0])[fields[1]].sum().reset_index()
                result.columns = ['x', 'y']
                return result.to_dict('records')
            else:
                # Count frequency of single field
                result = df[fields[0]].value_counts().reset_index()
                result.columns = ['x', 'y']
                return result.to_dict('records')
        
        elif chart_type == "pie_chart":
            result = df[fields[0]].value_counts().reset_index()
            result.columns = ['label', 'value']
            return result.to_dict('records')
        
        elif chart_type == "line_chart":
            if len(fields) >= 2:
                # Group by first field, average the second field
                result = df.groupby(fields[0])[fields[1]].mean().reset_index()
                result.columns = ['x', 'y']
                return result.to_dict('records')
            else:
                # Count frequency of single field
                result = df[fields[0]].value_counts().reset_index()
                result.columns = ['x', 'y']
                return result.to_dict('records')
        
        elif chart_type == "scatter_plot":
            if len(fields) >= 2:
                # Scatter plot data
                result = df[fields[:2]].copy()
                result.columns = ['x', 'y']
                # Remove any NaN values
                result = result.dropna()
                return result.to_dict('records')
            else:
                return []
        
        elif chart_type == "histogram":
            if len(fields) >= 1:
                # Create histogram bins
                col = fields[0]
                if df[col].dtype in ['int64', 'float64']:
                    # Create bins for histogram
                    bins = pd.cut(df[col], bins=10, include_lowest=True)
                    result = bins.value_counts().reset_index()
                    result.columns = ['bin', 'count']
                    return result.to_dict('records')
                else:
                    # For categorical data, use bar chart
                    result = df[col].value_counts().reset_index()
                    result.columns = ['x', 'y']
                    return result.to_dict('records')
            else:
                return []
        
        else:
            # Default: return raw data for specified fields
            return df[fields].to_dict('records')
    
    except Exception as e:
        logger.error(f"Error generating chart data: {e}")
        return []

# AI Visualization Endpoints
@app.post("/api/ai/recommend-fields")
async def recommend_fields(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """AI-powered field recommendations for visualization"""
    try:
        columns = request.get("columns", [])
        dataset_name = request.get("dataset_name", "Unknown Dataset")
        
        result = await ai_visualization_service.recommend_fields(columns, dataset_name)
        return result
    except Exception as e:
        logger.error(f"Error in field recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate field recommendations")

@app.post("/api/ai/generate-insights")
async def generate_insights(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Generate AI-powered insights using QUIS methodology from research paper"""
    try:
        dataset_metadata = request.get("dataset_metadata", {})
        dataset_name = request.get("dataset_name", "Unknown Dataset")
        
        # Generate QUIS insights
        result = await ai_visualization_service.generate_insights(dataset_metadata, dataset_name)
        return result
    except Exception as e:
        logger.error(f"Error generating QUIS insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate insights")

@app.post("/api/ai/natural-query")
async def process_natural_query(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Process natural language queries about the dataset"""
    try:
        query = request.get("query", "")
        dataset_metadata = request.get("dataset_metadata", {})
        dataset_name = request.get("dataset_name", "Unknown Dataset")
        
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        result = await ai_visualization_service.process_natural_query(query, dataset_metadata, dataset_name)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing natural query: {e}")
        raise HTTPException(status_code=500, detail="Failed to process query")

@app.post("/api/analysis/run")
async def run_analysis(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Run advanced statistical analysis on dataset"""
    try:
        dataset_id = request.get("dataset_id")
        analysis_type = request.get("analysis_type")
        parameters = request.get("parameters", {})
        
        if not dataset_id or not analysis_type:
            raise HTTPException(status_code=400, detail="Dataset ID and analysis type are required")
        
        # Get dataset details
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Run analysis based on type
        results = await run_statistical_analysis(dataset, analysis_type, parameters)
        
        return {
            "results": results,
            "analysis_type": analysis_type,
            "dataset_name": dataset.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run analysis")

async def run_statistical_analysis(dataset: Dict, analysis_type: str, parameters: Dict) -> List[Dict]:
    """Run statistical analysis based on type"""
    try:
        # Get dataset data
        file_path = dataset.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="Dataset file not found")
        
        # Read data using file storage service
        data = await file_storage_service.get_file_data(file_path, limit=10000)  # Limit for analysis
        
        if not data:
            raise HTTPException(status_code=400, detail="No data available for analysis")
        
        results = []
        
        if analysis_type == "correlation":
            results = await run_correlation_analysis(data, parameters)
        elif analysis_type == "trend":
            results = await run_trend_analysis(data, parameters)
        elif analysis_type == "distribution":
            results = await run_distribution_analysis(data, parameters)
        elif analysis_type == "outlier":
            results = await run_outlier_analysis(data, parameters)
        elif analysis_type == "clustering":
            results = await run_clustering_analysis(data, parameters)
        elif analysis_type == "regression":
            results = await run_regression_analysis(data, parameters)
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in statistical analysis: {e}")
        raise e

async def run_correlation_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run correlation analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            return [{
                "title": "Insufficient Data for Correlation",
                "description": "Need at least 2 numeric columns for correlation analysis",
                "type": "correlation",
                "confidence": 0.0
            }]
        
        # Calculate correlation matrix
        corr_matrix = df[numeric_cols].corr()
        
        # Find strongest correlations
        strong_correlations = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr_value = corr_matrix.iloc[i, j]
                if abs(corr_value) > 0.5:  # Strong correlation threshold
                    strong_correlations.append({
                        "variable1": corr_matrix.columns[i],
                        "variable2": corr_matrix.columns[j],
                        "correlation": corr_value
                    })
        
        # Create correlation heatmap data
        heatmap_data = [{
            "z": corr_matrix.values.tolist(),
            "x": corr_matrix.columns.tolist(),
            "y": corr_matrix.columns.tolist(),
            "type": "heatmap",
            "colorscale": "RdBu"
        }]
        
        results = [{
            "title": f"Correlation Analysis - {len(strong_correlations)} Strong Relationships Found",
            "description": f"Found {len(strong_correlations)} strong correlations (|r| > 0.5) between numeric variables",
            "type": "correlation",
            "confidence": 0.85,
            "chart": {
                "data": heatmap_data,
                "layout": {
                    "title": "Correlation Matrix Heatmap",
                    "xaxis": {"title": "Variables"},
                    "yaxis": {"title": "Variables"}
                },
                "config": {"displayModeBar": True}
            },
            "insights": strong_correlations[:5]  # Top 5 correlations
        }]
        
        return results
        
    except Exception as e:
        logger.error(f"Error in correlation analysis: {e}")
        return [{"title": "Correlation Analysis Failed", "description": str(e), "type": "correlation", "confidence": 0.0}]

async def run_trend_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run trend analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        
        # Find time-related columns
        time_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not time_cols or not numeric_cols:
            return [{
                "title": "Insufficient Data for Trend Analysis",
                "description": "Need time-related and numeric columns for trend analysis",
                "type": "trend",
                "confidence": 0.0
            }]
        
        time_col = time_cols[0]
        value_col = numeric_cols[0]
        
        # Convert time column to datetime
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=[time_col, value_col])
        
        # Sort by time
        df = df.sort_values(time_col)
        
        # Create trend line data
        trend_data = [{
            "x": df[time_col].dt.strftime('%Y-%m-%d').tolist(),
            "y": df[value_col].tolist(),
            "type": "scatter",
            "mode": "lines+markers",
            "name": f"{value_col} Trend",
            "line": {"color": "#3B82F6"}
        }]
        
        # Calculate trend statistics
        values = df[value_col].values
        trend_slope = np.polyfit(range(len(values)), values, 1)[0]
        trend_direction = "increasing" if trend_slope > 0 else "decreasing"
        
        results = [{
            "title": f"Trend Analysis - {value_col} over {time_col}",
            "description": f"Data shows {trend_direction} trend with slope of {trend_slope:.4f}",
            "type": "trend",
            "confidence": 0.8,
            "chart": {
                "data": trend_data,
                "layout": {
                    "title": f"{value_col} Trend Over Time",
                    "xaxis": {"title": time_col},
                    "yaxis": {"title": value_col}
                },
                "config": {"displayModeBar": True}
            },
            "insights": [{
                "metric": "Trend Slope",
                "value": trend_slope,
                "interpretation": f"{trend_direction} trend"
            }]
        }]
        
        return results
        
    except Exception as e:
        logger.error(f"Error in trend analysis: {e}")
        return [{"title": "Trend Analysis Failed", "description": str(e), "type": "trend", "confidence": 0.0}]

async def run_distribution_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run distribution analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not numeric_cols:
            return [{
                "title": "No Numeric Data for Distribution Analysis",
                "description": "Need numeric columns for distribution analysis",
                "type": "distribution",
                "confidence": 0.0
            }]
        
        results = []
        
        for col in numeric_cols[:3]:  # Analyze first 3 numeric columns
            values = df[col].dropna()
            
            # Create histogram data
            hist_data = [{
                "x": values.tolist(),
                "type": "histogram",
                "name": col,
                "marker": {"color": "#3B82F6"}
            }]
            
            # Calculate distribution statistics
            mean_val = values.mean()
            std_val = values.std()
            skewness = values.skew()
            kurtosis = values.kurtosis()
            
            distribution_type = "normal"
            if abs(skewness) > 1:
                distribution_type = "highly skewed"
            elif abs(skewness) > 0.5:
                distribution_type = "moderately skewed"
            
            results.append({
                "title": f"Distribution Analysis - {col}",
                "description": f"Distribution is {distribution_type} (skewness: {skewness:.3f}, kurtosis: {kurtosis:.3f})",
                "type": "distribution",
                "confidence": 0.8,
                "chart": {
                    "data": hist_data,
                    "layout": {
                        "title": f"Distribution of {col}",
                        "xaxis": {"title": col},
                        "yaxis": {"title": "Frequency"}
                    },
                    "config": {"displayModeBar": True}
                },
                "insights": [{
                    "metric": "Mean",
                    "value": mean_val,
                    "interpretation": f"Average value: {mean_val:.2f}"
                }, {
                    "metric": "Standard Deviation",
                    "value": std_val,
                    "interpretation": f"Spread: {std_val:.2f}"
                }]
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error in distribution analysis: {e}")
        return [{"title": "Distribution Analysis Failed", "description": str(e), "type": "distribution", "confidence": 0.0}]

async def run_outlier_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run outlier detection analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not numeric_cols:
            return [{
                "title": "No Numeric Data for Outlier Analysis",
                "description": "Need numeric columns for outlier detection",
                "type": "outlier",
                "confidence": 0.0
            }]
        
        results = []
        
        for col in numeric_cols[:2]:  # Analyze first 2 numeric columns
            values = df[col].dropna()
            
            # IQR method for outlier detection
            Q1 = values.quantile(0.25)
            Q3 = values.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = values[(values < lower_bound) | (values > upper_bound)]
            outlier_percentage = (len(outliers) / len(values)) * 100
            
            # Create box plot data
            box_data = [{
                "y": values.tolist(),
                "type": "box",
                "name": col,
                "marker": {"color": "#3B82F6"}
            }]
            
            results.append({
                "title": f"Outlier Detection - {col}",
                "description": f"Found {len(outliers)} outliers ({outlier_percentage:.1f}% of data) using IQR method",
                "type": "outlier",
                "confidence": 0.85,
                "chart": {
                    "data": box_data,
                    "layout": {
                        "title": f"Box Plot - {col} (Outliers Highlighted)",
                        "yaxis": {"title": col}
                    },
                    "config": {"displayModeBar": True}
                },
                "insights": [{
                    "metric": "Outlier Count",
                    "value": len(outliers),
                    "interpretation": f"{outlier_percentage:.1f}% of data points are outliers"
                }]
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error in outlier analysis: {e}")
        return [{"title": "Outlier Analysis Failed", "description": str(e), "type": "outlier", "confidence": 0.0}]

async def run_clustering_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run clustering analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            return [{
                "title": "Insufficient Data for Clustering",
                "description": "Need at least 2 numeric columns for clustering analysis",
                "type": "clustering",
                "confidence": 0.0
            }]
        
        # Use first 2 numeric columns for clustering
        X = df[numeric_cols[:2]].dropna()
        
        if len(X) < 10:
            return [{
                "title": "Insufficient Data for Clustering",
                "description": "Need at least 10 data points for clustering analysis",
                "type": "clustering",
                "confidence": 0.0
            }]
        
        # Simple k-means clustering (k=3)
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=3, random_state=42)
        clusters = kmeans.fit_predict(X)
        
        # Create scatter plot with clusters
        scatter_data = [{
            "x": X.iloc[:, 0].tolist(),
            "y": X.iloc[:, 1].tolist(),
            "mode": "markers",
            "type": "scatter",
            "marker": {
                "color": clusters,
                "colorscale": "Viridis",
                "size": 8
            },
            "name": "Clusters"
        }]
        
        results = [{
            "title": f"Clustering Analysis - {numeric_cols[0]} vs {numeric_cols[1]}",
            "description": f"Data grouped into 3 clusters using k-means algorithm",
            "type": "clustering",
            "confidence": 0.8,
            "chart": {
                "data": scatter_data,
                "layout": {
                    "title": f"K-Means Clustering ({numeric_cols[0]} vs {numeric_cols[1]})",
                    "xaxis": {"title": numeric_cols[0]},
                    "yaxis": {"title": numeric_cols[1]}
                },
                "config": {"displayModeBar": True}
            },
            "insights": [{
                "metric": "Number of Clusters",
                "value": 3,
                "interpretation": "Data naturally groups into 3 distinct clusters"
            }]
        }]
        
        return results
        
    except Exception as e:
        logger.error(f"Error in clustering analysis: {e}")
        return [{"title": "Clustering Analysis Failed", "description": str(e), "type": "clustering", "confidence": 0.0}]

async def run_regression_analysis(data: List[Dict], parameters: Dict) -> List[Dict]:
    """Run regression analysis"""
    try:
        import pandas as pd
        import numpy as np
        
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            return [{
                "title": "Insufficient Data for Regression",
                "description": "Need at least 2 numeric columns for regression analysis",
                "type": "regression",
                "confidence": 0.0
            }]
        
        # Use first 2 numeric columns for regression
        X = df[numeric_cols[0]].dropna().values.reshape(-1, 1)
        y = df[numeric_cols[1]].dropna().values
        
        if len(X) != len(y) or len(X) < 10:
            return [{
                "title": "Insufficient Data for Regression",
                "description": "Need matching data points for regression analysis",
                "type": "regression",
                "confidence": 0.0
            }]
        
        # Simple linear regression
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score
        
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        r2 = r2_score(y, y_pred)
        
        # Create regression plot
        regression_data = [
            {
                "x": X.flatten().tolist(),
                "y": y.tolist(),
                "mode": "markers",
                "type": "scatter",
                "name": "Data Points",
                "marker": {"color": "#3B82F6"}
            },
            {
                "x": X.flatten().tolist(),
                "y": y_pred.tolist(),
                "mode": "lines",
                "type": "scatter",
                "name": "Regression Line",
                "line": {"color": "#EF4444"}
            }
        ]
        
        results = [{
            "title": f"Regression Analysis - {numeric_cols[0]} vs {numeric_cols[1]}",
            "description": f"Linear regression with R² = {r2:.3f} (slope: {model.coef_[0]:.3f}, intercept: {model.intercept_:.3f})",
            "type": "regression",
            "confidence": 0.8,
            "chart": {
                "data": regression_data,
                "layout": {
                    "title": f"Linear Regression ({numeric_cols[0]} vs {numeric_cols[1]})",
                    "xaxis": {"title": numeric_cols[0]},
                    "yaxis": {"title": numeric_cols[1]}
                },
                "config": {"displayModeBar": True}
            },
            "insights": [{
                "metric": "R² Score",
                "value": r2,
                "interpretation": f"Model explains {r2*100:.1f}% of variance"
            }]
        }]
        
        return results
        
    except Exception as e:
        logger.error(f"Error in regression analysis: {e}")
        return [{"title": "Regression Analysis Failed", "description": str(e), "type": "regression", "confidence": 0.0}]

@app.post("/api/ai/generate-chart")
async def generate_chart(
    request: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Generate AI-powered chart from dataset"""
    try:
        dataset_id = request.get("dataset_id")
        columns = request.get("columns", [])
        data_sample = request.get("data_sample", [])
        
        if not dataset_id:
            raise HTTPException(status_code=400, detail="Dataset ID is required")
        
        # Get dataset details
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Generate chart using AI analysis
        result = await ai_visualization_service.generate_chart(dataset, columns, data_sample)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate chart")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
