"""
intelligence/dataset_memo.py — Dataset Intelligence Memo (DatasetMemo)

The single shared object that collects all upload-pipeline outputs so every
downstream stage (chat, dashboard, insights) reads from one cache instead of
re-computing domain detection, column profiling, KPI generation, metric graphs,
and chart recommendations.

          ┌─────────────────────────────────────────────┐
          │            Dataset Intelligence Memo         │
          ├─────────────────────────────────────────────┤
          │  domain_id, domain_name, domain_confidence  │
          │  column_mapping (template → actual columns) │
          │  profiles (lightweight column summaries)     │
          │  kpis (pre-computed KPI cards)               │
          │  charts (pre-computed chart specs)           │
          │  metric_graph (metric relationships)          │
          │  root_cause_chains (decomposition chains)     │
          │  deep_analysis, statistical_findings          │
          │  data_quality metrics                         │
          └─────────────────────────────────────────────┘

Usage:
    memo = DatasetMemo(dataset_id="...", user_id="...")
    memo.domain_id = "weather-metrics"
    DatasetMemoCache.set("...", memo)

    # Later, in another stage:
    memo = DatasetMemoCache.get(dataset_id)
    if memo and memo.domain_id:
        # Use memo.domain_id instead of calling LLM again
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# DatasetMemo — the shared intelligence object
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class DatasetMemo:
    """
    All computed intelligence about a dataset, cached as a single object.

    Populated during the upload pipeline (process.py). Downstream consumers
    (chat, dashboard, insights, KPI generator) read from the memo instead
    of re-running domain detection, profiling, or KPI generation.

    The memo is **write-once, read-many**: written during upload processing
    and read (but not modified) by every downstream stage.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    dataset_id: str
    user_id: str

    # ── Domain Detection (prevents 3x repeated LLM calls) ────────────────
    domain_id: Optional[str] = None            # e.g. "weather-metrics"
    domain_name: Optional[str] = None          # e.g. "weather"
    domain_confidence: float = 0.0             # 0.0-1.0
    domain_method: str = "unset"               # "llm_first" | "pattern_match" | "llm_no_match" | "fallback"
    column_mapping: Optional[Dict[str, str]] = None  # template_type → column_name

    # ── Column Profiles (lightweight — name + role + stats) ──────────────
    profiles: List[Dict[str, Any]] = field(default_factory=list)

    # ── Pre-computed KPIs (from IntelligentKPIGenerator) ─────────────────
    kpis: List[Dict[str, Any]] = field(default_factory=list)

    # ── Pre-computed Chart Recommendations ───────────────────────────────
    charts: List[Dict[str, Any]] = field(default_factory=list)
    chart_count: int = 0

    # ── Metric Relationship Graph (from metric_graph.py) ─────────────────
    metric_graph: Optional[Dict[str, Any]] = None
    metric_graph_edges: int = 0

    # ── Root Cause Chains (from root_cause_chain.py) ─────────────────────
    root_cause_chains: List[Dict[str, Any]] = field(default_factory=list)

    # ── Deep Analysis / Statistical Findings ─────────────────────────────
    deep_analysis: Dict[str, Any] = field(default_factory=dict)
    statistical_findings: Dict[str, Any] = field(default_factory=dict)
    data_quality: Dict[str, Any] = field(default_factory=dict)

    # ── Pipeline Metadata ────────────────────────────────────────────────
    pipeline_version: str = "3.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    row_count: int = 0
    column_count: int = 0

    # ── Convenience properties ───────────────────────────────────────────

    @property
    def domain_detected(self) -> bool:
        """True if a domain was successfully detected."""
        return self.domain_id is not None and self.domain_confidence >= 0.3

    @property
    def has_kpis(self) -> bool:
        return len(self.kpis) > 0

    @property
    def has_charts(self) -> bool:
        return len(self.charts) > 0

    @property
    def is_populated(self) -> bool:
        """True if the memo has been meaningfully populated (has domain info)."""
        return self.domain_id is not None or self.domain_method != "unset"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for storage."""
        return {
            # Identity
            "dataset_id": self.dataset_id,
            "user_id": self.user_id,
            # Domain
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "domain_confidence": self.domain_confidence,
            "domain_method": self.domain_method,
            "column_mapping": self.column_mapping or {},
            # Profiles
            "profiles": self.profiles,
            # KPIs
            "kpis": self.kpis,
            # Charts
            "charts": self.charts,
            "chart_count": self.chart_count,
            # Metric graph
            "metric_graph": self.metric_graph,
            "metric_graph_edges": self.metric_graph_edges,
            # Root cause
            "root_cause_chains": self.root_cause_chains,
            # Analysis
            "deep_analysis": self.deep_analysis,
            "statistical_findings": self.statistical_findings,
            "data_quality": self.data_quality,
            # Metadata
            "pipeline_version": self.pipeline_version,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, "isoformat") else str(self.updated_at),
            "row_count": self.row_count,
            "column_count": self.column_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetMemo":
        """Reconstruct a DatasetMemo from a dict (e.g. loaded from MongoDB)."""
        memo = cls(
            dataset_id=data.get("dataset_id", ""),
            user_id=data.get("user_id", ""),
            domain_id=data.get("domain_id"),
            domain_name=data.get("domain_name"),
            domain_confidence=data.get("domain_confidence", 0.0),
            domain_method=data.get("domain_method", "unset"),
            column_mapping=data.get("column_mapping"),
            profiles=data.get("profiles", []),
            kpis=data.get("kpis", []),
            charts=data.get("charts", []),
            chart_count=data.get("chart_count", 0),
            metric_graph=data.get("metric_graph"),
            metric_graph_edges=data.get("metric_graph_edges", 0),
            root_cause_chains=data.get("root_cause_chains", []),
            deep_analysis=data.get("deep_analysis", {}),
            statistical_findings=data.get("statistical_findings", {}),
            data_quality=data.get("data_quality", {}),
            pipeline_version=data.get("pipeline_version", "3.0"),
            row_count=data.get("row_count", 0),
            column_count=data.get("column_count", 0),
        )
        # Parse timestamps if present
        created = data.get("created_at")
        if created and isinstance(created, str):
            try:
                memo.created_at = datetime.fromisoformat(created)
            except (ValueError, TypeError):
                pass
        updated = data.get("updated_at")
        if updated and isinstance(updated, str):
            try:
                memo.updated_at = datetime.fromisoformat(updated)
            except (ValueError, TypeError):
                pass
        return memo


# ──────────────────────────────────────────────────────────────────────────────
# DatasetMemoCache — in-memory + optional MongoDB cache
# ──────────────────────────────────────────────────────────────────────────────


class DatasetMemoCache:
    """
    Store and retrieve DatasetMemo objects.

    Primary cache: in-memory dict (fast, no I/O).
    Secondary cache: MongoDB (persistent across restarts).

    The in-memory cache is sufficient for the upload pipeline since the
    memo is written and consumed within the same process lifetime. MongoDB
    persistence is used when the memo must survive process restarts.

    Usage:
        # Write
        memo = DatasetMemo(dataset_id="abc", user_id="user1")
        memo.domain_id = "weather-metrics"
        DatasetMemoCache.set("abc", memo)

        # Read
        memo = DatasetMemoCache.get("abc")
        if memo and memo.domain_detected:
            domain_id = memo.domain_id  # no LLM call needed

        # Clear (for testing / forced re-processing)
        DatasetMemoCache.clear("abc")
    """

    _cache: Dict[str, Dict[str, Any]] = {}  # dataset_id → serialized memo dict

    # Collection name for MongoDB storage
    MONGO_COLLECTION = "dataset_memos"

    @classmethod
    def set(
        cls,
        dataset_id: str,
        memo: DatasetMemo,
        persist_to_mongo: bool = False,
        mongo_db=None,
    ) -> None:
        """
        Store a DatasetMemo in the cache.

        Args:
            dataset_id: Dataset identifier (MongoDB _id).
            memo: The DatasetMemo to store.
            persist_to_mongo: If True, also persist to MongoDB.
            mongo_db: PyMongo database instance (required if persist_to_mongo=True).
        """
        memo.updated_at = datetime.utcnow()
        serialized = memo.to_dict()
        cls._cache[dataset_id] = serialized

        if persist_to_mongo and mongo_db is not None:
            try:
                collection = mongo_db[cls.MONGO_COLLECTION]
                collection.update_one(
                    {"dataset_id": dataset_id},
                    {"$set": serialized},
                    upsert=True,
                )
                logger.debug(f"[DatasetMemo] Persisted memo for {dataset_id} to MongoDB")
            except Exception as e:
                logger.warning(f"[DatasetMemo] MongoDB persist failed for {dataset_id}: {e}")

        logger.debug(f"[DatasetMemo] Cached memo for {dataset_id} (domain={memo.domain_id})")

    @classmethod
    def get(
        cls,
        dataset_id: str,
        load_from_mongo: bool = False,
        mongo_db=None,
    ) -> Optional[DatasetMemo]:
        """
        Retrieve a DatasetMemo from the cache.

        Args:
            dataset_id: Dataset identifier.
            load_from_mongo: If True and not found in memory, try MongoDB.
            mongo_db: PyMongo database instance (required if load_from_mongo=True).

        Returns:
            DatasetMemo if found, None otherwise.
        """
        # Try in-memory first (fast path)
        serialized = cls._cache.get(dataset_id)
        if serialized is not None:
            return DatasetMemo.from_dict(serialized)

        # Try MongoDB (slow path)
        if load_from_mongo and mongo_db is not None:
            try:
                collection = mongo_db[cls.MONGO_COLLECTION]
                doc = collection.find_one({"dataset_id": dataset_id})
                if doc is not None:
                    # Remove MongoDB _id before deserializing
                    doc.pop("_id", None)
                    memo = DatasetMemo.from_dict(doc)
                    # Re-populate in-memory cache
                    cls._cache[dataset_id] = doc
                    logger.debug(f"[DatasetMemo] Loaded memo for {dataset_id} from MongoDB")
                    return memo
            except Exception as e:
                logger.warning(f"[DatasetMemo] MongoDB load failed for {dataset_id}: {e}")

        return None

    @classmethod
    def clear(cls, dataset_id: Optional[str] = None) -> None:
        """
        Clear cached memo(s).

        Args:
            dataset_id: If provided, clear only this dataset's memo.
                        If None, clear all cached memos.
        """
        if dataset_id:
            cls._cache.pop(dataset_id, None)
            logger.debug(f"[DatasetMemo] Cleared cached memo for {dataset_id}")
        else:
            cls._cache.clear()
            logger.debug("[DatasetMemo] Cleared all cached memos")

    @classmethod
    def has(cls, dataset_id: str) -> bool:
        """Check if a memo exists in the in-memory cache."""
        return dataset_id in cls._cache

    @classmethod
    def count(cls) -> int:
        """Number of memos in the in-memory cache."""
        return len(cls._cache)


# ── Convenience singleton ─────────────────────────────────────────────────────

dataset_memo_cache = DatasetMemoCache()
