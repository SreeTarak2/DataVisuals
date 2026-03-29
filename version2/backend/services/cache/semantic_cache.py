"""
Semantic Cache Service
=====================
Intelligent caching using sentence embeddings for query similarity.

Features:
- Sentence embeddings for semantic similarity matching
- LRU cache with configurable TTL
- Per-dataset chart config caching
- Cost-effective caching strategy

Author: DataSage AI Team
Version: 1.0
"""

import logging
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import OrderedDict
import re

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    LRU cache with semantic similarity matching for LLM responses.

    Uses lightweight embeddings for fast similarity comparison.
    Falls back to word overlap matching when embeddings unavailable.
    """

    def __init__(
        self,
        max_size: int = 500,
        ttl_hours: int = 24,
        similarity_threshold: float = 0.85,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self.similarity_threshold = similarity_threshold
        self.embedding_model_name = embedding_model

        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._embeddings: Dict[str, List[float]] = {}  # cache_key -> embedding
        self._embedding_model = None
        self._use_embeddings = False

        self._initialize_embedding_model()

    def _initialize_embedding_model(self):
        """Initialize the embedding model for semantic similarity."""
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            self._use_embeddings = True
            logger.info(f"Semantic cache using embeddings: {self.embedding_model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not available, using word overlap matching"
            )
            self._use_embeddings = False
        except Exception as e:
            logger.warning(
                f"Failed to load embedding model: {e}, using word overlap matching"
            )
            self._use_embeddings = False

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent matching."""
        normalized = query.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[?!.,;:]+$", "", normalized)
        return normalized

    def _generate_cache_key(
        self, query: str, dataset_id: str, mode: str = "chat"
    ) -> str:
        """Generate deterministic cache key."""
        normalized = self._normalize_query(query)
        content = f"{dataset_id}:{mode}:{normalized}"
        return hashlib.md5(content.encode()).hexdigest()

    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired."""
        created_at = entry.get("created_at", 0)
        return time.time() - created_at > self.ttl_seconds

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding for text."""
        if not self._use_embeddings or not self._embedding_model:
            return None

        try:
            embedding = self._embedding_model.encode(
                text, normalize_embeddings=True, show_progress_bar=False
            )
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Embedding computation failed: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _word_overlap_similarity(self, text1: str, text2: str) -> float:
        """Compute Jaccard similarity using word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts."""
        if self._use_embeddings and self._embedding_model:
            emb1 = self._compute_embedding(text1)
            emb2 = self._compute_embedding(text2)

            if emb1 and emb2:
                return self._cosine_similarity(emb1, emb2)

        return self._word_overlap_similarity(text1, text2)

    def get(
        self, query: str, dataset_id: str, mode: str = "chat"
    ) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        key = self._generate_cache_key(query, dataset_id, mode)

        with self._lock():
            if key in self._cache:
                entry = self._cache[key]
                if not self._is_expired(entry):
                    self._cache.move_to_end(key)
                    logger.info(f"Semantic cache HIT (exact): {key[:8]}")
                    return entry["response"]
                else:
                    del self._cache[key]
                    if key in self._embeddings:
                        del self._embeddings[key]

        return None

    def get_similar(
        self, query: str, dataset_id: str, mode: str = "chat", threshold: float = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a similar cached query using semantic similarity.

        Returns:
            Cached response if similarity >= threshold, else None
        """
        threshold = threshold or self.similarity_threshold

        with self._lock():
            best_match = None
            best_score = threshold

            for key, entry in self._cache.items():
                if (
                    entry["dataset_id"] != dataset_id
                    or entry.get("mode", "chat") != mode
                    or self._is_expired(entry)
                ):
                    continue

                cached_query = entry.get("query", "")
                score = self._compute_similarity(query, cached_query)

                if score > best_score:
                    best_score = score
                    best_match = entry["response"]

        if best_match:
            logger.info(f"Semantic cache HIT (similar, score: {best_score:.2f})")

        return best_match

    def set(
        self, query: str, dataset_id: str, response: Dict[str, Any], mode: str = "chat"
    ) -> None:
        """Cache a successful response."""
        key = self._generate_cache_key(query, dataset_id, mode)

        with self._lock():
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                if oldest_key in self._embeddings:
                    del self._embeddings[oldest_key]

            self._cache[key] = {
                "response": response,
                "query": query,
                "dataset_id": dataset_id,
                "mode": mode,
                "created_at": time.time(),
            }

            embedding = self._compute_embedding(query)
            if embedding:
                self._embeddings[key] = embedding

        logger.info(f"Semantic cache SET: {key[:8]}")

    def invalidate(self, dataset_id: str = None, mode: str = None) -> int:
        """
        Invalidate cache entries.

        Args:
            dataset_id: If provided, invalidate all entries for this dataset
            mode: If provided, invalidate all entries for this mode

        Returns:
            Number of entries invalidated
        """
        count = 0
        keys_to_delete = []

        with self._lock():
            for key, entry in self._cache.items():
                should_delete = True

                if dataset_id and entry.get("dataset_id") != dataset_id:
                    should_delete = False
                if mode and entry.get("mode") != mode:
                    should_delete = False

                if should_delete:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]
                if key in self._embeddings:
                    del self._embeddings[key]
                count += 1

        logger.info(f"Semantic cache invalidated: {count} entries")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock():
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if self._is_expired(e))

            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": total - expired,
                "max_size": self.max_size,
                "ttl_hours": self.ttl_seconds / 3600,
                "similarity_threshold": self.similarity_threshold,
                "using_embeddings": self._use_embeddings,
                "embedding_model": self.embedding_model_name
                if self._use_embeddings
                else None,
            }

    def _lock(self):
        """Simple thread lock for thread safety."""
        import threading

        if not hasattr(self, "_thread_lock"):
            self._thread_lock = threading.Lock()
        return self._thread_lock


class ChartConfigCache:
    """
    Specialized cache for chart configurations per dataset.

    Caches:
    - Chart recommendations per dataset
    - Column mappings
    - Chart type recommendations
    """

    def __init__(self, ttl_hours: int = 168):  # 7 days default
        self.ttl_seconds = ttl_hours * 3600
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, dataset_id: str, context: str = "default") -> str:
        """Generate cache key."""
        return f"{dataset_id}:{context}"

    def get(
        self, dataset_id: str, context: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get cached chart config."""
        key = self._generate_key(dataset_id, context)

        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry.get("created_at", 0) < self.ttl_seconds:
                logger.info(f"Chart config cache HIT: {dataset_id}")
                return entry["config"]
            else:
                del self._cache[key]

        return None

    def set(
        self, dataset_id: str, config: Dict[str, Any], context: str = "default"
    ) -> None:
        """Cache chart config."""
        key = self._generate_key(dataset_id, context)

        self._cache[key] = {"config": config, "created_at": time.time()}

        logger.info(f"Chart config cache SET: {dataset_id}")

    def invalidate(self, dataset_id: str) -> None:
        """Invalidate all cache entries for a dataset."""
        keys_to_delete = [
            k for k in self._cache.keys() if k.startswith(f"{dataset_id}:")
        ]

        for key in keys_to_delete:
            del self._cache[key]

        logger.info(
            f"Chart config cache invalidated: {len(keys_to_delete)} entries for {dataset_id}"
        )


class DashboardLayoutCache:
    """
    Specialized cache for dashboard layouts per dataset.

    Caches:
    - Dashboard blueprints
    - Pattern selections
    - Component configurations
    """

    def __init__(self, ttl_hours: int = 168):  # 7 days default
        self.ttl_seconds = ttl_hours * 3600
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, dataset_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached dashboard layout."""
        key = f"{dataset_id}:{user_id}"

        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry.get("created_at", 0) < self.ttl_seconds:
                logger.info(f"Dashboard layout cache HIT: {key}")
                return entry["layout"]
            else:
                del self._cache[key]

        return None

    def set(self, dataset_id: str, user_id: str, layout: Dict[str, Any]) -> None:
        """Cache dashboard layout."""
        key = f"{dataset_id}:{user_id}"

        self._cache[key] = {"layout": layout, "created_at": time.time()}

        logger.info(f"Dashboard layout cache SET: {key}")

    def invalidate(self, dataset_id: str = None, user_id: str = None) -> int:
        """Invalidate cache entries."""
        count = 0

        if dataset_id:
            keys_to_delete = [
                k for k in self._cache.keys() if k.startswith(f"{dataset_id}:")
            ]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1

        if user_id:
            keys_to_delete = [
                k for k in self._cache.keys() if k.endswith(f":{user_id}")
            ]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1

        logger.info(f"Dashboard layout cache invalidated: {count} entries")
        return count


# Singleton instances
semantic_cache = SemanticCache(max_size=500, ttl_hours=24)
chart_config_cache = ChartConfigCache(ttl_hours=168)
dashboard_layout_cache = DashboardLayoutCache(ttl_hours=168)
