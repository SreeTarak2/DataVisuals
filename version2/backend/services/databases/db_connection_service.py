"""
Database Connection Service
Handles saving, testing, and extracting from user-connected databases.
Passwords are encrypted at rest using AES-128 (Fernet) derived from SECRET_KEY.
"""

import os
import base64
import hashlib
import logging
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
from services.databases.schema_discovery import SchemaDiscoveryService

logger = logging.getLogger(__name__)

DB_EXTRACT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "db_extracts"


# ---------------------------------------------------------------------------
# Encryption helpers — derive a Fernet key from SECRET_KEY so no new env var
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    raw_key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
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
        conn_id = str(uuid4())

        doc = {
            "_id": conn_id,
            "user_id": user_id,
            "name": name,
            "db_type": config["db_type"],
            "host": config["host"],
            "port": config["port"],
            "database": config["database"],
            "username": config["username"],
            "password_encrypted": _encrypt(config["password"]),
            "ssl_mode": config.get("ssl_mode", "prefer"),
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_used_at": None,
        }

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
        """
        from workers.pipeline.dataset import process_dataset_task

        connector, conn_doc = await self._get_live_connector(user_id, conn_id)
        try:
            # --- Extract ---
            if custom_query:
                rows = await self._extractor.extract_by_query(connector, custom_query)
                rows = rows[:row_limit]
            else:
                rows = await connector.extract_data(table_name=table_name, limit=row_limit)

            if not rows:
                raise ValueError("No data returned from the database query")

            # --- Convert to Polars ---
            df = pl.DataFrame(rows)

            # --- Persist as Parquet ---
            DB_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            dataset_id = str(uuid4())
            parquet_path = str(DB_EXTRACT_DIR / f"{dataset_id}.parquet")
            df.write_parquet(parquet_path, compression="zstd")

            # --- Create dataset record (same structure as file upload) ---
            db = get_database()
            final_name = dataset_name or f"{conn_doc['name']} — {table_name or 'custom query'}"

            await db.uploads.insert_one({
                "_id": dataset_id,
                "user_id": user_id,
                "name": final_name,
                "file_path": parquet_path,
                "source_type": "database",
                "source_db": {
                    "connection_id": conn_id,
                    "db_type": conn_doc["db_type"],
                    "table_name": table_name,
                    "custom_query": custom_query,
                    "row_limit": row_limit,
                },
                "file_type": "parquet",
                "is_processed": False,
                "processing_status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })

            # --- Fire Celery pipeline (identical to file upload) ---
            task = process_dataset_task.delay(dataset_id, parquet_path, user_id)

            await self._touch(conn_id)
            logger.info(f"Extracted {len(df)} rows → dataset {dataset_id} (task {task.id})")

            return {
                "dataset_id": dataset_id,
                "task_id": task.id,
                "rows_extracted": len(df),
                "name": final_name,
                "message": "Extraction complete. Processing pipeline started.",
            }
        finally:
            await self._safe_disconnect(connector)

    # ------------------------------------------------------------------
    # Delete connection
    # ------------------------------------------------------------------

    async def delete_connection(self, user_id: str, conn_id: str) -> None:
        db = get_database()
        result = await db.db_connections.delete_one({"_id": conn_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise ValueError("Connection not found")
        logger.info(f"Deleted DB connection {conn_id} for user {user_id}")

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
            "host": doc["host"],
            "port": doc["port"],
            "database": doc["database"],
            "username": doc["username"],
            "password": _decrypt(doc["password_encrypted"]),
            "ssl_mode": doc.get("ssl_mode", "prefer"),
            "allow_internal": True,
        }

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
