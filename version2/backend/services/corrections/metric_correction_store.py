"""
Metric Correction Store — Persistent user overrides for semantic classification
================================================================================

Flow:
  1. User submits a correction via API: POST /datasets/{id}/corrections
  2. MetricCorrectionStore stores it in MongoDB + Redis cache
  3. SemanticClassifier.classify() checks corrections before returning
  4. If a correction exists, the deterministic role is overridden

Storage:
  - Primary: MongoDB collection `metric_corrections`
  - Cache: Redis with no TTL (invalidated on write)

Schema (MongoDB document):
  {
    "dataset_id": "...",
    "column": "price",
    "original_role": "COUNT",          # what the system classified
    "corrected_role": "MEASURE",        # what the user specified
    "original_behavioral_role": "COUNT_MEASURE",
    "corrected_behavioral_role": "ADDITIVE_MEASURE",
    "aggregation_overrides": {
      "sum_allowed": True,
      "avg_allowed": True,
      "count_allowed": False,
      "median_allowed": True,
    },
    "corrected_by": "user_id",
    "corrected_at": ISODate(...),
  }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Data Model ────────────────────────────────────────────────────────────────


@dataclass
class MetricCorrection:
    """A single user-submitted correction for a column's semantic classification."""

    dataset_id: str
    column: str
    original_role: str = ""
    corrected_role: str = ""
    original_behavioral_role: str = ""
    corrected_behavioral_role: str = ""
    aggregation_overrides: Dict[str, bool] = field(default_factory=dict)
    corrected_by: str = ""
    corrected_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "column": self.column,
            "original_role": self.original_role,
            "corrected_role": self.corrected_role,
            "original_behavioral_role": self.original_behavioral_role,
            "corrected_behavioral_role": self.corrected_behavioral_role,
            "aggregation_overrides": self.aggregation_overrides,
            "corrected_by": self.corrected_by,
            "corrected_at": self.corrected_at
            or datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricCorrection":
        return cls(
            dataset_id=data.get("dataset_id", ""),
            column=data.get("column", ""),
            original_role=data.get("original_role", ""),
            corrected_role=data.get("corrected_role", ""),
            original_behavioral_role=data.get("original_behavioral_role", ""),
            corrected_behavioral_role=data.get("corrected_behavioral_role", ""),
            aggregation_overrides=data.get("aggregation_overrides", {}),
            corrected_by=data.get("corrected_by", ""),
            corrected_at=data.get("corrected_at", ""),
        )


# ─── Service ───────────────────────────────────────────────────────────────────


class MetricCorrectionStore:
    """
    Persistent store for user semantic overrides.

    Uses MongoDB as primary storage and an in-memory/Redis cache for fast lookups.

    Usage:
        store = MetricCorrectionStore(mongo_db, redis_client)
        await store.set_correction(dataset_id, column, correction)
        corrections = await store.get_corrections(dataset_id)
        # corrections: dict[column_name, MetricCorrection]
    """

    MONGO_COLLECTION = "metric_corrections"
    REDIS_PREFIX = "correction:"

    def __init__(self, mongo_db=None, redis_client=None):
        self._mongo_db = mongo_db
        self._redis = redis_client
        self._in_memory_cache: Dict[str, Dict[str, MetricCorrection]] = {}

    def _get_mongo(self):
        if self._mongo_db is None:
            from db.database import get_database

            self._mongo_db = get_database()
        return self._mongo_db

    def _get_redis(self):
        return self._redis

    # ─── CRUD ───────────────────────────────────────────────────────────

    async def set_correction(
        self,
        dataset_id: str,
        column: str,
        correction: MetricCorrection,
    ) -> None:
        """Store or update a correction for a column.

        Writes to MongoDB, invalidates Redis cache, updates in-memory cache.
        """
        doc = correction.to_dict()
        mongo = self._get_mongo()
        try:
            mongo[self.MONGO_COLLECTION].update_one(
                {"dataset_id": dataset_id, "column": column},
                {"$set": doc},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[MetricCorrection] MongoDB write failed: {e}")

        # Invalidate Redis cache for this dataset
        redis = self._get_redis()
        if redis:
            try:
                await redis.delete(f"{self.REDIS_PREFIX}{dataset_id}")
            except Exception as e:
                logger.debug(f"[MetricCorrection] Redis delete failed: {e}")

        # Update in-memory cache
        if dataset_id not in self._in_memory_cache:
            self._in_memory_cache[dataset_id] = {}
        self._in_memory_cache[dataset_id][column] = correction

        logger.info(
            f"[MetricCorrection] Stored correction: dataset={dataset_id[:8]}, "
            f"column={column}, role={correction.original_role}→{correction.corrected_role}"
        )

    async def get_corrections(
        self,
        dataset_id: str,
    ) -> Dict[str, MetricCorrection]:
        """Get all corrections for a dataset.

        Returns dict of {column_name: MetricCorrection}.
        Cache hierarchy: in-memory → Redis → MongoDB.
        """
        # L1: In-memory cache
        cached = self._in_memory_cache.get(dataset_id)
        if cached is not None:
            return cached

        # L2: Redis cache
        redis = self._get_redis()
        if redis:
            try:
                raw = await redis.get(f"{self.REDIS_PREFIX}{dataset_id}")
                if raw:
                    data = json.loads(raw)
                    result = {col: MetricCorrection.from_dict(c) for col, c in data.items()}
                    self._in_memory_cache[dataset_id] = result
                    return result
            except Exception as e:
                logger.debug(f"[MetricCorrection] Redis read failed: {e}")

        # L3: MongoDB
        mongo = self._get_mongo()
        result: Dict[str, MetricCorrection] = {}
        try:
            docs = (
                await mongo[self.MONGO_COLLECTION]
                .find(
                    {"dataset_id": dataset_id},
                )
                .to_list(length=None)
            )
            for doc in docs:
                doc.pop("_id", None)
                correction = MetricCorrection.from_dict(doc)
                result[correction.column] = correction
        except Exception as e:
            logger.warning(f"[MetricCorrection] MongoDB read failed: {e}")
            return {}

        # Populate caches
        self._in_memory_cache[dataset_id] = result
        if redis and result:
            try:
                serialized = {col: c.to_dict() for col, c in result.items()}
                await redis.setex(
                    f"{self.REDIS_PREFIX}{dataset_id}",
                    86400,
                    json.dumps(serialized),
                )
            except Exception as e:
                logger.debug(f"[MetricCorrection] Redis cache write failed: {e}")

        return result

    async def delete_correction(
        self,
        dataset_id: str,
        column: str,
    ) -> bool:
        """Delete a single correction. Returns True if existed."""
        mongo = self._get_mongo()
        try:
            result = mongo[self.MONGO_COLLECTION].delete_one(
                {"dataset_id": dataset_id, "column": column},
            )
            existed = result.deleted_count > 0
        except Exception as e:
            logger.warning(f"[MetricCorrection] MongoDB delete failed: {e}")
            existed = False

        # Invalidate caches
        self._in_memory_cache.pop(dataset_id, None)
        redis = self._get_redis()
        if redis:
            try:
                await redis.delete(f"{self.REDIS_PREFIX}{dataset_id}")
            except Exception:
                pass

        if existed:
            logger.info(
                f"[MetricCorrection] Deleted correction: dataset={dataset_id[:8]}, column={column}"
            )
        return existed

    async def delete_all_corrections(self, dataset_id: str) -> int:
        """Delete all corrections for a dataset. Returns count deleted."""
        mongo = self._get_mongo()
        count = 0
        try:
            result = mongo[self.MONGO_COLLECTION].delete_many(
                {"dataset_id": dataset_id},
            )
            count = result.deleted_count
        except Exception as e:
            logger.warning(f"[MetricCorrection] MongoDB delete failed: {e}")

        self._in_memory_cache.pop(dataset_id, None)
        redis = self._get_redis()
        if redis:
            try:
                await redis.delete(f"{self.REDIS_PREFIX}{dataset_id}")
            except Exception:
                pass

        if count:
            logger.info(
                f"[MetricCorrection] Deleted {count} corrections for dataset={dataset_id[:8]}"
            )
        return count

    # ─── Merge into classification ──────────────────────────────────────

    def apply_corrections(
        self,
        classification_dict: Dict[str, Any],
        column_name: str,
        corrections: Dict[str, MetricCorrection],
    ) -> Dict[str, Any]:
        """Apply user corrections to a classification result dict.

        Args:
            classification_dict: The ColumnIntelligence dict (from classify()).
            column_name: The column name to check corrections for.
            corrections: Corrections dict from get_corrections().

        Returns:
            Modified classification dict with corrections applied.
        """
        corr = corrections.get(column_name)
        if corr is None:
            return classification_dict

        result = dict(classification_dict)

        if corr.corrected_role:
            result["semantic_role"] = corr.corrected_role

        if corr.corrected_behavioral_role:
            result["behavioral_role"] = corr.corrected_behavioral_role

        if corr.aggregation_overrides:
            existing_agg = result.get("aggregation_suitability", {})
            if isinstance(existing_agg, dict):
                for key, val in corr.aggregation_overrides.items():
                    existing_agg[key] = val
                result["aggregation_suitability"] = existing_agg

        result["classification_confidence"] = 0.99
        result["needs_review"] = False
        result["corrected"] = True

        return result


# Singleton — lazy-initialized with references set later
metric_correction_store = MetricCorrectionStore()
