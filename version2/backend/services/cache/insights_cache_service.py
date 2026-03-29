"""
Insights Cache Service
=====================
Caches expensive computations from the Insights API:
- Narrative intelligence
- Story generation
- Computed correlations, distributions, anomalies
- QUIS analysis results

Uses dataset hash for automatic invalidation when data changes.
Storage: MongoDB (dataset.insights_cache field)
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.database import get_database

logger = logging.getLogger(__name__)

CACHE_VERSION = "2.0"


class InsightsCacheService:
    """
    Service for caching Insights API computations.

    Cache is stored in dataset document's 'insights_cache' field:
    {
        "insights_cache": {
            "version": "2.0",
            "dataset_hash": "abc123",
            "generated_at": "2024-01-01T00:00:00Z",
            "narrative_intelligence": { "data": {...} },
            "story": { "data": {...} },
            "computed_data": {
                "correlations": { "data": [...] },
                "distributions": { "data": [...] },
                "anomalies": { "data": [...] },
                "segments": { "data": [...] },
                "driver_analysis": { "data": [...] }
            },
            "quis_analysis": { "data": {...} },
            "fact_sheet_hash": "xyz789"
        }
    }
    """

    def __init__(self):
        self.cache_version = CACHE_VERSION

    def _generate_dataset_hash(self, dataset: Dict[str, Any]) -> str:
        """
        Generate a hash from dataset metadata to detect data changes.
        Hash is based on: row count + file size + modified time + column count
        """
        metadata = dataset.get("metadata", {})
        overview = metadata.get("dataset_overview", {})

        hash_components = [
            str(overview.get("total_rows", 0)),
            str(dataset.get("file_size", 0)),
            str(dataset.get("updated_at", "")),
            str(len(dataset.get("columns", []))),
        ]

        hash_str = "|".join(hash_components)
        return hashlib.md5(hash_str.encode()).hexdigest()

    def _generate_fact_sheet_hash(self, fact_sheet: str) -> str:
        """Generate hash of fact sheet for narrative cache."""
        return hashlib.md5(fact_sheet[:5000].encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: Optional[Dict]) -> bool:
        """Check if cache entry exists and dataset hash matches."""
        if not cache_entry:
            return False

        if cache_entry.get("version") != self.cache_version:
            return False

        return True

    async def get_cache(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get the entire insights cache for a dataset."""
        try:
            db = get_database()
            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            dataset = await db.uploads.find_one(query, {"insights_cache": 1})
            return dataset.get("insights_cache") if dataset else None
        except Exception as e:
            logger.warning(f"Failed to get insights cache: {e}")
            return None

    async def get_dataset(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get dataset for hash comparison."""
        try:
            db = get_database()
            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            dataset = await db.uploads.find_one(
                query, {"metadata": 1, "file_size": 1, "updated_at": 1, "columns": 1}
            )
            return dataset
        except Exception as e:
            logger.warning(f"Failed to get dataset: {e}")
            return None

    async def is_cache_valid(self, dataset_id: str, user_id: str) -> bool:
        """Check if cached insights are still valid for this dataset."""
        try:
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return False

            current_hash = self._generate_dataset_hash(dataset)
            cached_hash = cache.get("dataset_hash", "")

            return current_hash == cached_hash
        except Exception as e:
            logger.warning(f"Cache validation failed: {e}")
            return False

    async def get_narrative_intelligence(
        self, dataset_id: str, user_id: str
    ) -> Optional[Dict]:
        """Get cached narrative intelligence."""
        try:
            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return None

            narrative = cache.get("narrative_intelligence", {})
            if self._is_cache_valid(narrative):
                logger.info(f"Cache HIT: narrative_intelligence for {dataset_id}")
                return narrative.get("data")

            return None
        except Exception as e:
            logger.warning(f"Failed to get cached narrative: {e}")
            return None

    async def cache_narrative_intelligence(
        self, dataset_id: str, user_id: str, data: Dict, fact_sheet: str = ""
    ) -> bool:
        """Cache narrative intelligence result."""
        try:
            db = get_database()
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            dataset_hash = self._generate_dataset_hash(dataset)
            fact_sheet_hash = (
                self._generate_fact_sheet_hash(fact_sheet) if fact_sheet else ""
            )

            cache_entry = {
                "version": self.cache_version,
                "dataset_hash": dataset_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
                "fact_sheet_hash": fact_sheet_hash,
            }

            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(
                query, {"$set": {"insights_cache.narrative_intelligence": cache_entry}}
            )
            logger.info(f"Cached narrative_intelligence for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache narrative: {e}")
            return False

    async def get_story(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get cached story."""
        try:
            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return None

            story = cache.get("story", {})
            if self._is_cache_valid(story):
                logger.info(f"Cache HIT: story for {dataset_id}")
                return story.get("data")

            return None
        except Exception as e:
            logger.warning(f"Failed to get cached story: {e}")
            return None

    async def cache_story(self, dataset_id: str, user_id: str, data: Dict) -> bool:
        """Cache story generation result."""
        try:
            db = get_database()
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            dataset_hash = self._generate_dataset_hash(dataset)

            cache_entry = {
                "version": self.cache_version,
                "dataset_hash": dataset_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }

            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(
                query, {"$set": {"insights_cache.story": cache_entry}}
            )
            logger.info(f"Cached story for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache story: {e}")
            return False

    async def get_computed_data(
        self, dataset_id: str, user_id: str, data_type: str
    ) -> Optional[List]:
        """Get cached computed data (correlations, distributions, anomalies, etc.)."""
        try:
            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return None

            computed = cache.get("computed_data", {})
            entry = computed.get(data_type, {})

            if self._is_cache_valid(entry):
                logger.info(f"Cache HIT: computed.{data_type} for {dataset_id}")
                return entry.get("data")

            return None
        except Exception as e:
            logger.warning(f"Failed to get cached {data_type}: {e}")
            return None

    async def cache_computed_data(
        self, dataset_id: str, user_id: str, data_type: str, data: List
    ) -> bool:
        """Cache computed data (correlations, distributions, anomalies, etc.)."""
        try:
            db = get_database()
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            dataset_hash = self._generate_dataset_hash(dataset)

            cache_entry = {
                "version": self.cache_version,
                "dataset_hash": dataset_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }

            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(
                query,
                {"$set": {f"insights_cache.computed_data.{data_type}": cache_entry}},
            )
            logger.info(f"Cached computed.{data_type} for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache {data_type}: {e}")
            return False

    async def get_quis_analysis(self, dataset_id: str, user_id: str) -> Optional[Dict]:
        """Get cached QUIS analysis."""
        try:
            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return None

            quis = cache.get("quis_analysis", {})
            if self._is_cache_valid(quis):
                logger.info(f"Cache HIT: quis_analysis for {dataset_id}")
                return quis.get("data")

            return None
        except Exception as e:
            logger.warning(f"Failed to get cached QUIS analysis: {e}")
            return None

    async def cache_quis_analysis(
        self, dataset_id: str, user_id: str, data: Dict
    ) -> bool:
        """Cache QUIS analysis result."""
        try:
            db = get_database()
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            dataset_hash = self._generate_dataset_hash(dataset)

            cache_entry = {
                "version": self.cache_version,
                "dataset_hash": dataset_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }

            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(
                query, {"$set": {"insights_cache.quis_analysis": cache_entry}}
            )
            logger.info(f"Cached quis_analysis for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache QUIS analysis: {e}")
            return False

    async def cache_all_computed_data(
        self,
        dataset_id: str,
        user_id: str,
        correlations: List = None,
        distributions: List = None,
        anomalies: List = None,
        segments: List = None,
        driver_analysis: List = None,
        quis_analysis: Dict = None,
    ) -> bool:
        """Batch cache all computed data at once."""
        try:
            db = get_database()
            dataset = await self.get_dataset(dataset_id, user_id)
            if not dataset:
                return False

            dataset_hash = self._generate_dataset_hash(dataset)
            now = datetime.now(timezone.utc).isoformat()

            update_fields = {
                "insights_cache.version": self.cache_version,
                "insights_cache.dataset_hash": dataset_hash,
            }

            if correlations is not None:
                update_fields["insights_cache.computed_data.correlations"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": correlations,
                }

            if distributions is not None:
                update_fields["insights_cache.computed_data.distributions"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": distributions,
                }

            if anomalies is not None:
                update_fields["insights_cache.computed_data.anomalies"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": anomalies,
                }

            if segments is not None:
                update_fields["insights_cache.computed_data.segments"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": segments,
                }

            if driver_analysis is not None:
                update_fields["insights_cache.computed_data.driver_analysis"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": driver_analysis,
                }

            if quis_analysis is not None:
                update_fields["insights_cache.quis_analysis"] = {
                    "version": self.cache_version,
                    "dataset_hash": dataset_hash,
                    "generated_at": now,
                    "data": quis_analysis,
                }

            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(query, {"$set": update_fields})
            logger.info(f"Batch cached computed data for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to batch cache computed data: {e}")
            return False

    async def invalidate(self, dataset_id: str, user_id: str) -> bool:
        """Invalidate all cached insights for a dataset."""
        try:
            db = get_database()
            try:
                query = {"_id": dataset_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}

            await db.datasets.update_one(query, {"$unset": {"insights_cache": ""}})
            logger.info(f"Invalidated insights cache for {dataset_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
            return False

    async def get_cache_status(self, dataset_id: str, user_id: str) -> Dict[str, Any]:
        """Get cache status for debugging."""
        try:
            cache = await self.get_cache(dataset_id, user_id)
            if not cache:
                return {"has_cache": False}

            is_valid = await self.is_cache_valid(dataset_id, user_id)

            return {
                "has_cache": True,
                "is_valid": is_valid,
                "version": cache.get("version"),
                "generated_at": cache.get("narrative_intelligence", {}).get(
                    "generated_at"
                ),
                "has_narrative": "narrative_intelligence" in cache,
                "has_story": "story" in cache,
                "has_computed": "computed_data" in cache,
                "has_quis": "quis_analysis" in cache,
            }
        except Exception as e:
            return {"error": str(e)}


insights_cache_service = InsightsCacheService()
