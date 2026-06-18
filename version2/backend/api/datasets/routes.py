import asyncio
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
import uuid
from datetime import datetime
from bson import ObjectId

from db.schemas import DrillDownRequest
from db.database import get_database
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.datasets.file_storage_service import file_storage_service
from core.rate_limiter import limiter, RateLimits
from core.config import settings

from services.knowledge_graph.entity_discovery import entity_discovery
from services.knowledge_graph.primary_object_discovery import primary_object_discovery
from services.knowledge_graph.participation_discovery import participation_discovery
from services.knowledge_graph.reference_signal_detector import reference_signal_detector
from services.knowledge_graph.models import ColumnProfile

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Concurrency guards ────────────────────────────────────────────────────────
# Prevents simultaneous KPI/file I/O for the same dataset_id
_kpi_file_locks: dict[str, asyncio.Lock] = {}
_kpi_file_lock = asyncio.Lock()  # Protects the _kpi_file_locks dict itself


async def _get_kpi_lock(dataset_id: str) -> asyncio.Lock:
    """Get or create a per-dataset lock for KPI file reads."""
    async with _kpi_file_lock:
        if dataset_id not in _kpi_file_locks:
            _kpi_file_locks[dataset_id] = asyncio.Lock()
        return _kpi_file_locks[dataset_id]


# ── Shared Google Sheets helpers ────────────────────────────────────────────

import hashlib as _hashlib
import httpx as _httpx
import re as _re
import tempfile as _tempfile
import os as _os
from pathlib import Path as _Path


async def _download_google_sheet(url: str) -> tuple[str, str, bytes]:
    """
    Download a Google Sheet as CSV and return ``(sheet_id, export_url, content)``.

    Raises ``HTTPException`` with descriptive messages for:
    - Empty or missing URL
    - Invalid sheet ID format
    - Sheet not found (404)
    - Sheet requires authentication (302 redirect → non-CSV content)
    - Network errors
    - Content exceeds ``MAX_FILE_SIZE``
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    match = _re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google Sheets URL. Make sure it contains a valid sheet ID.",
        )

    sheet_id = match.group(1)
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

    try:
        async with _httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(export_url)

            # Detect auth walls: Google returns an HTML login page
            # (content-type: text/html) instead of CSV data
            content_type = response.headers.get("content-type", "")
            if response.status_code == 200 and "text/html" in content_type:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Sheet '{sheet_id[:8]}...' requires authentication. "
                        f"Make it publicly accessible (Share → 'Anyone with the link' → Viewer) "
                        f"or implement OAuth for private sheets."
                    ),
                )

            response.raise_for_status()
            content = response.content

            # Validate content is non-empty
            if not content or len(content.strip()) == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Google Sheet '{sheet_id[:8]}...' is empty. Add at least one row of data.",
                )

            # Validate file size against MAX_FILE_SIZE
            max_size = settings.MAX_FILE_SIZE
            if len(content) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Google Sheet exceeds maximum file size of {max_size // (1024 * 1024)}MB. "
                    f"Try importing a subset of the data.",
                )

            return sheet_id, export_url, content

    except _httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"Google Sheet '{sheet_id[:8]}...' not found. Check the URL and try again.",
            )
        logger.error(f"Google Sheets HTTP {e.response.status_code} for {export_url}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not access the Google Sheet. Make sure it is publicly accessible or shared with 'Anyone with the link'.",
        )
    except _httpx.RequestError as e:
        logger.error(f"Google Sheets request failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Google Sheets. Check the URL and network connectivity.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google Sheet download failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to download Google Sheet.")


async def _save_google_sheet_content(
    content: bytes,
    sheet_id: str,
    user_id: str,
) -> tuple[str, dict]:
    """
    Save downloaded Google Sheet CSV content to permanent storage.

    Returns ``(file_metadata_dict, content_hash)``.
    """
    content_hash = _hashlib.sha256(content).hexdigest()

    temp_fd, temp_path = _tempfile.mkstemp(suffix=".csv")
    try:
        with _os.fdopen(temp_fd, "wb") as f:
            f.write(content)

        file_metadata = await file_storage_service.save_file_from_path(
            temp_path,
            f"google-sheet-{sheet_id}.csv",
            user_id,
        )
        return file_metadata, content_hash
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save Google Sheet data: {e}")
        raise HTTPException(status_code=500, detail="Failed to save imported sheet data.")
    finally:
        if _Path(temp_path).exists():
            try:
                _Path(temp_path).unlink()
            except Exception:
                pass


async def _create_gsheet_dataset_doc(
    dataset_id: str,
    user_id: str,
    sheet_id: str,
    sheet_url: str,
    file_metadata: dict,
    content_hash: str,
    custom_name: str | None = None,
) -> str:
    """Create a MongoDB dataset document for a Google Sheet import and fire processing."""
    db = get_database()

    dataset_doc = {
        "_id": dataset_id,
        "user_id": user_id,
        "name": custom_name or f"Google Sheet ({sheet_id[:8]}...)",
        "description": f"Imported from Google Sheets: {sheet_url}",
        "source_type": "google_sheets",
        "sheet_url": sheet_url,
        "sheet_id": sheet_id,
        "file_id": file_metadata["file_id"],
        "file_path": file_metadata["file_path"],
        "file_size": file_metadata["file_size"],
        "file_extension": "csv",
        "content_hash": content_hash,
        "original_filename": f"google-sheet-{sheet_id}.csv",
        "upload_date": datetime.utcnow(),
        "is_processed": False,
        "is_active": True,
        "processing_status": "pending",
        "artifact_status": {
            "insights_report": "pending",
            "dashboard_design": "pending",
        },
        "metadata": {},
    }

    await db.uploads.insert_one(dataset_doc)

    from services.pipeline.process import process_dataset

    asyncio.create_task(
        process_dataset(dataset_id, file_metadata["file_path"], user_id)
    )

    return dataset_id


@router.post("/import-gsheet")
@limiter.limit(RateLimits.DATASET_UPLOAD)
async def import_google_sheet(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Import a Google Sheet by URL.

    Downloads the sheet as CSV via Google's export endpoint, validates size
    and content, detects duplicates, and feeds it through the standard
    processing pipeline.
    """
    url = body.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # 1. Download and validate
    sheet_id, export_url, content = await _download_google_sheet(url)

    # 2. Save to permanent storage + compute content hash
    file_metadata, content_hash = await _save_google_sheet_content(
        content, sheet_id, current_user["id"]
    )

    # 3. Duplicate detection
    db = get_database()
    existing = await db.uploads.find_one(
        {
            "user_id": current_user["id"],
            "content_hash": content_hash,
            "is_active": True,
        }
    )
    if existing:
        logger.info(
            f"Duplicate Google Sheet detected for user {current_user['id']}: "
            f"existing dataset {existing['_id']}"
        )
        # Clean up the file we just saved (it's a duplicate)
        await file_storage_service.delete_file(file_metadata["file_path"])
        return {
            "success": True,
            "is_duplicate": True,
            "dataset_id": str(existing["_id"]),
            "message": "This Google Sheet has already been imported.",
        }

    # 4. Create dataset and fire pipeline
    dataset_id = str(uuid.uuid4())
    await _create_gsheet_dataset_doc(
        dataset_id=dataset_id,
        user_id=current_user["id"],
        sheet_id=sheet_id,
        sheet_url=url,
        file_metadata=file_metadata,
        content_hash=content_hash,
        custom_name=body.get("name"),
    )

    logger.info(f"Google Sheet {sheet_id} imported as dataset {dataset_id}")

    return {
        "success": True,
        "is_duplicate": False,
        "dataset_id": dataset_id,
        "task_id": dataset_id,
        "message": "Google Sheet imported. Processing has started.",
    }


@router.post("/{dataset_id}/reimport-gsheet")
@limiter.limit(RateLimits.DATASET_UPLOAD)
async def reimport_google_sheet(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-import a Google Sheet dataset, refreshing its data in-place.

    Looks up the original sheet URL from the dataset record, re-downloads
    the CSV, replaces the stored file, and re-runs the processing pipeline.
    Uses the same validation pipeline as ``import_google_sheet``.
    """
    db = get_database()

    doc = await db.uploads.find_one({"_id": dataset_id, "user_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if doc.get("source_type") != "google_sheets":
        raise HTTPException(status_code=400, detail="Dataset is not a Google Sheets import")

    # Resolve the original sheet URL from the stored dataset record
    sheet_url = doc.get("sheet_url") or doc.get("metadata", {}).get("sheet_url")
    sheet_id = None

    if sheet_url:
        match = _re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", sheet_url)
        if match:
            sheet_id = match.group(1)

    # Fallback: extract from original_filename (for pre-URL-tracking imports)
    if not sheet_id:
        filename = doc.get("original_filename", "")
        file_match = _re.search(r"google-sheet-([a-zA-Z0-9_-]+)", filename)
        if file_match:
            sheet_id = file_match.group(1)

    if not sheet_id:
        raise HTTPException(
            status_code=400,
            detail="No original sheet URL or ID found. This dataset may have been imported before URL tracking was added.",
        )

    # Reconstruct URL for the helper if we only have the sheet_id
    if not sheet_url:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

    # 1. Download and validate (reuses shared helper)
    _, _, content = await _download_google_sheet(sheet_url)

    # 2. Save to permanent storage (replaces old file)
    file_metadata, content_hash = await _save_google_sheet_content(
        content, sheet_id, current_user["id"]
    )

    # 3. Update existing dataset record
    updated_at = datetime.utcnow()
    await db.uploads.update_one(
        {"_id": dataset_id},
        {
            "$set": {
                "file_id": file_metadata["file_id"],
                "file_path": file_metadata["file_path"],
                "file_size": file_metadata["file_size"],
                "content_hash": content_hash,
                "is_processed": False,
                "processing_status": "pending",
                "processing_progress": 0,
                "artifact_status": {
                    "insights_report": "pending",
                    "dashboard_design": "pending",
                },
                "updated_at": updated_at,
                "sheet_url": sheet_url,
                "sheet_id": sheet_id,
            }
        },
    )

    # 4. Fire background processing
    from services.pipeline.process import process_dataset

    asyncio.create_task(
        process_dataset(dataset_id, file_metadata["file_path"], current_user["id"])
    )

    logger.info(f"Google Sheet {sheet_id} re-imported for dataset {dataset_id}")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "task_id": dataset_id,
        "message": "Google Sheet refreshed. Processing has started.",
    }


@router.post("/upload")
@limiter.limit(RateLimits.DATASET_UPLOAD)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(None),
    description: str = Form(None),
    analysis_intent: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    return await enhanced_dataset_service.upload_dataset(
        file=file,
        name=name,
        description=description,
        analysis_intent=analysis_intent,
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
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
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
        raise HTTPException(status_code=500, detail="Failed to retrieve dataset columns.")


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
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])

        # ── Invalidate KPI cache before reprocessing ───────────────────────
        from services.cache.dashboard_cache_service import dashboard_cache_service

        try:
            await dashboard_cache_service.invalidate_cache(
                dataset_id, current_user["id"], cache_keys=["kpis"]
            )
            logger.info(f"[Reprocess] Invalidated KPI cache for dataset {dataset_id}")
        except Exception as cache_err:
            logger.warning(f"[Reprocess] Cache invalidation failed: {cache_err}")

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

        import asyncio as _asyncio
        from services.pipeline.process import process_dataset

        _asyncio.create_task(process_dataset(dataset_id, dataset["file_path"], current_user["id"]))

        return {
            "message": "Dataset reprocessing has been initiated.",
            "task_id": dataset_id,
            "dataset_id": dataset_id,
            "cache_invalidated": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start dataset reprocessing.")


@router.get("/{dataset_id}/stages")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_stages(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return per-stage execution history for a dataset's pipeline run.

    Stages are ordered by start time ascending. Each stage contains:
    - name (machine-readable key)
    - label (human-readable label)
    - status: running | done | failed
    - start_time / end_time (ISO 8601)
    - duration_ms
    - error (if failed)

    If no stages are found (e.g. legacy datasets), returns an empty list.
    """
    # Verify dataset ownership before exposing stage data
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    stages = (
        await db.pipeline_stages.find({"dataset_id": dataset_id})
        .sort("start_time", 1)
        .to_list(length=100)
    )

    # Clean ObjectIds for JSON serialization
    result = []
    for s in stages:
        result.append(
            {
                "name": s.get("name"),
                "label": s.get("label"),
                "status": s.get("status"),
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "duration_ms": s.get("duration_ms"),
                "error": s.get("error"),
            }
        )

    return {"stages": result}


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
      2. Smart migration — if cached KPIs lack new fields, regenerate once
      3. On-demand  — generate now from dataset metadata + Polars DataFrame
    """
    from services.cache.dashboard_cache_service import dashboard_cache_service

    user_id = current_user["id"]

    # Required fields that must be present in cached KPIs (added in KPI v2 upgrade)
    REQUIRED_KPI_FIELDS = {
        "period_label",
        "baseline_value",
        "vs_baseline_pct",
        "top_driver",
        "is_anomaly",
        "anomaly_direction",
        "z_score",
        "anomaly_severity",
        "expected_value",
        "trend_direction",
        "vs_previous_pct",
    }

    # ── 1. Cache check ────────────────────────────────────────────────────────
    if not refresh:
        try:
            cached = await dashboard_cache_service.get_cached_kpis(dataset_id, user_id)
            if cached:
                kpis = cached if isinstance(cached, list) else cached.get("kpis", [])
                if kpis:
                    # Smart migration: check if cached KPIs have all required fields
                    first_kpi = kpis[0] if kpis else {}
                    missing_fields = REQUIRED_KPI_FIELDS - set(first_kpi.keys())

                    if missing_fields:
                        logger.info(
                            f"[KPI] Cached KPIs for {dataset_id} missing fields: {missing_fields}. "
                            f"Regenerating once to migrate."
                        )
                        # Fall through to regeneration below
                    else:
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

    # ── 3. Generate KPIs (with per-dataset concurrency guard) ──────────────────
    #    File I/O and KPI computation happen under the same lock to prevent
    #    concurrent reads/writes to the same underlying dataset file.
    lock = await _get_kpi_lock(dataset_id)
    async with lock:
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
            raise HTTPException(
                status_code=500, detail="Failed to load dataset for KPI computation"
            )

        try:
            from services.ai.intelligent_kpi_generator import intelligent_kpi_generator

            domain = meta.get("domain_intelligence", {}).get("domain") or dataset.get(
                "domain", "general"
            )

            kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
                df=df,
                domain=domain,
                max_kpis=6,
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
@limiter.limit(RateLimits.DATASET_GET)
async def get_task_status(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get processing status for a dataset.

    The ``task_id`` parameter is actually the ``dataset_id`` — the upload
    endpoint returns ``task_id == dataset_id`` for backward compatibility
    with the frontend polling loop.
    """
    dataset = await enhanced_dataset_service.get_dataset(task_id, current_user["id"])
    if not dataset:
        return {"task_id": task_id, "state": "UNKNOWN", "info": {"error": "Dataset not found"}}

    processing_status = dataset.get("processing_status", "pending")
    processing_progress = dataset.get("processing_progress", 0)

    state_map = {
        "pending": "PENDING",
        "loading": "PROGRESS",
        "cleaning": "PROGRESS",
        "metadata": "PROGRESS",
        "domain_detection": "PROGRESS",
        "kpi_pipeline": "PROGRESS",
        "profiling": "PROGRESS",
        "analysis": "PROGRESS",
        "quis_analysis": "PROGRESS",
        "charts": "PROGRESS",
        "quality": "PROGRESS",
        "consolidating": "PROGRESS",
        "saving": "PROGRESS",
        "artifact_generation": "PROGRESS",
        "strategic_advisor": "PROGRESS",
        "vector_indexing": "PROGRESS",
        "completed": "SUCCESS",
        "success": "SUCCESS",
        "failed": "FAILURE",
    }

    response = {
        "task_id": task_id,
        "state": state_map.get(processing_status, "PENDING"),
        "info": {
            "status": processing_status,
            "progress": processing_progress,
        },
    }

    if processing_status == "failed":
        response["info"]["error"] = dataset.get("processing_error", "Processing failed")

    return response


# ─── User Layout Persistence ───────────────────────────────────────────────────


@router.get("/{dataset_id}/layout")
@limiter.limit(RateLimits.DATASET_GET)
async def get_user_layout(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get user's saved custom layout for a dataset."""
    db = get_database()
    dashboard = await db.dashboards.find_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True}
    )
    if not dashboard:
        return {"kpis": [], "charts": [], "added_components": []}

    user_layout = dashboard.get("user_layout", {})
    return {
        "kpis": user_layout.get("kpis", []),
        "charts": user_layout.get("charts", []),
        "added_components": user_layout.get("added_components", []),
    }


@router.post("/{dataset_id}/layout")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def save_user_layout(
    request: Request,
    dataset_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Save user's custom layout for a dataset."""
    db = get_database()

    user_layout = {
        "kpis": body.get("kpis", []),
        "charts": body.get("charts", []),
        "added_components": body.get("added_components", []),
    }

    await db.dashboards.update_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"$set": {"user_layout": user_layout}},
        upsert=False,
    )

    return {"success": True, "message": "Layout saved"}


@router.patch("/{dataset_id}/layout/priority")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def update_component_priority(
    request: Request,
    dataset_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Update priority level for a specific dashboard component.

    Body:
    {
        "component_id": "chart-key-123",
        "priority": "P1",  # P1, P2, P3, P4
        "reason": "User promoted to primary focus"
    }
    """
    db = get_database()

    component_id = body.get("component_id")
    priority = body.get("priority")
    reason = body.get("reason", "")

    if not component_id or not priority:
        raise HTTPException(status_code=400, detail="component_id and priority are required")

    if priority not in ("P1", "P2", "P3", "P4"):
        raise HTTPException(status_code=400, detail="priority must be P1, P2, P3, or P4")

    dashboard = await db.dashboards.find_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True}
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    user_layout = dashboard.get("user_layout", {})

    # Update priority in both kpis and charts arrays
    for section in ["kpis", "charts"]:
        items = user_layout.get(section, [])
        for item in items:
            if item.get("i") == component_id:
                item["priority"] = priority
                if reason:
                    item["priority_reason"] = reason

    await db.dashboards.update_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"$set": {"user_layout": user_layout}},
    )

    return {"success": True, "message": f"Component {component_id} priority updated to {priority}"}


@router.post("/{dataset_id}/layout/reset")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def reset_user_layout(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Reset user's custom layout, reverting to AI-generated default."""
    db = get_database()

    await db.dashboards.update_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"$unset": {"user_layout": ""}},
    )

    return {"success": True, "message": "Layout reset to AI default"}


@router.get("/{dataset_id}/profile")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_profile(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the unified deterministic profile for a dataset.

    This endpoint exposes the output of the new profiling/intelligence engines:
      - Column profiles with stats, cardinality, patterns, quality
      - Semantic classifications (role, behavioral role, business category)
      - Aggregation suitability (sum_allowed, avg_allowed, etc.)
      - Entities with counts
      - Geographic columns (lat/lng, country, state, city)
      - Hierarchies
      - Domain candidates with scores
      - Columns needing review (low confidence)

    All data is computed deterministically — no LLM calls.
    """
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    meta = dataset.get("metadata", {})
    unified_profile = meta.get("unified_profile")
    unified_intelligence = meta.get("unified_intelligence")

    if not unified_profile:
        # Profile hasn't been computed yet (e.g., legacy dataset or still processing)
        status = dataset.get("processing_status", "unknown")
        if status in ("pending", "processing"):
            raise HTTPException(
                status_code=202,
                detail="Dataset still processing — profile will be available after completion",
            )
        # Legacy dataset — profile doesn't exist
        return {
            "profile": None,
            "intelligence": None,
            "legacy": True,
            "message": "This dataset was processed before the unified profiling engine was added. Re-process to generate the profile.",
        }

    return {
        "profile": unified_profile,
        "intelligence": unified_intelligence,
        "legacy": False,
    }


@router.get("/{dataset_id}/understanding")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_understanding(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the Dataset Understanding Report — Signal's complete understanding
    of what a dataset is about, with evidence traceability.

    The report includes:
      - Primary object (what the dataset is "about")
      - Evidence strength and per-column contribution breakdown
      - Alternatives and ambiguity analysis
      - Participants (entities that participate in the primary object's domain)
      - Reference signals (FK-style relationships with cardinality)
      - Column coverage and quality summary

    This is the end result of the pipeline:
      Column Intelligence → Entity Discovery → Primary Object Discovery
      → Participation Discovery → Reference Signal Detection

    All computed deterministically — no LLM calls.
    """
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    meta = dataset.get("metadata", {})
    unified_profile = meta.get("unified_profile")

    if not unified_profile:
        status = dataset.get("processing_status", "unknown")
        if status in ("pending", "processing"):
            raise HTTPException(
                status_code=202,
                detail="Dataset still processing — understanding will be available after completion",
            )
        return {
            "understanding": None,
            "legacy": True,
            "message": "This dataset was processed before the profiling engine was added. Re-process to generate the understanding report.",
        }

    # ── 1. Build ColumnProfiles from unified profile ────────────────────────
    columns = unified_profile.get("columns", [])
    file_name = dataset.get("name") or dataset.get("file_name", "unknown")
    total_rows = dataset.get("row_count") or 0

    column_profiles: list[ColumnProfile] = []
    for col in columns:
        col_name = col.get("name", "unknown")
        col_dtype = col.get("dtype", "string")

        # Extract sample values from the profile if available
        sample_values: list[str] = []
        stats = col.get("stats") or {}
        cardinality = col.get("cardinality") or {}

        # Build sample values from stats where possible
        if "col_min" in stats and stats["col_min"] is not None:
            sample_values.append(str(stats["col_min"]))
        if "col_max" in stats and stats["col_max"] is not None:
            sample_values.append(str(stats["col_max"]))

        # Try to get sample values from intelligence if available
        intelligence = col.get("intelligence") or {}
        if not sample_values:
            intel_samples = intelligence.get("sample_values", [])
            if intel_samples:
                sample_values = [str(v) for v in intel_samples[:5]]

        distinct_count = cardinality.get("unique_count", 0)
        null_count = cardinality.get("null_count", 0)
        # cardinality_ratio is 0-1. Fall back to unique_pct for backward compat.
        distinct_ratio = (
            cardinality.get("cardinality_ratio")
            or (cardinality.get("unique_pct", 0) / 100.0)
            or 0.0
        )

        col_profile = ColumnProfile(
            name=col_name,
            data_type=col_dtype,
            distinct_count=distinct_count,
            distinct_ratio=distinct_ratio,
            sample_values=sample_values[:10],
            null_ratio=null_count / total_rows if total_rows > 0 else 0.0,
        )
        column_profiles.append(col_profile)

    total_cols = len(column_profiles)

    # ── 2. Entity Discovery ─────────────────────────────────────────────────
    report = entity_discovery.discover(column_profiles, file_name)
    entities = report.entities

    # ── 3. Primary Object Discovery ─────────────────────────────────────────
    primary = primary_object_discovery.discover(entities, file_name, total_cols)

    # ── 4. Participation Discovery ──────────────────────────────────────────
    participants = participation_discovery.discover(entities, primary)

    # ── 5. Reference Signal Detection ───────────────────────────────────────
    reference_signals = reference_signal_detector.detect(
        primary, participants, entities, column_profiles
    )
    relationship_report = reference_signal_detector.build_report(primary, reference_signals)

    # ── 6. Build response ───────────────────────────────────────────────────
    def _entity_to_dict(e):
        return {
            "label": e.label,
            "columns": e.columns,
            "identifier_column": e.identifier_column,
            "role_counts": e.role_counts,
            "entity_confidence": e.entity_confidence,
            "is_valid": e.is_valid,
        }

    def _alternative_to_dict(a):
        return {
            "label": a.label,
            "confidence": a.confidence,
            "table_name_score": a.table_name_score,
            "column_dominance_score": a.column_dominance_score,
            "entity_confidence_score": a.entity_confidence_score,
            "evidence_columns": a.evidence_columns,
        }

    def _trace_to_dict(t):
        return {
            "column_name": t.column_name,
            "role": t.role,
            "contribution": t.contribution,
        }

    def _participant_to_dict(p):
        return {
            "label": p.label,
            "identifier_column": p.identifier_column,
            "participation_score": p.participation_score,
            "entity_confidence": p.entity_confidence,
            "naming_evidence": p.naming_evidence,
            "is_valid": p.is_valid,
        }

    def _signal_to_dict(s):
        return {
            "source_entity": s.source_entity,
            "target_entity": s.target_entity,
            "reference_column": s.reference_column,
            "cardinality": s.cardinality,
            "confidence": s.confidence,
            "naming_evidence": s.naming_evidence,
            "entity_confidence": s.entity_confidence,
            "value_overlap": s.value_overlap,
            "is_valid": s.is_valid,
        }

    # Data quality summary from unified profile
    quality_summary = {}
    quality = unified_profile.get("quality", {})
    if quality:
        quality_summary = {
            "missing_values": quality.get("missing_cells", 0),
            "missing_percentage": quality.get("missing_percentage", 0),
            "duplicate_rows": quality.get("duplicate_rows", 0),
            "duplicate_percentage": quality.get("duplicate_percentage", 0),
        }

    understanding = {
        "dataset_name": file_name,
        "table_name": file_name.rsplit(".", 1)[0] if "." in file_name else file_name,
        "row_count": total_rows,
        "column_count": total_cols,
        "primary_object": {
            "label": primary.label,
            "evidence_strength": primary.evidence_strength,
            "table_name_score": primary.table_name_score,
            "column_dominance_score": primary.column_dominance_score,
            "entity_confidence_score": primary.entity_confidence_score,
            "is_valid": primary.is_valid,
            "evidence_trace": [_trace_to_dict(t) for t in primary.evidence_trace],
            "alternatives": [_alternative_to_dict(a) for a in primary.alternatives],
            "ambiguity": {
                "score": primary.ambiguity.score if primary.ambiguity else 0.0,
                "level": primary.ambiguity.level if primary.ambiguity else "low",
                "top_gap": primary.ambiguity.top_gap if primary.ambiguity else 1.0,
                "alternative_count": primary.ambiguity.alternative_count
                if primary.ambiguity
                else 0,
                "has_alternatives": primary.ambiguity.has_alternatives
                if primary.ambiguity
                else False,
            }
            if primary.ambiguity
            else None,
        },
        "entities": [_entity_to_dict(e) for e in entities if e.is_valid],
        "participants": [_participant_to_dict(p) for p in participants],
        "reference_signals": {
            "signals": [_signal_to_dict(s) for s in reference_signals],
            "precision": relationship_report.precision,
            "reference_count": relationship_report.reference_count,
        },
        "quality_summary": quality_summary,
        "trust_score": report.trust_score,
        "data_quality_score": report.data_quality_score,
        "generated_at": report.generated_at.isoformat(),
    }

    return {
        "understanding": understanding,
        "legacy": False,
    }


# ─── KPI Override Persistence ────────────────────────────────────────────────


@router.put("/{dataset_id}/kpis/{kpi_id}")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def update_kpi_override(
    request: Request,
    dataset_id: str,
    kpi_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Persist a user's KPI card edit (column, aggregation, format, icon changes)
    so the override survives page refreshes.

    Overrides are stored in the dashboard's user_layout.kpi_overrides map,
    keyed by the KPI's unique ID. On dashboard load, the frontend merges
    these overrides with the base KPIs from the backend.

    Body (all fields optional — only changed fields need to be sent):
    {
        "column": "column_name",
        "aggregation": "sum" | "mean" | "count" | "median",
        "format": "currency" | "percentage" | "integer" | "decimal" | "number",
        "icon": "DollarSign" | "Users" | ...
    }
    """
    db = get_database()

    # Verify dataset ownership
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Build the override entry — only store fields that were actually changed
    override = {
        k: v
        for k, v in body.items()
        if v is not None and k in ("column", "aggregation", "format", "icon", "value")
    }
    if not override:
        raise HTTPException(status_code=400, detail="At least one field to update is required")

    # Store in user_layout.kpi_overrides as a map keyed by kpi_id
    await db.dashboards.update_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"$set": {f"user_layout.kpi_overrides.{kpi_id}": override}},
        upsert=True,
    )

    logger.info(f"[KPI] Persisted override for {kpi_id} in dataset {dataset_id}: {override}")
    return {"success": True, "message": "KPI override saved"}


@router.get("/{dataset_id}/kpis/overrides")
@limiter.limit(RateLimits.DATASET_GET)
async def get_kpi_overrides(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return all persisted KPI overrides for the current user and dataset."""
    db = get_database()

    dashboard = await db.dashboards.find_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"user_layout.kpi_overrides": 1},
    )

    overrides = dashboard.get("user_layout", {}).get("kpi_overrides", {}) if dashboard else {}
    return {"overrides": overrides}


# ─── Chat-Driven Component Addition ───────────────────────────────────────────


@router.post("/{dataset_id}/components/add")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def add_component(
    request: Request,
    dataset_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Add a new component (KPI or chart) to the dashboard, requested via chatbot.

    Body:
    {
        "type": "kpi" | "chart",
        "column": "column_name",
        "aggregation": "sum" | "mean" | "count" | "median",
        "title": "Custom Title",          # optional
        "chart_type": "bar" | "line" | ... # only for charts
    }
    """
    from services.ai.intelligent_kpi_generator import intelligent_kpi_generator

    db = get_database()
    dataset = await enhanced_dataset_service.get_dataset(dataset_id, current_user["id"])
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.get("is_processed"):
        raise HTTPException(status_code=202, detail="Dataset still processing")

    component_type = body.get("type", "kpi")
    column = body.get("column")
    aggregation = body.get("aggregation", "sum")
    custom_title = body.get("title")

    if not column:
        raise HTTPException(status_code=400, detail="Column name is required")

    # Verify column exists
    col_meta = dataset.get("metadata", {}).get("column_metadata", [])
    col_info = next((c for c in col_meta if c.get("name") == column), None)
    if not col_info:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found in dataset")

    # Load DataFrame for computation (with per-dataset concurrency guard)
    lock = await _get_kpi_lock(dataset_id)
    async with lock:
        try:
            import polars as pl

            file_path = dataset.get("file_path", "")
            ext = file_path.rsplit(".", 1)[-1].lower()
            if ext == "parquet":
                df = pl.read_parquet(file_path)
            elif ext == "csv":
                df = pl.read_csv(file_path, infer_schema_length=5000, ignore_errors=True)
            else:
                raise HTTPException(status_code=422, detail=f"Unsupported format: {ext}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    if component_type == "kpi":
        # Generate single KPI
        kpi = await intelligent_kpi_generator.generate_single_kpi(
            df=df,
            column=column,
            aggregation=aggregation,
            custom_title=custom_title,
            dataset_metadata=dataset.get("metadata", {}),
        )
        if not kpi:
            raise HTTPException(status_code=500, detail="Failed to generate KPI")

        # Add to user_layout added_components
        await db.dashboards.update_one(
            {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
            {
                "$push": {
                    "user_layout.added_components": {
                        "type": "kpi",
                        "data": kpi,
                        "added_at": __import__("datetime").datetime.utcnow().isoformat(),
                    }
                }
            },
        )

        return {"success": True, "component": kpi, "type": "kpi"}

    elif component_type == "chart":
        chart_type = body.get("chart_type", "bar")
        group_by = body.get("group_by")

        chart_config = {
            "type": "chart",
            "id": f"chart_{column}_{chart_type}",
            "title": custom_title or f"{chart_type.title()} of {column}",
            "config": {
                "chart_type": chart_type,
                "columns": [column],
                "aggregation": aggregation,
            },
            "span": 6,
        }

        if group_by:
            chart_config["config"]["group_by"] = [group_by]

        # Add to user_layout added_components
        await db.dashboards.update_one(
            {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
            {
                "$push": {
                    "user_layout.added_components": {
                        "type": "chart",
                        "data": chart_config,
                        "added_at": __import__("datetime").datetime.utcnow().isoformat(),
                    }
                }
            },
        )

        return {"success": True, "component": chart_config, "type": "chart"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown component type: {component_type}")
