"""
Response Cache Service
=====================
Intelligent caching to handle API rate limits (429 errors) gracefully.

Features:
- Caches successful LLM responses by query similarity
- Provides fallback responses when API is unavailable
- Tracks rate limit status per model
- Generates synthetic helpful responses when all else fails

This ensures users ALWAYS get a helpful response, even during:
- OpenRouter rate limits (50 req/day on free tier)
- API outages
- Network issues
"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import re

import numpy as np

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    LRU cache for LLM responses with intelligent matching and fallbacks.

    Features:
    - Exact match caching (hash-based)
    - Semantic similarity caching (embeddings)
    - Word overlap fallback (no embeddings)
    - Rate limit tracking
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
        self._embeddings: Dict[str, np.ndarray] = {}  # cache_key -> embedding
        self._rate_limit_status: Dict[
            str, Dict
        ] = {}  # model -> {limited_until, count_today}
        self._lock = threading.Lock()
        self._embedding_model = None

        # Initialize embedding model for semantic matching
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        """Initialize sentence transformer for semantic similarity."""
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(
                f"Response cache using semantic embeddings: {self.embedding_model_name}"
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not available, using word overlap matching"
            )
            self._embedding_model = None
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}, using word overlap")
            self._embedding_model = None

    def _compute_embedding(self, text: str) -> Optional[np.ndarray]:
        """Compute embedding for text using loaded model."""
        if self._embedding_model is None:
            return None
        try:
            return self._embedding_model.encode(
                text, normalize_embeddings=True, show_progress_bar=False
            )
        except Exception as e:
            logger.warning(f"Embedding computation failed: {e}")
            return None

    def _normalize_query(self, query: str) -> str:
        """Normalize query for cache matching."""
        # Lowercase, remove extra whitespace, remove punctuation variations
        normalized = query.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[?!.,;:]+$", "", normalized)
        return normalized

    def _generate_cache_key(
        self, query: str, dataset_id: str, mode: str = "learning"
    ) -> str:
        """Generate cache key from normalized query, dataset, and chat mode."""
        normalized = self._normalize_query(query)
        content = f"{dataset_id}:{mode}:{normalized}"
        return hashlib.md5(content.encode()).hexdigest()

    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired."""
        created_at = entry.get("created_at", 0)
        return time.time() - created_at > self.ttl_seconds

    def get(
        self, query: str, dataset_id: str, mode: str = "learning"
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available and not expired.

        Returns:
            Cached response dict or None
        """
        key = self._generate_cache_key(query, dataset_id, mode)

        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not self._is_expired(entry):
                    # Move to end (LRU)
                    self._cache.move_to_end(key)
                    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
                    logger.info(f"Cache HIT for query hash: {query_hash}")
                    return entry["response"]
                else:
                    # Remove expired entry
                    del self._cache[key]

        return None

    def set(
        self,
        query: str,
        dataset_id: str,
        response: Dict[str, Any],
        mode: str = "learning",
    ) -> None:
        """
        Cache a successful response.
        Also computes and stores embedding for semantic similarity.
        """
        key = self._generate_cache_key(query, dataset_id, mode)

        with self._lock:
            # Evict oldest if at capacity
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

            # Compute and store embedding for semantic matching
            embedding = self._compute_embedding(query)
            if embedding is not None:
                self._embeddings[key] = embedding

            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            logger.info(f"Cached response for query hash: {query_hash}")

    def find_similar(
        self,
        query: str,
        dataset_id: str,
        mode: str = "learning",
        threshold: float = 0.7,
        use_semantic: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a similar cached query using semantic similarity.

        This helps when users ask slightly different versions of the same question.
        Uses embeddings when available, falls back to word overlap.

        Args:
            query: User query
            dataset_id: Dataset ID
            mode: Chat mode
            threshold: Minimum similarity threshold (0.0-1.0)
            use_semantic: Whether to use semantic embeddings (default True)

        Returns:
            Cached response if similarity >= threshold, else None
        """
        # Try semantic matching first if available
        if use_semantic and self._embedding_model:
            semantic_result = self._find_similar_semantic(
                query, dataset_id, mode, threshold
            )
            if semantic_result:
                return semantic_result

        # Fallback to word overlap matching
        return self._find_similar_word_overlap(query, dataset_id, mode, threshold)

    def _find_similar_semantic(
        self, query: str, dataset_id: str, mode: str, threshold: float
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar query using semantic embeddings.

        This provides better matching for semantically similar queries
        that use different words but have the same meaning.
        """
        try:
            if not self._embedding_model:
                return None

            query_embedding = self._embedding_model.encode(
                query, normalize_embeddings=True, show_progress_bar=False
            )

            best_match = None
            best_score = threshold

            with self._lock:
                for key, entry in self._cache.items():
                    if (
                        entry["dataset_id"] != dataset_id
                        or entry.get("mode", "learning") != mode
                        or self._is_expired(entry)
                    ):
                        continue

                    cached_embedding = self._embeddings.get(key)
                    if cached_embedding is None:
                        continue

                    # Cosine similarity
                    score = float(np.dot(query_embedding, cached_embedding))

                    if score > best_score:
                        best_score = score
                        best_match = entry["response"]

            if best_match:
                logger.info(f"Semantic cache HIT (score: {best_score:.2f})")

            return best_match

        except Exception as e:
            logger.warning(f"Semantic similarity failed: {e}")
            return None

    def _find_similar_word_overlap(
        self, query: str, dataset_id: str, mode: str, threshold: float
    ) -> Optional[Dict[str, Any]]:
        """
        Find similar query using word overlap (Jaccard similarity).

        Fallback when embeddings are unavailable.
        """
        normalized = self._normalize_query(query)
        query_words = set(normalized.split())

        best_match = None
        best_score = threshold

        with self._lock:
            for key, entry in self._cache.items():
                if (
                    entry["dataset_id"] != dataset_id
                    or entry.get("mode", "learning") != mode
                    or self._is_expired(entry)
                ):
                    continue

                cached_words = set(self._normalize_query(entry["query"]).split())

                # Jaccard similarity
                if not query_words or not cached_words:
                    continue

                intersection = len(query_words & cached_words)
                union = len(query_words | cached_words)
                score = intersection / union if union > 0 else 0

                if score > best_score:
                    best_score = score
                    best_match = entry["response"]

        if best_match:
            logger.info(f"Word overlap cache HIT (score: {best_score:.2f})")

        return best_match

    # ---------------------------------------------------------------
    # Rate Limit Tracking
    # ---------------------------------------------------------------
    def mark_rate_limited(self, model: str, retry_after_seconds: int = 3600) -> None:
        """Mark a model as rate limited."""
        self._rate_limit_status[model] = {
            "limited_until": time.time() + retry_after_seconds,
            "last_limited": time.time(),
        }
        logger.warning(
            f"Model {model} marked as rate limited for {retry_after_seconds}s"
        )

    def is_rate_limited(self, model: str) -> bool:
        """Check if model is currently rate limited."""
        status = self._rate_limit_status.get(model)
        if not status:
            return False
        return time.time() < status.get("limited_until", 0)

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit status for all models."""
        info = {}
        for model, status in self._rate_limit_status.items():
            limited_until = status.get("limited_until", 0)
            if time.time() < limited_until:
                info[model] = {
                    "is_limited": True,
                    "seconds_remaining": int(limited_until - time.time()),
                    "retry_at": datetime.fromtimestamp(limited_until).isoformat(),
                }
            else:
                info[model] = {"is_limited": False}
        return info

    def clear_rate_limit(self, model: str) -> None:
        """Clear rate limit status for a model."""
        if model in self._rate_limit_status:
            del self._rate_limit_status[model]


class FallbackResponseGenerator:
    """
    Generates helpful fallback responses when AI is unavailable.

    Provides contextual, useful responses based on:
    - Query type detection
    - Dataset metadata
    - Common analytics patterns
    """

    # Query patterns and response templates
    QUERY_PATTERNS = {
        "summary": {
            "patterns": [
                r"summary",
                r"overview",
                r"describe",
                r"tell me about",
                r"what is this",
            ],
            "response": """## Dataset Overview

Your dataset has:

📊 **Quick Stats:**
- **Rows**: {row_count:,}
- **Columns**: {col_count}
- **Data Types**: {data_types}

📋 **Available Columns:**
{column_list}

**Some questions you could ask next:**
- What are the key trends in this data?
- Are there any correlations between columns?
- What segments or groups exist in the data?""",
        },
        "total": {
            "patterns": [r"total", r"sum of", r"how much"],
            "response": """## Analyzing Totals

To find totals, look at these numeric columns:

📊 **Numeric columns**: {numeric_columns}

**Quick options:**
1. Check the **Dashboard** KPIs for pre-calculated totals
2. Use **Chart Studio** → Select column → Aggregation: "Sum"

**Questions to try:**
- What's the average of {numeric_columns}?
- Show me totals grouped by {categorical_columns}""",
        },
        "average": {
            "patterns": [r"average", r"mean", r"avg"],
            "response": """## Calculating Averages

These numeric columns are available for averaging:

📊 **Numeric columns**: {numeric_columns}

**Quick options:**
1. Check the **Dashboard** for pre-computed averages
2. Use **Chart Studio** → Select column → Aggregation: "Mean"

**Questions to try:**
- What are the totals by {categorical_columns}?
- Show me the distribution of {numeric_columns}""",
        },
        "trend": {
            "patterns": [r"trend", r"over time", r"change", r"growth"],
            "response": """## Looking at Trends

For trend analysis, you have:

📈 **Numeric columns**: {numeric_columns}
📅 **Date columns**: {date_columns}

**To visualize trends:**
1. Go to **Chart Studio**
2. Create a **Line Chart**
3. Use the date column for the X-axis

**Questions to try:**
- What patterns exist in {numeric_columns}?
- Are there seasonal variations in the data?""",
        },
        "compare": {
            "patterns": [r"compare", r"vs", r"versus", r"difference"],
            "response": """## Comparing Values

For comparisons, use these columns:

📊 **Categories**: {categorical_columns}
📈 **Values**: {numeric_columns}

**To compare visually:**
1. **Chart Studio** → Grouped Bar Chart
2. Select a category to group by
3. Pick a numeric column to compare

**Questions to try:**
- How does {numeric_columns} vary by {categorical_columns}?
- What are the key differences between groups?""",
        },
        "correlation": {
            "patterns": [
                r"correlat",
                r"relationship",
                r"related",
                r"explain",
                r"causal",
                r"driven",
            ],
            "response": """## Finding Relationships

To explore correlations:

📊 **Numeric columns**: {numeric_columns}

**Quick options:**
1. **Insights Page** → Check the correlation matrix
2. **Chart Studio** → Create a scatter plot between two numeric columns

**Questions to try:**
- What are the main patterns in {numeric_columns}?
- How do different columns relate to each other?""",
        },
        "top": {
            "patterns": [r"top \d+", r"highest", r"best", r"most"],
            "response": """## Finding Top Values

Available columns for ranking:

📊 **All columns**: {all_columns}

**To find top values:**
1. **Chart Studio** → Bar Chart
2. Sort by value (descending)
3. Limit to top N rows

**Questions to try:**
- What are the highest values in {numeric_columns}?
- Show me the distribution of key metrics?""",
        },
        "default": {
            "patterns": [],
            "response": """## Your Dataset

**{dataset_name}**
- **{row_count:,}** rows × **{col_count}** columns

📋 **Key columns:**
{column_preview}

**Explore further:**
- Check the **Dashboard** for quick insights
- Use **Chart Studio** to visualize relationships
- Visit the **Insights** page for detected patterns

**What would you like to know about this data?**""",
        },
    }

    @classmethod
    def generate(
        cls,
        query: str,
        dataset_metadata: Dict[str, Any],
        error_type: str = "rate_limit",
    ) -> Dict[str, Any]:
        """
        Generate a helpful fallback response based on query type.

        Args:
            query: User's original question
            dataset_metadata: Dataset info for context
            error_type: Type of error (rate_limit, timeout, unavailable)

        Returns:
            Response dict with response_text and metadata
        """
        # Extract metadata
        overview = dataset_metadata.get("dataset_overview", {})
        columns = dataset_metadata.get("column_metadata", [])

        row_count = overview.get("total_rows", 0)
        col_count = len(columns)
        dataset_name = overview.get("filename", "your dataset")

        # Categorize columns
        numeric_cols = [
            c["name"]
            for c in columns
            if c.get("type", "") in ["float64", "int64", "number", "integer", "float"]
        ]
        categorical_cols = [
            c["name"]
            for c in columns
            if c.get("type", "") in ["object", "string", "category", "categorical"]
        ]
        date_cols = [
            c["name"]
            for c in columns
            if "date" in c.get("type", "").lower()
            or "time" in c.get("name", "").lower()
            or "date" in c.get("name", "").lower()
        ]
        all_cols = [c.get("name", "") for c in columns if c.get("name")]

        # Detect query type
        query_lower = query.lower()
        template_key = "default"

        for key, config in cls.QUERY_PATTERNS.items():
            if key == "default":
                continue
            for pattern in config["patterns"]:
                if re.search(pattern, query_lower):
                    template_key = key
                    break
            if template_key != "default":
                break

        # Get template
        template = cls.QUERY_PATTERNS[template_key]["response"]

        # Format response
        response_text = template.format(
            dataset_name=dataset_name,
            row_count=row_count,
            col_count=col_count,
            data_types=", ".join(set(c.get("type", "unknown") for c in columns[:5])),
            column_list="\n".join(
                [f"- `{c['name']}` ({c.get('type', 'unknown')})" for c in columns[:10]]
            )
            + (f"\n- ... and {len(columns) - 10} more" if len(columns) > 10 else ""),
            column_preview=", ".join(all_cols[:5])
            + ("..." if len(all_cols) > 5 else ""),
            numeric_columns=", ".join(numeric_cols[:5])
            if numeric_cols
            else "None detected",
            categorical_columns=", ".join(categorical_cols[:5])
            if categorical_cols
            else "None detected",
            date_columns=", ".join(date_cols[:3]) if date_cols else "None detected",
            all_columns=", ".join(all_cols[:8]) + ("..." if len(all_cols) > 8 else ""),
        )

        return {
            "response": response_text,
            "response_text": response_text,
            "chart_config": None,
            "is_fallback": True,
            "fallback_reason": error_type,
            "query_type_detected": template_key,
        }


# Global instances
response_cache = ResponseCache(max_size=500, ttl_hours=24)
fallback_generator = FallbackResponseGenerator()
