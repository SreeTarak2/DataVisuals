"""
DuckDB Connection Helpers
=========================
Centralised factory for creating configured DuckDB connections.

Every DuckDB connection in the application should go through
:func:`create_duckdb_connection` to ensure consistent resource
governance — memory limits, thread counts, and temp directory
are set from ``core.config.settings``.

Why a helper
------------
Before this helper, every module that needed DuckDB wrote::

    conn = duckdb.connect(":memory:")

with no resource limits. A single expensive query could consume
all available RAM and starve other requests. Now every connection
is created with a bounded memory limit and thread count, preventing
any single query from overwhelming the server.

Usage
-----
    from services.query.duckdb_helpers import create_duckdb_connection

    with create_duckdb_connection() as conn:
        conn.execute("SELECT 1")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import duckdb

from core.config import settings

logger = logging.getLogger(__name__)


def create_duckdb_connection(
    memory_limit: Optional[str] = None,
    threads: Optional[int] = None,
    temp_directory: Optional[str] = None,
) -> duckdb.DuckDBPyConnection:
    """Create a configured DuckDB in-memory connection.

    Applies resource governance settings from ``core.config.settings``
    so every connection is bounded by a memory limit and thread cap.

    Parameters
    ----------
    memory_limit:
        Override the default memory limit (e.g. ``"4GB"``).
        Falls back to ``settings.DUCKDB_MEMORY_LIMIT``.
    threads:
        Override the default thread count.
        Falls back to ``settings.DUCKDB_THREADS``.
    temp_directory:
        Override the default temp directory for disk spillover.
        Falls back to ``settings.DUCKDB_TEMP_DIRECTORY``.

    Returns
    -------
    duckdb.DuckDBPyConnection
        A DuckDB connection with config applied via the ``config``
        parameter of ``duckdb.connect()``.

    Examples
    --------
        >>> conn = create_duckdb_connection()
        >>> conn.execute("SELECT current_setting('memory_limit')").fetchone()[0]
        '2.0 GB'
    """
    _memory_limit = memory_limit or settings.DUCKDB_MEMORY_LIMIT
    _threads = str(threads or settings.DUCKDB_THREADS)
    _temp_dir = temp_directory or settings.DUCKDB_TEMP_DIRECTORY

    # Ensure the temp directory exists
    try:
        os.makedirs(_temp_dir, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create DuckDB temp directory '%s': %s", _temp_dir, exc)
        _temp_dir = "/tmp"

    config = {
        "memory_limit": _memory_limit,
        "threads": _threads,
        "temp_directory": _temp_dir,
    }

    conn = duckdb.connect(database=":memory:", config=config)

    logger.debug(
        "Created DuckDB connection (memory=%s, threads=%s, temp=%s)",
        _memory_limit,
        _threads,
        _temp_dir,
    )

    return conn
