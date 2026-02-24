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

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    LRU cache for LLM responses with intelligent matching and fallbacks.
    """
    
    def __init__(self, max_size: int = 500, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._rate_limit_status: Dict[str, Dict] = {}  # model -> {limited_until, count_today}
        self._lock = threading.Lock()
        
    def _normalize_query(self, query: str) -> str:
        """Normalize query for cache matching."""
        # Lowercase, remove extra whitespace, remove punctuation variations
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[?!.,;:]+$', '', normalized)
        return normalized
    
    def _generate_cache_key(self, query: str, dataset_id: str) -> str:
        """Generate cache key from normalized query and dataset."""
        normalized = self._normalize_query(query)
        content = f"{dataset_id}:{normalized}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired."""
        created_at = entry.get("created_at", 0)
        return time.time() - created_at > self.ttl_seconds
    
    def get(self, query: str, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available and not expired.
        
        Returns:
            Cached response dict or None
        """
        key = self._generate_cache_key(query, dataset_id)
        
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
    
    def set(self, query: str, dataset_id: str, response: Dict[str, Any]) -> None:
        """
        Cache a successful response.
        """
        key = self._generate_cache_key(query, dataset_id)
        
        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = {
                "response": response,
                "query": query,
                "dataset_id": dataset_id,
                "created_at": time.time()
            }
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            logger.info(f"Cached response for query hash: {query_hash}")
    
    def find_similar(self, query: str, dataset_id: str, threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        Find a similar cached query using simple word overlap.
        
        This helps when users ask slightly different versions of the same question.
        """
        normalized = self._normalize_query(query)
        query_words = set(normalized.split())
        
        best_match = None
        best_score = threshold
        
        with self._lock:
            for key, entry in self._cache.items():
                if entry["dataset_id"] != dataset_id or self._is_expired(entry):
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
            logger.info(f"Found similar cached response (score: {best_score:.2f})")
            
        return best_match
    
    # ---------------------------------------------------------------
    # Rate Limit Tracking
    # ---------------------------------------------------------------
    def mark_rate_limited(self, model: str, retry_after_seconds: int = 3600) -> None:
        """Mark a model as rate limited."""
        self._rate_limit_status[model] = {
            "limited_until": time.time() + retry_after_seconds,
            "last_limited": time.time()
        }
        logger.warning(f"Model {model} marked as rate limited for {retry_after_seconds}s")
    
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
                    "retry_at": datetime.fromtimestamp(limited_until).isoformat()
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
            "patterns": [r"summary", r"overview", r"describe", r"tell me about", r"what is this"],
            "response": """## Dataset Overview

Based on the dataset **{dataset_name}**:

📊 **Quick Stats:**
- **Rows**: {row_count:,}
- **Columns**: {col_count}
- **Data Types**: {data_types}

📋 **Available Columns:**
{column_list}

*I'm currently experiencing high demand. For detailed analysis, please try again in a few minutes or explore the Dashboard tab for pre-computed insights.*"""
        },
        "total": {
            "patterns": [r"total", r"sum of", r"how much"],
            "response": """## Calculating Totals

To get the **total** for your data, I recommend:

1. **Dashboard View**: Check the KPI cards for pre-calculated totals
2. **Chart Studio**: Create a bar chart with aggregation set to "Sum"

📊 **Available numeric columns**: {numeric_columns}

*Note: I'm currently rate-limited. The Dashboard shows pre-computed totals that are available immediately.*"""
        },
        "average": {
            "patterns": [r"average", r"mean", r"avg"],
            "response": """## Calculating Averages

For **average/mean** calculations:

📊 **Numeric columns available**: {numeric_columns}

**Quick Options:**
1. Check the **Dashboard** for pre-computed averages
2. Use **Chart Studio** → Select column → Aggregation: Mean

*I'm experiencing high demand right now. Pre-computed statistics are available in the Dashboard.*"""
        },
        "trend": {
            "patterns": [r"trend", r"over time", r"change", r"growth"],
            "response": """## Trend Analysis

To analyze **trends** in your data:

📈 **Time-related columns**: {date_columns}
📊 **Numeric columns**: {numeric_columns}

**Suggested Approach:**
1. Go to **Chart Studio**
2. Create a **Line Chart**
3. X-axis: Date/time column
4. Y-axis: Metric of interest

*Full trend analysis requires AI processing. Please try again shortly.*"""
        },
        "compare": {
            "patterns": [r"compare", r"vs", r"versus", r"difference"],
            "response": """## Comparison Analysis

For **comparing** values:

📊 **Categorical columns** (for grouping): {categorical_columns}
📈 **Numeric columns** (for values): {numeric_columns}

**How to Compare:**
1. **Chart Studio** → Grouped Bar Chart
2. Select category to group by
3. Select value to compare

*Detailed AI comparison is temporarily unavailable. Use Chart Studio for visual comparisons.*"""
        },
        "correlation": {
            "patterns": [r"correlat", r"relationship", r"related"],
            "response": """## Correlation Analysis

To find **correlations** between variables:

📊 **Numeric columns**: {numeric_columns}

**Options:**
1. **Dashboard** → Check correlation matrix (if available)
2. **Chart Studio** → Scatter plot between two numeric columns

*Deep statistical analysis requires AI processing. Pre-computed correlations may be available in Dashboard insights.*"""
        },
        "top": {
            "patterns": [r"top \d+", r"highest", r"best", r"most"],
            "response": """## Top/Highest Analysis

To find **top values**:

📊 **Available for ranking**: {all_columns}

**Quick Method:**
1. **Chart Studio** → Bar Chart
2. Sort by value (descending)
3. Limit to top N rows

*Full ranking analysis will be available when AI capacity returns.*"""
        },
        "default": {
            "patterns": [],
            "response": """## I'm Here to Help! 

I received your question but I'm currently experiencing **high demand** on the AI service.

**While you wait, try these:**

1. 📊 **Dashboard** - View pre-computed KPIs and insights
2. 📈 **Chart Studio** - Create custom visualizations
3. 🔄 **Retry** - Try your question again in 1-2 minutes

**Your Dataset**: {dataset_name}
- {row_count:,} rows × {col_count} columns
- Columns: {column_preview}

*The free AI tier has limited requests. Your question has been noted and will process when capacity is available.*"""
        }
    }
    
    @classmethod
    def generate(
        cls,
        query: str,
        dataset_metadata: Dict[str, Any],
        error_type: str = "rate_limit"
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
        numeric_cols = [c["name"] for c in columns if c.get("type", "") in ["float64", "int64", "number", "integer", "float"]]
        categorical_cols = [c["name"] for c in columns if c.get("type", "") in ["object", "string", "category", "categorical"]]
        date_cols = [c["name"] for c in columns if "date" in c.get("type", "").lower() or "time" in c.get("name", "").lower() or "date" in c.get("name", "").lower()]
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
            column_list="\n".join([f"- `{c['name']}` ({c.get('type', 'unknown')})" for c in columns[:10]]) + (f"\n- ... and {len(columns)-10} more" if len(columns) > 10 else ""),
            column_preview=", ".join(all_cols[:5]) + ("..." if len(all_cols) > 5 else ""),
            numeric_columns=", ".join(numeric_cols[:5]) if numeric_cols else "None detected",
            categorical_columns=", ".join(categorical_cols[:5]) if categorical_cols else "None detected",
            date_columns=", ".join(date_cols[:3]) if date_cols else "None detected",
            all_columns=", ".join(all_cols[:8]) + ("..." if len(all_cols) > 8 else "")
        )
        
        # Add error-specific footer
        if error_type == "rate_limit":
            response_text += "\n\n---\n⚠️ *AI requests are limited on the free tier. Your query will process when capacity is available.*"
        elif error_type == "timeout":
            response_text += "\n\n---\n⏱️ *The request timed out. This usually means the analysis was too complex. Try a simpler question.*"
        else:
            response_text += "\n\n---\n🔧 *The AI service is temporarily unavailable. Please try again shortly.*"
        
        return {
            "response": response_text,
            "response_text": response_text,
            "chart_config": None,
            "is_fallback": True,
            "fallback_reason": error_type,
            "query_type_detected": template_key
        }


# Global instances
response_cache = ResponseCache(max_size=500, ttl_hours=24)
fallback_generator = FallbackResponseGenerator()
