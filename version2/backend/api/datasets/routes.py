import logging
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)
from celery.result import AsyncResult
from bson import ObjectId

from db.schemas import DrillDownRequest
from db.database import get_database
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from workers.tasks import celery_app, process_dataset_task
from core.rate_limiter import limiter, RateLimits
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
@limiter.limit(RateLimits.DATASET_UPLOAD)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    return await enhanced_dataset_service.upload_dataset(
        file=file,
        name=name,
        description=description,
        user_id=current_user["id"],
    )


@router.get("")
@limiter.limit(RateLimits.DATASET_LIST)
async def list_datasets(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    current_user: dict = Depends(get_current_user),
):
    return await enhanced_dataset_service.list_datasets(
        user_id=current_user["id"],
        page=page,
        limit=limit,
        search=search,
    )


@router.get("/{dataset_id}")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.delete("/{dataset_id}")
@limiter.limit(RateLimits.DATASET_DELETE)
async def delete_dataset(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    await enhanced_dataset_service.delete_dataset(dataset_id, current_user["id"])
    return {"message": "Dataset deleted successfully"}


@router.get("/{dataset_id}/columns")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_columns(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        dataset = await enhanced_dataset_service.get_dataset(
            dataset_id, current_user["id"]
        )
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        columns = []
        for col_meta in dataset.get("columns", []):
            col_type = col_meta.get("type", "unknown")
            is_numeric = (
                "int" in col_type.lower()
                or "float" in col_type.lower()
                or "number" in col_type.lower()
            )
            is_categorical = (
                "object" in col_type.lower()
                or "string" in col_type.lower()
                or "utf8" in col_type.lower()
                or "categorical" in col_type.lower()
            )
            is_temporal = "date" in col_type.lower()

            columns.append(
                {
                    "name": col_meta.get("name"),
                    "type": col_type,
                    "is_numeric": is_numeric,
                    "is_categorical": is_categorical,
                    "is_temporal": is_temporal,
                }
            )

        return {
            "success": True,
            "columns": columns,
            "dataset_info": {
                "name": dataset.get("name"),
                "row_count": dataset.get("row_count"),
                "column_count": dataset.get("column_count"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset columns for {dataset_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve dataset columns."
        )


@router.post("/{dataset_id}/reprocess")
@limiter.limit(RateLimits.DATASET_REPROCESS)
async def reprocess_dataset(
    request: Request, dataset_id: str, current_user: dict = Depends(get_current_user)
):
    try:
        dataset = await enhanced_dataset_service.get_dataset(
            dataset_id, current_user["id"]
        )

        db = get_database()
        if db is not None:
            try:
                try:
                    query = {"_id": ObjectId(dataset_id), "user_id": current_user["id"]}
                except Exception:
                    query = {"_id": dataset_id, "user_id": current_user["id"]}
                await db.uploads.update_one(
                    query,
                    {
                        "$set": {
                            "artifact_status.insights_report": "pending",
                            "artifact_status.dashboard_design": "pending",
                        },
                        "$unset": {
                            "precomputed_insights_report": "",
                        },
                    },
                )
            except Exception as artifact_error:
                logger.warning(
                    f"Failed to reset artifact status for dataset {dataset_id}: {artifact_error}"
                )

        task = process_dataset_task.delay(
            dataset_id, dataset["file_path"], current_user["id"]
        )

        return {
            "message": "Dataset reprocessing has been initiated.",
            "task_id": task.id,
            "dataset_id": dataset_id,
            "cache_invalidated": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to start dataset reprocessing."
        )


@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    task_result = AsyncResult(task_id, app=celery_app)

    response = {"task_id": task_id, "state": task_result.state, "info": {}}

    if task_result.state == "PROGRESS":
        response["info"] = task_result.info
    elif task_result.state == "SUCCESS":
        response["info"] = task_result.result
    elif task_result.state == "FAILURE":
        info = task_result.info
        error_message = str(info) if info else "An unknown error occurred."
        response["info"] = {"error": error_message}

    return response
