"""
QueryCache — DiskCache-backed result caching for DuckDB queries
================================================================
Uses ``diskcache.Cache`` (SQLite-backed) to persist query results
across restarts without external infrastructure.

Cache entries are keyed by ``qry:<dataset_id>:<sql_hash>:<limit>``.

TTL is configurable via ``settings.QUERY_CACHE_TTL`` (default 300 s).
Set to 0 to disable caching.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from diskcache import Cache as DiskCache

from core.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — the DiskCache is thread-safe by design
_cache: DiskCache | None = None


def _get_cache() -> DiskCache | None:
    """Lazy-initialize the shared DiskCache instance.

    Returns ``None`` when caching is disabled (TTL <= 0).
    """
    global _cache
    if settings.QUERY_CACHE_TTL <= 0:
        return None
    if _cache is None:
        cache_dir = Path(settings.QUERY_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache = DiskCache(str(cache_dir))
        logger.info(
            "[QueryCache] Initialised at %s (TTL=%ds)",
            cache_dir,
            settings.QUERY_CACHE_TTL,
        )
    return _cache


def _make_key(dataset_id: str, sql: str, limit: int) -> str:
    """Deterministic cache key from query parameters."""
    sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
    return f"qry:{dataset_id}:{sql_hash}:{limit}"


def get(dataset_id: str, sql: str, limit: int) -> dict[str, Any] | None:
    """Return cached result dict, or ``None`` on miss / disabled cache.

    The returned dict has the same shape as ``execute_sql_async()`` output:
    ``{success, columns, data, row_count, execution_time_ms, error}``.
    """
    cache = _get_cache()
    if cache is None:
        return None
    key = _make_key(dataset_id, sql, limit)
    result = cache.get(key)
    if result is not None:
        logger.debug("[QueryCache] HIT  %s", key[:40])
    return result


def set(
    dataset_id: str,
    sql: str,
    limit: int,
    result: dict[str, Any],
) -> None:
    """Store a query result in the cache with the configured TTL.

    Only successful results are cached (``result["success"] == True``).
    """
    if not result.get("success"):
        return
    cache = _get_cache()
    if cache is None:
        return
    key = _make_key(dataset_id, sql, limit)
    cache.set(key, result, expire=settings.QUERY_CACHE_TTL)
    logger.debug(
        "[QueryCache] SET  %s (%d rows, %d ms)",
        key[:40],
        result.get("row_count", 0),
        result.get("execution_time_ms", 0),
    )


def invalidate_dataset(dataset_id: str) -> int:
    """Remove all cached query results for a specific dataset.

    Called when a dataset is re-processed so stale query results
    are not served after the data changes.

    Returns the number of evicted entries.
    """
    cache = _get_cache()
    if cache is None:
        return 0

    prefix = f"qry:{dataset_id}:"
    keys_to_delete = [key for key in cache.iterkeys() if key.startswith(prefix)]

    for key in keys_to_delete:
        cache.delete(key)

    count = len(keys_to_delete)
    if count:
        logger.info("[QueryCache] Invalidated %d entries for dataset %s", count, dataset_id[:8])
    return count


def clear() -> None:
    """Evict all cached query results."""
    cache = _get_cache()
    if cache is None:
        return
    cache.clear()
    logger.info("[QueryCache] Cleared")
