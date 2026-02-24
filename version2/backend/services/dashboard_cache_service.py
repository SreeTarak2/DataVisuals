"""
Dashboard Cache Service
=======================
Caches generated dashboard components (KPIs, charts, insights) in MongoDB.
Prevents redundant AI calls and improves load times.

Storage Structure in datasets collection:
{
    ...existing dataset fields...
    "dashboard_cache": {
        "kpis": {
            "data": [...],
            "generated_at": datetime,
            "version": "1.0"
        },
        "charts": {
            "data": {...},
            "generated_at": datetime,
            "version": "1.0"
        },
        "insights": {
            "data": [...],
            "generated_at": datetime,
            "version": "1.0"
        }
    }
}
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId

from db.database import get_database

logger = logging.getLogger(__name__)

# Cache TTL - how long cached data is valid
CACHE_TTL_HOURS = 24 * 7  # 7 days - dashboard data doesn't change unless dataset changes


class DashboardCacheService:
    """
    Service for caching and retrieving dashboard components.
    Stores cache in the dataset document's 'dashboard_cache' field.
    """
    
    def __init__(self):
        self._cache_version = "1.0"
    
    def _get_db(self):
        """Get database instance (synchronous - Motor handles async internally)."""
        return get_database()
    
    def _is_cache_valid(self, cache_entry: Optional[Dict]) -> bool:
        """Check if cache entry exists and is not expired."""
        if not cache_entry:
            return False
        
        generated_at = cache_entry.get("generated_at")
        if not generated_at:
            return False
        
        # Handle both datetime objects and ISO strings
        if isinstance(generated_at, str):
            try:
                generated_at = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            except ValueError:
                return False
        
        # Ensure timezone-aware for correct comparison
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        
        expiry_time = generated_at + timedelta(hours=CACHE_TTL_HOURS)
        return datetime.now(timezone.utc) < expiry_time
    
    async def _get_dataset_cache(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get the dashboard_cache field from dataset document."""
        db = self._get_db()
        
        try:
            dataset_oid = ObjectId(dataset_id)
            query = {"_id": dataset_oid, "user_id": user_id}
        except Exception:
            query = {"_id": dataset_id, "user_id": user_id}
        
        dataset = await db.datasets.find_one(query, {"dashboard_cache": 1})
        return dataset.get("dashboard_cache") if dataset else None
    
    async def _update_cache(self, dataset_id: str, user_id: str, cache_key: str, data: Any) -> bool:
        """Update a specific cache key in the dashboard_cache field."""
        db = self._get_db()
        
        try:
            dataset_oid = ObjectId(dataset_id)
            query = {"_id": dataset_oid, "user_id": user_id}
        except Exception:
            query = {"_id": dataset_id, "user_id": user_id}
        
        cache_entry = {
            "data": data,
            "generated_at": datetime.utcnow(),
            "version": self._cache_version
        }
        
        result = await db.datasets.update_one(
            query,
            {"$set": {f"dashboard_cache.{cache_key}": cache_entry}}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Cached {cache_key} for dataset {dataset_id}")
            return True
        return False

    # ---------------------------------------------------------------
    # KPI CACHE
    # ---------------------------------------------------------------
    async def get_cached_kpis(self, dataset_id: str, user_id: str) -> Optional[List[Dict]]:
        """Get cached KPIs if available and valid."""
        cache = await self._get_dataset_cache(dataset_id, user_id)
        if not cache:
            return None
        
        kpi_cache = cache.get("kpis")
        if self._is_cache_valid(kpi_cache):
            logger.info(f"📊 KPI cache HIT for dataset {dataset_id}")
            return kpi_cache.get("data")
        
        logger.info(f"📊 KPI cache MISS for dataset {dataset_id}")
        return None
    
    async def cache_kpis(self, dataset_id: str, user_id: str, kpis: List[Dict]) -> bool:
        """Cache KPI data for a dataset."""
        return await self._update_cache(dataset_id, user_id, "kpis", kpis)

    # ---------------------------------------------------------------
    # CHARTS CACHE
    # ---------------------------------------------------------------
    async def get_cached_charts(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get cached charts if available and valid."""
        cache = await self._get_dataset_cache(dataset_id, user_id)
        if not cache:
            return None
        
        charts_cache = cache.get("charts")
        if self._is_cache_valid(charts_cache):
            logger.info(f"📈 Charts cache HIT for dataset {dataset_id}")
            return charts_cache.get("data")
        
        logger.info(f"📈 Charts cache MISS for dataset {dataset_id}")
        return None
    
    async def cache_charts(self, dataset_id: str, user_id: str, charts: Dict) -> bool:
        """Cache chart data for a dataset."""
        return await self._update_cache(dataset_id, user_id, "charts", charts)

    # ---------------------------------------------------------------
    # INSIGHTS CACHE
    # ---------------------------------------------------------------
    async def get_cached_insights(self, dataset_id: str, user_id: str) -> Optional[List[Dict]]:
        """Get cached insights if available and valid."""
        cache = await self._get_dataset_cache(dataset_id, user_id)
        if not cache:
            return None
        
        insights_cache = cache.get("insights")
        if self._is_cache_valid(insights_cache):
            logger.info(f"💡 Insights cache HIT for dataset {dataset_id}")
            return insights_cache.get("data")
        
        logger.info(f"💡 Insights cache MISS for dataset {dataset_id}")
        return None
    
    async def cache_insights(self, dataset_id: str, user_id: str, insights: List[Dict]) -> bool:
        """Cache insights data for a dataset."""
        return await self._update_cache(dataset_id, user_id, "insights", insights)

    # ---------------------------------------------------------------
    # CACHE INVALIDATION
    # ---------------------------------------------------------------
    async def invalidate_cache(self, dataset_id: str, user_id: str, cache_keys: Optional[List[str]] = None) -> bool:
        """
        Invalidate dashboard cache for a dataset.
        
        Args:
            dataset_id: Dataset identifier
            user_id: User identifier
            cache_keys: Specific keys to invalidate ['kpis', 'charts', 'insights']. 
                       If None, invalidates all.
        
        Returns:
            True if cache was invalidated
        """
        db = self._get_db()
        
        try:
            dataset_oid = ObjectId(dataset_id)
            query = {"_id": dataset_oid, "user_id": user_id}
        except Exception:
            query = {"_id": dataset_id, "user_id": user_id}
        
        if cache_keys:
            # Invalidate specific keys
            unset_fields = {f"dashboard_cache.{key}": "" for key in cache_keys}
            result = await db.datasets.update_one(query, {"$unset": unset_fields})
        else:
            # Invalidate entire cache
            result = await db.datasets.update_one(query, {"$unset": {"dashboard_cache": ""}})
        
        if result.modified_count > 0:
            logger.info(f"🗑️ Invalidated dashboard cache for dataset {dataset_id}")
            return True
        return False
    
    async def get_cache_status(self, dataset_id: str, user_id: str) -> Dict[str, Any]:
        """Get cache status for debugging/monitoring."""
        cache = await self._get_dataset_cache(dataset_id, user_id)
        
        if not cache:
            return {
                "has_cache": False,
                "kpis": {"cached": False},
                "charts": {"cached": False},
                "insights": {"cached": False}
            }
        
        def get_key_status(key: str) -> Dict:
            entry = cache.get(key)
            if not entry:
                return {"cached": False}
            
            is_valid = self._is_cache_valid(entry)
            return {
                "cached": True,
                "valid": is_valid,
                "generated_at": entry.get("generated_at"),
                "version": entry.get("version")
            }
        
        return {
            "has_cache": True,
            "kpis": get_key_status("kpis"),
            "charts": get_key_status("charts"),
            "insights": get_key_status("insights")
        }


# Global instance
dashboard_cache_service = DashboardCacheService()
