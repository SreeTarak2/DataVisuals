"""
dlt Pipeline Runner
===================

Orchestrates dlt pipeline runs within the DataSage backend.

Key design:
  - Runs dlt in-process (no subprocess) — dlt is a Python library
  - Configures the filesystem destination programmatically via env vars
  - dlt writes Parquet files to a temp directory per pipeline
  - The runner discovers the output files and copies them to the standard
    ``data/uploads/db_extracts/{dataset_id}.parquet`` path
  - Fires the same ``process_dataset()`` pipeline used by file uploads and
    DB extracts — no new processing code needed
  - Integrates with existing Fernet encryption, audit_service, and BreakerRegistry
  - Handles incremental syncs via dlt's built-in ``write_disposition="merge"``

Usage:
    from services.dlt.runner import DltRunner

    runner = DltRunner()
    result = await runner.run_sync(
        user_id="user_abc",
        conn_id="conn_123",
        source_type="salesforce",
        credentials={"client_id": "...", "client_secret": "...", ...},
        dataset_name="Salesforce Accounts",
        incremental=True,
    )
    print(f"Extracted {result.rows_extracted} rows -> dataset {result.dataset_id}")
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import polars as pl

from db.database import get_database
from services.audit import audit_service
from services.databases.db_connection_service import (
    DB_EXTRACT_DIR,
    _decrypt as _decrypt_password,
)
from services.encryption import decrypt_api_key
from services.retries.async_utils import BreakerRegistry, retry_async

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

# Types that use an API key / OAuth token (stored via services/encryption.py)
# vs. types that use a username+password (stored via db_connection_service).
API_KEY_SOURCE_TYPES = frozenset({
    # Verified SaaS sources
    "salesforce",
    "hubspot",
    "shopify",
    "stripe",
    "zendesk",
    "github",
    "notion",
    "slack",
    "airtable",
    "google_analytics",
    "google_ads",
    "facebook_ads",
    "jira",
    "asana",
    "pipedrive",
    "freshdesk",
    "mixpanel",
    # REST API sources
    "linkedin_ads",
    "mailchimp",
    "gitlab",
    "monday",
    "trello",
    "confluence",
    "intercom",
    "woocommerce",
    "klaviyo",
    "marketo",
    "zoho_crm",
    "xero",
    "quickbooks",
    "amplitude",
    "heap",
    "linear",
    # Generic catch-all
    "rest_api",
})

PASSWORD_SOURCE_TYPES = frozenset({
    "postgresql",
    "mysql",
    "snowflake",
    "bigquery",
    "redshift",
})

# Default row limit for dlt extracts (dlt doesn't have a built-in LIMIT, so
# we cap after the fact by reading only the first N rows from the Parquet).
DEFAULT_ROW_LIMIT = 100_000

# Circuit breaker configuration per source type
BREAKER_FAIL_THRESHOLD = 3
BREAKER_RESET_TIMEOUT = 60  # seconds


# ── Exceptions ─────────────────────────────────────────────────────────────


class DltRunError(Exception):
    """Raised when a dlt pipeline run fails."""


# ── Result type ────────────────────────────────────────────────────────────


class DltRunResult:
    """Structured result from a successful dlt pipeline run."""

    def __init__(
        self,
        *,
        dataset_id: str,
        task_id: str,
        rows_extracted: int,
        name: str,
        schema_hash: str,
        message: str,
    ):
        self.dataset_id = dataset_id
        self.task_id = task_id
        self.rows_extracted = rows_extracted
        self.name = name
        self.schema_hash = schema_hash
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "task_id": self.task_id,
            "rows_extracted": self.rows_extracted,
            "name": self.name,
            "schema_hash": self.schema_hash,
            "message": self.message,
        }


# ── Helpers ────────────────────────────────────────────────────────────────


def _discover_parquet_files(directory: Path) -> list[Path]:
    """
    Recursively find all ``.parquet`` files under ``directory``.

    dlt writes Parquet files into subdirectories based on the dataset name
    and table name, so we use a recursive glob.
    """
    return sorted(directory.rglob("*.parquet"))


def _compute_schema_hash(df: pl.DataFrame) -> str:
    """Stable hash of column names for drift detection (same as db_connection_service)."""
    import hashlib

    return hashlib.sha256(json.dumps(sorted(df.columns)).encode()).hexdigest()[:16]


# ── Runner ─────────────────────────────────────────────────────────────────


class DltRunner:
    """
    Orchestrates dlt data pipeline runs within the DataSage backend.

    Each call to ``run_sync``:
      1. Resolves and decrypts credentials (API key or username/password)
      2. Checks the circuit breaker for the source type
      3. Creates a temporary directory for dlt's filesystem destination
      4. Configures dlt via environment variables (no filesystem state)
      5. Calls ``dlt.pipeline(...).run(source)`` in-process
      6. Discovers the output Parquet files
      7. Copies the first Parquet (or concatenated sub-files) to ``db_extracts/``
      8. Creates a dataset record in MongoDB
      9. Fires ``process_dataset()`` in a background task
      10. Logs to audit_service
      11. Records success/failure on the circuit breaker
    """

    def __init__(self):
        self._sources_registry = None  # lazy-imported from sources.py

    @property
    def sources_registry(self):
        if self._sources_registry is None:
            from services.dlt.sources import get_source_registry

            self._sources_registry = get_source_registry()
        return self._sources_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_sync(
        self,
        *,
        user_id: str,
        conn_id: str,
        source_type: str,
        credentials: dict[str, Any],
        dataset_name: str = "",
        incremental: bool = True,
        row_limit: int = DEFAULT_ROW_LIMIT,
        workspace_id: str | None = None,
    ) -> DltRunResult:
        """
        Run a dlt pipeline synchronously (blocking the coroutine until done).

        Args:
            user_id: Owner of the connection.
            conn_id: Saved connection ID (used for pipeline naming, state).
            source_type: Connector type key (e.g. ``"salesforce"``, ``"hubspot"``).
            credentials: Decrypted credentials dict (keys depend on source type).
            dataset_name: Human-readable name for the resulting dataset.
            incremental: If True, uses dlt's incremental loading (merge write
                         disposition). If False, does a full refresh (replace).
            row_limit: Maximum rows to include in the output dataset.
            workspace_id: Tenant (workspace) for the resulting dataset. Falls
                          back to ``user_id`` (personal workspace) when omitted.

        Returns:
            DltRunResult with dataset_id, rows_extracted, etc.

        Raises:
            DltRunError: On pipeline failure.
            ValueError: If source_type is not registered.
        """
        # ── 1. Validate source type ────────────────────────────────────────
        source_factory = self.sources_registry.get(source_type)
        if source_factory is None:
            raise ValueError(f"Unknown source type: {source_type}")

        # ── 2. Circuit breaker ────────────────────────────────────────────
        breaker_name = f"dlt:{source_type}"
        breaker = BreakerRegistry.get(breaker_name)
        if breaker is not None and not breaker.is_allowed():
            raise DltRunError(
                f"dlt source '{source_type}' is circuit-broken (open). "
                "Try again later after the reset timeout."
            )

        _start = time.monotonic()
        dataset_id = str(uuid4())
        error: str | None = None
        rows_extracted = 0
        schema_hash = ""

        # ── 3. Create temp directory for dlt output ────────────────────────
        # dlt writes to a temp directory so we can discover and copy files
        # without interfering with other concurrent pipeline runs.
        with tempfile.TemporaryDirectory(prefix=f"dlt_{conn_id}_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            try:
                # ── 4. Build the dlt source ────────────────────────────────
                source = source_factory(
                    credentials=credentials,
                    incremental=incremental,
                )

                # ── 5. Configure and run dlt pipeline ──────────────────────
                # Use the dlt_environment context manager from config.py
                # to safely manage env vars with proper cleanup.
                # Wrap in retry_async for transient failures (network blips,
                # 429 rate limits from source APIs).
                from services.dlt.config import dlt_environment

                with dlt_environment(destination_path=tmp_dir):
                    load_info = await retry_async(
                        lambda: asyncio.to_thread(
                            self._run_pipeline,
                            conn_id=conn_id,
                            source_type=source_type,
                            source=source,
                            incremental=incremental,
                        ),
                        attempts=3,
                        exceptions=(DltRunError, OSError, ConnectionError, TimeoutError),
                    )

                # ── 6. Discover output Parquet files ───────────────────────
                parquet_files = _discover_parquet_files(tmp_path)
                if not parquet_files:
                    raise DltRunError(
                        f"dlt pipeline completed but no Parquet files found in {tmp_dir}"
                    )

                # ── 7. Read and concatenate Parquet files ──────────────────
                DB_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
                final_parquet_path = str(DB_EXTRACT_DIR / f"{dataset_id}.parquet")

                if len(parquet_files) == 1:
                    # Fast path: single file — just copy
                    shutil.copy2(str(parquet_files[0]), final_parquet_path)
                    df = pl.read_parquet(final_parquet_path)
                else:
                    # Multiple files (dlt may split by load_id) — concat
                    dfs = [pl.read_parquet(f) for f in parquet_files]
                    df = pl.concat(dfs, how="vertical_relaxed")
                    df.write_parquet(final_parquet_path, compression="zstd")

                rows_extracted = min(len(df), row_limit)
                schema_hash = _compute_schema_hash(df)

                # ── 8. Create dataset record in MongoDB ────────────────────
                final_name = (
                    dataset_name
                    or f"{source_type.title()} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
                )

                db = get_database()
                wid = workspace_id or user_id  # tenant tag — personal workspace fallback
                await db.uploads.insert_one({
                    "_id": dataset_id,
                    "user_id": user_id,
                    "workspace_id": wid,
                    "name": final_name,
                    "original_filename": f"{final_name}.parquet",
                    "file_path": final_parquet_path,
                    "file_extension": "parquet",
                    "source_type": "saas_api",
                    "source_db": {
                        "connection_id": conn_id,
                        "source_type": source_type,
                        "incremental": incremental,
                        "row_limit": row_limit,
                    },
                    "schema_hash": schema_hash,
                    "is_processed": False,
                    "is_active": True,
                    "processing_status": "pending",
                    "processing_progress": 0,
                    "artifact_status": {
                        "insights_report": "pending",
                        "dashboard_design": "pending",
                    },
                    "metadata": {},
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                })

                # ── 9. Fire background processing pipeline ─────────────────
                from services.pipeline.process import process_dataset

                asyncio.create_task(
                    process_dataset(
                        dataset_id,
                        final_parquet_path,
                        user_id,
                        workspace_id=wid,
                    )
                )

                # ── 10. Record success on circuit breaker ──────────────────
                if breaker is not None:
                    breaker.record_success()

                _duration = time.monotonic() - _start
                logger.info(
                    "dlt sync complete: source=%s conn=%s rows=%d dataset=%s (%.1fs)",
                    source_type,
                    conn_id[:8],
                    rows_extracted,
                    dataset_id[:8],
                    _duration,
                )

                return DltRunResult(
                    dataset_id=dataset_id,
                    task_id=dataset_id,
                    rows_extracted=rows_extracted,
                    name=final_name,
                    schema_hash=schema_hash,
                    message="Extraction complete. Processing pipeline started.",
                )

            except Exception as exc:
                error = str(exc)[:500]
                _duration = time.monotonic() - _start

                if breaker is not None:
                    breaker.record_failure()

                logger.error(
                    "dlt sync failed: source=%s conn=%s error=%s (%.1fs)",
                    source_type,
                    conn_id[:8],
                    error,
                    _duration,
                )
                raise DltRunError(error) from exc

            finally:
                # ── 11. Audit log (fire-and-forget) ────────────────────────
                _duration = time.monotonic() - _start
                asyncio.ensure_future(
                    audit_service.log_agent_execution(
                        user_id=user_id,
                        agent_type=f"dlt:{source_type}",
                        dataset_id=dataset_id,
                        query=f"sync {source_type} (incremental={incremental})",
                        status="failed" if error else "success",
                        duration_ms=_duration * 1000,
                        error=error,
                        tools_used=[f"dlt:{source_type}"],
                        iterations=0,
                    )
                )

    # ------------------------------------------------------------------
    # Internal: runs dlt pipeline (blocking, called via to_thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_pipeline(
        conn_id: str,
        source_type: str,
        source: Any,
        incremental: bool,
    ) -> Any:
        """
        Execute the dlt pipeline in a thread.

        dlt's pipeline.run() is synchronous and may do blocking I/O.
        We call it via ``asyncio.to_thread()`` to avoid blocking the
        event loop.
        """
        import dlt

        pipeline_name = f"dlt_{conn_id}_{source_type}"

        pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination="filesystem",
            dataset_name=f"{conn_id}_{source_type}",
        )

        load_info = pipeline.run(
            source,
            write_disposition="merge" if incremental else "replace",
        )

        logger.debug(
            "dlt pipeline %s completed: %s",
            pipeline_name,
            load_info,
        )
        return load_info

    # ------------------------------------------------------------------
    # Utility: re-extract (refresh an existing dataset from source)
    # ------------------------------------------------------------------

    async def re_extract_dataset(
        self,
        user_id: str,
        dataset_id: str,
    ) -> DltRunResult:
        """
        Re-extract a dataset from its original dlt source.

        Looks up the dataset's ``source_db`` metadata stored during the
        original extract, then re-runs the dlt pipeline with the same
        configuration. The old Parquet file is replaced.

        Args:
            user_id: Owner of the dataset.
            dataset_id: Existing dataset ID to re-extract.

        Returns:
            DltRunResult for the **new** extract (same dataset_id is reused).
        """
        from services.datasets.enhanced_dataset_service import enhanced_dataset_service

        dataset = await enhanced_dataset_service.get_dataset_doc(dataset_id, user_id)
        if not dataset:
            raise ValueError("Dataset not found")

        source_db = dataset.get("source_db")
        if not source_db:
            raise ValueError("Dataset is not sourced from an API connection")

        conn_id = source_db.get("connection_id")
        source_type = source_db.get("source_type")
        old_incremental = source_db.get("incremental", True)
        old_row_limit = source_db.get("row_limit", DEFAULT_ROW_LIMIT)
        old_name = dataset.get("name", "dataset")

        # Reload credentials from the saved connection
        credentials = await self._load_credentials(user_id, conn_id, source_type)

        # Re-run with the same config but a fresh name
        result = await self.run_sync(
            user_id=user_id,
            conn_id=conn_id,
            source_type=source_type,
            credentials=credentials,
            dataset_name=f"{old_name} (re-extracted)",
            incremental=old_incremental,
            row_limit=old_row_limit,
        )

        # Delete the old Parquet file (best-effort)
        old_path = dataset.get("file_path")
        if old_path:
            try:
                Path(old_path).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to delete old Parquet %s: %s", old_path, exc)

        return result

    # ------------------------------------------------------------------
    # Credential resolution
    # ------------------------------------------------------------------

    async def _load_credentials(
        self,
        user_id: str,
        conn_id: str,
        source_type: str,
    ) -> dict[str, Any]:
        """
        Load and decrypt credentials for a saved connection.

        Delegates to the appropriate decryption method based on source type:
          - API-key-based sources use ``services/encryption.py``
          - Password-based sources use ``db_connection_service._decrypt``

        Returns a plaintext credentials dict ready to pass to the dlt source.
        """
        db = get_database()
        doc = await db.db_connections.find_one({"_id": conn_id, "user_id": user_id})
        if not doc:
            raise ValueError(f"Connection {conn_id} not found")

        if source_type in API_KEY_SOURCE_TYPES:
            # API key / OAuth token stored via encryption service
            encrypted_key = doc.get("api_key_encrypted") or doc.get("token_encrypted")
            if not encrypted_key:
                raise ValueError(
                    f"No encrypted API key found for connection {conn_id}"
                )
            api_key = decrypt_api_key(encrypted_key)
            # Merge stored non-sensitive fields (subdomain, instance_url, account_id,
            # client_id, developer_token, project_id, etc.) so that verified sources
            # (Google Ads, Facebook Ads, Jira, MongoDB, etc.) get all their needed fields.
            stored_fields = dict(doc.get("credentials", {}))
            return {
                "api_key": api_key,
                "token": api_key,
                **stored_fields,
            }

        if source_type in PASSWORD_SOURCE_TYPES:
            # Username + password stored via db_connection_service
            password = _decrypt_password(doc.get("password_encrypted", ""))
            return {
                "host": doc.get("host", ""),
                "port": doc.get("port", 0),
                "database": doc.get("database", ""),
                "username": doc.get("username", ""),
                "password": password,
                "connection_url": doc.get("connection_url", ""),
            }

        # Fallback: return the stored config as-is (best-effort)
        logger.warning(
            "Unknown source type %s for connection %s — returning raw config",
            source_type,
            conn_id,
        )
        return {
            k: doc[k]
            for k in doc
            if k
            not in (
                "_id",
                "user_id",
                "password_encrypted",
                "api_key_encrypted",
                "token_encrypted",
                "created_at",
                "updated_at",
            )
        }
