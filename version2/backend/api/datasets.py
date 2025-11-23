# backend/api/datasets.py

import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status
from celery.result import AsyncResult

# --- Application Modules ---
from db.schemas import DrillDownRequest
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.dynamic_drilldown_service import drilldown_service
from tasks import celery_app, process_dataset_task # Import Celery app and specific task

# --- Configuration ---
logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dataset Management Endpoints ---

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Handles the upload of a new dataset.
    This endpoint validates the file, saves it, and triggers a background
    processing task via Celery.
    """
    return await enhanced_dataset_service.upload_dataset(
        file, current_user["id"], name, description
    )

@router.get("/")
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """
    Lists all datasets belonging to the current authenticated user with pagination.
    """
    datasets = await enhanced_dataset_service.get_user_datasets(
        current_user["id"], skip, limit
    )
    return {"datasets": datasets}

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """
    Retrieves detailed information and metadata for a single dataset.
    """
    return await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])

@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """
    Permanently deletes a dataset, its associated file, and any related data.
    """
    await enhanced_dataset_service.delete_dataset(dataset_id, current_user["id"])
    return {"message": "Dataset deleted successfully"}

@router.get("/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """
    Fetches paginated data rows from a specific dataset file.
    """
    return await enhanced_dataset_service.get_dataset_data(
        dataset_id, current_user["id"], page, page_size
    )

@router.get("/{dataset_id}/preview")
async def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    Provides a small preview of the dataset (first few rows).
    """
    result = await enhanced_dataset_service.get_dataset_data(
        dataset_id, current_user["id"], page=1, page_size=limit
    )
    return {
        "success": True,
        "rows": result.get("data", []),
        "limit": limit
    }

@router.get("/{dataset_id}/columns")
async def get_dataset_columns(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **REFACTORED ENDPOINT**
    Efficiently gets dataset columns and their types directly from the stored
    metadata, avoiding the need to read the file again.
    """
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Check if the dataset has been processed and has metadata
        if not dataset.get("is_processed") or not dataset.get("metadata"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dataset is still processing or has no metadata. Please wait and try again."
            )
        
        column_metadata = dataset.get("metadata", {}).get("column_metadata", [])
        
        if not column_metadata:
            raise HTTPException(status_code=404, detail="Column metadata not found.")
            
        # Format the response to match the frontend's expected structure
        columns = []
        for col_meta in column_metadata:
            col_type = col_meta.get("type", "unknown")
            is_numeric = "int" in col_type.lower() or "float" in col_type.lower()
            is_categorical = "str" in col_type.lower() or "utf8" in col_type.lower() or "categorical" in col_type.lower()
            is_temporal = "date" in col_type.lower()
            
            columns.append({
                "name": col_meta.get("name"),
                "type": col_type,
                "is_numeric": is_numeric,
                "is_categorical": is_categorical,
                "is_temporal": is_temporal,
            })

        return {
            "success": True,
            "columns": columns,
            "dataset_info": {
                "name": dataset.get("name"),
                "row_count": dataset.get("row_count"),
                "column_count": dataset.get("column_count")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset columns for {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset columns.")


# --- Dataset Processing and Task Management ---

@router.post("/{dataset_id}/reprocess")
async def reprocess_dataset(dataset_id: str, current_user: dict = Depends(get_current_user)):
    """
    Triggers a background task to re-process a dataset, regenerating its metadata.
    """
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        
        # Dispatch the same processing task used for uploads
        task = process_dataset_task.delay(dataset_id, dataset["file_path"])
        
        return {
            "message": "Dataset reprocessing has been initiated.",
            "task_id": task.id,
            "dataset_id": dataset_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start dataset reprocessing.")

@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """
    Polls the status of a Celery background task (e.g., dataset processing).
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "state": task_result.state,
        "info": {}
    }

    if task_result.state == 'PROGRESS':
        response["info"] = task_result.info
    elif task_result.state == 'SUCCESS':
        response["info"] = task_result.result
    elif task_result.state == 'FAILURE':
        # Ensure the error information is serializable
        info = task_result.info
        error_message = str(info) if info else "An unknown error occurred."
        response["info"] = {'error': error_message}
        
    return response

# --- Drill-Down Endpoints ---
# (Logically related to interacting with a dataset's content)

@router.post("/{dataset_id}/drill-down")
async def drill_down(
    dataset_id: str,
    request: DrillDownRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Executes a drill-down operation on a dataset based on a specified hierarchy.
    """
    # Note: page_size is set high to fetch all data for in-memory drill-down.
    # For very large datasets, this could be refactored to perform drill-downs
    # with lazy Polars DataFrames or directly in a database.
    dataset = await enhanced_dataset_service.get_dataset_data(
        dataset_id, current_user["id"], page=1, page_size=50000 
    )
    
    return await drilldown_service.execute_drilldown(
        dataset_data=dataset.get("data", []),
        hierarchy=request.hierarchy,
        current_level=request.current_level,
        filters=request.filters
    )