"""
api/v2/query_routes.py — Async SQL Execution API
================================================
Implements the async query execution pattern with cancellation support.

Endpoints
---------
POST /api/v2/query/execute     — Submit SQL for async execution
GET  /api/v2/query/{id}/status  — Poll for completion
GET  /api/v2/query/{id}/results — Fetch paginated results
POST /api/v2/query/{id}/cancel  — Cancel running query
GET  /api/v2/query/history       — List recent queries
DELETE /api/v2/query/{id}        — Delete query log entry

See the async-query-execution design doc for full state machine and
architecture rationale.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.query.async_executor import (
    cancel_query,
    execute_sql_async,
    register_task,
    unregister_task,
)
from services.query.concurrency import concurrency_controller
from services.query import query_cache
from services.query.query_store import query_store

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic schemas
# ═══════════════════════════════════════════════════════════════════════════


class ExecuteRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset UUID")
    sql: str = Field(..., description="SQL query (SELECT / WITH only)")
    limit: int = Field(default=1000, ge=1)
    workspace_id: str | None = None


class StatusResponse(BaseModel):
    query_id: str
    status: str  # queued | running | completed | failed | cancelled
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    execution_time_ms: int | None = None
    row_count: int | None = None
    error: str | None = None


class ResultsResponse(BaseModel):
    query_id: str
    status: str
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    total_rows: int = 0
    offset: int = 0
    limit: int = 0
    execution_time_ms: int | None = None
    truncated: bool = False
    error: str | None = None


class CancelResponse(BaseModel):
    query_id: str
    status: str
    cancelled_at: str | None = None


class ExecuteResponse(BaseModel):
    success: bool = True
    query_id: str
    status: str
    position: int = 0
    created_at: str | None = None
    # Fast-path: immediate results
    execution_time_ms: int | None = None
    row_count: int | None = None
    columns: list[str] = []
    data: list[dict[str, Any]] = []
    error: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/query/execute", response_model=ExecuteResponse)
@limiter.limit(RateLimits.AI_INSIGHTS)
async def execute_query(
    request: Request,
    body: ExecuteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Submit SQL for async execution.

    Returns immediately with a ``query_id``.  The client polls
    ``GET /{query_id}/status`` to learn when execution completes,
    then fetches results with ``GET /{query_id}/results``.

    *Fast-path*: if the query completes before the endpoint returns
    (e.g. trivial ``SELECT 1``), the result is included inline and
    ``status`` will be ``"completed"``.
    """
    user_id = str(current_user.get("id", ""))
    dataset_id = body.dataset_id
    # Clamp user-specified limit to 5_000 to prevent memory blowup
    # (frontend may send 1_000_000 for "All rows" preset)
    limit = min(body.limit, 5_000)
    original_sql = body.sql.strip()

    # When the editor has multiple queries (appended via AI generation),
    # execute only the LAST non-empty SQL statement.
    #
    # We use a smarter split that respects string literals so semicolons
    # inside strings or identifiers don't cause false splits.
    raw_sql = original_sql
    if not raw_sql:
        raise HTTPException(status_code=400, detail="SQL query is required")
    statements = _split_statements_safe(raw_sql)
    if not statements:
        raise HTTPException(status_code=400, detail="No valid SQL statement found")
    sql = statements[-1]
    # Strip leading comment lines (-- ...) before the SQL statement
    lines = sql.split("\n")
    sql_lines = [l for l in lines if not l.strip().startswith("--")]
    sql = "\n".join(sql_lines).strip()

    # ── 1. Validate the dataset exists ─────────────────────────────
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {exc}")

    # ── 2. Create the query_log document ────────────────────────────
    query_id = await query_store.create(
        dataset_id=dataset_id,
        user_id=user_id,
        sql=original_sql,  # Log the original multi-statement SQL for accurate history
        limit=limit,
        workspace_id=body.workspace_id,
    )

    # ── 3. Try to acquire a concurrency slot ────────────────────────
    slot = await concurrency_controller.try_acquire(query_id)

    if slot is None:
        # Queue full — reject
        await query_store.set_failed(query_id, "Too many queued queries. Try again shortly.")
        raise HTTPException(
            status_code=429,
            detail="Query execution queue is full. Please try again shortly.",
        )

    if slot is False:
        # Queued — register runner with concurrency controller
        concurrency_controller.register_runner(
            query_id,
            lambda: _run_and_store(query_id, sql, dataset, limit, user_id),
        )
        doc = await query_store.get(query_id)
        return ExecuteResponse(
            success=True,
            query_id=query_id,
            status="queued",
            position=await concurrency_controller.count_waiting(),
            created_at=str(doc.get("created_at")) if doc else None,
        )

    # ── 4. Slot acquired — start execution immediately ──────────────
    doc = await query_store.get(query_id)
    response = await _run_and_store(query_id, sql, dataset, limit, user_id)

    if response["success"]:
        return ExecuteResponse(
            success=True,
            query_id=query_id,
            status="completed",
            execution_time_ms=response.get("execution_time_ms"),
            row_count=response.get("row_count", 0),
            columns=response.get("columns", []),
            data=response.get("data", []),
            created_at=str(doc.get("created_at")) if doc else None,
        )

    return ExecuteResponse(
        success=False,
        query_id=query_id,
        status="failed",
        error=response.get("error"),
        created_at=str(doc.get("created_at")) if doc else None,
    )


@router.get("/query/{query_id}/status", response_model=StatusResponse)
async def get_query_status(
    query_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll for query completion.

    Lightweight — reads only the status fields from MongoDB,
    not the result data.
    """
    doc = await query_store.get_status(query_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query not found")

    # Verify ownership
    user_id = str(current_user.get("id", ""))
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return StatusResponse(
        query_id=doc["query_id"],
        status=doc.get("status", "unknown"),
        created_at=str(doc.get("created_at")) if doc.get("created_at") else None,
        started_at=str(doc.get("started_at")) if doc.get("started_at") else None,
        completed_at=str(doc.get("completed_at")) if doc.get("completed_at") else None,
        execution_time_ms=doc.get("execution_time_ms"),
        row_count=doc.get("row_count"),
        error=doc.get("error"),
    )


@router.get("/query/{query_id}/results", response_model=ResultsResponse)
async def get_query_results(
    query_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=10_000),
    current_user: dict = Depends(get_current_user),
):
    """Fetch paginated query results.

    Only available when ``status == "completed"``.
    For large result sets, uses file-backed pagination.
    """
    doc = await query_store.get_results(query_id, offset=offset, limit=limit)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query not found")

    # Verify ownership
    user_id = str(current_user.get("id", ""))
    stored = await query_store.get(query_id)
    if stored and stored.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ResultsResponse(**doc)


@router.post("/query/{query_id}/cancel", response_model=CancelResponse)
async def cancel_running_query(
    query_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Cancel a running query.

    Uses ``task.cancel()`` to raise ``CancelledError`` inside the
    executor coroutine.  The ``finally`` block closes the DuckDB
    connection, terminating the stuck query on the C++ side.
    """
    doc = await query_store.get(query_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Query not found")

    user_id = str(current_user.get("id", ""))
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if doc.get("status") not in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel query in '{doc.get('status')}' state",
        )

    cancelled = await cancel_query(query_id)
    if not cancelled and doc.get("status") == "queued":
        # Query hasn't started yet — just mark it cancelled
        pass

    await query_store.set_cancelled(query_id)
    concurrency_controller.cleanup(query_id)

    return CancelResponse(
        query_id=query_id,
        status="cancelled",
        cancelled_at=str(datetime.now(UTC)),
    )


@router.get("/query/history")
async def get_query_history(
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """Return recent queries for the current user.

    Optionally filtered by ``dataset_id``.
    Returns metadata only — no result data.
    """
    user_id = str(current_user.get("id", ""))
    history = await query_store.get_history(
        user_id=user_id,
        dataset_id=dataset_id,
        limit=limit,
        offset=offset,
    )

    # Format timestamps as strings
    for entry in history:
        for key in ("created_at", "started_at", "completed_at", "ttl_expire_at"):
            if isinstance(entry.get(key), datetime):
                entry[key] = str(entry[key])

    return {"queries": history, "total": len(history), "offset": offset, "limit": limit}


@router.delete("/query/{query_id}")
async def delete_query(
    query_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a query log entry and its stored results.

    Verifies ownership before deletion.  Silently succeeds if the
    query doesn't exist (idempotent).
    """
    doc = await query_store.get(query_id)
    if doc is None:
        # Idempotent — already gone
        return {"deleted": True, "query_id": query_id}

    user_id = str(current_user.get("id", ""))
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await query_store.delete(query_id)
    concurrency_controller.cleanup(query_id)

    return {"deleted": True, "query_id": query_id}


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


async def _run_and_store(
    query_id: str,
    sql: str,
    dataset: dict[str, Any],
    limit: int,
    user_id: str,
) -> dict[str, Any]:
    """Execute the full lifecycle: load data → execute → store results.

    Wraps the entire operation in a cancellable asyncio task so that
    ``POST /{id}/cancel`` can abort it mid-flight.
    """
    task = asyncio.current_task()
    if task:
        register_task(query_id, task)

    try:
        await query_store.set_running(query_id)

        # ── Check result cache (identical queries skip DuckDB) ────
        dataset_id_internal = dataset.get("_id") or dataset.get("id")
        cached = query_cache.get(dataset_id_internal, sql, limit)
        if cached is not None:
            logger.info(
                "[QueryCache] Full hit for %s (%d rows)",
                query_id[:12],
                cached.get("row_count", 0),
            )
            result = cached
        else:
            # ── Load the Polars DataFrame ──────────────────────────
            # This is async (reads from cache / disk / S3).
            df = await enhanced_dataset_service.load_dataset_data(
                dataset_id_internal,
                user_id,
            )
            if df is None:
                raise RuntimeError("Dataset has no data")

            # ── Execute SQL in thread pool ─────────────────────────
            result = await execute_sql_async(
                sql=sql,
                df=df,
                limit=limit,
                query_id=query_id,
            )

            # Cache successful results for subsequent identical queries
            query_cache.set(dataset_id_internal, sql, limit, result)

        if result.get("success"):
            await query_store.set_completed(
                query_id,
                columns=result["columns"],
                data=result["data"],
                row_count=result["row_count"],
                execution_time_ms=result["execution_time_ms"],
            )
        else:
            await query_store.set_failed(query_id, result.get("error", "Unknown error"))

        return result

    except asyncio.CancelledError:
        await query_store.set_cancelled(query_id)
        raise
    except Exception as exc:
        logger.error("[Query] %s failed: %s", query_id[:12], exc, exc_info=True)
        await query_store.set_failed(query_id, str(exc))
        return {
            "success": False,
            "error": str(exc),
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": 0,
        }
    finally:
        if task:
            unregister_task(query_id)
        concurrency_controller.release()


def _split_statements_safe(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting string literals.

    A naive ``;`` split breaks when a semicolon appears inside a string
    literal (e.g. ``WHERE name = 'hello; world'``).  This function tracks
    single-quote / double-quote state to avoid false splits.

    Returns a list of non-empty, stripped statement strings.
    """
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False

    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            continue
        current.append(ch)

    # Last statement after the final semicolon (or the whole string if no semicolons)
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements
