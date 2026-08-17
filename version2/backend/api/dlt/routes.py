"""
dlt API Routes
==============

REST endpoints for managing dlt-powered data connections.

Endpoints:
  GET    /api/dlt/sources          — List available dlt source types
  POST   /api/dlt/setup            — Save a new dlt connection (test + persist)
  GET    /api/dlt/connections      — List saved dlt connections
  POST   /api/dlt/sync             — Trigger a dlt sync on a saved connection
  GET    /api/dlt/{conn_id}/status — Get connection sync status
  DELETE /api/dlt/{conn_id}        — Delete a dlt connection
  POST   /api/dlt/{conn_id}/reset  — Reset incremental state (force full re-sync)

All endpoints require authentication. Passwords/API keys are encrypted at rest.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from api.dlt.schemas import (
    DltConnectionResponse,
    DltSetupRequest,
    DltSourceListResponse,
    DltStatusResponse,
    DltSyncRequest,
    DltSyncResponse,
)
from core.rate_limiter import RateLimits, limiter
from db.database import get_database
from services.auth_service import get_current_user
from services.dlt import dlt_runner
from services.dlt.sources import list_available_sources
from services.dlt.state import (
    get_pipeline_state,
    list_pipeline_states,
    reset_pipeline_state,
    save_pipeline_state,
)
from services.encryption import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dlt", tags=["dlt Data Connectors"])


# ---------------------------------------------------------------------------
# GET /sources — List available source types
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=DltSourceListResponse)
@limiter.limit(RateLimits.DB_LIST)
async def list_sources(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all available dlt source types (Salesforce, HubSpot, etc.)."""
    sources = list_available_sources()
    return DltSourceListResponse(sources=sources)


# ---------------------------------------------------------------------------
# POST /setup — Save a new dlt connection
# ---------------------------------------------------------------------------


@router.post("/setup", response_model=DltConnectionResponse, status_code=201)
@limiter.limit(RateLimits.DB_CONNECT)
async def setup_dlt_connection(
    request: Request,
    body: DltSetupRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Save a new dlt connection.

    Encrypts the API key or password before storage, creates a connection
    record in MongoDB, and returns the connection_id.
    """
    db = get_database()
    conn_id = str(uuid4())

    # Encrypt the API key (if present) for storage
    encrypted_key = ""
    api_key = body.credentials.get("api_key") or body.credentials.get("token")
    if api_key:
        try:
            encrypted_key = encrypt_api_key(api_key)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to encrypt credentials: {e}",
            )

    doc = {
        "_id": conn_id,
        "user_id": current_user["id"],
        "name": body.name,
        "source_type": body.source_type,
        "connection_type": "dlt",
        "credentials": {
            k: v
            for k, v in body.credentials.items()
            if k not in ("api_key", "token", "password")
        },
        "api_key_encrypted": encrypted_key or None,
        "incremental": body.incremental,
        "row_limit": body.row_limit,
        "status": "active",
        "last_synced_at": None,
        "last_sync_status": None,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }

    # If there's a password (for DB sources), encrypt it the same way as
    # db_connection_service does
    password = body.credentials.get("password")
    if password:
        from services.databases.db_connection_service import _encrypt

        doc["password_encrypted"] = _encrypt(password)
        doc.pop("api_key_encrypted", None)  # DB sources don't use API keys

    # Strip the plaintext password from the stored credentials dict
    doc["credentials"].pop("password", None)

    await db.db_connections.insert_one(doc)
    logger.info(
        "Saved dlt connection '%s' (%s) for user %s",
        body.name,
        conn_id[:8],
        current_user["id"][:8],
    )

    return DltConnectionResponse(
        connection_id=conn_id,
        name=body.name,
        source_type=body.source_type,
        status="active",
        created_at=doc["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /connections — List saved dlt connections
# ---------------------------------------------------------------------------


@router.get("/connections", response_model=list[DltConnectionResponse])
@limiter.limit(RateLimits.DB_LIST)
async def list_dlt_connections(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all dlt connections saved by the current user."""
    db = get_database()
    connections = []

    async for doc in db.db_connections.find(
        {"user_id": current_user["id"], "connection_type": "dlt"},
        {"api_key_encrypted": 0, "password_encrypted": 0},
    ):
        connections.append(
            DltConnectionResponse(
                connection_id=str(doc["_id"]),
                name=doc.get("name", ""),
                source_type=doc.get("source_type", ""),
                status=doc.get("status", "active"),
                created_at=doc.get("created_at"),
                last_synced_at=doc.get("last_synced_at"),
                last_sync_status=doc.get("last_sync_status"),
            )
        )

    return connections


# ---------------------------------------------------------------------------
# POST /sync — Trigger a sync on a saved connection
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=DltSyncResponse, status_code=202)
@limiter.limit(RateLimits.DB_EXTRACT)
async def trigger_dlt_sync(
    request: Request,
    body: DltSyncRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger a dlt sync on a saved connection.

    This runs the dlt pipeline in-process (non-blocking). For large datasets,
    this may take several minutes. Returns the dataset_id immediately.

    The sync:
      1. Loads and decrypts the saved credentials
      2. Runs the dlt pipeline (Salesforce, HubSpot, etc.)
      3. Writes Parquet to the standard db_extracts/ directory
      4. Fires the processing pipeline (profiling → KPI → dashboard)
    """
    db = get_database()

    # Load the connection document
    doc = await db.db_connections.find_one(
        {"_id": body.conn_id, "user_id": current_user["id"]},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Connection not found")
    if doc.get("connection_type") != "dlt":
        raise HTTPException(
            status_code=400,
            detail=f"Connection {body.conn_id[:8]} is not a dlt connection",
        )

    source_type = doc.get("source_type", "")
    credentials = _build_credentials(doc)

    try:
        result = await dlt_runner.run_sync(
            user_id=current_user["id"],
            conn_id=body.conn_id,
            source_type=source_type,
            credentials=credentials,
            dataset_name=body.dataset_name or doc.get("name", ""),
            incremental=body.incremental,
            row_limit=body.row_limit,
            workspace_id=current_user.get("workspace_id", current_user["id"]),
        )

        # Update connection metadata
        await db.db_connections.update_one(
            {"_id": body.conn_id},
            {
                "$set": {
                    "last_synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "last_sync_status": "success",
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            },
        )

        return DltSyncResponse(
            dataset_id=result.dataset_id,
            task_id=result.task_id,
            rows_extracted=result.rows_extracted,
            name=result.name,
            schema_hash=result.schema_hash,
            message=result.message,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "dlt sync failed for conn %s: %s",
            body.conn_id[:8],
            str(e),
        )
        # Update connection metadata with failure
        await db.db_connections.update_one(
            {"_id": body.conn_id},
            {
                "$set": {
                    "last_synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "last_sync_status": "failed",
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            },
        )
        raise HTTPException(status_code=502, detail=f"Sync failed: {str(e)[:300]}")


# ---------------------------------------------------------------------------
# GET /{conn_id}/status — Get connection status
# ---------------------------------------------------------------------------


@router.get("/{conn_id}/status", response_model=DltStatusResponse)
@limiter.limit(RateLimits.DB_LIST)
async def get_connection_status(
    request: Request,
    conn_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the status and last sync info for a dlt connection."""
    db = get_database()
    doc = await db.db_connections.find_one(
        {"_id": conn_id, "user_id": current_user["id"]},
        {"api_key_encrypted": 0, "password_encrypted": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Check if pipeline state exists (for incremental sync status)
    state = None
    if doc.get("connection_type") == "dlt":
        state = await get_pipeline_state(
            current_user["id"],
            conn_id,
            doc.get("source_type", ""),
        )

    return DltStatusResponse(
        connection_id=conn_id,
        source_type=doc.get("source_type", ""),
        status=doc.get("status", "active"),
        last_synced_at=doc.get("last_synced_at"),
        last_sync_status=doc.get("last_sync_status"),
        pipeline_state_exists=state is not None,
    )


# ---------------------------------------------------------------------------
# DELETE /{conn_id} — Delete a connection
# ---------------------------------------------------------------------------


@router.delete("/{conn_id}", status_code=204)
@limiter.limit(RateLimits.DB_LIST)
async def delete_dlt_connection(
    request: Request,
    conn_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a dlt connection and its pipeline state."""
    db = get_database()
    result = await db.db_connections.delete_one(
        {"_id": conn_id, "user_id": current_user["id"]},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Also clean up pipeline state
    # We don't know the source_type here, so delete by conn_id prefix
    await db.dlt_states.delete_many({"conn_id": conn_id, "user_id": current_user["id"]})

    logger.info("Deleted dlt connection %s for user %s", conn_id[:8], current_user["id"][:8])


# ---------------------------------------------------------------------------
# POST /{conn_id}/reset — Reset incremental state
# ---------------------------------------------------------------------------


@router.post("/{conn_id}/reset", status_code=200)
@limiter.limit(RateLimits.DB_LIST)
async def reset_connection_state(
    request: Request,
    conn_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Reset the incremental sync state for a connection.

    The next sync will do a **full re-extract** instead of an incremental
    update. Use this when the source schema has changed or the state is
    corrupted.
    """
    db = get_database()
    doc = await db.db_connections.find_one(
        {"_id": conn_id, "user_id": current_user["id"]},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Connection not found")

    source_type = doc.get("source_type", "")
    await reset_pipeline_state(current_user["id"], conn_id, source_type)

    return {"message": f"Incremental state reset for {doc.get('name', source_type)}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_credentials(doc: dict) -> dict:
    """
    Decrypt and assemble the credentials dict for a dlt source.

    Handles both API-key-based sources and password-based sources.
    """
    source_type = doc.get("source_type", "")
    credentials = dict(doc.get("credentials", {}))

    # Restore encrypted API key
    encrypted_key = doc.get("api_key_encrypted")
    if encrypted_key:
        try:
            credentials["api_key"] = decrypt_api_key(encrypted_key)
        except Exception as e:
            logger.warning("Failed to decrypt API key for %s: %s", doc.get("_id", "?"), e)

    # Restore encrypted password
    encrypted_password = doc.get("password_encrypted")
    if encrypted_password:
        from services.databases.db_connection_service import _decrypt

        try:
            credentials["password"] = _decrypt(encrypted_password)
        except Exception as e:
            logger.warning(
                "Failed to decrypt password for %s: %s",
                doc.get("_id", "?"),
                e,
            )

    return credentials
