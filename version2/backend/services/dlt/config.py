"""
dlt Configuration
=================

Manages dlt's runtime configuration via environment variables.

dlt reads configuration from environment variables with a specific naming
convention (``DESTINATION__FILESYSTEM__BUCKET_URL``). This module provides
a context manager for temporarily setting these vars around a pipeline run.

Usage:
    with dlt_config(destination_path="/tmp/dlt_output"):
        pipeline.run(source)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)


@contextmanager
def dlt_environment(
    destination_path: str | Path,
    *,
    loader_file_format: str = "parquet",
    log_level: str = "WARNING",
) -> Generator[None, None, None]:
    """
    Temporarily set dlt environment variables for a pipeline run.

    This avoids writing any configuration files (``secrets.toml``,
    ``config.toml``) to disk. dlt picks up these env vars at import time
    and during ``pipeline.run()``.

    Args:
        destination_path: Local filesystem path for dlt's output.
        loader_file_format: Output format (``"parquet"``, ``"jsonl"``, etc.).
        log_level: dlt's runtime log level (``"WARNING"``, ``"INFO"``, etc.).
    """
    # Save a snapshot of the current environment
    saved = os.environ.copy()

    override_vars = {
        "DESTINATION__FILESYSTEM__BUCKET_URL": f"file://{destination_path}",
        "DESTINATION__FILESYSTEM__FORMAT": loader_file_format,
        "DESTINATION__FILESYSTEM__LOADER_FILE_FORMAT": loader_file_format,
        "RUNTIME__LOG_LEVEL": log_level,
        # Disable dlt's progress bars and interactive prompts
        "DLT_PROGRESS": "enlighten",
        "DLT__DOWNLOAD_TIMEOUT": "120",
    }

    try:
        os.environ.update(override_vars)
        logger.debug(
            "dlt env vars set: bucket_url=file://%s format=%s",
            destination_path,
            loader_file_format,
        )
        yield
    finally:
        # Restore the original environment exactly
        os.environ.clear()
        os.environ.update(saved)
        logger.debug("dlt env vars restored")
