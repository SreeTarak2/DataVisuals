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

faiss_vector_service = FAISSVectorService()