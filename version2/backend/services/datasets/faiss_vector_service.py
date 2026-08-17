import logging
import json
import pickle
import os
import asyncio
import time
from collections import OrderedDict
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
import faiss
from langchain_huggingface import HuggingFaceEmbeddings
from bson import ObjectId

from db.database import get_database
from core.config import settings

logger = logging.getLogger(__name__)


class LRUDict(OrderedDict):
    """
    OrderedDict with a max size — drops the least-recently-used item on overflow.
    Accessing or updating an item moves it to the end (most recently used).
    """

    def __init__(self, maxsize: int = 100):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            self.popitem(last=False)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


class FAISSVectorService:
    """
    FAISS-based vector search service with thread-safe index operations.
    Uses asyncio.Lock to prevent concurrent index modifications.
    """

    def __init__(self):
        self.embedding_model_name = settings.EMBEDDING_MODEL
        self.vector_db_path = settings.VECTOR_DB_PATH
        self.enable_vector_search = settings.ENABLE_VECTOR_SEARCH
        self.embedding_dimension = 1024

        self._dataset_dirty = False
        self._query_dirty = False

        # Thread-safety locks — lazily initialized to ensure loop-binding in workers
        self._dataset_index_lock = None
        self._query_index_lock = None

        self.embedding_model = None
        self.dataset_index = None
        self.query_history_index = None
        self.dataset_metadata = {}
        self.query_history_metadata = {}

        # ── Per-dataset chunk index cache (LRU, initialized early for robustness) ─
        self._chunk_indices: LRUDict = LRUDict(maxsize=settings.CHUNK_INDEX_CACHE_MAX)  # dataset_id → faiss.Index
        self._chunk_metadata: LRUDict = LRUDict(maxsize=settings.CHUNK_INDEX_CACHE_MAX)  # dataset_id → {idx → metadata}
        self._chunks_dir: str = ""  # set in _initialize_faiss_indices once vector_db_path is known

        if self.enable_vector_search:
            logger.info("Vector search is enabled — will initialize on first use.")
        else:
            logger.info("Vector search is disabled by configuration.")

    def _ensure_initialized(self):
        if self.embedding_model is not None:
            return
        if not self.enable_vector_search:
            return
        self._initialize_components()

    def _initialize_components(self):
        try:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(f"Embedding model '{self.embedding_model_name}' loaded successfully")

            os.makedirs(self.vector_db_path, exist_ok=True)

            self._initialize_faiss_indices()

            logger.info("FAISS vector service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize FAISS vector service: {e}")
            self.enable_vector_search = False

    def _initialize_faiss_indices(self):
        try:
            dataset_index_path = os.path.join(self.vector_db_path, "dataset_index.faiss")
            dataset_metadata_path = os.path.join(self.vector_db_path, "dataset_metadata.pkl")

            if os.path.exists(dataset_index_path) and os.path.exists(dataset_metadata_path):
                self.dataset_index = faiss.read_index(dataset_index_path)
                with open(dataset_metadata_path, "rb") as f:
                    self.dataset_metadata = pickle.load(f)
                logger.info(f"Loaded dataset index with {self.dataset_index.ntotal} vectors")
            else:
                self.dataset_index = faiss.IndexFlatIP(self.embedding_dimension)
                self.dataset_metadata = {}
                logger.info("Created new dataset index")

            query_index_path = os.path.join(self.vector_db_path, "query_index.faiss")
            query_metadata_path = os.path.join(self.vector_db_path, "query_metadata.pkl")

            if os.path.exists(query_index_path) and os.path.exists(query_metadata_path):
                self.query_history_index = faiss.read_index(query_index_path)
                with open(query_metadata_path, "rb") as f:
                    self.query_history_metadata = pickle.load(f)
                logger.info(
                    f"Loaded query history index with {self.query_history_index.ntotal} vectors"
                )
            else:
                self.query_history_index = faiss.IndexFlatIP(self.embedding_dimension)
                self.query_history_metadata = {}
                logger.info("Created new query history index")

            # ── Per-dataset chunk indices subdirectory ──────────────────
            self._chunks_dir = os.path.join(self.vector_db_path, "chunks")
            os.makedirs(self._chunks_dir, exist_ok=True)

        except Exception as e:
            logger.error(f"Failed to initialize FAISS indices: {e}")
            raise

    # ── Per-dataset chunk index path helpers ─────────────────────────────
    def _chunk_index_path(self, dataset_id: str) -> str:
        return os.path.join(self._chunks_dir, f"{dataset_id}.faiss")

    def _chunk_metadata_path(self, dataset_id: str) -> str:
        return os.path.join(self._chunks_dir, f"{dataset_id}.pkl")

    # ── MongoDB chunks collection ────────────────────────────────────────
    @property
    def chunks_collection(self):
        return self.mongo_db["chunks"]

    def _ensure_locks(self):
        """Lazy initialization of asyncio locks."""
        if self._dataset_index_lock is None:
            self._dataset_index_lock = asyncio.Lock()
        if self._query_index_lock is None:
            self._query_index_lock = asyncio.Lock()

    @property
    def mongo_db(self):
        db_conn = get_database()
        if db_conn is None:
            raise Exception("MongoDB is not connected.")
        return db_conn

    async def add_dataset_to_vector_db(
        self,
        dataset_id: str,
        dataset_metadata: Dict,
        user_id: str,
        workspace_id: str | None = None,
    ) -> bool:
        """Add dataset to vector index with thread-safe locking and idempotency.

        Idempotency: checks whether ``dataset_id`` already exists in the
        in-memory metadata. If it does, the index entry is treated as a
        no-op (already indexed). This prevents duplicate FAISS entries when
        the pipeline retries or reprocesses a dataset.
        """
        self._ensure_initialized()
        if not self.enable_vector_search or not self.embedding_model:
            return False

        try:
            # ── Idempotency check: skip if already indexed ──────────────
            existing_id = None
            for idx, meta in self.dataset_metadata.items():
                if meta.get("dataset_id") == dataset_id:
                    existing_id = idx
                    break
            if existing_id is not None:
                logger.info(
                    "[FAISS Idempotency] Dataset %s already indexed at offset %s — skipping",
                    dataset_id[:8],
                    existing_id,
                )
                return True

            # Compute embedding outside the lock (CPU-intensive)
            content = json.dumps(dataset_metadata)
            embedding = np.array(
                await asyncio.to_thread(self.embedding_model.embed_documents, [content])
            ).astype("float32")

            # Lock for index modification
            self._ensure_locks()
            async with self._dataset_index_lock:
                # Double-check after acquiring the lock (race condition guard)
                for idx, meta in self.dataset_metadata.items():
                    if meta.get("dataset_id") == dataset_id:
                        logger.info(
                            "[FAISS Idempotency] Dataset %s indexed between check and lock — skipping",
                            dataset_id[:8],
                        )
                        return True

                self.dataset_index.add(embedding)
                index_id = self.dataset_index.ntotal - 1
                self.dataset_metadata[index_id] = {
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "workspace_id": workspace_id or user_id,
                    "content": content,
                    "added_at": datetime.now().isoformat(),
                }

                self._dataset_dirty = True
                self._persist_dataset_index()

            logger.info(f"Added dataset {dataset_id} to vector DB at index {index_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add dataset {dataset_id} to vector DB: {e}")
            return False

    async def add_query_to_history(self, query: str, dataset_id: str, user_id: str) -> bool:
        """Add query to history index with thread-safe locking."""
        self._ensure_initialized()
        if not self.enable_vector_search or not self.embedding_model:
            return False

        try:
            # Compute embedding outside the lock (CPU-intensive)
            embedding = np.array(
                [await asyncio.to_thread(self.embedding_model.embed_query, query)]
            ).astype("float32")

            # Lock for index modification
            self._ensure_locks()
            async with self._query_index_lock:
                self.query_history_index.add(embedding)
                index_id = self.query_history_index.ntotal - 1
                self.query_history_metadata[index_id] = {
                    "query": query,
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                }

                self._query_dirty = True
                self._persist_query_history_index()

            logger.info(f"Added query to history for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add query to history: {e}")
            return False

    async def search_similar_datasets(
        self,
        query: str,
        user_id: str,
        k: int = 5,
        workspace_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        if not self.enable_vector_search or not self.embedding_model:
            return []

        try:
            if self._dataset_dirty:
                await self._lazy_rebuild_dataset_index()

            query_embedding = np.array(
                [await asyncio.to_thread(self.embedding_model.embed_query, query)]
            ).astype("float32")

            distances, indices = self.dataset_index.search(query_embedding, k)

            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.dataset_metadata):
                    metadata = self.dataset_metadata[idx]
                    # Tenant guard: only surface entries owned by this user AND
                    # (when a workspace is supplied) in that same workspace.
                    if metadata.get("user_id") != user_id:
                        continue
                    if workspace_id is not None and metadata.get("workspace_id") != workspace_id:
                        continue
                    results.append(
                        {
                            "dataset_id": metadata["dataset_id"],
                            "similarity": float(distances[0][i]),
                            "content_preview": metadata["content"][:200] + "...",
                        }
                    )

            return sorted(results, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            logger.error(f"Failed to search similar datasets: {e}")
            return []

    async def search_similar_queries(
        self, query: str, user_id: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        if not self.enable_vector_search or not self.embedding_model:
            return []

        try:
            if self._query_dirty:
                await self._lazy_rebuild_query_history_index()

            query_embedding = np.array(
                [await asyncio.to_thread(self.embedding_model.embed_query, query)]
            ).astype("float32")

            distances, indices = self.query_history_index.search(query_embedding, k)

            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.query_history_metadata):
                    metadata = self.query_history_metadata[idx]
                    if metadata["user_id"] == user_id:
                        results.append(
                            {
                                "query": metadata["query"],
                                "dataset_id": metadata["dataset_id"],
                                "similarity": float(distances[0][i]),
                                "timestamp": metadata["timestamp"],
                            }
                        )

            return sorted(results, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            logger.error(f"Failed to search similar queries: {e}")
            return []

    @staticmethod
    def _atomic_write(data: Any, path: str, is_faiss: bool = False) -> None:
        """
        Write data atomically: write to temp file, then rename to target.
        os.rename() is atomic on POSIX when source and target are on the same filesystem.
        """
        tmp_path = path + ".tmp"
        try:
            if is_faiss:
                faiss.write_index(data, tmp_path)
            else:
                with open(tmp_path, "wb") as f:
                    pickle.dump(data, f)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise

    def _persist_dataset_index(self):
        try:
            base = self.vector_db_path
            self._atomic_write(self.dataset_index, os.path.join(base, "dataset_index.faiss"), is_faiss=True)
            self._atomic_write(self.dataset_metadata, os.path.join(base, "dataset_metadata.pkl"), is_faiss=False)
        except Exception as e:
            logger.error(f"Error persisting dataset index: {e}")

    def _persist_query_history_index(self):
        try:
            base = self.vector_db_path
            self._atomic_write(self.query_history_index, os.path.join(base, "query_index.faiss"), is_faiss=True)
            self._atomic_write(self.query_history_metadata, os.path.join(base, "query_metadata.pkl"), is_faiss=False)
        except Exception as e:
            logger.error(f"Error persisting query history index: {e}")

    async def get_vector_db_stats(self, user_id: str) -> Dict[str, Any]:
        if not self.enable_vector_search:
            return {"status": "disabled", "indices": {}}

        if self._dataset_dirty:
            await self._lazy_rebuild_dataset_index()

        stats = {
            "status": "enabled",
            "embedding_model": self.embedding_model_name,
            "embedding_dimension": self.embedding_dimension,
            "indices": {
                "datasets": {
                    "total_vectors": self.dataset_index.ntotal if self.dataset_index else 0,
                    "user_vectors": len(
                        [m for m in self.dataset_metadata.values() if m["user_id"] == user_id]
                    ),
                },
                "query_history": {
                    "total_vectors": self.query_history_index.ntotal
                    if self.query_history_index
                    else 0,
                    "user_vectors": len(
                        [m for m in self.query_history_metadata.values() if m["user_id"] == user_id]
                    ),
                },
            },
        }

        return stats

    async def reset_vector_db(self, user_id: str) -> bool:
        if not self.enable_vector_search:
            logger.info("Vector search disabled. Skipping reset.")
            return False

        try:
            self.dataset_metadata = {
                idx: metadata
                for idx, metadata in self.dataset_metadata.items()
                if metadata["user_id"] != user_id
            }

            self.query_history_metadata = {
                idx: metadata
                for idx, metadata in self.query_history_metadata.items()
                if metadata["user_id"] != user_id
            }

            self._dataset_dirty = True
            self._query_dirty = True

            logger.info(f"Vector database reset for user {user_id} (lazy rebuild pending)")
            return True

        except Exception as e:
            logger.error(f"Error resetting vector database for user {user_id}: {e}")
            return False

    async def _lazy_rebuild_dataset_index(self):
        if not self._dataset_dirty:
            return
        try:
            if self.dataset_metadata:
                new_dataset_index = faiss.IndexFlatIP(self.embedding_dimension)
                # Batch-embed all documents in one call for efficiency
                texts = [m["content"] for m in self.dataset_metadata.values()]
                embeddings = np.array(
                    await asyncio.to_thread(self.embedding_model.embed_documents, texts)
                ).astype("float32")
                new_dataset_index.add(embeddings)
                self.dataset_index = new_dataset_index
            else:
                self.dataset_index = faiss.IndexFlatIP(self.embedding_dimension)

            self._dataset_dirty = False
            self._persist_dataset_index()
            logger.info("Dataset index lazily rebuilt")
        except Exception as e:
            logger.error(f"Lazy rebuild failed for dataset index: {e}")
            raise

    async def _lazy_rebuild_query_history_index(self):
        if not self._query_dirty:
            return
        try:
            if self.query_history_metadata:
                new_query_index = faiss.IndexFlatIP(self.embedding_dimension)
                # Batch-embed all queries in one call for efficiency
                texts = [m["query"] for m in self.query_history_metadata.values()]
                embeddings = np.array(
                    await asyncio.to_thread(self.embedding_model.embed_documents, texts)
                ).astype("float32")
                new_query_index.add(embeddings)
                self.query_history_index = new_query_index
            else:
                self.query_history_index = faiss.IndexFlatIP(self.embedding_dimension)

            self._query_dirty = False
            self._persist_query_history_index()
            logger.info("Query history index lazily rebuilt")
        except Exception as e:
            logger.error(f"Lazy rebuild failed for query history index: {e}")
            raise

    async def _rebuild_indices(self):
        await self._lazy_rebuild_dataset_index()
        await self._lazy_rebuild_query_history_index()

    # =========================================================================
    # CHUNK-LEVEL VECTOR INDEXING FOR RAG
    # =========================================================================

    async def index_dataset_chunks(
        self, dataset_id: str, chunks: List[Dict[str, Any]], user_id: str
    ) -> bool:
        """
        Index semantic chunks for a dataset for RAG retrieval.
        SaaS-grade: stores chunks in MongoDB (source of truth) AND FAISS (cache).

        Args:
            dataset_id: Unique dataset identifier
            chunks: List of chunk dicts from ChunkService
            user_id: Owner user ID

        Returns:
            True if indexing succeeded
        """
        if not self.enable_vector_search or not self.embedding_model:
            logger.warning("Vector search disabled, skipping chunk indexing")
            return False

        if not chunks:
            logger.warning(f"No chunks to index for dataset {dataset_id}")
            return False

        try:
            _start = time.monotonic()

            # ── Step 1: Store in MongoDB (source of truth) ──────────────
            chunk_docs = []
            for chunk in chunks:
                chunk_docs.append(
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "chunk_type": chunk.get("chunk_type"),
                        "content": chunk.get("content", ""),
                        "metadata": chunk.get("metadata", {}),
                        "created_at": datetime.now(),
                        "expire_at": None,  # never auto-expire; TTL index only applies if set
                    }
                )

            # Delete existing chunks for this dataset first (idempotent re-index)
            await self.chunks_collection.delete_many({"dataset_id": dataset_id})
            if chunk_docs:
                await self.chunks_collection.insert_many(chunk_docs)

            # ── Step 2: Build per-dataset FAISS index ───────────────────
            texts = [chunk.get("content", "") for chunk in chunks]
            embeddings = np.array(
                await asyncio.to_thread(self.embedding_model.embed_documents, texts)
            ).astype("float32")

            index = faiss.IndexFlatIP(self.embedding_dimension)
            index.add(embeddings)

            metadata = {}
            for i, chunk in enumerate(chunks):
                metadata[i] = {
                    "chunk_id": chunk.get("chunk_id"),
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "chunk_type": chunk.get("chunk_type"),
                    "content": chunk.get("content", ""),
                    "metadata": chunk.get("metadata", {}),
                    "indexed_at": datetime.now().isoformat(),
                }

            # ── Step 3: Atomically persist to disk ──────────────────────
            self._atomic_write(index, self._chunk_index_path(dataset_id), is_faiss=True)
            self._atomic_write(metadata, self._chunk_metadata_path(dataset_id), is_faiss=False)

            # ── Step 4: Update in-memory cache ──────────────────────────
            self._chunk_indices[dataset_id] = index
            self._chunk_metadata[dataset_id] = metadata

            _elapsed = time.monotonic() - _start
            logger.info(
                "[RAG] Indexed %d chunks for dataset %s in %.2fs "
                "(MongoDB + per-dataset FAISS)",
                len(chunks),
                dataset_id[:8],
                _elapsed,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to index chunks for dataset {dataset_id}: {e}")
            return False

    async def search_relevant_chunks(
        self,
        query: str,
        dataset_id: str,
        k: int = 5,
        score_threshold: float = 0.5,
        chunk_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant chunks using per-dataset FAISS index.
        SaaS-grade: only searches the dataset's own index (no cross-tenant touching).

        Args:
            query: User query to match against chunks
            dataset_id: Dataset to search (isolated per-dataset index)
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            chunk_types: Optional filter for chunk types

        Returns:
            List of matching chunks with similarity scores
        """
        self._ensure_initialized()
        if not self.enable_vector_search or not self.embedding_model:
            return []

        try:
            _start = time.monotonic()

            # ── Load or recover per-dataset index ───────────────────────
            index = self._chunk_indices.get(dataset_id)
            metadata = self._chunk_metadata.get(dataset_id)

            if index is None or metadata is None:
                index = await self._load_chunk_index(dataset_id)
                if index is None:
                    logger.debug(
                        "[RAG] No chunk index for dataset %s (not yet indexed)",
                        dataset_id[:8],
                    )
                    return []
                metadata = self._chunk_metadata.get(dataset_id, {})

            if index.ntotal == 0:
                logger.debug("[RAG] Chunk index for %s is empty", dataset_id[:8])
                return []

            # ── Compute query embedding ─────────────────────────────────
            query_embedding = np.array(
                [await asyncio.to_thread(self.embedding_model.embed_query, query)]
            ).astype("float32")

            # ── Search (no post-filter needed — index is already scoped) ─
            search_k = min(k * 3, index.ntotal)
            distances, indices = index.search(query_embedding, search_k)

            results = []
            for i, idx in enumerate(indices[0]):
                if idx < 0:
                    continue

                meta = metadata.get(idx)
                if not meta:
                    continue

                # Filter by chunk type if specified (metadata-level only)
                if chunk_types and meta.get("chunk_type") not in chunk_types:
                    continue

                score = float(distances[0][i])
                if score < score_threshold:
                    continue

                results.append(
                    {
                        "chunk_id": meta.get("chunk_id"),
                        "chunk_type": meta.get("chunk_type"),
                        "content": meta.get("content"),
                        "metadata": meta.get("metadata", {}),
                        "similarity": score,
                    }
                )

                if len(results) >= k:
                    break

            _elapsed = time.monotonic() - _start
            logger.info(
                "[RAG] Found %d/%d chunks for dataset %s in %.0fms (per-dataset index)",
                len(results),
                search_k,
                dataset_id[:8],
                _elapsed * 1000,
            )
            return sorted(results, key=lambda x: x["similarity"], reverse=True)

        except Exception as e:
            logger.error(f"[RAG] Failed to search chunks for {dataset_id[:8]}: {e}")
            return []

    async def delete_dataset_chunks(self, dataset_id: str, user_id: str) -> bool:
        """
        O(1) delete all chunks for a dataset.
        SaaS-grade: deletes from MongoDB (source of truth) + FAISS file (cache).
        No lazy rebuild needed.
        """
        if not self.enable_vector_search:
            return False

        try:
            # ── Delete from MongoDB (source of truth) ───────────────────
            mongo_result = await self.chunks_collection.delete_many({"dataset_id": dataset_id})

            # ── Safety net: mark any remaining orphaned chunks with TTL expiry ─
            # If delete_many above fails silently or is skipped, the TTL index
            # will clean up documents whose expire_at is set to now().
            await self.chunks_collection.update_many(
                {"dataset_id": dataset_id, "expire_at": None},
                {"$set": {"expire_at": datetime.now()}},
            )

            # ── Delete per-dataset FAISS files ──────────────────────────
            index_path = self._chunk_index_path(dataset_id)
            meta_path = self._chunk_metadata_path(dataset_id)

            deleted_files = 0
            for path in [index_path, meta_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        deleted_files += 1
                    except OSError as e:
                        logger.warning("[RAG] Failed to delete chunk file %s: %s", path, e)

            # ── Remove from in-memory cache ─────────────────────────────
            self._chunk_indices.pop(dataset_id, None)
            self._chunk_metadata.pop(dataset_id, None)

            logger.info(
                "[RAG] Deleted %d MongoDB chunks + %d FAISS files for dataset %s",
                mongo_result.deleted_count,
                deleted_files,
                dataset_id[:8],
            )
            return True

        except Exception as e:
            logger.error(f"[RAG] Failed to delete chunks for dataset {dataset_id[:8]}: {e}")
            return False

    async def _load_chunk_index(self, dataset_id: str) -> Optional[faiss.Index]:
        """
        Load a per-dataset chunk index from disk, with MongoDB fallback.
        SaaS recovery: if FAISS file is missing/corrupt, rebuild from MongoDB.
        """
        index_path = self._chunk_index_path(dataset_id)
        meta_path = self._chunk_metadata_path(dataset_id)

        # ── Try loading from disk first ─────────────────────────────────
        if os.path.exists(index_path) and os.path.exists(meta_path):
            try:
                index = faiss.read_index(index_path)
                with open(meta_path, "rb") as f:
                    metadata = pickle.load(f)
                self._chunk_indices[dataset_id] = index
                self._chunk_metadata[dataset_id] = metadata
                logger.debug(
                    "[RAG] Loaded chunk index for dataset %s (%d vectors)",
                    dataset_id[:8],
                    index.ntotal,
                )
                return index
            except Exception as e:
                logger.warning(
                    "[RAG] Failed to load chunk index for %s from disk: %s. "
                    "Attempting MongoDB recovery...",
                    dataset_id[:8],
                    e,
                )

        # ── Fallback: rebuild from MongoDB ──────────────────────────────
        return await self._rebuild_chunk_index_from_mongodb(dataset_id)

    async def _rebuild_chunk_index_from_mongodb(self, dataset_id: str) -> Optional[faiss.Index]:
        """
        Rebuild a per-dataset FAISS index from MongoDB chunks.
        This is the disaster recovery path — MongoDB is the source of truth.
        """
        try:
            _start = time.monotonic()
            cursor = self.chunks_collection.find({"dataset_id": dataset_id})
            chunk_docs = await cursor.to_list(length=None)

            if not chunk_docs:
                logger.debug(
                    "[RAG] No MongoDB chunks found for dataset %s (not indexed yet)",
                    dataset_id[:8],
                )
                return None

            texts = [doc.get("content", "") for doc in chunk_docs]
            embeddings = np.array(
                await asyncio.to_thread(self.embedding_model.embed_documents, texts)
            ).astype("float32")

            index = faiss.IndexFlatIP(self.embedding_dimension)
            index.add(embeddings)

            metadata = {}
            for i, doc in enumerate(chunk_docs):
                metadata[i] = {
                    "chunk_id": doc.get("chunk_id"),
                    "dataset_id": dataset_id,
                    "user_id": doc.get("user_id"),
                    "chunk_type": doc.get("chunk_type"),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "indexed_at": datetime.now().isoformat(),
                }

            # Persist to disk for future loads
            self._atomic_write(index, self._chunk_index_path(dataset_id), is_faiss=True)
            self._atomic_write(metadata, self._chunk_metadata_path(dataset_id), is_faiss=False)

            self._chunk_indices[dataset_id] = index
            self._chunk_metadata[dataset_id] = metadata

            _elapsed = time.monotonic() - _start
            logger.info(
                "[RAG] Rebuilt chunk index for dataset %s from MongoDB "
                "(%d chunks, %.2fs)",
                dataset_id[:8],
                len(chunk_docs),
                _elapsed,
            )
            return index

        except Exception as e:
            logger.error(
                "[RAG] Failed to rebuild chunk index for %s from MongoDB: %s",
                dataset_id[:8],
                e,
            )
            return None

    def assemble_context_from_chunks(
        self, chunks: List[Dict[str, Any]], max_tokens: int = 2000
    ) -> str:
        """
        Assemble retrieved chunks into a context string for LLM.

        Args:
            chunks: Retrieved chunks with content
            max_tokens: Approximate token limit (1 token ≈ 4 chars)

        Returns:
            Assembled context string
        """
        max_chars = max_tokens * 4
        context_parts = []
        current_chars = 0

        # Prioritize by chunk type
        type_priority = ["schema", "statistics", "column", "relationship", "sample"]
        sorted_chunks = sorted(
            chunks,
            key=lambda c: (
                type_priority.index(c.get("chunk_type", "sample"))
                if c.get("chunk_type") in type_priority
                else 99
            ),
        )

        for chunk in sorted_chunks:
            content = chunk.get("content", "")
            if current_chars + len(content) > max_chars:
                # Truncate last chunk if needed
                remaining = max_chars - current_chars
                if remaining > 100:
                    context_parts.append(content[:remaining] + "...")
                break

            context_parts.append(content)
            current_chars += len(content) + 2  # +2 for separator

        return "\n\n".join(context_parts)


faiss_vector_service = FAISSVectorService()
