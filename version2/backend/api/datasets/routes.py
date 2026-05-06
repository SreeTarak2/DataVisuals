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
from workers import celery_app
from workers.pipeline.dataset import process_dataset_task
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
@router.get("/")
@limiter.limit(RateLimits.DATASET_LIST)
async def list_datasets(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    skip = (page - 1) * limit
    datasets = await enhanced_dataset_service.get_user_datasets(
        user_id=current_user["id"],
        skip=skip,
        limit=limit,
    )
    return {"datasets": datasets}


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


@router.get("/{dataset_id}/data")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_data(
    request: Request,
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
    current_user: dict = Depends(get_current_user),
):
    """Return paginated dataset rows for dashboard and preview consumers."""
    result = await enhanced_dataset_service.get_dataset_data(
        dataset_id=dataset_id,
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
    )
    return {
        "data": result.get("data", []),
        "total_count": result.get("total_rows", 0),
        "total_rows": result.get("total_rows", 0),
        "current_page": result.get("current_page", page),
        "page_size": result.get("page_size", page_size),
        "has_more": result.get("has_more", False),
    }


@router.get("/{dataset_id}/preview")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_preview(
    request: Request,
    dataset_id: str,
    limit: int = Query(200, ge=1, le=2000),
    current_user: dict = Depends(get_current_user),
):
    """Return a small row sample and inferred columns for fast table preview."""
    result = await enhanced_dataset_service.get_dataset_data(
        dataset_id=dataset_id,
        user_id=current_user["id"],
        page=1,
        page_size=limit,
    )

    rows = result.get("data", [])
    columns = list(rows[0].keys()) if rows else []

    if not columns:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
        column_meta = dataset.get("metadata", {}).get("column_metadata", [])
        columns = [c.get("name") for c in column_meta if c.get("name")]

    return {
        "rows": rows,
        "columns": columns,
        "total_rows": result.get("total_rows", len(rows)),
        "limit": limit,
    }


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


@router.get("/{dataset_id}/kpis")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_kpis(
    request: Request,
    dataset_id: str,
    refresh: bool = Query(False, description="Force regeneration even if cached"),
    current_user: dict = Depends(get_current_user),
):
    """
    Return intelligent, data-science-grade KPI cards for a dataset.

    Priority:
      1. Cache hit  — pre-computed during upload, served instantly
      2. On-demand  — generate now from dataset metadata + Polars DataFrame
    """
    from services.cache.dashboard_cache_service import dashboard_cache_service

    user_id = current_user["id"]

    # ── 1. Cache check ────────────────────────────────────────────────────────
    if not refresh:
        try:
            cached = await dashboard_cache_service.get_cached_kpis(dataset_id, user_id)
            if cached:
                kpis = cached if isinstance(cached, list) else cached.get("kpis", [])
                if kpis:
                    return {"kpis": kpis, "source": "cache", "dataset_id": dataset_id}
        except Exception as e:
            logger.warning(f"[KPI] Cache read failed for {dataset_id}: {e}")

    # ── 2. Fetch dataset metadata ─────────────────────────────────────────────
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.get("is_processed"):
        raise HTTPException(status_code=202, detail="Dataset still processing — try again shortly")

    meta = dataset.get("metadata", {})

    # ── 3. Load DataFrame from file ───────────────────────────────────────────
    try:
        import polars as pl
        file_path = dataset.get("file_path", "")
        if not file_path:
            raise HTTPException(status_code=422, detail="Dataset file path not found")

        ext = file_path.rsplit(".", 1)[-1].lower()
        if ext == "csv":
            df = pl.read_csv(file_path, infer_schema_length=5000, ignore_errors=True)
        elif ext in ("xlsx", "xls"):
            df = pl.read_excel(file_path)
        elif ext == "parquet":
            df = pl.read_parquet(file_path)
        elif ext == "json":
            df = pl.read_json(file_path)
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported file format: {ext}")

        if df.is_empty():
            raise HTTPException(status_code=422, detail="Dataset is empty")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[KPI] Failed to load DataFrame for {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dataset for KPI computation")

    # ── 4. Generate KPIs ──────────────────────────────────────────────────────
    try:
        from services.ai.intelligent_kpi_generator import intelligent_kpi_generator

        domain = (
            meta.get("domain_intelligence", {}).get("domain")
            or dataset.get("domain", "general")
        )

        kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
            df=df,
            domain=domain,
            max_kpis=4,
            dataset_metadata=meta,
        )

        # Persist to cache so subsequent requests are instant
        if kpis:
            try:
                await dashboard_cache_service.cache_kpis(dataset_id, user_id, kpis)
            except Exception as cache_err:
                logger.warning(f"[KPI] Cache write failed: {cache_err}")

        return {"kpis": kpis, "source": "generated", "dataset_id": dataset_id}

    except Exception as e:
        logger.error(f"[KPI] Generation failed for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="KPI generation failed")


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
