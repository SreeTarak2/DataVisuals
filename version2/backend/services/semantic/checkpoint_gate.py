"""
semantic/checkpoint_gate.py — Human-in-the-Loop Checkpoint Gate (Phase 3)
==========================================================================

The HITL gate is a mandatory checkpoint before executing certain query types:

1. First query on a new dataset by this user (no execution history)
2. Query returning >10,000 rows (large data export)
3. Query involving sensitive/PII columns (email, phone, ssn, etc.)
4. Query with complex filters that might indicate user error

Architecture:
  execute() → CheckpointGate.evaluate() → requires_confirmation?
    → No: execute normally
    → Yes: return checkpoint_id → frontend shows confirmation dialog
      → User confirms: POST /confirm with checkpoint_id → execute

  Pending queries are stored in MongoDB with a 30-minute TTL.
  Confirmation removes the checkpoint and executes the stored query.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import polars as pl

logger = logging.getLogger(__name__)


# ── Sensitive column patterns ──────────────────────────────────────────────

_SENSITIVE_COLUMN_PATTERNS: Set[str] = {
    "email", "e-mail", "phone", "telephone", "mobile", "cell",
    "ssn", "social_security", "socialsecurity",
    "credit_card", "creditcard", "cc_number", "ccnum",
    "password", "passwd", "secret", "token", "auth_token",
    "bank_account", "bankaccount", "routing_number",
    "dob", "date_of_birth", "birth_date",
    "passport", "driver_license", "license_number",
    "address", "street", "zip", "postal_code",
    "ip_address", "ipaddr",
    "salary", "wage", "compensation",
}

_HIGH_CARDINALITY_HINTS: Set[str] = {
    "id", "uuid", "guid", "hash", "email", "phone",
}


# ── Checkpoint models ──────────────────────────────────────────────────────


@dataclass
class CheckpointDecision:
    """Result of the checkpoint evaluation."""

    requires_confirmation: bool
    checkpoint_id: str = ""
    reason: str = ""
    details: List[str] = field(default_factory=list)
    estimated_row_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requires_confirmation": self.requires_confirmation,
            "checkpoint_id": self.checkpoint_id,
            "reason": self.reason,
            "details": self.details,
            "estimated_row_count": self.estimated_row_count,
        }


@dataclass
class PendingQuery:
    """A query waiting for human confirmation."""

    checkpoint_id: str
    query: str
    dataset_id: str
    user_id: str
    sql: str
    intent_json: str
    resolved_metrics_json: str
    validation_json: str
    estimated_row_count: int
    reason: str
    created_at: float
    ttl_seconds: float = 1800.0  # 30 minutes


# ── Pending query store ────────────────────────────────────────────────────


class PendingQueryStore:
    """Stores pending queries awaiting human confirmation.

    Backed by an in-memory dict + optional MongoDB persistence.
    Queries expire after TTL (default 30 minutes).
    """

    def __init__(self):
        self._pending: Dict[str, PendingQuery] = {}
        self._mongo_collection = None

    async def _get_collection(self):
        """Lazy-load MongoDB collection."""
        if self._mongo_collection is None:
            try:
                from db.database import get_database
                db = get_database()
                self._mongo_collection = db["pending_queries"]
                # Create TTL index
                await self._mongo_collection.create_index(
                    "created_at", expireAfterSeconds=1800
                )
            except Exception as e:
                logger.warning(f"[PendingQueryStore] MongoDB not available: {e}")
                self._mongo_collection = False  # Sentinel
        return self._mongo_collection if self._mongo_collection else None

    async def store(self, query: PendingQuery) -> str:
        """Store a pending query and return its checkpoint_id."""
        self._pending[query.checkpoint_id] = query

        # Also persist to MongoDB if available
        collection = await self._get_collection()
        if collection:
            try:
                await collection.insert_one({
                    "checkpoint_id": query.checkpoint_id,
                    "query": query.query,
                    "dataset_id": query.dataset_id,
                    "user_id": query.user_id,
                    "sql": query.sql,
                    "intent_json": query.intent_json,
                    "resolved_metrics_json": query.resolved_metrics_json,
                    "validation_json": query.validation_json,
                    "estimated_row_count": query.estimated_row_count,
                    "reason": query.reason,
                    "created_at": datetime.utcnow(),
                })
                logger.info(f"[PendingQueryStore] Stored in MongoDB: {query.checkpoint_id[:8]}")
            except Exception as e:
                logger.warning(f"[PendingQueryStore] MongoDB store failed: {e}")

        logger.info(
            f"[PendingQueryStore] Query pending: {query.checkpoint_id[:8]} "
            f"reason={query.reason}"
        )
        return query.checkpoint_id

    async def retrieve(self, checkpoint_id: str) -> Optional[PendingQuery]:
        """Retrieve a pending query by checkpoint_id."""
        # Check in-memory first
        query = self._pending.get(checkpoint_id)
        if query:
            # Check TTL
            if time.time() - query.created_at > query.ttl_seconds:
                del self._pending[checkpoint_id]
                return None
            return query

        # Check MongoDB
        collection = await self._get_collection()
        if collection:
            try:
                doc = await collection.find_one({"checkpoint_id": checkpoint_id})
                if doc:
                    query = PendingQuery(
                        checkpoint_id=doc["checkpoint_id"],
                        query=doc["query"],
                        dataset_id=doc["dataset_id"],
                        user_id=doc["user_id"],
                        sql=doc["sql"],
                        intent_json=doc.get("intent_json", ""),
                        resolved_metrics_json=doc.get("resolved_metrics_json", ""),
                        validation_json=doc.get("validation_json", ""),
                        estimated_row_count=doc.get("estimated_row_count", 0),
                        reason=doc.get("reason", ""),
                        created_at=doc["created_at"].timestamp(),
                    )
                    # Cache in memory
                    self._pending[checkpoint_id] = query
                    return query
            except Exception as e:
                logger.warning(f"[PendingQueryStore] MongoDB retrieve failed: {e}")

        return None

    async def confirm(self, checkpoint_id: str) -> bool:
        """Mark a pending query as confirmed — remove from store."""
        existed = checkpoint_id in self._pending
        self._pending.pop(checkpoint_id, None)

        collection = await self._get_collection()
        if collection:
            try:
                result = await collection.delete_one({"checkpoint_id": checkpoint_id})
                existed = existed or result.deleted_count > 0
            except Exception as e:
                logger.warning(f"[PendingQueryStore] MongoDB delete failed: {e}")

        return existed

    async def cleanup_expired(self):
        """Remove expired pending queries from memory."""
        now = time.time()
        expired = [
            cid for cid, q in self._pending.items()
            if now - q.created_at > q.ttl_seconds
        ]
        for cid in expired:
            del self._pending[cid]
        if expired:
            logger.info(f"[PendingQueryStore] Cleaned up {len(expired)} expired queries")


# ── Checkpoint gate ────────────────────────────────────────────────────────


class CheckpointGate:
    """Evaluates queries against HITL conditions and manages the confirmation flow.

    The gate checks:
    1. First-time query on this dataset by this user
    2. High row count (>10,000 estimated)
    3. Sensitive columns in SELECT or WHERE
    4. Very broad filters (no WHERE, LIMIT > 1000)
    """

    HIGH_ROW_COUNT_THRESHOLD = 10_000

    def __init__(self):
        self._store = PendingQueryStore()
        self._execution_history: Set[str] = set()
        # Track (user_id, dataset_id) pairs that have been queried before

    async def evaluate(
        self,
        query: str,
        sql: str,
        dataset_id: str,
        user_id: str,
        df: pl.DataFrame,
        columns: Optional[List[str]] = None,
        estimated_row_count: int = 0,
    ) -> CheckpointDecision:
        """Evaluate whether this query needs human confirmation.

        Args:
            query: The original user question
            sql: The compiled SQL
            dataset_id: The dataset being queried
            user_id: The user executing the query
            df: The full dataset DataFrame
            columns: Column names available
            estimated_row_count: Estimated row count from EXPLAIN (if available)

        Returns:
            CheckpointDecision with requires_confirmation status and reason
        """
        columns = columns or list(df.columns) if df is not None else []

        reasons: List[str] = []
        details: List[str] = []

        # Condition 1: First-time query on this dataset
        history_key = f"{user_id}:{dataset_id}"
        if history_key not in self._execution_history:
            reasons.append("first_query_on_dataset")
            details.append(
                f"This is your first query on dataset {dataset_id[:8]}. "
                "Please confirm you want to proceed."
            )

        # Condition 2: High row count
        if estimated_row_count >= self.HIGH_ROW_COUNT_THRESHOLD:
            reasons.append("high_row_count")
            details.append(
                f"This query may return {estimated_row_count:,} rows. "
                "Large result sets may take time to load."
            )
        elif len(df) >= self.HIGH_ROW_COUNT_THRESHOLD and not sql.strip().upper().startswith(
            "SELECT"
        ):
            # Full dataset scan
            reasons.append("large_dataset")
            details.append(
                f"The dataset has {len(df):,} rows. "
                "This query may process a large amount of data."
            )

        # Condition 3: Sensitive columns
        sensitive_cols = self._find_sensitive_columns(columns, sql)
        if sensitive_cols:
            reasons.append("sensitive_columns")
            details.append(
                f"Query involves potentially sensitive columns: "
                f"{', '.join(sensitive_cols[:5])}. "
                "Please confirm you intend to access this data."
            )

        # Condition 4: Broad query (no WHERE, high LIMIT or no LIMIT)
        if self._is_broad_query(sql):
            reasons.append("broad_query")
            details.append(
                "This query has no filters — it will return all data. "
                "Please confirm this is intentional."
            )

        if not reasons:
            # No conditions triggered — pass through
            self._execution_history.add(history_key)
            return CheckpointDecision(
                requires_confirmation=False,
                reason="",
                estimated_row_count=estimated_row_count,
            )

        # Create checkpoint
        checkpoint_id = f"chk_{uuid.uuid4().hex[:16]}"
        reason_str = "; ".join(details)

        # Store the pending query (without execution yet)
        pending = PendingQuery(
            checkpoint_id=checkpoint_id,
            query=query,
            dataset_id=dataset_id,
            user_id=user_id,
            sql=sql,
            intent_json="",
            resolved_metrics_json="",
            validation_json="",
            estimated_row_count=estimated_row_count,
            reason="; ".join(reasons),
            created_at=time.time(),
        )
        await self._store.store(pending)

        return CheckpointDecision(
            requires_confirmation=True,
            checkpoint_id=checkpoint_id,
            reason=reason_str,
            details=details,
            estimated_row_count=estimated_row_count,
        )

    async def acknowledge(
        self,
        checkpoint_id: str,
        user_id: str,
    ) -> Optional[PendingQuery]:
        """Retrieve and validate a pending query WITHOUT deleting it from store.

        This is the first step of the two-phase commit:
        1. acknowledge() — validate user_id, check TTL, retrieve the query
        2. complete()   — delete from store AFTER successful execution

        If the subsequent execution fails, the checkpoint remains in store
        so the user can retry without re-submitting the original query.

        Args:
            checkpoint_id: The checkpoint ID to confirm
            user_id: The user confirming (must match the original user)

        Returns:
            The PendingQuery if valid, None if not found, expired, or user mismatch
        """
        query = await self._store.retrieve(checkpoint_id)
        if query is None:
            logger.warning(f"[CheckpointGate] Checkpoint not found or expired: {checkpoint_id[:8]}")
            return None

        if query.user_id != user_id:
            logger.warning(
                f"[CheckpointGate] User mismatch for checkpoint {checkpoint_id[:8]}: "
                f"{user_id[:8]} vs {query.user_id[:8]}"
            )
            return None

        logger.info(f"[CheckpointGate] Query acknowledged: {checkpoint_id[:8]}")
        return query

    async def complete(self, checkpoint_id: str, user_id: str = "", dataset_id: str = "") -> bool:
        """Delete checkpoint from store after successful execution.

        Call this only AFTER the query has been successfully re-executed.
        This is the second step of the two-phase commit — if this fails,
        the checkpoint is simply cleaned up by TTL.

        If user_id and dataset_id are provided, records the execution
        history so future queries from this user on this dataset won't
        trigger the "first_query_on_dataset" checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to remove
            user_id: The confirming user (for execution history)
            dataset_id: The confirmed dataset (for execution history)

        Returns:
            True if the checkpoint existed and was removed
        """
        existed = await self._store.confirm(checkpoint_id)
        if existed:
            logger.info(f"[CheckpointGate] Checkpoint completed and removed: {checkpoint_id[:8]}")
        else:
            logger.warning(f"[CheckpointGate] Checkpoint already removed: {checkpoint_id[:8]}")

        # Record execution history so future queries don't re-trigger "first_query" check
        if user_id and dataset_id:
            self._execution_history.add(f"{user_id}:{dataset_id}")

        return existed

    # ── Helper methods ────────────────────────────────────────────────────

    @staticmethod
    def _find_sensitive_columns(columns: List[str], sql: str) -> List[str]:
        """Find columns that match sensitive patterns."""
        sensitive: List[str] = []
        sql_lower = sql.lower()

        for col in columns:
            col_lower = col.lower().strip("`\"'")
            for pattern in _SENSITIVE_COLUMN_PATTERNS:
                if pattern in col_lower:
                    # Check if this column is actually referenced in the SQL
                    if col_lower in sql_lower or f"`{col_lower}`" in sql_lower:
                        sensitive.append(col)
                        break

        return sensitive

    @staticmethod
    def _is_broad_query(sql: str) -> bool:
        """Check if a query is very broad (no filters, no limits)."""
        sql_upper = sql.strip().upper()

        # No WHERE clause
        if "WHERE" not in sql_upper:
            return True

        # No LIMIT clause (high chance of large return)
        if "LIMIT" not in sql_upper:
            # Check if it's a simple aggregation (which is fine)
            has_aggregation = any(
                agg in sql_upper for agg in ["SUM(", "COUNT(", "AVG(", "MIN(", "MAX("]
            )
            if not has_aggregation:
                return True

        return False


# Singleton
checkpoint_gate = CheckpointGate()
# The standalone pending_query_store singleton was removed as redundant
# because CheckpointGate owns its own PendingQueryStore internally.
