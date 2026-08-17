import uuid
import hashlib
import tempfile
import shutil
from datetime import datetime, timezone
import logging
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from bson import ObjectId

from db.database import get_database
from db.tenant_guard import enforce_workspace_filter, tenant_scope_query
from core.config import settings
from utils.json_encoder import ensure_json_serializable
from services.datasets.file_storage_service import file_storage_service
from services.datasets.faiss_vector_service import faiss_vector_service
from services.cache import cache_service

# Note: process_dataset_task imported lazily to avoid circular imports
from services.datasets import dataset_loader
from services.datasets.dataset_loader import load_dataset_s3_lazy

logger = logging.getLogger(__name__)


class EnhancedDatasetService:
    """
    Manages the lifecycle of dataset metadata records in the database.
    This service does NOT perform file I/O or heavy computation itself;
    it delegates those tasks to file_storage_service and Celery workers.
    """

    def __init__(self):
        """Initialize the enhanced dataset service."""
        pass

    @property
    def db(self):
        """Lazily gets the database connection on first access."""
        db_conn = get_database()
        if db_conn is None:
            raise Exception("Database is not connected. Application startup may have failed.")
        return db_conn

    async def _effective_workspace(self, workspace_id: str | None, user_id: str) -> str:
        """
        Resolve the workspace to scope a read/write with.

        Uses the explicit ``workspace_id`` when provided; otherwise resolves the
        user's personal workspace (the canonical tag the backfill migration
        wrote on all legacy documents). This is what lets legacy callers that
        predate workspace threading keep working under strict workspace scoping.
        """
        from services.workspace import workspace_service

        return await workspace_service.resolve_effective_workspace_id(
            workspace_id, user_id
        )

    def _generate_content_hash(self, file_content: bytes) -> str:
        """
        Generate a SHA-256 hash of the file content for duplicate detection.

        Args:
            file_content: The raw file content as bytes

        Returns:
            str: SHA-256 hash of the content
        """
        return hashlib.sha256(file_content).hexdigest()

    async def _check_duplicate_dataset(
        self,
        content_hash: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Optional[Dict]:
        """
        Check if a dataset with the same content hash already exists in the
        caller's workspace.

        Args:
            content_hash: SHA-256 hash of the file content
            user_id: User ID to check duplicates for
            workspace_id: Optional tenant scope; falls back to the user's
                personal workspace when omitted.

        Returns:
            Optional[Dict]: Existing dataset if found, None otherwise
        """
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            # Failed datasets don't count as duplicates: the previous pipeline
            # run never produced a usable dataset, so re-uploading the same file
            # should be allowed (a fresh attempt) instead of returning 409 and
            # pointing the user at an invisible failed record.
            existing_dataset = await self.db.uploads.find_one(
                tenant_scope_query(
                    "uploads",
                    {
                        "content_hash": content_hash,
                        "is_active": True,
                        "processing_status": {"$ne": "failed"},
                    },
                    wid,
                    user_id,
                )
            )

            if existing_dataset:
                existing_dataset["id"] = str(existing_dataset["_id"])
                existing_dataset.pop("_id", None)
                # Sanitize datetime & other non-serializable types for JSON response
                return ensure_json_serializable(existing_dataset)

            return None
        except Exception as e:
            logger.error(f"Error checking for duplicate dataset: {e}")
            return None

    async def upload_dataset(
        self,
        file: UploadFile,
        user_id: str,
        name: str = None,
        description: str = None,
        analysis_intent: str = None,
        workspace_id: str | None = None,
        user_doc: dict | None = None,
    ) -> JSONResponse:
        """
        Handles the initial upload request with validation and duplicate detection.

        Security checks:
        1. Validates file extension against whitelist
        2. Enforces file size limit with chunked reading (prevents memory exhaustion)
        3. Streams file to disk while computing hash (constant memory usage)
        4. Checks if identical dataset already exists
        5. If new, moves file and creates dataset record
        6. Dispatches background task for processing
        """
        temp_path = None
        try:
            # --- VALIDATION: File Extension ---
            if not file.filename:
                raise HTTPException(status_code=400, detail="Filename is required")

            file_ext = Path(file.filename).suffix.lower().lstrip(".")
            if file_ext not in settings.ALLOWED_FILE_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: .{file_ext}. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}",
                )

            # --- STREAMING UPLOAD: Write to temp file + compute hash incrementally ---
            # This uses constant ~1MB memory regardless of file size (vs accumulating entire file)
            # The effective limit is the pricing-tier limit capped by the
            # pipeline memory-safety ceiling (see services/datasets/size_limits.py).
            from services.datasets.size_limits import (
                effective_size_limit_bytes,
                effective_size_limit_mb,
                resolve_user_tier,
                size_limit_error_message,
            )

            tier = resolve_user_tier(user_doc)
            tier_limit_mb = effective_size_limit_mb(tier=tier)
            max_size = effective_size_limit_bytes(tier=tier)
            chunk_size = 1024 * 1024  # 1MB chunks
            hasher = hashlib.sha256()
            total_size = 0

            # Resolve the tenant boundary up-front so the dataset doc is tagged
            # with the correct workspace from the moment it is created.
            wid = await self._effective_workspace(workspace_id, user_id)

            temp_fd, temp_path = tempfile.mkstemp(suffix=f".{file_ext}")
            try:
                import os as _os

                with _os.fdopen(temp_fd, "wb") as tmp_file:
                    while True:
                        chunk = await file.read(chunk_size)
                        if not chunk:
                            break
                        total_size += len(chunk)
                        if total_size > max_size:
                            raise HTTPException(
                                status_code=413,
                                detail=size_limit_error_message(
                                    total_size / (1024 * 1024),
                                    tier_limit_mb,
                                    tier,
                                ),
                            )
                        hasher.update(chunk)
                        tmp_file.write(chunk)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error during file upload: {str(e)}")

            if total_size == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")

            # --- TIER SIZE LIMIT (already enforced during streaming above) ---
            # The streaming loop rejects over-limit files as soon as the byte
            # count crosses the effective (tier-capped) limit, so a file that
            # passes upload is guaranteed to fit the pipeline's memory ceiling.
            # The effective limit is recorded on the dataset doc so the
            # background pipeline can re-check without re-resolving the tier.
            effective_limit_mb = tier_limit_mb

            # --- DUPLICATE DETECTION ---
            content_hash = hasher.hexdigest()
            existing_dataset = await self._check_duplicate_dataset(
                content_hash, user_id, workspace_id=wid
            )

            if existing_dataset:
                logger.info(
                    f"Duplicate dataset detected for user {user_id}. Existing dataset: {existing_dataset['id']}"
                )
                return JSONResponse(
                    status_code=409,
                    content={
                        "is_duplicate": True,
                        "existing_dataset": existing_dataset,
                        "message": "Dataset with identical content already exists.",
                    },
                )

            # Move temp file to permanent storage
            file_metadata = await file_storage_service.save_file_from_path(
                temp_path, file.filename, user_id
            )
            temp_path = None  # File has been moved, don't delete in finally

            dataset_id = str(uuid.uuid4())

            dataset_doc = {
                "_id": dataset_id,
                "user_id": user_id,
                "workspace_id": wid,
                "name": name or file.filename.split(".")[0],
                "description": description or "",
                "analysis_intent": analysis_intent or None,
                "file_id": file_metadata["file_id"],
                "original_filename": file.filename,
                "file_path": file_metadata["file_path"],
                "file_size": file_metadata["file_size"],
                "file_extension": file_metadata["file_extension"],
                "size_limit_mb": effective_limit_mb,
                "content_hash": content_hash,
                "upload_date": datetime.now(timezone.utc).replace(tzinfo=None),
                "is_processed": False,
                "is_active": True,
                "processing_status": "pending",
                "artifact_status": {
                    "insights_report": "pending",
                    "dashboard_design": "pending",
                },
                "metadata": {},
            }

            await self.db.uploads.insert_one(dataset_doc)

            # Fire-and-forget: launch processing in background
            import asyncio as _asyncio
            from services.pipeline.process import process_dataset

            _asyncio.create_task(
                process_dataset(
                    dataset_id,
                    file_metadata["file_path"],
                    user_id,
                    workspace_id=wid,
                )
            )

            logger.info(f"New dataset {dataset_id} accepted for processing.")

            return JSONResponse(
                status_code=202,
                content={
                    "is_duplicate": False,
                    "dataset_id": dataset_id,
                    "task_id": dataset_id,
                    "message": "Dataset upload accepted and is now being processed.",
                },
            )

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error in upload_dataset orchestration: {e}")
            raise HTTPException(status_code=500, detail="Failed to initiate dataset upload.")
        finally:
            # Clean up temp file on error
            if temp_path and Path(temp_path).exists():
                try:
                    Path(temp_path).unlink()
                except Exception:
                    pass

    async def get_dataset_doc(
        self,
        dataset_id: str,
        user_id: str,
        workspace_id: str | None = None,
        projection: dict | None = None,
    ) -> Optional[Dict]:
        """
        Fetch a raw dataset document with strict workspace scoping.

        Handles both UUID-string and ObjectId ``_id`` forms (mirroring
        ``get_dataset``). Raw reads on the ``uploads`` collection outside
        ``get_dataset()`` should route through here so the DB-layer tenant
        guard is applied to every read path.

        Args:
            dataset_id: Dataset identifier (string UUID or ObjectId).
            user_id:    Owner.
            workspace_id: Optional tenant scope; falls back to the user's
                personal workspace when omitted.
            projection: Optional MongoDB projection dict.

        Returns:
            Raw dataset doc (including ``_id``) or None.
        """
        from core.objectid_utils import safe_objectid

        wid = await self._effective_workspace(workspace_id, user_id)
        oid = safe_objectid(dataset_id)
        base = {"_id": oid} if oid else {"_id": dataset_id}
        query = tenant_scope_query("uploads", base, wid, user_id)
        return await self.db.uploads.find_one(query, projection)

    async def get_user_datasets(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        workspace_id: str | None = None,
    ) -> List[Dict]:
        """
        Gets all active datasets for a specific user with proper formatting.

        Args:
            user_id: User ID to fetch datasets for
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            workspace_id: Optional tenant scope. When omitted, falls back to
                the user's personal workspace (legacy single-tenant behavior).

        Returns:
            List[Dict]: List of formatted dataset documents
        """
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            cursor = (
                self.db.uploads.find(
                    tenant_scope_query(
                        "uploads",
                        {"is_active": True},
                        wid,
                        user_id,
                    )
                )
                .sort("upload_date", -1)
                .skip(skip)
                .limit(limit)
            )

            datasets = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                doc["name"] = doc.get("name") or doc.get("original_filename", "Unnamed Dataset")
                doc["row_count"] = doc.get("row_count", 0)
                doc["column_count"] = doc.get("column_count", 0)
                doc["created_at"] = doc.get("created_at") or doc.get("upload_date")
                datasets.append(doc)

            return datasets

        except Exception as e:
            logger.error(f"Error fetching user datasets: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch datasets.")

    async def get_dataset(
        self,
        dataset_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Dict:
        """
        Gets a single, complete dataset document, including its metadata.

        Args:
            dataset_id: Dataset ID (supports both ObjectId and UUID formats)
            user_id: User ID for ownership verification
            workspace_id: Optional tenant scope. When omitted, falls back to
                the user's personal workspace (legacy single-tenant behavior).
                A caller can never read a dataset that belongs to a different
                workspace than the one it supplies.

        Returns:
            Dict: Complete dataset document

        Raises:
            HTTPException: If dataset not found or access denied
        """
        try:
            from core.objectid_utils import safe_objectid
            dataset_oid = safe_objectid(dataset_id)
            if dataset_oid:
                base = {"_id": dataset_oid, "is_active": True}
            else:
                base = {"_id": dataset_id, "is_active": True}

            # DB-layer tenant guard: strictly workspace-scoped. Legacy callers
            # without a workspace context resolve their personal workspace
            # (which the backfill migration tagged their docs with).
            wid = await self._effective_workspace(workspace_id, user_id)
            query = tenant_scope_query(
                "uploads",
                base,
                wid,
                user_id,
            )

            dataset = await self.db.uploads.find_one(query)
            if not dataset:
                raise HTTPException(status_code=404, detail="Dataset not found.")

            dataset["id"] = str(dataset["_id"])
            dataset.pop("_id", None)
            return dataset

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching dataset {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch dataset.")

    async def delete_dataset(self, dataset_id: str, user_id: str) -> bool:
        """
        Permanently deletes a dataset record, its associated file, and
        all split-collection data (profile, intelligence, analytics).

        Args:
            dataset_id: Dataset ID to delete
            user_id: User ID for ownership verification

        Returns:
            bool: True if deletion successful

        Raises:
            HTTPException: If dataset not found or deletion fails
        """
        try:
            dataset = await self.get_dataset(dataset_id, user_id)

            if dataset.get("file_path"):
                await file_storage_service.delete_file(dataset["file_path"])

            # Clean up S3 parquet if present
            s3_key = dataset.get("s3_parquet_key")
            if s3_key:
                try:
                    from services.storage.s3_service import s3_storage

                    s3_storage.delete_file(s3_key)
                except Exception as e:
                    logger.warning(f"S3 delete failed for {s3_key}: {e}")

            # Cascade delete: conversations
            await self.db.conversations.delete_many({"dataset_id": dataset_id, "user_id": user_id})

            # Cascade delete: profile collection
            await self.db.dataset_profiles.delete_one({"dataset_id": dataset_id})

            # Cascade delete: intelligence collection
            await self.db.dataset_intelligence.delete_one({"dataset_id": dataset_id})

            # Cascade delete: analytics collection
            await self.db.dataset_analytics.delete_many({"dataset_id": dataset_id})

            from core.objectid_utils import safe_objectid
            object_id = safe_objectid(dataset_id)
            if object_id:
                query = {"_id": object_id, "user_id": user_id}
            else:
                query = {"_id": dataset_id, "user_id": user_id}

            result = await self.db.uploads.delete_one(query)

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Dataset could not be deleted.")

            logger.info(f"Dataset {dataset_id} permanently deleted by user {user_id}.")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting dataset {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete dataset.")

    async def get_dataset_data(
        self, dataset_id: str, user_id: str, page: int = 1, page_size: int = 100
    ) -> Dict:
        """
        Gets paginated data directly from the dataset's file.

        Args:
            dataset_id: Dataset ID to fetch data for
            user_id: User ID for ownership verification
            page: Page number (1-based)
            page_size: Number of records per page

        Returns:
            Dict: Paginated data with metadata
        """
        try:
            dataset = await self.get_dataset(dataset_id, user_id)
            offset = (page - 1) * page_size
            data, total_rows = await file_storage_service.get_paginated_file_data(
                dataset["file_path"], limit=page_size, offset=offset
            )

            return {
                "data": data,
                "total_rows": total_rows,
                "current_page": page,
                "page_size": page_size,
                "has_more": (page * page_size) < total_rows,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching dataset data for {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch dataset data.")

    async def load_dataset_data(
        self,
        dataset_id: str,
        user_id: str,
        max_rows: int | None = None,
        max_cols: int | None = None,
    ):
        """Load a dataset as a Polars DataFrame.

        **S3 path** (when ``settings.S3_ENABLED`` and the dataset has a
        ``s3_parquet_key``):
            Reads parquet from S3 lazily with optional row/column pruning.
            Skips the Redis pickle cache entirely (DataFrames can be large).

        **Local path** (legacy fallback):
            1. Redis cache (fastest)
            2. Local parquet file
            3. Original CSV/Excel file

        Parameters
        ----------
        max_rows:
            If set, only the first *max_rows* rows are returned (S3 path only).
        max_cols:
            If set, only the first *max_cols* columns are returned (S3 path only).
        """
        import polars as pl

        dataset = await self.get_dataset(dataset_id, user_id)
        file_path = dataset.get("file_path")
        s3_key = dataset.get("s3_parquet_key")

        # ── S3 path (lazy, pruned, no Redis pickle cache) ────────────────
        if settings.S3_ENABLED and s3_key:
            try:
                s3_url = f"s3://{settings.SUPABASE_BUCKET_NAME}/{s3_key}"
                max_rows = max_rows or settings.AGENT_MAX_CONTEXT_ROWS
                max_cols = max_cols or settings.AGENT_MAX_CONTEXT_COLS
                lf = load_dataset_s3_lazy(s3_url, max_rows=max_rows, max_cols=max_cols)
                df = lf.collect()
                logger.info(
                    "Loaded dataset %s from S3 (%s rows × %s cols)",
                    dataset_id,
                    len(df),
                    len(df.columns),
                )
                return df
            except Exception as e:
                logger.warning("S3 load failed for %s, falling back to local: %s", dataset_id, e)

        # ── Local path (legacy) ────────────────────────────────────────────
        cache_key = f"df:{dataset_id}"

        try:
            cached_df = await cache_service.get_dataframe(cache_key)
            if cached_df is not None:
                logger.debug(f"Cache hit for dataset {dataset_id}")
                return cached_df
        except Exception as e:
            logger.warning(f"Cache read failed for {dataset_id}: {e}")

        try:
            if not file_path:
                raise HTTPException(status_code=404, detail="Dataset file not found.")

            parquet_path = dataset.get("parquet_path")
            df = None

            if parquet_path and Path(parquet_path).exists():
                try:
                    df = pl.read_parquet(parquet_path)
                    logger.info(f"Loaded Parquet for dataset {dataset_id} ({len(df):,} rows)")
                except Exception as e:
                    logger.warning(f"Parquet read failed, falling back to original: {e}")
                    df = None

            if df is None:
                path = Path(file_path)
                if not path.exists():
                    raise HTTPException(status_code=404, detail="Dataset file not found on disk.")

                file_ext = path.suffix.lower()
                if file_ext == ".csv":
                    df = pl.read_csv(file_path, infer_schema_length=10000)
                elif file_ext in [".xlsx", ".xls"]:
                    df = pl.read_excel(file_path)
                elif file_ext == ".json":
                    df = pl.read_json(file_path)
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Unsupported file format: {file_ext}"
                    )

            try:
                await cache_service.set_dataframe(cache_key, df, ttl=3600)
                logger.debug(f"Cached DataFrame for dataset {dataset_id}")
            except Exception as e:
                logger.warning(f"Cache write failed for {dataset_id}: {e}")

            return df

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to load dataset from {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not load dataset: {str(e)}")

    async def auto_index_dataset_to_vector_db(self, dataset_id: str, user_id: str) -> bool:
        """
        Automatically index a dataset to vector database after processing.
        Creates semantic chunks and indexes them for RAG retrieval.

        Args:
            dataset_id: Dataset ID to index
            user_id: User ID for ownership verification

        Returns:
            bool: True if indexing successful, False otherwise
        """
        try:
            dataset_doc = await self.get_dataset(dataset_id, user_id)

            if not dataset_doc or not dataset_doc.get("metadata"):
                logger.warning(f"Dataset {dataset_id} not ready for vector indexing")
                return False

            metadata = dataset_doc["metadata"]

            # 1. Index dataset-level metadata (existing behavior)
            #    Tenant-tag the FAISS record with the dataset's workspace so
            #    workspace-scoped vector search finds it (matches the pipeline).
            await faiss_vector_service.add_dataset_to_vector_db(
                dataset_id=dataset_id,
                dataset_metadata=metadata,
                user_id=user_id,
                workspace_id=dataset_doc.get("workspace_id"),
            )

            # 2. Create and index semantic chunks for RAG
            try:
                from services.rag.chunk_service import chunk_service

                # Load DataFrame for sample extraction
                df = None
                try:
                    df = await self.load_dataset_data(dataset_id, user_id)
                except Exception as e:
                    logger.warning(f"Could not load DataFrame for chunk creation: {e}")

                # Create chunks
                chunks = chunk_service.create_chunks_from_metadata(
                    dataset_id=dataset_id, metadata=metadata, df=df
                )

                if chunks:
                    # Delete existing chunks for this dataset (for re-indexing)
                    await faiss_vector_service.delete_dataset_chunks(dataset_id, user_id)

                    # Index new chunks in FAISS (dense retrieval)
                    success = await faiss_vector_service.index_dataset_chunks(
                        dataset_id=dataset_id, chunks=chunks, user_id=user_id
                    )

                    if success:
                        logger.info(f"Dataset {dataset_id} indexed with {len(chunks)} RAG chunks")

                        # Also build BM25 index for hybrid search
                        try:
                            from services.rag.hybrid_search import hybrid_search_service

                            hybrid_search_service.build_bm25_index(dataset_id, chunks)
                        except ImportError:
                            pass  # Hybrid search not available
                        except Exception as e:
                            logger.warning(f"BM25 indexing optional failure: {e}")
                    else:
                        logger.warning(f"Failed to index chunks for dataset {dataset_id}")
                else:
                    logger.warning(f"No chunks created for dataset {dataset_id}")

            except ImportError:
                logger.warning("ChunkService not available, skipping RAG chunk indexing")
            except Exception as e:
                logger.error(f"RAG chunk indexing failed for {dataset_id}: {e}")

            return True

        except Exception as e:
            logger.error(f"Auto-indexing failed for dataset {dataset_id}: {e}")
            return False

    async def get_dataset_analytics(
        self,
        dataset_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Optional[Dict]:
        """
        Fetch pre-computed analytics from the dataset_analytics collection.
        Falls back to metadata for backward compatibility.

        Args:
            dataset_id: Dataset ID to fetch analytics for
            user_id: User ID for ownership verification
            workspace_id: Optional tenant scope; falls back to the user's
                personal workspace when omitted.

        Returns:
            Dict: Analytics data or None
        """
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            analytics_filter: dict = {"dataset_id": dataset_id, "workspace_id": wid}
            # Fail-closed: the query must be pinned to the caller's workspace.
            enforce_workspace_filter("dataset_analytics", analytics_filter, wid, "read")
            analytics = await self.db.dataset_analytics.find_one(analytics_filter)

            if analytics:
                analytics["id"] = str(analytics["_id"])
                analytics.pop("_id", None)
                return analytics

            return None
        except Exception as e:
            logger.warning(f"Could not fetch analytics for {dataset_id}: {e}")
            return None

    async def save_dataset_analytics(
        self,
        dataset_id: str,
        user_id: str,
        analytics_data: Dict,
        workspace_id: str | None = None,
    ) -> bool:
        """
        Save pre-computed analytics to the dataset_analytics collection.

        Args:
            dataset_id: Dataset ID
            user_id: User ID
            analytics_data: Analytics data to save
            workspace_id: Optional tenant scope; falls back to the user's
                personal workspace when omitted.

        Returns:
            bool: True if successful
        """
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            analytics_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "workspace_id": wid,
                "chart_recommendations": analytics_data.get("chart_recommendations", []),
                "statistical_findings": analytics_data.get("statistical_findings", []),
                "deep_analysis": analytics_data.get("deep_analysis", {}),
                "data_profile": analytics_data.get("data_profile", {}),
                "domain_intelligence": analytics_data.get("domain_intelligence", {}),
                "data_quality": analytics_data.get("data_quality", {}),
                "computed_at": now,
                "updated_at": now,
                "pipeline_version": analytics_data.get("pipeline_version", "3.0"),
            }

            analytics_filter: dict = {"dataset_id": dataset_id, "workspace_id": wid}
            # Fail-closed: the write must be pinned to the caller's workspace.
            enforce_workspace_filter("dataset_analytics", analytics_filter, wid, "write")
            await self.db.dataset_analytics.update_one(
                analytics_filter,
                {"$set": analytics_doc},
                upsert=True,
            )

            logger.info(f"Saved analytics for dataset {dataset_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save analytics for {dataset_id}: {e}")
            return False

    async def get_full_dataset_with_analytics(self, dataset_id: str, user_id: str) -> Dict:
        """
        Get a dataset with its analytics combined.
        For backward compatibility, merges analytics into metadata if not found separately.

        Args:
            dataset_id: Dataset ID
            user_id: User ID

        Returns:
            Dict: Dataset with analytics merged
        """
        dataset = await self.get_dataset(dataset_id, user_id)
        analytics = await self.get_dataset_analytics(dataset_id, user_id)

        if analytics:
            dataset["analytics"] = analytics
        else:
            dataset["analytics"] = None

        return dataset

    async def load_dataset_as_polars(self, dataset_id: str, user_id: str):
        """
        Alias for load_dataset_data for cleaner API.
        Loads dataset as a Polars DataFrame.

        Args:
            dataset_id: Dataset ID
            user_id: User ID for ownership verification

        Returns:
            pl.DataFrame: The loaded dataset
        """
        return await self.load_dataset_data(dataset_id, user_id)

    async def ensure_dataframe_for_agent(
        self, dataset_id: str, user_id: str, sample: bool = False, max_rows: int = 10000
    ):
        """Helper for agents: return a Polars DataFrame.

        Attempts to load a cached/sample DataFrame suitable for quick analysis.
        Agents should call this instead of implementing loading logic themselves.
        """
        try:
            if sample:
                # Use dataset_loader's sampling strategy when a sample is preferred
                ds = await self.get_dataset(dataset_id, user_id)
                file_path = ds.get("file_path")
                if not file_path:
                    raise Exception("Dataset file_path missing")
                return await dataset_loader.load_dataset_sample(file_path, max_rows)

            # Default: return the full cached/parquet-backed DataFrame
            return await self.load_dataset_as_polars(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"ensure_dataframe_for_agent failed for {dataset_id}: {e}")
            return None

    async def build_compact_schema_context(
        self, dataset_id: str, user_id: str, sample_rows: int = 3
    ) -> str:
        """Build a compact schema + sample context string for planner prompts.

        Uses metadata and a small sample (if available) to produce a short
        string suitable for inclusion in LLM prompts.
        """
        try:
            metadata = await self.get_dataset_analytics(dataset_id, user_id)
            if metadata is None:
                # Fallback to raw metadata
                ds = await self.get_dataset(dataset_id, user_id)
                file_path = ds.get("file_path")
                metadata = await dataset_loader.get_dataset_metadata(file_path)

            # Try to obtain a tiny sample for context
            ds = await self.get_dataset(dataset_id, user_id)
            file_path = ds.get("file_path")
            sample_df = None
            try:
                sample_df = await dataset_loader.load_dataset_sample(
                    file_path, max_rows=sample_rows
                )
            except Exception:
                sample_df = None

            return dataset_loader.create_context_string(metadata or {}, sample_df)
        except Exception as e:
            logger.warning(f"build_compact_schema_context failed for {dataset_id}: {e}")
            return "Schema not available"

    # ═══════════════════════════════════════════════════════════════════
    # SPLIT-COLLECTION HELPERS (profile + intelligence)
    # ═══════════════════════════════════════════════════════════════════

    async def get_dataset_profile(
        self,
        dataset_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Optional[Dict]:
        """
        Fetch unified profile from ``dataset_profiles`` collection.

        Falls back to legacy ``metadata.unified_profile`` in the uploads doc
        for datasets processed before the split (pipeline_version < 3.1).

        Args:
            dataset_id: Dataset identifier.
            user_id:    Owner (for legacy fallback permission check).
            workspace_id: Optional tenant scope for the split-collection query.

        Returns:
            Profile dict or None if not found.
        """
        # ── 1. Try separate collection first ──────────────────────────────
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            split_filter: dict = {"dataset_id": dataset_id, "workspace_id": wid}
            # Fail-closed: the query must be pinned to the caller's workspace.
            enforce_workspace_filter("dataset_profiles", split_filter, wid, "read")
            doc = await self.db.dataset_profiles.find_one(
                split_filter,
                {"profile": 1, "pipeline_version": 1},
            )
            if doc and doc.get("profile"):
                return doc["profile"]
        except Exception as e:
            # Log the split-collection failure (including any guard rejection)
            # and fall through to the legacy embedded fallback, which re-checks
            # ownership via get_dataset() — so no access leak.
            logger.debug(f"[Profile] Split-collection read failed for {dataset_id[:8]}: {e}")

        # ── 2. Legacy fallback: embedded in metadata ───────────────────────
        try:
            ds = await self.get_dataset(dataset_id, user_id)
            meta = ds.get("metadata", {})
            legacy = meta.get("unified_profile")
            if legacy:
                logger.info(
                    f"[Profile] Legacy fallback for {dataset_id[:8]} — embedded in metadata"
                )
                return legacy
        except Exception:
            pass

        return None

    async def get_dataset_intelligence(
        self,
        dataset_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Optional[Dict]:
        """
        Fetch unified intelligence from ``dataset_intelligence`` collection.

        Falls back to legacy ``metadata.unified_intelligence`` in the uploads
        doc for datasets processed before the split.

        Args:
            dataset_id: Dataset identifier.
            user_id:    Owner (for legacy fallback permission check).
            workspace_id: Optional tenant scope for the split-collection query.

        Returns:
            Intelligence dict or None if not found.
        """
        # ── 1. Try separate collection first ──────────────────────────────
        try:
            wid = await self._effective_workspace(workspace_id, user_id)
            split_filter: dict = {"dataset_id": dataset_id, "workspace_id": wid}
            # Fail-closed: the query must be pinned to the caller's workspace.
            enforce_workspace_filter(
                "dataset_intelligence", split_filter, wid, "read"
            )
            doc = await self.db.dataset_intelligence.find_one(
                split_filter,
                {"intelligence": 1, "pipeline_version": 1},
            )
            if doc and doc.get("intelligence"):
                return doc["intelligence"]
        except Exception as e:
            # Log the split-collection failure (including any guard rejection)
            # and fall through to the legacy embedded fallback, which re-checks
            # ownership via get_dataset() — so no access leak.
            logger.debug(f"[Intel] Split-collection read failed for {dataset_id[:8]}: {e}")

        # ── 2. Legacy fallback: embedded in metadata ───────────────────────
        try:
            ds = await self.get_dataset(dataset_id, user_id)
            meta = ds.get("metadata", {})
            legacy = meta.get("unified_intelligence")
            if legacy:
                logger.info(f"[Intel] Legacy fallback for {dataset_id[:8]} — embedded in metadata")
                return legacy
        except Exception:
            pass

        return None


enhanced_dataset_service = EnhancedDatasetService()
