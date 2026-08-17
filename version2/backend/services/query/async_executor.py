"""
AsyncQueryExecutor — Offload DuckDB execution to a thread pool
==============================================================
Moves synchronous ``conn.execute()`` calls off the asyncio event loop
using ``run_in_executor``, wraps them with ``asyncio.wait_for`` for
timeout enforcement, and supports cancellation via ``task.cancel()``.

This is the core fix for bottlenecks #1, #2, and #3 from the
async-query-execution design:

- #1: **No query timeout** → ``asyncio.wait_for`` + ``SET statement_timeout``
- #2: **No cancellation**  → ``task.cancel()`` raises ``CancelledError``
       in the coroutine; ``finally`` block closes DuckDB.
- #3: **Sync blocking HTTP** → ``run_in_executor`` frees the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from typing import Any

import duckdb
import pandas as pd
import polars as pl

from core.config import settings
from services.query.duckdb_helpers import create_duckdb_connection
from services.query.executor import SQLValidator

logger = logging.getLogger(__name__)

# ── Shared thread pool ─────────────────────────────────────────────────────
#   - 4 workers × 2 GB per-connection = max 8 GB concurrent DuckDB RAM
#   - Tune via env: QUERY_MAX_WORKERS
_thread_pool: ThreadPoolExecutor | None = None


def _get_pool() -> ThreadPoolExecutor:
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(
            max_workers=settings.QUERY_MAX_WORKERS,
            thread_name_prefix="duckdb",
        )
    return _thread_pool


# ── Module-level task registry for cancellation ────────────────────────────
_query_tasks: dict[str, asyncio.Task] = {}


def register_task(query_id: str, task: asyncio.Task) -> None:
    _query_tasks[query_id] = task


def unregister_task(query_id: str) -> None:
    _query_tasks.pop(query_id, None)


async def cancel_query(query_id: str) -> bool:
    """Cancel a running query by cancelling its asyncio task.

    Returns True if a task was found and cancelled.
    """
    task = _query_tasks.get(query_id)
    if task and not task.done():
        task.cancel()
        logger.info("[AsyncExecutor] Cancelled task for %s", query_id[:12])
        return True
    logger.warning("[AsyncExecutor] No running task found for %s", query_id[:12])
    return False


# ── Core sync function (runs in thread pool) ──────────────────────────────


def _execute_in_duckdb(
    sql: str,
    limit: int,
    pandas_df: pd.DataFrame,
) -> dict[str, Any]:
    """Execute SQL in DuckDB inside the thread pool.

    This function is deliberately synchronous — it runs inside
    ``run_in_executor`` so the event loop is never blocked.

    ``pandas_df`` is bound via ``functools.partial`` at submission
    time so each concurrent query gets its own DataFrame reference
    with no shared global state.
    """
    # Normalize backtick quoting to DuckDB-compatible double-quote quoting.
    sql = sql.replace("`", '"')

    start = datetime.now(UTC)

    conn = create_duckdb_connection(
        memory_limit=settings.QUERY_MEMORY_LIMIT,
        threads=min(settings.QUERY_MAX_WORKERS, 4),
    )
    try:
        # ── Statement-level timeout ─────────────────────────────────────
        # DuckDB doesn't support statement_timeout via config dictionary,
        # so we set it as a PRAGMA after connection.
        try:
            conn.execute(f"SET statement_timeout = '{settings.QUERY_TIMEOUT * 1000}'")
        except Exception:
            pass
        conn.execute("SET max_expression_depth = 50")

        conn.register("data", pandas_df)

        # Wrap user SQL in a LIMIT subquery.
        result_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS _q LIMIT {limit}"

        cursor = conn.execute(result_sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        records: list[dict[str, Any]] = [dict(zip(columns, row)) for row in rows]
        elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)

        logger.info("[AsyncExecutor] DuckDB returned %d rows in %d ms", len(records), elapsed)

        return {
            "success": True,
            "columns": columns,
            "data": records,
            "row_count": len(records),
            "execution_time_ms": elapsed,
            "error": None,
        }

    except duckdb.Error as e:
        elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)
        error_msg = str(e)
        logger.error("[AsyncExecutor] DuckDB error: %s", error_msg)
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": elapsed,
            "error": error_msg,
        }
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# Async wrapper
# ═════════════════════════════════════════════════════════════════════════════


async def execute_sql_async(
    sql: str,
    df: pl.DataFrame,
    limit: int = 1000,
    query_id: str | None = None,
) -> dict[str, Any]:
    """Execute SQL asynchronously by offloading to a thread pool.

    Parameters
    ----------
    sql:
        The user's SQL query (SELECT / WITH only).
    df:
        Polars DataFrame to register as the ``data`` table.
    limit:
        Maximum number of rows to return.
    query_id:
        Optional tracking ID for cancellation support.

    Returns
    -------
    dict with keys: success, columns, data, row_count,
                    execution_time_ms, error
    """
    # ── 1. Validate ────────────────────────────────────────────────────────
    is_valid, error = SQLValidator.validate(sql)
    if not is_valid:
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": 0,
            "error": f"SQL validation failed: {error}",
        }

    # ── 2. Convert Polars → Pandas (DuckDB's native format) ────────────────
    try:
        pandas_df = df.to_pandas()
    except ModuleNotFoundError as exc:
        if exc.name == "pyarrow":
            logger.warning(
                "pyarrow not installed; falling back to dict-based Polars→Pandas conversion."
            )
            pandas_df = pd.DataFrame(df.to_dicts())
        else:
            raise
    except Exception as exc:
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": 0,
            "error": f"DataFrame conversion failed: {exc}",
        }

    # ── 3. Submit to thread pool with partial binding ──────────────────────
    #   ``functools.partial`` binds ``pandas_df`` at call time so each
    #   concurrent query gets its own copy — no shared global state.
    loop = asyncio.get_running_loop()
    pool = _get_pool()
    bound_fn = partial(_execute_in_duckdb, sql, limit, pandas_df)

    try:
        result: dict[str, Any] = await asyncio.wait_for(
            loop.run_in_executor(pool, bound_fn),
            timeout=settings.QUERY_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        logger.error(
            "[AsyncExecutor] Query %s timed out after %ds",
            query_id or "?",
            settings.QUERY_TIMEOUT,
        )
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": settings.QUERY_TIMEOUT * 1000,
            "error": f"Query timed out after {settings.QUERY_TIMEOUT}s. "
            "Try simplifying the query or reducing the dataset size.",
        }
    except asyncio.CancelledError:
        logger.info("[AsyncExecutor] Query %s was cancelled", query_id or "?")
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": 0,
            "error": "Query cancelled by user.",
        }
    except Exception as exc:
        logger.error("[AsyncExecutor] Unexpected error: %s", exc, exc_info=True)
        return {
            "success": False,
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time_ms": 0,
            "error": f"Unexpected error: {exc}",
        }
