"""
dlt State Persistence
=====================

Manages dlt's incremental loading state by storing pipeline state in MongoDB.

dlt tracks incremental loading state (bookmarks, high-water marks) internally.
By default it stores state in a local SQLite database (``.dlt/pipelines/``),
but in a serverless/server environment we want to persist state centrally.

This module provides:
  - ``get_pipeline_state()`` — retrieve the last known state for a pipeline
  - ``save_pipeline_state()`` — persist state after a successful run
  - ``reset_pipeline_state()`` — force a full re-sync (discard state)

State is stored per ``{user_id}:{conn_id}:{source_type}`` key in a
``dlt_states`` MongoDB collection.

Usage:
    from services.dlt.state import get_pipeline_state, save_pipeline_state

    state = await get_pipeline_state(user_id, conn_id, "salesforce")
    if state is None:
        # First run — no incremental state yet
        pass
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from db.database import get_database

logger = logging.getLogger(__name__)


def _state_key(*, user_id: str, conn_id: str, source_type: str) -> str:
    """Stable key for identifying a pipeline's state."""
    return f"{user_id}:{conn_id}:{source_type}"


async def get_pipeline_state(
    user_id: str,
    conn_id: str,
    source_type: str,
) -> Optional[dict[str, Any]]:
    """
    Retrieve the last persisted state for a dlt pipeline.

    Args:
        user_id: Owner of the connection.
        conn_id: Saved connection ID.
        source_type: Connector type key (e.g. ``"salesforce"``).

    Returns:
        The state dict (``{"bookmarks": {...}}``), or None if no state exists.
    """
    db = get_database()
    doc = await db.dlt_states.find_one({
        "state_key": _state_key(
            user_id=user_id,
            conn_id=conn_id,
            source_type=source_type,
        ),
    })
    if doc is None:
        return None
    return json.loads(doc["state_json"])


async def save_pipeline_state(
    user_id: str,
    conn_id: str,
    source_type: str,
    state: dict[str, Any],
) -> None:
    """
    Persist dlt pipeline state after a successful incremental sync.

    Args:
        user_id: Owner of the connection.
        conn_id: Saved connection ID.
        source_type: Connector type key.
        state: The state dict (as returned by dlt's pipeline.state).
    """
    db = get_database()
    key = _state_key(user_id=user_id, conn_id=conn_id, source_type=source_type)

    await db.dlt_states.update_one(
        {"state_key": key},
        {
            "$set": {
                "state_key": key,
                "user_id": user_id,
                "conn_id": conn_id,
                "source_type": source_type,
                "state_json": json.dumps(state),
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        },
        upsert=True,
    )
    logger.debug("Saved dlt state for %s", key)


async def reset_pipeline_state(
    user_id: str,
    conn_id: str,
    source_type: str,
) -> None:
    """
    Delete the persisted state for a pipeline, forcing a full re-sync.

    Call this when the user wants a fresh extract (e.g. after fixing a
    broken connection or when schema changes require a full reload).
    """
    db = get_database()
    key = _state_key(user_id=user_id, conn_id=conn_id, source_type=source_type)

    result = await db.dlt_states.delete_one({"state_key": key})
    if result.deleted_count:
        logger.info("Reset dlt state for %s", key)


async def list_pipeline_states(
    user_id: str,
) -> list[dict[str, Any]]:
    """
    List all pipeline states for a user (for diagnostics / UI display).

    Args:
        user_id: Owner of the connections.

    Returns:
        List of state metadata dicts (without the full state JSON).
    """
    db = get_database()
    docs = []
    async for doc in db.dlt_states.find(
        {"user_id": user_id},
        {"state_json": 0},  # Exclude the large state blob
    ):
        docs.append({
            "conn_id": doc.get("conn_id"),
            "source_type": doc.get("source_type"),
            "updated_at": doc.get("updated_at"),
        })
    return docs
