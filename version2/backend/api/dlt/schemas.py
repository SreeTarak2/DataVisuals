"""
dlt API Schemas
===============

Pydantic request/response models for the dlt integration endpoints.
Follows the same patterns as ``api/databases/schemas.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


# ── Request Schemas ────────────────────────────────────────────────────────


class DltSetupRequest(BaseModel):
    """Request body for setting up a new dlt connection."""

    name: str
    source_type: str
    credentials: dict[str, Any]
    incremental: bool = True
    row_limit: int = 100_000

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("Name must be 1–100 characters")
        return v

    @field_validator("row_limit")
    @classmethod
    def validate_row_limit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("row_limit must be positive")
        if v > 1_000_000:
            raise ValueError("row_limit cannot exceed 1,000,000")
        return v

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        # Derive allowed types from the registry at runtime to avoid
        # duplicating the list in two places.
        from services.dlt.sources import get_source_registry

        registry = get_source_registry()
        v = v.strip().lower()
        if v not in registry:
            raise ValueError(
                f"Unsupported source_type: {v}. "
                f"Supported types: {', '.join(sorted(registry.keys()))}"
            )
        return v


class DltSyncRequest(BaseModel):
    """Request body for triggering a dlt sync on an existing connection."""

    conn_id: str
    dataset_name: Optional[str] = None
    incremental: bool = True
    row_limit: int = 100_000


# ── Response Schemas ───────────────────────────────────────────────────────


class DltConnectionResponse(BaseModel):
    """Response for a saved dlt connection."""

    connection_id: str
    name: str
    source_type: str
    status: str = "active"
    created_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None


class DltSyncResponse(BaseModel):
    """Response for a completed dlt sync."""

    dataset_id: str
    task_id: str
    rows_extracted: int
    name: str
    schema_hash: Optional[str] = None
    message: str


class DltSourceListResponse(BaseModel):
    """Response listing available dlt source types."""

    sources: list[dict[str, Any]]


class DltStatusResponse(BaseModel):
    """Response for connection status / health."""

    connection_id: str
    source_type: str
    status: str
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    pipeline_state_exists: bool = False
