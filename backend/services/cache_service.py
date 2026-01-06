"""
Cache Service for DataSage AI
==============================

Provides caching layer for DataFrames and other expensive-to-compute data.
Uses Redis if available, falls back to in-memory LRU cache.

Features:
- DataFrame serialization/deserialization with Polars
- TTL-based expiration
- LRU eviction for memory cache
- Graceful degradation when Redis unavailable

Usage:
    from services.cache_service import cache_service
    
    # Cache a DataFrame
    await cache_service.set_dataframe("df:dataset123", df, ttl=3600)
    
    # Retrieve cached DataFrame
    df = await cache_service.get_dataframe("df:dataset123")
"""

import os
import logging
import pickle
from typing import Optional, Any
from functools import lru_cache
from collections import OrderedDict
import polars as pl

logger = logging.getLogger(__name__)

# ============================================================
# IN-MEMORY LRU CACHE (Fallback)
# ============================================================

class LRUCache:
    """
    Simple LRU cache with size and item limits.
    Thread-safe for read operations (write requires external locking in production).
    """
    
    def __init__(self, max_items: int = 100, max_size_mb: int = 500):
        self.max_items = max_items
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache: OrderedDict = OrderedDict()
        self.size_bytes = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item and move to end (most recently used)."""
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]["value"]
        return None
    
    def set(self, key: str, value: Any, size_bytes: int = 0) -> None:
        """Set item, evicting if necessary."""
        # Remove if exists
        if key in self.cache:
            self.size_bytes -= self.cache[key]["size"]
            del self.cache[key]
        
        # Evict until we have space
        while (len(self.cache) >= self.max_items or 
               self.size_bytes + size_bytes > self.max_size_bytes) and self.cache:
            oldest = next(iter(self.cache))
            self.size_bytes -= self.cache[oldest]["size"]
            del self.cache[oldest]
        
        # Add new item
        self.cache[key] = {"value": value, "size": size_bytes}
        self.size_bytes += size_bytes
    
    def delete(self, key: str) -> bool:
        """Remove item from cache."""
        if key in self.cache:
            self.size_bytes -= self.cache[key]["size"]
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all items."""
        self.cache.clear()
        self.size_bytes = 0
    
    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "items": len(self.cache),
            "size_mb": self.size_bytes / (1024 * 1024),
            "max_items": self.max_items,
            "max_size_mb": self.max_size_bytes / (1024 * 1024)
        }


# ============================================================
# CACHE SERVICE
# ============================================================

class CacheService:
    """
    Unified caching service with Redis primary and in-memory fallback.
    """
    
    def __init__(self):
        self._redis = None
        self._redis_available = False
        self._memory_cache = LRUCache(max_items=100, max_size_mb=500)
        self._init_redis()
    
    def _init_redis(self):
        """Try to initialize Redis connection."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.info("REDIS_URL not set, using in-memory cache only")
            return
        
        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=False)
            # Test connection
            self._redis.ping()
            self._redis_available = True
            logger.info(f"Connected to Redis for caching: {redis_url}")
        except ImportError:
            logger.warning("redis package not installed, using in-memory cache")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using in-memory cache")
    
    # --------------------------------------------------------
    # Generic Cache Operations
    # --------------------------------------------------------
    
    async def get(self, key: str) -> Optional[bytes]:
        """Get raw bytes from cache."""
        # Try Redis first
        if self._redis_available:
            try:
                return self._redis.get(key)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Fall back to memory
        return self._memory_cache.get(key)
    
    async def set(self, key: str, value: bytes, ttl: int = 3600) -> bool:
        """Set raw bytes in cache with TTL."""
        size_bytes = len(value) if isinstance(value, bytes) else 0
        
        # Try Redis first
        if self._redis_available:
            try:
                self._redis.setex(key, ttl, value)
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # Fall back to memory (no TTL support in simple implementation)
        self._memory_cache.set(key, value, size_bytes)
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete from cache."""
        deleted = False
        
        if self._redis_available:
            try:
                deleted = self._redis.delete(key) > 0
            except Exception:
                pass
        
        deleted = self._memory_cache.delete(key) or deleted
        return deleted
    
    # --------------------------------------------------------
    # DataFrame-Specific Operations
    # --------------------------------------------------------
    
    async def get_dataframe(self, key: str) -> Optional[pl.DataFrame]:
        """
        Retrieve a cached DataFrame.
        
        Args:
            key: Cache key (e.g., "df:{dataset_id}")
            
        Returns:
            Polars DataFrame or None if not cached
        """
        data = await self.get(key)
        if data is None:
            return None
        
        try:
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize DataFrame from cache: {e}")
            await self.delete(key)
            return None
    
    async def set_dataframe(self, key: str, df: pl.DataFrame, ttl: int = 3600) -> bool:
        """
        Cache a DataFrame.
        
        Args:
            key: Cache key (e.g., "df:{dataset_id}")
            df: Polars DataFrame to cache
            ttl: Time-to-live in seconds (default 1 hour)
            
        Returns:
            True if cached successfully
        """
        try:
            serialized = pickle.dumps(df)
            size_mb = len(serialized) / (1024 * 1024)
            
            # Skip caching very large DataFrames (>100MB)
            if size_mb > 100:
                logger.warning(f"DataFrame too large to cache: {size_mb:.1f}MB")
                return False
            
            return await self.set(key, serialized, ttl)
        except Exception as e:
            logger.error(f"Failed to serialize DataFrame for caching: {e}")
            return False
    
    async def invalidate_dataset(self, dataset_id: str) -> None:
        """Invalidate all cached data for a dataset."""
        await self.delete(f"df:{dataset_id}")
        logger.info(f"Invalidated cache for dataset {dataset_id}")
    
    def stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "redis_available": self._redis_available,
            "memory_cache": self._memory_cache.stats()
        }
        
        if self._redis_available:
            try:
                info = self._redis.info("memory")
                stats["redis_memory_mb"] = info.get("used_memory", 0) / (1024 * 1024)
            except Exception:
                pass
        
        return stats


# Singleton instance
cache_service = CacheService()
