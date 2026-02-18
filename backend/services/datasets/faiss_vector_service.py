import logging
import json
import pickle
import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
import faiss
from langchain_huggingface import HuggingFaceEmbeddings
from bson import ObjectId

from db.database import get_database
from core.config import settings

logger = logging.getLogger(__name__)

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
        
        # Thread-safety locks for index modifications
        self._dataset_index_lock = asyncio.Lock()
        self._query_index_lock = asyncio.Lock()
        
        self.embedding_model = None
        self.dataset_index = None
        self.query_history_index = None
        self.dataset_metadata = {}
        self.query_history_metadata = {}
        
        if self.enable_vector_search:
            self._initialize_components()
        else:
            logger.info("Vector search is disabled by configuration.")

    def _initialize_components(self):
        try:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name="BAAI/bge-large-en-v1.5",
                model_kwargs={'device': 'cpu'}, 
                encode_kwargs={'normalize_embeddings': True}  
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
                with open(dataset_metadata_path, 'rb') as f:
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
                with open(query_metadata_path, 'rb') as f:
                    self.query_history_metadata = pickle.load(f)
                logger.info(f"Loaded query history index with {self.query_history_index.ntotal} vectors")
            else:
                self.query_history_index = faiss.IndexFlatIP(self.embedding_dimension)
                self.query_history_metadata = {}
                logger.info("Created new query history index")
                
        except Exception as e:
            logger.error(f"Failed to initialize FAISS indices: {e}")
            raise

    @property
    def mongo_db(self):
        db_conn = get_database()
        if db_conn is None:
            raise Exception("MongoDB is not connected.")
        return db_conn

    async def add_dataset_to_vector_db(self, dataset_id: str, dataset_metadata: Dict, user_id: str) -> bool:
        """Add dataset to vector index with thread-safe locking."""
        if not self.enable_vector_search or not self.embedding_model:
            return False
        
        try:
            # Compute embedding outside the lock (CPU-intensive)
            content = json.dumps(dataset_metadata)
            embedding = np.array(self.embedding_model.embed_documents([content])).astype('float32')
            
            # Lock for index modification
            async with self._dataset_index_lock:
                self.dataset_index.add(embedding)
                index_id = self.dataset_index.ntotal - 1
                self.dataset_metadata[index_id] = {
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "content": content,
                    "added_at": datetime.now().isoformat()
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
        if not self.enable_vector_search or not self.embedding_model:
            return False
        
        try:
            # Compute embedding outside the lock (CPU-intensive)
            embedding = np.array([self.embedding_model.embed_query(query)]).astype('float32')
            
            # Lock for index modification
            async with self._query_index_lock:
                self.query_history_index.add(embedding)
                index_id = self.query_history_index.ntotal - 1
                self.query_history_metadata[index_id] = {
                    "query": query,
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                self._query_dirty = True
                self._persist_query_history_index()
            
            logger.info(f"Added query to history for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add query to history: {e}")
            return False

    async def search_similar_datasets(self, query: str, user_id: str, k: int = 5) -> List[Dict[str, Any]]:
        if not self.enable_vector_search or not self.embedding_model:
            return []
        
        try:
            if self._dataset_dirty:
                self._lazy_rebuild_dataset_index()
            
            query_embedding = np.array([self.embedding_model.embed_query(query)]).astype('float32')
            
            distances, indices = self.dataset_index.search(query_embedding, k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.dataset_metadata):
                    metadata = self.dataset_metadata[idx]
                    if metadata["user_id"] == user_id:
                        results.append({
                            "dataset_id": metadata["dataset_id"],
                            "similarity": float(distances[0][i]),
                            "content_preview": metadata["content"][:200] + "..."
                        })
            
            return sorted(results, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            logger.error(f"Failed to search similar datasets: {e}")
            return []

    async def search_similar_queries(self, query: str, user_id: str, k: int = 5) -> List[Dict[str, Any]]:
        if not self.enable_vector_search or not self.embedding_model:
            return []
        
        try:
            if self._query_dirty:
                self._lazy_rebuild_query_history_index()
            
            query_embedding = np.array([self.embedding_model.embed_query(query)]).astype('float32')
            
            distances, indices = self.query_history_index.search(query_embedding, k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.query_history_metadata):
                    metadata = self.query_history_metadata[idx]
                    if metadata["user_id"] == user_id:
                        results.append({
                            "query": metadata["query"],
                            "dataset_id": metadata["dataset_id"],
                            "similarity": float(distances[0][i]),
                            "timestamp": metadata["timestamp"]
                        })
            
            return sorted(results, key=lambda x: x["similarity"], reverse=True)
        except Exception as e:
            logger.error(f"Failed to search similar queries: {e}")
            return []

    def _persist_dataset_index(self):
        try:
            dataset_index_path = os.path.join(self.vector_db_path, "dataset_index.faiss")
            dataset_metadata_path = os.path.join(self.vector_db_path, "dataset_metadata.pkl")
            
            faiss.write_index(self.dataset_index, dataset_index_path)
            with open(dataset_metadata_path, 'wb') as f:
                pickle.dump(self.dataset_metadata, f)
                
        except Exception as e:
            logger.error(f"Error persisting dataset index: {e}")

    def _persist_query_history_index(self):
        try:
            query_index_path = os.path.join(self.vector_db_path, "query_index.faiss")
            query_metadata_path = os.path.join(self.vector_db_path, "query_metadata.pkl")
            
            faiss.write_index(self.query_history_index, query_index_path)
            with open(query_metadata_path, 'wb') as f:
                pickle.dump(self.query_history_metadata, f)
                
        except Exception as e:
            logger.error(f"Error persisting query history index: {e}")

    async def get_vector_db_stats(self, user_id: str) -> Dict[str, Any]:
        if not self.enable_vector_search:
            return {"status": "disabled", "indices": {}}
        
        if self._dataset_dirty:
            self._lazy_rebuild_dataset_index()
        
        stats = {
            "status": "enabled",
            "embedding_model": self.embedding_model_name,
            "embedding_dimension": self.embedding_dimension,
            "indices": {
                "datasets": {
                    "total_vectors": self.dataset_index.ntotal if self.dataset_index else 0,
                    "user_vectors": len([m for m in self.dataset_metadata.values() if m["user_id"] == user_id])
                },
                "query_history": {
                    "total_vectors": self.query_history_index.ntotal if self.query_history_index else 0,
                    "user_vectors": len([m for m in self.query_history_metadata.values() if m["user_id"] == user_id])
                }
            }
        }
        
        return stats

    async def reset_vector_db(self, user_id: str) -> bool:
        if not self.enable_vector_search:
            logger.info("Vector search disabled. Skipping reset.")
            return False
        
        try:
            self.dataset_metadata = {
                idx: metadata for idx, metadata in self.dataset_metadata.items()
                if metadata["user_id"] != user_id
            }
            
            self.query_history_metadata = {
                idx: metadata for idx, metadata in self.query_history_metadata.items()
                if metadata["user_id"] != user_id
            }
            
            self._dataset_dirty = True
            self._query_dirty = True
            
            logger.info(f"Vector database reset for user {user_id} (lazy rebuild pending)")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting vector database for user {user_id}: {e}")
            return False

    def _lazy_rebuild_dataset_index(self):
        if not self._dataset_dirty:
            return
        try:
            if self.dataset_metadata:
                new_dataset_index = faiss.IndexFlatIP(self.embedding_dimension)
                for metadata in self.dataset_metadata.values():
                    embedding = np.array(self.embedding_model.embed_documents([metadata["content"]]))
                    new_dataset_index.add(embedding)
                self.dataset_index = new_dataset_index
            else:
                self.dataset_index = faiss.IndexFlatIP(self.embedding_dimension)
            
            self._dataset_dirty = False
            self._persist_dataset_index()
            logger.info("Dataset index lazily rebuilt")
        except Exception as e:
            logger.error(f"Lazy rebuild failed for dataset index: {e}")
            raise

    def _lazy_rebuild_query_history_index(self):
        if not self._query_dirty:
            return
        try:
            if self.query_history_metadata:
                new_query_index = faiss.IndexFlatIP(self.embedding_dimension)
                for metadata in self.query_history_metadata.values():
                    embedding = np.array([self.embedding_model.embed_query(metadata["query"])])
                    new_query_index.add(embedding)
                self.query_history_index = new_query_index
            else:
                self.query_history_index = faiss.IndexFlatIP(self.embedding_dimension)
            
            self._query_dirty = False
            self._persist_query_history_index()
            logger.info("Query history index lazily rebuilt")
        except Exception as e:
            logger.error(f"Lazy rebuild failed for query history index: {e}")
            raise

    def _rebuild_indices(self):
        self._lazy_rebuild_dataset_index()
        self._lazy_rebuild_query_history_index()

    # =========================================================================
    # CHUNK-LEVEL VECTOR INDEXING FOR RAG
    # =========================================================================
    
    async def index_dataset_chunks(
        self, 
        dataset_id: str, 
        chunks: List[Dict[str, Any]], 
        user_id: str
    ) -> bool:
        """
        Index semantic chunks for a dataset for RAG retrieval.
        
        Args:
            dataset_id: Unique dataset identifier
            chunks: List of chunk dicts from ChunkService
            user_id: Owner user ID for filtering
            
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
            # Initialize chunk index if not exists
            if not hasattr(self, 'chunk_index') or self.chunk_index is None:
                self._initialize_chunk_index()
            
            # Extract text content for embedding
            texts = [chunk.get("content", "") for chunk in chunks]
            
            # Compute embeddings (outside lock for performance)
            embeddings = np.array(
                self.embedding_model.embed_documents(texts)
            ).astype('float32')
            
            # Lock for index modification
            async with self._dataset_index_lock:
                for i, chunk in enumerate(chunks):
                    self.chunk_index.add(embeddings[i:i+1])
                    index_id = self.chunk_index.ntotal - 1
                    
                    self.chunk_metadata[index_id] = {
                        "chunk_id": chunk.get("chunk_id"),
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "chunk_type": chunk.get("chunk_type"),
                        "content": chunk.get("content", ""),
                        "metadata": chunk.get("metadata", {}),
                        "indexed_at": datetime.now().isoformat()
                    }
                
                self._persist_chunk_index()
            
            logger.info(f"Indexed {len(chunks)} chunks for dataset {dataset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index chunks for dataset {dataset_id}: {e}")
            return False
    
    async def search_relevant_chunks(
        self, 
        query: str, 
        dataset_id: str, 
        user_id: str,
        k: int = 5,
        score_threshold: float = 0.5,
        chunk_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant chunks using semantic similarity.
        
        Args:
            query: User query to match against chunks
            dataset_id: Filter to specific dataset
            user_id: Filter to user's datasets
            k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            chunk_types: Optional filter for chunk types
            
        Returns:
            List of matching chunks with similarity scores
        """
        if not self.enable_vector_search or not self.embedding_model:
            return []
        
        try:
            # Initialize chunk index if not exists
            if not hasattr(self, 'chunk_index') or self.chunk_index is None:
                self._initialize_chunk_index()
            
            if self.chunk_index.ntotal == 0:
                logger.debug(f"Chunk index is empty, no results for query")
                return []
            
            # Compute query embedding
            query_embedding = np.array(
                [self.embedding_model.embed_query(query)]
            ).astype('float32')
            
            # Search with extra results for filtering
            search_k = min(k * 3, self.chunk_index.ntotal)
            distances, indices = self.chunk_index.search(query_embedding, search_k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < 0 or idx >= len(self.chunk_metadata):
                    continue
                    
                metadata = self.chunk_metadata.get(idx)
                if not metadata:
                    continue
                
                # Filter by dataset and user
                if metadata.get("dataset_id") != dataset_id:
                    continue
                if metadata.get("user_id") != user_id:
                    continue
                
                # Filter by chunk type if specified
                if chunk_types and metadata.get("chunk_type") not in chunk_types:
                    continue
                
                # Filter by score threshold
                score = float(distances[0][i])
                if score < score_threshold:
                    continue
                
                results.append({
                    "chunk_id": metadata.get("chunk_id"),
                    "chunk_type": metadata.get("chunk_type"),
                    "content": metadata.get("content"),
                    "metadata": metadata.get("metadata", {}),
                    "similarity": score
                })
                
                if len(results) >= k:
                    break
            
            logger.debug(f"Found {len(results)} relevant chunks for query: '{query[:50]}...'")
            return sorted(results, key=lambda x: x["similarity"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}")
            return []
    
    async def delete_dataset_chunks(self, dataset_id: str, user_id: str) -> bool:
        """Delete all chunks for a dataset (for re-indexing)."""
        if not self.enable_vector_search:
            return False
        
        try:
            if not hasattr(self, 'chunk_metadata'):
                return True
            
            # Remove from metadata (lazy rebuild will handle index)
            indices_to_remove = [
                idx for idx, meta in self.chunk_metadata.items()
                if meta.get("dataset_id") == dataset_id and meta.get("user_id") == user_id
            ]
            
            for idx in indices_to_remove:
                del self.chunk_metadata[idx]
            
            self._chunk_dirty = True
            logger.info(f"Marked {len(indices_to_remove)} chunks for deletion from dataset {dataset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete chunks for dataset {dataset_id}: {e}")
            return False
    
    def _initialize_chunk_index(self):
        """Initialize or load chunk index."""
        try:
            chunk_index_path = os.path.join(self.vector_db_path, "chunk_index.faiss")
            chunk_metadata_path = os.path.join(self.vector_db_path, "chunk_metadata.pkl")
            
            if os.path.exists(chunk_index_path) and os.path.exists(chunk_metadata_path):
                self.chunk_index = faiss.read_index(chunk_index_path)
                with open(chunk_metadata_path, 'rb') as f:
                    self.chunk_metadata = pickle.load(f)
                logger.info(f"Loaded chunk index with {self.chunk_index.ntotal} vectors")
            else:
                self.chunk_index = faiss.IndexFlatIP(self.embedding_dimension)
                self.chunk_metadata = {}
                logger.info("Created new chunk index")
            
            self._chunk_dirty = False
            
        except Exception as e:
            logger.error(f"Failed to initialize chunk index: {e}")
            self.chunk_index = faiss.IndexFlatIP(self.embedding_dimension)
            self.chunk_metadata = {}
    
    def _persist_chunk_index(self):
        """Persist chunk index to disk."""
        try:
            chunk_index_path = os.path.join(self.vector_db_path, "chunk_index.faiss")
            chunk_metadata_path = os.path.join(self.vector_db_path, "chunk_metadata.pkl")
            
            faiss.write_index(self.chunk_index, chunk_index_path)
            with open(chunk_metadata_path, 'wb') as f:
                pickle.dump(self.chunk_metadata, f)
                
            logger.debug("Chunk index persisted to disk")
        except Exception as e:
            logger.error(f"Error persisting chunk index: {e}")
    
    def assemble_context_from_chunks(
        self, 
        chunks: List[Dict[str, Any]], 
        max_tokens: int = 2000
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
            key=lambda c: (type_priority.index(c.get("chunk_type", "sample")) 
                          if c.get("chunk_type") in type_priority else 99)
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