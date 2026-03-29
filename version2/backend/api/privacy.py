# backend/api/privacy.py

"""
Privacy API Endpoints
===================
REST API for managing privacy settings, PII detection, and audit logs.

Endpoints:
- GET/PUT /api/privacy/settings - Global privacy settings
- GET/PUT /api/privacy/settings/{dataset_id} - Per-dataset settings
- POST /api/privacy/detect-pii/{dataset_id} - Scan for PII
- GET /api/privacy/detect-pii/{dataset_id}/results - Get PII results
- POST /api/privacy/preview/{dataset_id} - Dry-run: what LLM sees
- GET /api/privacy/audit-log - Get audit log
- GET /api/privacy/export - GDPR data export
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from services.auth_service import get_current_user
from services.privacy import (
    pii_detector,
    redaction_service,
    privacy_settings_service,
    privacy_audit_service,
    PrivacyEventType,
    RedactionMode,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic Models ---


class GlobalSettingsUpdate(BaseModel):
    pii_auto_detect: Optional[bool] = None
    pii_auto_redact: Optional[bool] = None
    share_column_names: Optional[bool] = None
    share_sample_rows: Optional[bool] = None
    max_sample_rows: Optional[int] = None
    data_retention_days: Optional[int] = None
    show_dry_run_first_time: Optional[bool] = None
    send_retention_warnings: Optional[bool] = None


class DatasetSettingsUpdate(BaseModel):
    pii_auto_redact: Optional[bool] = None
    private_columns: Optional[List[str]] = None
    share_column_names: Optional[bool] = None
    share_sample_rows: Optional[bool] = None
    max_sample_rows: Optional[int] = None


class PrivateColumnAction(BaseModel):
    action: str  # "add" or "remove"
    column_name: str


class PiiScanRequest(BaseModel):
    sample_size: Optional[int] = 100


class DryRunRequest(BaseModel):
    pass  # No body needed


# --- Helper Functions ---


async def get_dataset_for_user(dataset_id: str, user_id: str) -> Dict[str, Any]:
    """Get a dataset document, ensuring it belongs to the user."""
    from db.database import get_database
    from bson import ObjectId

    db = get_database()

    # Try both string and ObjectId formats
    query = {"user_id": user_id}
    try:
        query["_id"] = ObjectId(dataset_id)
    except Exception:
        query["_id"] = dataset_id

    dataset = await db.uploads.find_one(query)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )

    return dataset


async def get_dataset_data(dataset: Dict[str, Any]) -> Dict[str, List]:
    """Load dataset data for PII scanning."""
    import polars as pl
    from pathlib import Path

    file_path = dataset.get("file_path")
    parquet_path = dataset.get("parquet_path")

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset file path not found",
        )

    # Try parquet first, fall back to original
    data_path = (
        parquet_path if parquet_path and Path(parquet_path).exists() else file_path
    )

    try:
        df = pl.read_parquet(data_path)
    except Exception:
        try:
            df = pl.read_csv(data_path)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read dataset: {str(e)}",
            )

    # Convert to dict format
    data = {}
    for col in df.columns:
        data[col] = df[col].to_list()

    return data


# --- Privacy Settings Endpoints ---


@router.get("/settings")
async def get_global_settings(current_user: dict = Depends(get_current_user)):
    """
    Get global privacy settings for the current user.

    Returns the global default settings that apply to all datasets
    unless overridden per-dataset.
    """
    settings = await privacy_settings_service.get_user_settings(current_user["id"])

    return {
        "global_defaults": settings.global_defaults.__dict__,
        "created_at": settings.created_at,
        "updated_at": settings.updated_at,
    }


@router.put("/settings")
async def update_global_settings(
    updates: GlobalSettingsUpdate, current_user: dict = Depends(get_current_user)
):
    """
    Update global privacy settings.

    These settings serve as defaults for all datasets. They can be
    overridden on a per-dataset basis.
    """
    updates_dict = {k: v for k, v in updates.__dict__.items() if v is not None}

    if not updates_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided"
        )

    old_settings = await privacy_settings_service.get_user_settings(current_user["id"])
    old_dict = old_settings.global_defaults.__dict__

    new_settings = await privacy_settings_service.update_global_settings(
        current_user["id"], updates_dict
    )

    # Log the change
    await privacy_audit_service.log_settings_change(
        user_id=current_user["id"],
        old_settings=old_dict,
        new_settings=new_settings.global_defaults.__dict__,
    )

    return {
        "global_defaults": new_settings.global_defaults.__dict__,
        "updated_at": new_settings.updated_at,
    }


@router.get("/settings/{dataset_id}")
async def get_dataset_settings(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get effective privacy settings for a specific dataset.

    Returns merged settings (dataset override + global defaults).
    Also indicates which settings come from where.
    """
    # Verify dataset exists and belongs to user
    dataset = await get_dataset_for_user(dataset_id, current_user["id"])

    effective = await privacy_settings_service.get_effective_settings(
        current_user["id"], dataset_id
    )

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.get("name", "Unnamed Dataset"),
        "effective_settings": effective,
        "has_override": dataset_id
        in (
            await privacy_settings_service.get_user_settings(current_user["id"])
        ).dataset_overrides,
    }


@router.put("/settings/{dataset_id}")
async def update_dataset_settings(
    dataset_id: str,
    updates: DatasetSettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update privacy settings for a specific dataset.

    These settings override the global defaults for this dataset only.
    """
    # Verify dataset exists and belongs to user
    await get_dataset_for_user(dataset_id, current_user["id"])

    updates_dict = {k: v for k, v in updates.__dict__.items() if v is not None}

    if not updates_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided"
        )

    old_override = await privacy_settings_service.get_dataset_settings(
        current_user["id"], dataset_id
    )
    old_dict = old_override.__dict__ if old_override else {}

    new_override = await privacy_settings_service.update_dataset_settings(
        current_user["id"], dataset_id, updates_dict
    )

    # Log the change
    await privacy_audit_service.log_settings_change(
        user_id=current_user["id"],
        old_settings=old_dict,
        new_settings=new_override.__dict__,
        dataset_id=dataset_id,
    )

    return {"dataset_id": dataset_id, "settings": new_override.__dict__}


@router.post("/settings/{dataset_id}/columns")
async def manage_private_column(
    dataset_id: str,
    action: PrivateColumnAction,
    current_user: dict = Depends(get_current_user),
):
    """
    Add or remove a column from the private columns list.

    Private columns will not be shared with the LLM.
    """
    await get_dataset_for_user(dataset_id, current_user["id"])

    if action.action == "add":
        success = await privacy_settings_service.add_private_column(
            current_user["id"], dataset_id, action.column_name
        )
        message = f"Column '{action.column_name}' marked as private"
    elif action.action == "remove":
        success = await privacy_settings_service.remove_private_column(
            current_user["id"], dataset_id, action.column_name
        )
        message = f"Column '{action.column_name}' removed from private list"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action. Use 'add' or 'remove'",
        )

    return {
        "success": success,
        "message": message,
        "column_name": action.column_name,
        "action": action.action,
    }


# --- PII Detection Endpoints ---


@router.post("/detect-pii/{dataset_id}")
async def scan_dataset_for_pii(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Scan a dataset for PII (Personally Identifiable Information).

    This endpoint performs PII detection on the dataset and returns
    a list of columns that may contain sensitive information.

    The scan is performed synchronously for immediate results.
    For large datasets, consider using the async task version.
    """
    dataset = await get_dataset_for_user(dataset_id, current_user["id"])

    # Check if dataset is processed
    if not dataset.get("metadata"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset is still being processed",
        )

    try:
        # Load dataset data
        data = await get_dataset_data(dataset)
        columns = list(data.keys())

        # Perform PII scan
        scan_result = pii_detector.scan_dataset(
            dataset_id=dataset_id, columns=columns, data=data, sample_size=100
        )

        # Get redaction candidates
        candidates = pii_detector.get_redaction_candidates(scan_result)

        # Log the scan
        await privacy_audit_service.log_pii_scan(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            columns_found=columns,
            pii_detected=[
                {
                    "column": c.column_name,
                    "type": c.pii_type.value if c.pii_type else None,
                }
                for c in scan_result.columns_with_pii
            ],
            confidence_scores={
                c.column_name: c.confidence for c in scan_result.columns_with_pii
            },
        )

        return {
            "dataset_id": dataset_id,
            "scan_result": {
                "columns_scanned": scan_result.columns_scanned,
                "total_pii_detections": scan_result.total_pii_detections,
                "high_confidence_count": scan_result.high_confidence_count,
                "medium_confidence_count": scan_result.medium_confidence_count,
                "scan_timestamp": scan_result.scan_timestamp,
                "recommendations": scan_result.recommendations,
            },
            "columns_with_pii": [
                {
                    "column_name": c.column_name,
                    "pii_type": c.pii_type.value if c.pii_type else None,
                    "confidence": c.confidence,
                    "sample_matches": c.sample_matches,
                    "should_redact": c.should_redact,
                    "reason": c.reason,
                }
                for c in scan_result.columns_with_pii
            ],
            "redaction_candidates": candidates,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PII scan failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PII scan failed: {str(e)}",
        )


# --- Privacy Preview (Dry-Run) ---


@router.post("/preview/{dataset_id}")
async def generate_privacy_preview(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Generate a privacy preview showing what the LLM will receive.

    This is the "dry-run" feature that shows:
    - Which columns will be shared
    - Which columns will be redacted
    - Sample data with redactions applied

    Call this before the first query on a new dataset.
    """
    dataset = await get_dataset_for_user(dataset_id, current_user["id"])

    # Get effective settings
    effective = await privacy_settings_service.get_effective_settings(
        current_user["id"], dataset_id
    )

    # Load dataset data
    data = await get_dataset_data(dataset)
    columns = list(data.keys())

    # Scan for PII if enabled
    columns_to_redact = set(effective["private_columns"])

    if effective["pii_auto_detect"]:
        scan_result = pii_detector.scan_dataset(
            dataset_id=dataset_id,
            columns=columns,
            data=data,
            sample_size=50,  # Smaller for preview
        )

        # Add auto-detected columns to redact list
        for col_result in scan_result.columns_with_pii:
            if col_result.should_redact and effective["pii_auto_redact"]:
                columns_to_redact.add(col_result.column_name)

    # Determine which columns to share
    if not effective["share_column_names"]:
        # Don't share any column names
        columns_to_share = []
    else:
        columns_to_share = [c for c in columns if c not in columns_to_redact]

    # Generate sample rows with redactions
    max_rows = effective["max_sample_rows"]
    sample_rows = []
    for i in range(min(max_rows, len(next(iter(data.values()))))):
        row = {}
        for col in columns:
            if col in columns_to_redact:
                row[col] = "[REDACTED]"
            else:
                value = data[col][i] if i < len(data[col]) else None
                row[col] = str(value) if value is not None else ""
        sample_rows.append(row)

    # Log the dry-run
    await privacy_audit_service.log_dry_run(
        user_id=current_user["id"],
        dataset_id=dataset_id,
        columns_to_share=columns_to_share,
        columns_to_redact=list(columns_to_redact),
    )

    # Mark dry-run as completed
    await privacy_settings_service.mark_dry_run_completed(
        current_user["id"], dataset_id
    )

    return {
        "dataset_id": dataset_id,
        "privacy_settings_applied": {
            "pii_auto_detect": effective["pii_auto_detect"],
            "pii_auto_redact": effective["pii_auto_redact"],
            "share_column_names": effective["share_column_names"],
            "share_sample_rows": effective["share_sample_rows"],
            "max_sample_rows": effective["max_sample_rows"],
        },
        "columns_to_share": columns_to_share,
        "columns_to_redact": list(columns_to_redact),
        "sample_rows": sample_rows,
        "dry_run_completed": True,
        "llm_will_receive": {
            "column_count": len(columns_to_share),
            "row_count": len(sample_rows),
            "pii_protected": len(columns_to_redact) > 0,
        },
    }


# --- Audit Log Endpoints ---


@router.get("/audit-log")
async def get_audit_log(
    current_user: dict = Depends(get_current_user),
    event_types: Optional[str] = Query(
        None, description="Comma-separated event types to filter"
    ),
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum events to return"),
    skip: int = Query(0, ge=0, description="Number of events to skip"),
):
    """
    Get privacy audit log for the current user.

    Returns a list of privacy-related events such as:
    - PII scans
    - Data redactions
    - Settings changes
    - LLM data access
    """
    event_type_list = None
    if event_types:
        event_type_list = [t.strip() for t in event_types.split(",")]

    start_date = datetime.utcnow() - datetime.timedelta(days=days)

    events = await privacy_audit_service.get_user_events(
        user_id=current_user["id"],
        event_types=event_type_list,
        dataset_id=dataset_id,
        start_date=start_date,
        limit=limit,
        skip=skip,
    )

    # Get stats
    stats = await privacy_audit_service.get_event_stats(
        user_id=current_user["id"], days=days
    )

    return {
        "events": events,
        "stats": stats,
        "pagination": {"limit": limit, "skip": skip, "returned": len(events)},
    }


@router.get("/audit-log/stats")
async def get_audit_stats(
    current_user: dict = Depends(get_current_user), days: int = Query(30, ge=1, le=365)
):
    """
    Get privacy audit statistics.

    Returns counts of different event types over the specified period.
    """
    stats = await privacy_audit_service.get_event_stats(
        user_id=current_user["id"], days=days
    )

    return stats


# --- GDPR / Export Endpoints ---


@router.get("/export")
async def export_privacy_data(current_user: dict = Depends(get_current_user)):
    """
    Export all privacy-related data for GDPR compliance.

    Returns:
    - Privacy settings
    - Audit log (last year)
    """
    settings_export = await privacy_settings_service.export_user_data(
        current_user["id"]
    )
    audit_export = await privacy_audit_service.export_user_events(current_user["id"])

    return {
        "export_date": datetime.utcnow().isoformat(),
        "privacy_settings": settings_export,
        "audit_log": {
            "events": audit_export["events"][:1000],  # Limit to last 1000
            "total_in_period": audit_export["total_events"],
        },
    }


# --- Privacy Notice Dismissal ---


class DismissalUpdate(BaseModel):
    dismissed: bool = True


@router.post("/notice-dismissal")
async def update_notice_dismissal(
    dismissed: DismissalUpdate, current_user: dict = Depends(get_current_user)
):
    """
    Update whether the user has dismissed the privacy notice.

    When dismissed=True, the privacy notice won't show on upload anymore.
    This preference is stored client-side, but we log it for compliance.
    """
    if dismissed.dismissed:
        await privacy_audit_service.log_event(
            user_id=current_user["id"],
            event_type=PrivacyEventType.SETTINGS_CHANGED,
            details={"notice_dismissed": True},
        )

    return {
        "notice_dismissed": dismissed.dismissed,
        "timestamp": datetime.utcnow().isoformat(),
    }
