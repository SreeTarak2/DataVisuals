"""
Layout Snapshots API
--------------------
CRUD endpoints for saving and restoring dashboard layout snapshots.
Snapshots capture the full layout state (KPI positions, chart positions, priorities)
so users can bookmark workspaces and revert to previous layouts.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from bson import ObjectId

from db.database import get_database
from services.auth_service import get_current_user
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets/{dataset_id}/layout-snapshots")


@router.post("/")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def create_snapshot(
    request: Request,
    dataset_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Save a named snapshot of the current dashboard layout.

    Body:
    {
        "name": "My Analysis View",
        "layout": {
            "kpis": [...],
            "charts": [...]
        },
        "is_auto": false
    }
    """
    db = get_database()

    name = body.get("name", "Untitled Snapshot")
    layout = body.get("layout", {})
    is_auto = body.get("is_auto", False)

    if not layout or (not layout.get("kpis") and not layout.get("charts")):
        raise HTTPException(status_code=400, detail="Layout must contain kpis and/or charts")

    snapshot = {
        "dataset_id": dataset_id,
        "user_id": current_user["id"],
        "name": name,
        "layout": layout,
        "is_auto": is_auto,
        "created_at": datetime.utcnow(),
        "version": "1.0",
    }

    result = await db.layout_snapshots.insert_one(snapshot)

    return {
        "success": True,
        "snapshot": {
            "id": str(result.inserted_id),
            "name": name,
            "created_at": snapshot["created_at"].isoformat(),
            "is_auto": is_auto,
        },
    }


@router.get("/")
@limiter.limit(RateLimits.DATASET_GET)
async def list_snapshots(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List all saved snapshots for this dataset, newest first."""
    db = get_database()

    snapshots = (
        await db.layout_snapshots.find(
            {"dataset_id": dataset_id, "user_id": current_user["id"]}
        )
        .sort("created_at", -1)
        .to_list(length=50)
    )

    result = []
    for s in snapshots:
        result.append({
            "id": str(s["_id"]),
            "name": s.get("name", "Untitled"),
            "created_at": s.get("created_at", datetime.utcnow()).isoformat(),
            "is_auto": s.get("is_auto", False),
        })

    return {"snapshots": result, "total": len(result)}


@router.post("/{snapshot_id}/restore")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def restore_snapshot(
    request: Request,
    dataset_id: str,
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Restore a saved snapshot as the active dashboard layout.
    The snapshot's layout is copied into the dashboard's user_layout field.
    """
    db = get_database()

    try:
        snapshot = await db.layout_snapshots.find_one(
            {
                "_id": ObjectId(snapshot_id),
                "dataset_id": dataset_id,
                "user_id": current_user["id"],
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid snapshot ID format")

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    layout = snapshot.get("layout", {})

    await db.dashboards.update_one(
        {"dataset_id": dataset_id, "user_id": current_user["id"], "is_default": True},
        {"$set": {"user_layout": layout}},
        upsert=True,
    )

    return {
        "success": True,
        "message": f"Restored snapshot: {snapshot.get('name')}",
        "layout": layout,
    }


@router.delete("/{snapshot_id}")
@limiter.limit(RateLimits.DATASET_DELETE)
async def delete_snapshot(
    request: Request,
    dataset_id: str,
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a saved layout snapshot."""
    db = get_database()

    try:
        result = await db.layout_snapshots.delete_one(
            {
                "_id": ObjectId(snapshot_id),
                "dataset_id": dataset_id,
                "user_id": current_user["id"],
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid snapshot ID format")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return {"success": True, "message": "Snapshot deleted"}
