"""
Database Connection Service
Handles saving, testing, and extracting from user-connected databases.
Passwords are encrypted at rest using AES-128 (Fernet) derived from
DB_ENCRYPTION_KEY (separate from the JWT SECRET_KEY, with SECRET_KEY fallback
for backward compatibility during migration).
"""

import asyncio
import json
import os
import base64
import hashlib
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import polars as pl
from cryptography.fernet import Fernet

from core.config import settings
from db.database import get_database
from services.databases.factory import DatabaseConnectorFactory
from services.databases.data_extractor import DataExtractor
from services.databases.schema_discovery import SchemaDiscoveryService, _flatten_document

logger = logging.getLogger(__name__)

DB_EXTRACT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "db_extracts"


# ---------------------------------------------------------------------------
# Module-level helpers for type compatibility & confidence scoring
# ---------------------------------------------------------------------------

# Parquet type compatibility groups — columns in the same group can be
# reasonably compared as FK/PK pairs.
_TYPE_FAMILIES = {
    # NOTE: All members are stored as UPPERCASE because _normalize_type()
    # calls .upper() on the input before matching. Polars exports PascalCase
    # (Int64, Utf8) and SQL connectors export UPPER_CASE (INTEGER, VARCHAR).
    # Both sets are converted to UPPERCASE here for case-insensitive matching.
    "int":    {"INT8", "INT16", "INT32", "INT64", "UINT8", "UINT16", "UINT32", "UINT64", "INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT"},
    "float":  {"FLOAT32", "FLOAT64", "FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC"},
    "text":   {"UTF8", "STRING", "LARGEUTF8", "VARCHAR", "CHAR", "TEXT", "CATEGORY"},
    "binary": {"BINARY", "LARGEBINARY", "BYTEA", "BLOB"},
    "uuid":   {"UUID"},
    "date":   {"DATE", "DATE32", "DATE64", "TIMESTAMP", "TIMESTAMPTZ", "DATETIME", "TIMESTAMPNS", "TIMESTAMPMS"},
}


def _normalize_type(dtype: str) -> str:
    """Map a type string to its family name for compatibility checking."""
    upper = dtype.upper().split("(")[0].split(" ")[0].strip()
    for family, members in _TYPE_FAMILIES.items():
        if upper in members:
            return family
    return "other"


def _types_are_compatible(t1: str, t2: str) -> bool:
    """Return True if two type strings belong to the same family."""
    return _normalize_type(t1) == _normalize_type(t2)


def _compute_confidence(col_a: str, col_b: str, type_a: str, type_b: str, strategy: str) -> float:
    """
    Compute a confidence score (0.0-1.0) for a potential FK→PK relationship.

    Factors:
      - Exact column name match → 0.85 base
      - Entity-based match → 0.65-0.85 based on naming quality
      - Type compatibility → +0.05-0.10
      - Column being "id" on the target side → +0.10
      - Column being "{entity}_id" on the source side → +0.05
    """
    score = 0.5  # baseline

    a_lower = col_a.lower()
    b_lower = col_b.lower()

    if strategy == "exact_match":
        score = 0.85
    elif strategy == "entity_match":
        # Check how good the entity match is
        # "customer_id" → "customers.id" is a strong match
        if b_lower in {"id", "pk", "uid", "uuid"}:
            score = 0.80  # FK → "id" is classic star-schema pattern
        elif a_lower == b_lower:
            score = 0.85
        else:
            score = 0.70

    # Bonus for type compatibility
    if _types_are_compatible(type_a, type_b):
        score += 0.10

    # Bonus: source column ends with _id, target is "id"
    if a_lower.endswith("_id") and b_lower == "id":
        score += 0.05

    return round(min(score, 1.0), 2)


def _score_identifier_likeness(col_name: str) -> float:
    """
    Score how much a column name looks like an identifier (0.0-1.0).

    This prevents false positives where two low-cardinality attribute columns
    (e.g. ``order_status`` ↔ ``customer_segment``) happen to share values.
    Genuine FK→PK relationships nearly always involve at least one column
    with an identifier-like name.

    Scoring:
      - 1.0:  Explicit primary key names (``id``, ``pk``, ``uid``)
      - 0.95: Identifier suffix (``_id``, ``_key``, ``_code``, ``_num``, ``_ref``, ``_sku``)
      - 0.40: Generic business keys (``code``, ``key``, ``ref``, ``sku`` without suffix)
      - 0.60: Neutral (no strong signal either way)
      - 0.15: Heavy attribute words (``status``, ``type``, ``category``, ``segment``,
              ``group``, ``class``, ``grade``, ``rank``)
    """
    lower = col_name.lower().strip()

    # ── Strong identifier signals ───────────────────────────────────────
    if lower in {"id", "pk", "uid", "uuid"}:
        return 1.0

    # Suffix-based identifiers
    if lower.endswith(("_id", "_key", "_code", "_num", "_no", "_ref", "_sku", "_hash", "_token", "_fk")):
        return 0.95

    # Exact match for short identifier names
    if lower in {"code", "key", "ref", "sku", "token"}:
        return 0.40

    # ── Heavy attribute signals — these are NOT identifiers ─────────────
    heavy_attribute_words = {"status", "type", "category", "segment", "group", "class", "grade", "rank"}
    if any(word in lower for word in heavy_attribute_words):
        return 0.15

    # ── Default: neutral ────────────────────────────────────────────────
    return 0.60


# ---------------------------------------------------------------------------
# Encryption helpers — use dedicated DB_ENCRYPTION_KEY (separate from JWT SECRET_KEY)
# Falls back to SECRET_KEY with a loud warning for backward compatibility
# during migration, but requires the dedicated key in production.
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    raw_key_str = settings.DB_ENCRYPTION_KEY or settings.SECRET_KEY
    if not settings.DB_ENCRYPTION_KEY:
        logger.warning(
            "DB_ENCRYPTION_KEY not set — falling back to SECRET_KEY. "
            "Set a separate DB_ENCRYPTION_KEY in .env for production security. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    raw_key = hashlib.sha256(raw_key_str.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw_key))


def _encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DatabaseConnectionService:

    def __init__(self):
        self._extractor = DataExtractor(batch_size=5000)
        self._schema_svc = SchemaDiscoveryService()

    # ------------------------------------------------------------------
    # Test (no save)
    # ------------------------------------------------------------------

    async def test_connection(self, config: Dict) -> Dict:
        """Test a connection without persisting anything."""
        connector = DatabaseConnectorFactory.create_connector(
            config["db_type"],
            {**config, "allow_internal": True},
            validate_config=False,
        )
        if not connector:
            return {"success": False, "message": f"Unsupported type: {config['db_type']}", "response_time_ms": 0.0}

        try:
            result = await connector.test_connection()
            # Attach table count for the UI "sneak peek"
            if result.get("success"):
                try:
                    tables = await connector.get_tables()
                    result["tables_count"] = len(tables)
                except Exception:
                    pass
            return result
        finally:
            try:
                await connector.disconnect()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Save connection
    # ------------------------------------------------------------------

    async def save_connection(self, user_id: str, name: str, config: Dict) -> Dict:
        """Test then persist a connection. Raises ValueError on test failure."""
        test = await self.test_connection(config)
        if not test.get("success"):
            raise ValueError(f"Connection test failed: {test.get('message', 'unknown error')}")

        db = get_database()

        # ── Duplicate detection ────────────────────────────────────────────
        # If the same user saves the same connection (same name + host + db)
        # twice, return the existing record instead of creating a duplicate.
        dup_query = {
            "user_id": user_id,
            "name": name,
            "db_type": config["db_type"],
        }
        if config.get("connection_url"):
            dup_query["connection_url"] = config["connection_url"]
        else:
            dup_query["host"] = config.get("host", "")
            dup_query["database"] = config.get("database", "")

        existing = await db.db_connections.find_one(dup_query)
        if existing:
            logger.info(
                f"Duplicate connection detected for '{name}' — "
                f"returning existing {existing['_id']}"
            )
            return self._safe_doc(existing, str(existing["_id"]))

        conn_id = str(uuid4())

        doc = {
            "_id": conn_id,
            "user_id": user_id,
            "name": name,
            "db_type": config["db_type"],
            "host": config.get("host", ""),
            "port": config.get("port", 0),
            "database": config.get("database", ""),
            "username": config.get("username", ""),
            "ssl_mode": config.get("ssl_mode", "prefer"),
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_used_at": None,
        }

        # Store full connection URL for MongoDB Atlas-style strings (e.g. mongodb+srv://...)
        if config.get("connection_url"):
            doc["connection_url"] = config["connection_url"]
        doc["password_encrypted"] = _encrypt(config.get("password", ""))

        await db.db_connections.insert_one(doc)
        logger.info(f"Saved DB connection '{name}' ({conn_id}) for user {user_id}")

        return self._safe_doc(doc, conn_id)

    # ------------------------------------------------------------------
    # List connections
    # ------------------------------------------------------------------

    async def list_connections(self, user_id: str) -> List[Dict]:
        db = get_database()
        docs = []
        async for doc in db.db_connections.find(
            {"user_id": user_id},
            {"password_encrypted": 0},
        ):
            docs.append(self._safe_doc(doc, str(doc["_id"])))
        return docs

    # ------------------------------------------------------------------
    # Get tables
    # ------------------------------------------------------------------

    async def get_tables(self, user_id: str, conn_id: str) -> List[str]:
        connector, _ = await self._get_live_connector(user_id, conn_id)
        try:
            tables = await self._schema_svc.get_tables(connector)
            await self._touch(conn_id)
            return tables
        finally:
            await self._safe_disconnect(connector)

    # ------------------------------------------------------------------
    # Extract → dataset
    # ------------------------------------------------------------------

    async def extract_to_dataset(
        self,
        user_id: str,
        conn_id: str,
        table_name: Optional[str],
        custom_query: Optional[str],
        dataset_name: Optional[str],
        row_limit: int,
    ) -> Dict:
        """
        Extract rows from the connected DB, save as Parquet, create a dataset
        record, and fire the Celery processing pipeline.

        **Streaming:** For table extracts, chunks of 5 000 rows are fetched via
        ``extract_paginated`` and written to temporary Parquet fragments that
        are then concatenated — no OOM for large tables.

        **Nested documents:** Every row is passed through ``_flatten_document``
        so nested MongoDB/JSON columns survive as dot-notation keys.

        **Schema hash:** A stable ``schema_hash`` (sha256 of column-name→type)
        is stored on the dataset record for drift detection.
        """
        connector, conn_doc = await self._get_live_connector(user_id, conn_id)
        try:
            DB_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            dataset_id = str(uuid4())

            if custom_query:
                # ── Custom query — single-shot, no pagination ──
                rows = await self._extractor.extract_by_query(connector, custom_query)
                rows = rows[:row_limit]
                if not rows:
                    raise ValueError("No data returned from the database query")
                flat = [_flatten_document(r) for r in rows]
                df = pl.from_dicts(flat)
                parquet_path = str(DB_EXTRACT_DIR / f"{dataset_id}.parquet")
                df.write_parquet(parquet_path, compression="zstd")
                total_rows = len(df)
            else:
                # ── Table extract — streaming via pagination ──
                chunk_dir = DB_EXTRACT_DIR / f"{dataset_id}_chunks"
                chunk_dir.mkdir(parents=True, exist_ok=True)

                total_rows = 0
                chunk_files: List[str] = []

                async for batch in self._extractor.extract_paginated(
                    connector, table_name=table_name, page_size=5000
                ):
                    if not batch:
                        break
                    if total_rows >= row_limit:
                        break
                    remaining = row_limit - total_rows
                    if len(batch) > remaining:
                        batch = batch[:remaining]

                    flat_batch = [_flatten_document(r) for r in batch]
                    chunk_df = pl.from_dicts(flat_batch)

                    chunk_path = str(chunk_dir / f"chunk_{total_rows:08d}.parquet")
                    chunk_df.write_parquet(chunk_path, compression="zstd")
                    chunk_files.append(chunk_path)

                    total_rows += len(batch)

                if total_rows == 0:
                    shutil.rmtree(chunk_dir, ignore_errors=True)
                    raise ValueError("No data returned from the database query")

                final_parquet_path = str(DB_EXTRACT_DIR / f"{dataset_id}.parquet")
                if len(chunk_files) == 1:
                    df = chunk_df
                    df.write_parquet(final_parquet_path, compression="zstd")
                else:
                    dfs = [pl.read_parquet(f) for f in chunk_files]
                    df = pl.concat(dfs, how="vertical_relaxed")
                    df.write_parquet(final_parquet_path, compression="zstd")
                parquet_path = final_parquet_path

                shutil.rmtree(chunk_dir, ignore_errors=True)

            schema_hash = hashlib.sha256(
                json.dumps(sorted(df.columns)).encode()
            ).hexdigest()[:16]

            db = get_database()
            final_name = dataset_name or f"{conn_doc['name']} — {table_name or 'custom query'}"

            await db.uploads.insert_one({
                "_id": dataset_id,
                "user_id": user_id,
                "name": final_name,
                "original_filename": f"{final_name}.parquet",
                "file_path": parquet_path,
                "file_extension": "parquet",
                "source_type": "database",
                "source_db": {
                    "connection_id": conn_id,
                    "db_type": conn_doc["db_type"],
                    "table_name": table_name,
                    "custom_query": custom_query,
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
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })

            # ── Fire background processing pipeline ──
            import asyncio as _asyncio
            from services.pipeline.process import process_dataset

            _asyncio.create_task(process_dataset(dataset_id, parquet_path, user_id))

            # ── Auto-refresh relationship cache after extraction ──
            # When a new dataset is extracted from a DB connection, the
            # inferred relationships may now include it. Fire a background
            # refresh so the RelationshipGraph is up-to-date on next load.
            _asyncio.create_task(
                self._refresh_relationship_cache(user_id, conn_id)
            )

            await self._touch(conn_id)
            logger.info(f"Extracted {total_rows} rows → dataset {dataset_id}")

            return {
                "dataset_id": dataset_id,
                "task_id": dataset_id,
                "rows_extracted": total_rows,
                "name": final_name,
                "schema_hash": schema_hash,
                "message": "Extraction complete. Processing pipeline started.",
            }
        finally:
            await self._safe_disconnect(connector)

    # ------------------------------------------------------------------
    # Delete connection
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Schema drift detection
    # ------------------------------------------------------------------

    async def check_schema_drift(
        self, user_id: str, dataset_id: str
    ) -> Dict[str, Any]:
        """
        Compare the schema of the source database table against the schema_hash
        stored when the dataset was extracted.

        Returns:
            {
                "has_drift": bool,
                "stored_hash": str | None,
                "current_hash": str | None,
                "added_columns": ["col"],
                "removed_columns": ["col"],
                "changed_types": {"col": {"was": "Int64", "now": "Float64"}},
            }
        """
        import polars as pl

        db = get_database()
        dataset = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset:
            raise ValueError("Dataset not found")

        source_db = dataset.get("source_db")
        if not source_db:
            return {
                "has_drift": False,
                "stored_hash": None,
                "current_hash": None,
                "message": "Dataset is not sourced from a database connection",
            }

        stored_hash = dataset.get("schema_hash")
        if not stored_hash:
            return {
                "has_drift": False,
                "stored_hash": None,
                "current_hash": None,
                "message": "No schema_hash stored for this dataset (pre-drifting era)",
            }

        conn_id = source_db.get("connection_id")
        table_name = source_db.get("table_name")
        if not conn_id or not table_name:
            return {
                "has_drift": False,
                "stored_hash": stored_hash,
                "current_hash": None,
                "message": "Dataset does not reference a specific table for drift checking",
            }

        # Re-connect to source and get the current schema
        connector, _ = await self._get_live_connector(user_id, conn_id)
        try:
            raw_schema = await connector.get_table_schema(table_name)

            # Build column info from the SQL schema
            current_type_map: Dict[str, str] = {}
            for c in raw_schema:
                col_name = c["name"].replace(".", "_")
                current_type_map[col_name] = c["type"]

            current_col_names = sorted(current_type_map.keys())
            current_hash = hashlib.sha256(
                json.dumps(current_col_names).encode()
            ).hexdigest()[:16]

            has_drift = stored_hash != current_hash

            # Compute what changed (only relevant when drift exists)
            added_columns: List[str] = []
            removed_columns: List[str] = []
            changed_types: Dict[str, Dict[str, str]] = {}

            if has_drift:
                # Load stored column names from Parquet metadata (no data decompression)
                file_path = dataset.get("file_path")
                if file_path:
                    try:
                        parquet_schema = pl.read_parquet_schema(file_path)
                        stored_cols = set(parquet_schema.keys())
                    except Exception:
                        # Fallback: read just the first row
                        try:
                            stored_df = pl.read_parquet(file_path, n_rows=1)
                            stored_cols = set(stored_df.columns)
                            parquet_schema = stored_df.schema
                        except Exception:
                            stored_cols = set()
                            parquet_schema = {}

                    current_cols = set(current_col_names)
                    added_columns = sorted(current_cols - stored_cols)
                    removed_columns = sorted(stored_cols - current_cols)

                    # Detect type changes (best-effort) — Parquet schema vs SQL type
                    for col in sorted(current_cols & stored_cols):
                        stored_type = str(parquet_schema[col]) if col in parquet_schema else None
                        current_type = current_type_map.get(col)
                        if stored_type and current_type and stored_type.lower() != current_type.lower():
                            type_family_current = current_type.lower().split(" ")[0].split("(")[0]
                            type_family_stored = stored_type.lower().split(" ")[0].split("(")[0]
                            if type_family_current != type_family_stored:
                                changed_types[col] = {"was": stored_type, "now": current_type}

            return {
                "has_drift": has_drift,
                "stored_hash": stored_hash,
                "current_hash": current_hash,
                "added_columns": added_columns,
                "removed_columns": removed_columns,
                "changed_types": changed_types,
            }
        finally:
            await self._safe_disconnect(connector)

    # ------------------------------------------------------------------
    # Re-extract (refresh dataset from source)
    # ------------------------------------------------------------------

    async def re_extract_dataset(
        self, user_id: str, dataset_id: str
    ) -> Dict[str, Any]:
        """
        Re-extract a DB-sourced dataset from its original source.
        Deletes the old Parquet file, creates a new snapshot, fires the
        Celery pipeline, and returns the new dataset info.
        """
        db = get_database()
        dataset = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})
        if not dataset:
            raise ValueError("Dataset not found")

        source_db = dataset.get("source_db")
        if not source_db:
            raise ValueError("Dataset is not sourced from a database connection — cannot re-extract")

        table_name = source_db.get("table_name")
        custom_query = source_db.get("custom_query")
        row_limit = source_db.get("row_limit", 100_000)
        old_name = dataset.get("name", "dataset")

        # Re-extract using the same source_db config
        result = await self.extract_to_dataset(
            user_id=user_id,
            conn_id=source_db["connection_id"],
            table_name=table_name,
            custom_query=custom_query,
            dataset_name=f"{old_name} (re-extracted)",
            row_limit=row_limit,
        )

        # Delete the old Parquet file (best-effort — not a failure if it fails)
        old_path = dataset.get("file_path")
        if old_path:
            try:
                Path(old_path).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning(f"Failed to delete old Parquet {old_path}: {exc}")

        logger.info(
            f"Re-extracted dataset {dataset_id} → {result['dataset_id']} "
            f"({result['rows_extracted']} rows)"
        )
        return result

    # ------------------------------------------------------------------
    # Get foreign keys from a saved connection
    # ------------------------------------------------------------------

    async def get_foreign_keys(
        self, user_id: str, conn_id: str, refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Query the connected database for declared foreign key constraints
        AND infer cross-dataset relationships from column name + type matching.

        Tier 1: Queries the live DB for explicit FK constraints via
        ``connector.get_foreign_keys()``, caches them in MongoDB.

        Tier 2 + 3: Infers relationships across datasets via name matching
        and value-overlap sampling. Results are cached in MongoDB so they
        don't recompute on every page load.

        Args:
            user_id: Owner of the connection.
            conn_id: Saved connection ID.
            refresh: If True, bypass all caches and re-compute from scratch.

        Returns:
            {
                "connection_id": conn_id,
                "db_type": ... ,
                "foreign_keys": [ ... declared FK constraints ... ],
                "count": 3,
                "cached": True/False,
                "inferred": [ ... inferred relationships ... ],
                "inferred_count": 2,
            }
        """
        db = get_database()

        fks = []
        inferred = []
        db_type = ""
        cached = False

        # ── Check cache (unless refresh requested) ────────────────────────
        if not refresh:
            existing = await db.db_relationships.find_one(
                {"connection_id": conn_id, "user_id": user_id}
            )

            if existing:
                db_type = existing.get("db_type", "")

                if existing.get("foreign_keys"):
                    fks = existing["foreign_keys"]

                if existing.get("inferred"):
                    inferred = existing["inferred"]
                    cached = True
                    logger.info(
                        f"Returning {len(fks)} FK + {len(inferred)} inferred relationships "
                        f"from cache for conn {conn_id}"
                    )

        # ── Cache miss or refresh: re-query live DB ───────────────────────
        if not cached or refresh:
            # Connect and query live for FK constraints
            connector, conn_doc = await self._get_live_connector(user_id, conn_id)
            try:
                fks = await connector.get_foreign_keys()
                db_type = conn_doc["db_type"]
                logger.info(f"Discovered {len(fks)} foreign keys for conn {conn_id}")
            finally:
                await self._safe_disconnect(connector)

            # Run cross-dataset inference (Tier 2 + Tier 3)
            inferred = await self.infer_cross_dataset_relationships(user_id, conn_id)

            # Store everything in MongoDB for persistence
            await db.db_relationships.update_one(
                {"connection_id": conn_id, "user_id": user_id},
                {
                    "$set": {
                        "connection_id": conn_id,
                        "user_id": user_id,
                        "db_type": db_type,
                        "foreign_keys": fks,
                        "inferred": inferred,
                        "discovered_at": datetime.utcnow(),
                    }
                },
                upsert=True,
            )

            # Update FK count on connection doc for quick display
            await db.db_connections.update_one(
                {"_id": conn_id},
                {"$set": {"foreign_key_count": len(fks)}},
            )

            cached = False

        return {
            "connection_id": conn_id,
            "db_type": db_type,
            "foreign_keys": fks,
            "count": len(fks),
            "cached": cached,
            "inferred": inferred,
            "inferred_count": len(inferred),
        }

    # ------------------------------------------------------------------
    # Delete connection
    # ------------------------------------------------------------------

    async def delete_connection(self, user_id: str, conn_id: str) -> None:
        db = get_database()
        result = await db.db_connections.delete_one({"_id": conn_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise ValueError("Connection not found")

        # Also clean up cached relationships
        await db.db_relationships.delete_many({"connection_id": conn_id, "user_id": user_id})

        logger.info(f"Deleted DB connection {conn_id} for user {user_id}")

    # ------------------------------------------------------------------
    # Cross-dataset relationship inference (Tier 2 + Tier 3)
    # Detects relationships between tables extracted from the same connection
    # by matching column names, types, cardinality patterns, and value overlap.
    # ------------------------------------------------------------------

    async def _refresh_relationship_cache(self, user_id: str, conn_id: str) -> None:
        """
        Re-compute and cache inferred relationships for a connection.

        Called as a background task after dataset extraction so the
        RelationshipGraph is immediately up-to-date.
        """
        try:
            inferred = await self.infer_cross_dataset_relationships(user_id, conn_id)
            db = get_database()
            await db.db_relationships.update_one(
                {"connection_id": conn_id, "user_id": user_id},
                {"$set": {"inferred": inferred, "discovered_at": datetime.utcnow()}},
            )
            logger.info(f"Refreshed relationship cache for conn {conn_id}: {len(inferred)} inferred")
        except Exception as e:
            logger.warning(f"Failed to refresh relationship cache for conn {conn_id}: {e}")

    async def infer_cross_dataset_relationships(
        self, user_id: str, conn_id: str
    ) -> List[Dict[str, Any]]:
        """
        Scan all datasets extracted from the given connection and infer
        relationships between them using three strategies:

        **Tier 2 — Name-based matching:**
          1. Find all datasets belonging to this connection
          2. Load Parquet schemas (column names + types) — metadata only =
             no data decompression
          3. For each pair of tables, look for matching column name patterns:
             a. Direct name match (both have "customer_id")
             b. Entity match: "orders.customer_id" → "customers.id"
          4. Verify type compatibility (both integer, both UUID, etc.)

        **Tier 3 — Value-overlap sampling (NEW):**
          5. For FK-like columns that didn't match by name, sample unique values
             from the actual Parquet data and check for value overlap with
             PK-like columns in other tables.
          6. High overlap (FK values found in PK) → strong data-level evidence
             even when column names don't match.

        Returns:
            List of inferred relationship dicts:
              {
                "source_table": str,
                "source_column": str,
                "target_table": str,
                "target_column": str,
                "confidence": float (0.0-1.0),
                "method": "name_match" | "value_overlap",
                "overlap_ratio": float | None,  # only for value_overlap
                "fk_sample_size": int | None,   # only for value_overlap
              }
        """
        db = get_database()

        # 1. Find all datasets from this connection
        cursor = db.uploads.find(
            {
                "user_id": user_id,
                "source_type": "database",
                "source_db.connection_id": conn_id,
                "file_path": {"$exists": True, "$ne": None},
            },
            {
                "_id": 1,
                "name": 1,
                "file_path": 1,
                "source_db.table_name": 1,
                "source_db.custom_query": 1,
            }
        )

        datasets = []
        async for doc in cursor:
            table_name = doc.get("source_db", {}).get("table_name") or doc.get("name", "unknown")
            datasets.append({
                "dataset_id": doc["_id"],
                "name": doc.get("name", "unknown"),
                "table_name": table_name,
                "file_path": doc.get("file_path"),
            })

        if len(datasets) < 2:
            return []

        table_schemas = {}
        for ds in datasets:
            fp = ds["file_path"]
            if not fp or not os.path.exists(fp):
                continue
            try:
                parquet_schema = pl.read_parquet_schema(fp)
                table_schemas[ds["table_name"]] = {
                    col: str(dtype) for col, dtype in parquet_schema.items()
                }
            except Exception as e:
                logger.warning(f"Failed to read Parquet schema for {ds['table_name']}: {e}")
                continue

        if len(table_schemas) < 2:
            return []

        return await self._infer_from_datasets(datasets, table_schemas)

    async def _infer_from_datasets(
        self,
        datasets: List[Dict[str, Any]],
        table_schemas: Dict[str, Dict[str, str]],
        pk_sample_coverage: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Core cross-table inference logic. Takes dataset metadata + schemas
        directly, with no MongoDB dependency. Usable from both the production
        pipeline and the benchmark suite.

        Args:
            datasets: List of dataset dicts with keys ``dataset_id``,
                ``name``, ``table_name``, ``file_path``.
            table_schemas: Dict mapping ``table_name`` to ``{col: type}``.
            pk_sample_coverage: Minimum ratio of ``|PK_uniques| / |FK_uniques|``
                for the cardinality-gap guard. Default 1.0 (strict: PK must
                have at least as many values as the FK). Lower values (e.g.
                0.8) relax the guard for cases where the PK sample may not
                capture all unique values due to sampling limits.

        Tier 2: Name-based matching.
        Tier 3: Value-overlap sampling.
        """
        # Build inverse map: normalized column name -> list of (table_name, column_name, type)
        col_index = {}  # normalized_base -> [(table, column, type)]
        for tbl_name, cols in table_schemas.items():
            for col_name, col_type in cols.items():
                # Normalize: lowercase, strip _id suffix for matching
                normalized = col_name.lower().replace("_", " ").strip()
                base = normalized.replace("_id", "").replace(" id", "").strip()

                if base not in col_index:
                    col_index[base] = []
                col_index[base].append((tbl_name, col_name, col_type))

                # Also index by the raw column name
                raw_lower = col_name.lower()
                if raw_lower not in col_index:
                    col_index[raw_lower] = []
                col_index[raw_lower].append((tbl_name, col_name, col_type))

        # 4. Find matching pairs — Tier 2: Name-based matching
        table_names = list(table_schemas.keys())
        inferred = []
        seen_pairs = set()

        # ID suffix pattern: _id, _key, _fk, _ref
        id_suffix = re.compile(r"(_id|_key|_fk|_ref)$", re.I)
        # Common PK column names
        pk_names = {"id", "pk", "row_id", "record_id", "uid", "uuid"}

        for tbl_a in table_names:
            for col_a, type_a in table_schemas[tbl_a].items():
                col_a_lower = col_a.lower()

                # Check if this column looks like an FK (ends with _id)
                m = id_suffix.search(col_a_lower)
                if not m:
                    continue

                # Extract the entity name (e.g., "customer_id" -> "customer")
                entity_base = col_a_lower[:m.start()].replace("_", " ").strip()

                # Look for match candidates in other tables
                for tbl_b in table_names:
                    if tbl_b == tbl_a:
                        continue

                    pair_key = f"{tbl_a}:{col_a}->{tbl_b}"
                    if pair_key in seen_pairs:
                        continue

                    # Strategy A: Look for a column with the same name in table B
                    if col_a_lower in col_index:
                        for (other_tbl, other_col, other_type) in col_index[col_a_lower]:
                            if other_tbl != tbl_a and other_tbl == tbl_b:
                                if _types_are_compatible(type_a, other_type):
                                    conf = _compute_confidence(col_a, other_col, type_a, other_type, "exact_match")
                                    inferred.append({
                                        "source_table": tbl_a,
                                        "source_column": col_a,
                                        "target_table": tbl_b,
                                        "target_column": other_col,
                                        "confidence": conf,
                                        "method": "name_match",
                                    })
                                    seen_pairs.add(pair_key)
                                    break

                    # Strategy B: Look for matching columns by entity name
                    # e.g., "orders.customer_id" -> "customers.id" or "customers.customer_id"
                    # by checking if table_b name contains the entity name or vice versa
                    if pair_key not in seen_pairs:
                        tbl_b_lower = tbl_b.lower()
                        entity_in_tbl = entity_base in tbl_b_lower or tbl_b_lower in entity_base

                        if entity_in_tbl:
                            # Look for PK-like columns in table B
                            for col_b, type_b in table_schemas[tbl_b].items():
                                col_b_lower = col_b.lower()
                                # Match if: same name, or "id", or "{entity}_id" in target
                                is_pk = col_b_lower in pk_names
                                is_same_name = col_a_lower == col_b_lower
                                is_entity_match = (
                                    entity_base in col_b_lower
                                    or col_b_lower.replace("_id", "").replace(" id", "").strip() == entity_base
                                )

                                if (is_pk or is_same_name or is_entity_match) and _types_are_compatible(type_a, type_b):
                                    conf = _compute_confidence(col_a, col_b, type_a, type_b, "entity_match")
                                    if conf >= 0.55:
                                        inferred.append({
                                            "source_table": tbl_a,
                                            "source_column": col_a,
                                            "target_table": tbl_b,
                                            "target_column": col_b,
                                            "confidence": conf,
                                            "method": "name_match",
                                        })
                                        seen_pairs.add(pair_key)
                                        break

        # 5. Tier 3: Value-overlap sampling for unmatched FK-like columns
        # When names don't match, we check if the actual data values overlap
        overlap_inferred = await self._detect_value_overlap_relationships(
            datasets=datasets,
            table_schemas=table_schemas,
            existing_pairs=seen_pairs,
            pk_sample_coverage=pk_sample_coverage,
        )
        inferred.extend(overlap_inferred)

        # Deduplicate and sort by confidence
        seen_dedup = set()
        unique_inferred = []
        for r in sorted(inferred, key=lambda x: -x["confidence"]):
            dedup_key = (r["source_table"], r["target_table"])
            if dedup_key not in seen_dedup:
                seen_dedup.add(dedup_key)
                unique_inferred.append(r)

        logger.info(
            f"Inferred {len(unique_inferred)} cross-dataset relationships "
            f"({len(overlap_inferred)} via value overlap)"
        )
        return unique_inferred

    # ------------------------------------------------------------------
    # Tier 3: Value-overlap sampling
    # Detect relationships by sampling actual data values and computing
    # overlap ratios between FK-like and PK-like columns.
    # This catches relationships that name matching misses entirely.
    # ------------------------------------------------------------------

    @staticmethod
    async def _sample_unique_values(file_path: str, column: str, max_rows: int = 5000, sample_limit: int = 500) -> set:
        """
        Read unique values from a Parquet column efficiently.

        Strategy:
          1. Read only the target column from the Parquet file (columnar =
             fast, skips all other columns)
          2. Read at most ``max_rows`` rows to avoid OOM on large tables
          3. Compute unique values and cap at ``sample_limit``

        Uses ``asyncio.to_thread()`` to avoid blocking the event loop on I/O.

        Returns a set of hashable values (int, str, float, etc.). Empty set
        if the column doesn't exist or can't be read.
        """
        try:
            def _read():
                df = pl.read_parquet(file_path, columns=[column], n_rows=max_rows)
                if df.is_empty():
                    return set()
                series = df[column]
                unique_series = series.drop_nulls().unique()
                if len(unique_series) > sample_limit:
                    unique_series = unique_series[:sample_limit]
                return set(unique_series.to_list())

            return await asyncio.to_thread(_read)
        except Exception as e:
            logger.debug(f"Failed to sample values from {file_path}:{column} — {e}")
            return set()

    async def _detect_value_overlap_relationships(
        self,
        datasets: List[Dict[str, Any]],
        table_schemas: Dict[str, Dict[str, str]],
        existing_pairs: set,
        pk_sample_coverage: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect FK→PK relationships by sampling actual data values and
        checking for value overlap between columns.

        Only checks column pairs that aren't already in ``existing_pairs``.
        Uses data-level evidence (value overlap ratio) as the primary
        confidence signal, so it can detect relationships even when
        column names are completely different.

        Args:
            datasets: List of dataset dicts with ``file_path`` and ``table_name``.
            table_schemas: Dict mapping ``table_name`` to ``{col: type}``.
            existing_pairs: Set of ``{tbl}:{col}->{tbl}`` pair keys already
                matched by name-matching (Tier 2).
            pk_sample_coverage: Minimum ``|PK_uniques| / |FK_uniques|`` ratio.
                Default 1.0 (strict). Relaxing this (e.g. 0.8) tolerates
                cases where the 5K-row PK sample undercounts true cardinality.
                Set to 0.0 to disable the cardinality-gap guard entirely.

        Algorithm:
          1. Identify FK-like columns (_id/_key/_fk/_ref suffix) in every table
          2. Identify PK-like columns (id, pk, uid, uuid, or high-cardinality
             unique columns) in every table
          3. For each FK→PK pair that wasn't matched by name:
             a. Check type compatibility
             b. Sample unique values from both columns (max 5K rows → 500 uniques)
             c. Compute overlap_ratio = |FK_values ∩ PK_values| / |FK_values|
             d. If overlap_ratio >= 0.3 and at least 3 values overlap → emit
        """
        if len(table_schemas) < 2:
            return []

        id_suffix = re.compile(r"(_id|_key|_fk|_ref)$", re.I)
        pk_names = {"id", "pk", "uid", "uuid", "_id"}

        # ── Phase 1: Classify columns ───────────────────────────────────
        # Build table_name → file_path lookup
        fp_by_table = {ds["table_name"]: ds["file_path"] for ds in datasets if ds.get("file_path")}

        # FK-like columns per table (columns ending in _id/_key/_fk/_ref)
        fk_cols_by_table: Dict[str, List[tuple]] = {}
        # PK-like columns per table (id, pk, uid, uuid, or _id)
        pk_cols_by_table: Dict[str, List[tuple]] = {}

        for tbl_name, cols in table_schemas.items():
            fk_list = []
            pk_list = []
            for col_name, col_type in cols.items():
                col_lower = col_name.lower()
                if id_suffix.search(col_lower):
                    fk_list.append((col_name, col_type))
                if col_lower in pk_names or col_lower == "id":
                    pk_list.append((col_name, col_type))                    # If a table has no explicit "id" column, use up to 5 string/int/uuid columns
            # as PK candidates (they might be natural keys). Prefer columns whose names
            # suggest they are identifiers (code, key, num, ref, no, sku).
            if not pk_list:
                fallback = []
                priority_words = {"code", "key", "num", "ref", "no", "sku", "hash", "token"}
                for col_name, col_type in cols.items():
                    if _normalize_type(col_type) in {"int", "text", "uuid"}:
                        col_lower = col_name.lower()
                        # Score: higher = more likely to be a natural key
                        score = 0
                        if any(w in col_lower for w in priority_words):
                            score = 2
                        elif col_lower.endswith("_id") or col_lower.endswith("_key"):
                            score = 1
                        fallback.append((score, col_name, col_type))
                # Sort by score descending, then name, take top 5
                fallback.sort(key=lambda x: (-x[0], x[1]))
                for _, col_name, col_type in fallback[:5]:
                    pk_list.append((col_name, col_type))
            fk_cols_by_table[tbl_name] = fk_list
            pk_cols_by_table[tbl_name] = pk_list

        # ── Phase 2: Check overlap for each FK→PK pair ──────────────────
        inferred = []
        table_names = list(table_schemas.keys())

        for tbl_a in table_names:
            fk_candidates = fk_cols_by_table.get(tbl_a, [])
            if not fk_candidates:
                continue

            for tbl_b in table_names:
                if tbl_a == tbl_b:
                    continue

                pk_candidates = pk_cols_by_table.get(tbl_b, [])
                if not pk_candidates:
                    continue

                fp_a = fp_by_table.get(tbl_a)
                fp_b = fp_by_table.get(tbl_b)
                if not fp_a or not fp_b:
                    continue

                for fk_col, fk_type in fk_candidates:
                    pair_key = f"{tbl_a}:{fk_col}->{tbl_b}"
                    if pair_key in existing_pairs:
                        continue

                    for pk_col, pk_type in pk_candidates:
                        if not _types_are_compatible(fk_type, pk_type):
                            continue

                        # Sample unique values from both columns
                        fk_values = await self._sample_unique_values(fp_a, fk_col)
                        pk_values = await self._sample_unique_values(fp_b, pk_col)

                        if not fk_values or not pk_values:
                            continue

                        # ── Compute overlap ────────────────────────────
                        # Need enough samples to make meaningful inference
                        if len(fk_values) < 5:
                            continue

                        # ── Cardinality-gap guard (configurable) ──────────
                        # In a valid FK→PK relationship every FK value must
                        # exist in the PK. If PK has *fewer* unique values
                        # than the FK, some FK values can't possibly reference
                        # valid PK rows — the relationship is impossible.
                        #
                        # ``pk_sample_coverage`` lets users relax this guard for
                        # cases where the 5K-row PK sample undercounts true
                        # cardinality. Set to 0.0 to disable entirely.
                        if pk_sample_coverage > 0 and len(pk_values) < len(fk_values) * pk_sample_coverage:
                            continue

                        # overlap_ratio = fraction of FK values present in PK
                        overlap = fk_values & pk_values
                        if len(overlap) < 3:
                            # Need at least 3 matching values to be confident
                            continue

                        overlap_ratio = len(overlap) / len(fk_values)

                        if overlap_ratio >= 0.3:
                            # Data-driven confidence: 0.5 base + overlap bonus
                            # Max 0.95 to leave room for uncertainty
                            raw_confidence = 0.5 + overlap_ratio * 0.45

                            # Apply identifier-likeness multiplier
                            # Attribute-like columns (status, type, category) get
                            # heavily penalized — they can share values by coincidence
                            fk_likeness = _score_identifier_likeness(fk_col)
                            pk_likeness = _score_identifier_likeness(pk_col)
                            combined_likeness = (fk_likeness * pk_likeness) ** 0.5  # geometric mean

                            # Multiplier: 0.15 floor prevents complete crushing,
                            # but attribute-only pairs get ~0.02 final confidence
                            likeness_multiplier = max(0.15, combined_likeness)

                            # ── Fix (2): Bare-id + low-cardinality penalty ──
                            # When neither side is a bare `id`/`pk`/`uid`/`uuid`
                            # column (identifier-likeness < 1.0), the relationship
                            # is between two suffixed columns (e.g. status_id →
                            # customer_id). These are suspicious because:
                            #   - A genuine PK is almost always bare `id`
                            #   - Low-cardinality FK columns are often enums
                            #     disguised as FK columns
                            #
                            # Apply a penalty proportional to how few unique
                            # values the FK has. A low-cardinality FK with no
                            # bare `id` on either side is likely an attribute
                            # (status_id, type_id) whose values happen to
                            # overlap with another table by coincidence.
                            if fk_likeness < 1.0 and pk_likeness < 1.0:
                                fk_cardinality_factor = min(1.0, len(fk_values) / 50)
                                likeness_multiplier *= max(0.1, fk_cardinality_factor)

                            confidence = round(min(raw_confidence * likeness_multiplier, 0.95), 2)

                            inferred.append({
                                "source_table": tbl_a,
                                "source_column": fk_col,
                                "target_table": tbl_b,
                                "target_column": pk_col,
                                "confidence": confidence,
                                "method": "value_overlap",
                                "overlap_ratio": round(overlap_ratio, 3),
                                "fk_sample_size": len(fk_values),
                            })
                            existing_pairs.add(pair_key)
                            break  # One relationship per FK→table pair

        logger.info(f"Value-overlap detection found {len(inferred)} relationships")
        return inferred

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _get_live_connector(self, user_id: str, conn_id: str):
        """Load connection from DB, decrypt password, connect, return connector + doc."""
        db = get_database()
        doc = await db.db_connections.find_one({"_id": conn_id, "user_id": user_id})
        if not doc:
            raise ValueError("Connection not found")

        config = {
            "db_type": doc["db_type"],
            "host": doc.get("host", ""),
            "port": doc.get("port", 0),
            "database": doc.get("database", ""),
            "username": doc.get("username", ""),
            "password": _decrypt(doc.get("password_encrypted", "")),
            "ssl_mode": doc.get("ssl_mode", "prefer"),
            "allow_internal": True,
        }

        # Restore full connection URL for MongoDB Atlas-style strings
        if doc.get("connection_url"):
            config["connection_url"] = doc["connection_url"]

        connector = DatabaseConnectorFactory.create_connector(
            doc["db_type"], config, validate_config=False
        )
        if not connector:
            raise ValueError(f"Unsupported database type: {doc['db_type']}")

        connected = await connector.connect()
        if not connected:
            raise RuntimeError("Could not connect to database. Check credentials and network.")

        return connector, doc

    async def _touch(self, conn_id: str) -> None:
        db = get_database()
        await db.db_connections.update_one(
            {"_id": conn_id},
            {"$set": {"last_used_at": datetime.utcnow()}},
        )

    @staticmethod
    async def _safe_disconnect(connector) -> None:
        try:
            await connector.disconnect()
        except Exception:
            pass

    @staticmethod
    def _safe_doc(doc: Dict, conn_id: str) -> Dict:
        """Return a connection dict safe to send to the frontend (no password)."""
        return {
            "connection_id": conn_id,
            "name": doc.get("name"),
            "db_type": doc.get("db_type"),
            "host": doc.get("host"),
            "port": doc.get("port"),
            "database": doc.get("database"),
            "username": doc.get("username"),
            "status": doc.get("status", "active"),
            "created_at": doc.get("created_at"),
            "last_used_at": doc.get("last_used_at"),
        }


db_connection_service = DatabaseConnectionService()
