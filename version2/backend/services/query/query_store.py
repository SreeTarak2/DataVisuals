"""
QueryStore — MongoDB persistence for async query execution
==========================================================
Each submitted SQL query gets a document in the ``query_log`` MongoDB
collection tracking its lifecycle from ``queued`` → ``running`` →
``completed`` | ``failed`` | ``cancelled``.

Results are stored inline for small results (≤ 500 rows) or
written to a file on disk for large results.

500-row cap prevents MongoDB 16MB document limit violations — wide
result sets (50+ columns with long text) at 500 rows average ~2-5 MB.

"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config import settings

logger = logging.getLogger(__name__)

# Directory for large result files (> 10K rows)
_RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "query_results"


class QueryStore:
    """MongoDB persistence for the query execution lifecycle.

    Every method lazily imports ``get_database`` to avoid
    circular imports at module level.
    """

    COLLECTION = "query_log"

    # ── Lifecycle helpers ──────────────────────────────────────────────────

    _STATUSES = frozenset({"queued", "running", "completed", "failed", "cancelled"})

    @staticmethod
    def _db():
        from db.database import get_database

        return get_database()

    # ── Create ──────────────────────────────────────────────────────────────

    async def create(
        self,
        dataset_id: str,
        user_id: str,
        sql: str,
        limit: int = 1000,
        workspace_id: str | None = None,
    ) -> str:
        """Insert a new query_log document and return the query_id."""
        query_id = f"qry_{uuid4().hex[:12]}"

        ttl_hours = settings.QUERY_RESULT_TTL_HOURS
        doc = {
            "_id": query_id,
            "dataset_id": dataset_id,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "sql": sql,
            "limit": limit,
            "status": "queued",
            "created_at": datetime.now(UTC),
            "started_at": None,
            "completed_at": None,
            "execution_time_ms": None,
            "row_count": None,
            "total_rows": None,
            "columns": None,
            "error": None,
            "result_stored": None,  # "inline" | "file" | None
            "result_file_path": None,
            "ttl_expire_at": datetime.now(UTC) + timedelta(hours=ttl_hours),
        }

        await self._db()[self.COLLECTION].insert_one(doc)
        logger.debug("[QueryStore] Created %s for dataset %s", query_id, dataset_id[:8])
        return query_id

    # ── Status mutations ────────────────────────────────────────────────────

    async def set_running(self, query_id: str) -> None:
        await self._db()[self.COLLECTION].update_one(
            {"_id": query_id},
            {"$set": {"status": "running", "started_at": datetime.now(UTC)}},
        )

    async def set_completed(
        self,
        query_id: str,
        *,
        columns: list[str],
        data: list[dict[str, Any]],
        row_count: int,
        execution_time_ms: int,
    ) -> None:
        now = datetime.now(UTC)
        store = "inline"
        file_path: str | None = None

        # Large results → write to file (MongoDB 16MB document limit)
        # Inline storage is safe up to ~300 rows — worst-case wide tables
        # (50 cols × 500 bytes/cell) at 300 rows ≈ 7.5 MB text + BSON overhead
        if row_count > 300:
            store = "file"
            file_path = await self._write_result_file(query_id, data)

        await self._db()[self.COLLECTION].update_one(
            {"_id": query_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now,
                    "columns": columns,
                    "data": data if store == "inline" else [],
                    "row_count": row_count,
                    "total_rows": row_count,
                    "execution_time_ms": execution_time_ms,
                    "result_stored": store,
                    "result_file_path": file_path,
                }
            },
        )

    async def set_failed(self, query_id: str, error: str) -> None:
        await self._db()[self.COLLECTION].update_one(
            {"_id": query_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(UTC),
                    "error": error,
                }
            },
        )

    async def set_cancelled(self, query_id: str) -> None:
        await self._db()[self.COLLECTION].update_one(
            {"_id": query_id},
            {
                "$set": {
                    "status": "cancelled",
                    "completed_at": datetime.now(UTC),
                    "error": "Query cancelled by user",
                }
            },
        )

    # ── Queries ─────────────────────────────────────────────────────────────

    async def get(self, query_id: str) -> dict[str, Any] | None:
        """Return the full query_log document or None."""
        doc = await self._db()[self.COLLECTION].find_one({"_id": query_id})
        if doc is None:
            return None
        doc["query_id"] = doc.pop("_id")
        return doc

    async def get_status(self, query_id: str) -> dict[str, Any] | None:
        """Lightweight status-only fetch (excludes result data)."""
        doc = await self._db()[self.COLLECTION].find_one(
            {"_id": query_id},
            {
                "sql": 0,
                "data": 0,
                "result_file_path": 0,
                "ttl_expire_at": 0,
            },
        )
        if doc is None:
            return None
        doc["query_id"] = doc.pop("_id")
        return doc

    async def get_results(
        self, query_id: str, *, offset: int = 0, limit: int = 100
    ) -> dict[str, Any] | None:
        """Fetch results with pagination.

        For file-stored results, reads and slices from disk.
        For inline results, slices from the stored document.
        """
        doc = await self._db()[self.COLLECTION].find_one(
            {"_id": query_id},
            {
                "columns": 1,
                "data": 1,
                "row_count": 1,
                "total_rows": 1,
                "result_stored": 1,
                "result_file_path": 1,
                "status": 1,
                "execution_time_ms": 1,
                "error": 1,
            },
        )
        if doc is None:
            return None

        status = doc.get("status")
        if status != "completed":
            return {
                "query_id": query_id,
                "status": status,
                "error": doc.get("error"),
            }

        if doc.get("result_stored") == "file":
            rows = await self._read_result_file(
                doc["result_file_path"], offset, limit
            )
        else:
            all_data = doc.get("data", [])
            rows = all_data[offset : offset + limit]

        return {
            "query_id": query_id,
            "status": "completed",
            "columns": doc.get("columns", []),
            "rows": rows,
            "row_count": len(rows),
            "total_rows": doc.get("total_rows", 0),
            "offset": offset,
            "limit": limit,
            "execution_time_ms": doc.get("execution_time_ms"),
            "truncated": (offset + limit) < (doc.get("total_rows", 0)),
            "error": None,
        }

    async def get_history(
        self,
        user_id: str,
        dataset_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return recent query history (no result data)."""
        query_filter: dict[str, Any] = {"user_id": user_id}
        if dataset_id:
            query_filter["dataset_id"] = dataset_id

        cursor = (
            self._db()[self.COLLECTION]
            .find(query_filter, {"data": 0, "result_file_path": 0})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )

        history = []
        async for doc in cursor:
            doc["query_id"] = doc.pop("_id")
            history.append(doc)
        return history

    # ── File storage helpers ────────────────────────────────────────────────

    async def _write_result_file(
        self, query_id: str, data: list[dict[str, Any]]
    ) -> str:
        """Write large result sets as newline-delimited JSON."""
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = str(_RESULTS_DIR / f"{query_id}.ndjson")
        with open(file_path, "w") as f:
            for row in data:
                f.write(json.dumps(row, default=str) + "\n")
        logger.debug("[QueryStore] Wrote %d rows to %s", len(data), file_path)
        return file_path

    async def _read_result_file(
        self, file_path: str, offset: int, limit: int
    ) -> list[dict[str, Any]]:
        """Read a slice from a newline-delimited JSON file."""
        if not Path(file_path).exists():
            logger.warning("[QueryStore] Result file not found: %s", file_path)
            return []
        rows = []
        with open(file_path) as f:
            for i, line in enumerate(f):
                if i < offset:
                    continue
                if len(rows) >= limit:
                    break
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    # ── Cleanup ─────────────────────────────────────────────────────────────

    async def delete(self, query_id: str) -> None:
        """Delete a query document and its result file if present."""
        doc = await self._db()[self.COLLECTION].find_one(
            {"_id": query_id}, {"result_file_path": 1}
        )
        if doc and doc.get("result_file_path"):
            try:
                Path(doc["result_file_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        await self._db()[self.COLLECTION].delete_one({"_id": query_id})


# Module-level singleton
query_store = QueryStore()
