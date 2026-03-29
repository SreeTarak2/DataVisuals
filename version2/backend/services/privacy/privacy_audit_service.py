"""
Privacy Audit Service
===================
Logs all privacy-related events for compliance and transparency.

Events Logged:
- pii_scan: Dataset scanned for PII
- redaction_applied: Data was redacted
- settings_changed: Privacy settings were modified
- data_accessed: Data was sent to LLM
- dataset_deleted: Dataset was deleted (manual or retention)
- dry_run_completed: Privacy preview was shown
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class PrivacyEventType(Enum):
    """Types of privacy-related events."""

    PII_SCAN = "pii_scan"
    REDACTION_APPLIED = "redaction_applied"
    SETTINGS_CHANGED = "settings_changed"
    DATA_ACCESSED = "data_accessed"
    DATASET_DELETED = "dataset_deleted"
    DRY_RUN_COMPLETED = "dry_run_completed"
    RETENTION_WARNING_SENT = "retention_warning_sent"


@dataclass
class PrivacyAuditEvent:
    """A single privacy audit event."""

    event_id: str
    user_id: str
    event_type: str
    dataset_id: Optional[str] = None
    details: Dict[str, Any] = None
    timestamp: str = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.details is None:
            self.details = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "event_type": self.event_type.value
            if isinstance(self.event_type, PrivacyEventType)
            else self.event_type,
            "dataset_id": self.dataset_id,
            "details": self.details,
            "timestamp": self.timestamp,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


class PrivacyAuditService:
    """
    Service for logging and retrieving privacy audit events.

    Retention: 90 days (configurable)
    Indexes: user_id, event_type, dataset_id, timestamp
    """

    COLLECTION_NAME = "privacy_audit_log"
    DEFAULT_RETENTION_DAYS = 90

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        """Lazy database initialization."""
        if self._db is None:
            from db.database import get_database

            self._db = get_database()
        return self._db

    async def _ensure_indexes(self):
        """Ensure required indexes exist."""
        collection = self.db[self.COLLECTION_NAME]
        await collection.create_index("user_id")
        await collection.create_index("event_type")
        await collection.create_index("dataset_id")
        await collection.create_index("timestamp")
        await collection.create_index([("user_id", 1), ("timestamp", -1)])

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid

        return str(uuid.uuid4())

    async def log_event(
        self,
        user_id: str,
        event_type: PrivacyEventType,
        dataset_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Log a privacy event.

        Args:
            user_id: User identifier
            event_type: Type of event
            dataset_id: Optional dataset identifier
            details: Event-specific details
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Event ID
        """
        event = PrivacyAuditEvent(
            event_id=self._generate_event_id(),
            user_id=user_id,
            event_type=event_type,
            dataset_id=dataset_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        try:
            await self.db[self.COLLECTION_NAME].insert_one(event.to_dict())
            logger.debug(f"Privacy event logged: {event_type.value} for user {user_id}")
            return event.event_id
        except Exception as e:
            logger.error(f"Failed to log privacy event: {e}")
            return event.event_id  # Return ID even if logging fails

    async def log_pii_scan(
        self,
        user_id: str,
        dataset_id: str,
        columns_found: List[str],
        pii_detected: List[Dict[str, Any]],
        confidence_scores: Dict[str, float],
    ):
        """Log a PII scan event."""
        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.PII_SCAN,
            dataset_id=dataset_id,
            details={
                "columns_found": columns_found,
                "pii_detected": pii_detected,
                "confidence_scores": confidence_scores,
                "total_pii_columns": len(pii_detected),
            },
        )

    async def log_redaction(
        self,
        user_id: str,
        dataset_id: str,
        columns_redacted: List[str],
        pii_types: List[str],
        redaction_mode: str,
    ):
        """Log a data redaction event."""
        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.REDACTION_APPLIED,
            dataset_id=dataset_id,
            details={
                "columns_redacted": columns_redacted,
                "pii_types": pii_types,
                "redaction_mode": redaction_mode,
                "total_redacted": len(columns_redacted),
            },
        )

    async def log_settings_change(
        self,
        user_id: str,
        old_settings: Dict[str, Any],
        new_settings: Dict[str, Any],
        dataset_id: Optional[str] = None,
    ):
        """Log a privacy settings change."""
        # Only log what changed
        changes = {}
        all_keys = set(old_settings.keys()) | set(new_settings.keys())
        for key in all_keys:
            if old_settings.get(key) != new_settings.get(key):
                changes[key] = {
                    "old": old_settings.get(key),
                    "new": new_settings.get(key),
                }

        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.SETTINGS_CHANGED,
            dataset_id=dataset_id,
            details={"changes": changes, "affected_keys": list(changes.keys())},
        )

    async def log_data_access(
        self,
        user_id: str,
        dataset_id: str,
        llm_model: str,
        columns_shared: List[str],
        sample_rows_shared: int,
        pii_redacted: List[str],
    ):
        """Log when data is accessed by LLM."""
        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.DATA_ACCESSED,
            dataset_id=dataset_id,
            details={
                "llm_model": llm_model,
                "columns_shared": columns_shared,
                "sample_rows_shared": sample_rows_shared,
                "pii_redacted": pii_redacted,
                "total_columns": len(columns_shared),
                "total_pii_redacted": len(pii_redacted),
            },
        )

    async def log_dataset_deletion(
        self,
        user_id: str,
        dataset_id: str,
        reason: str = "manual",
        triggered_by: str = "user",
    ):
        """Log dataset deletion."""
        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.DATASET_DELETED,
            dataset_id=dataset_id,
            details={"reason": reason, "triggered_by": triggered_by},
        )

    async def log_dry_run(
        self,
        user_id: str,
        dataset_id: str,
        columns_to_share: List[str],
        columns_to_redact: List[str],
    ):
        """Log a dry-run preview completion."""
        await self.log_event(
            user_id=user_id,
            event_type=PrivacyEventType.DRY_RUN_COMPLETED,
            dataset_id=dataset_id,
            details={
                "columns_to_share": columns_to_share,
                "columns_to_redact": columns_to_redact,
            },
        )

    async def get_user_events(
        self,
        user_id: str,
        event_types: Optional[List[str]] = None,
        dataset_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get privacy events for a user.

        Args:
            user_id: User identifier
            event_types: Filter by event types
            dataset_id: Filter by dataset
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum events to return
            skip: Number of events to skip

        Returns:
            List of privacy events
        """
        query = {"user_id": user_id}

        if event_types:
            query["event_type"] = {"$in": event_types}

        if dataset_id:
            query["dataset_id"] = dataset_id

        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date.isoformat()
            if end_date:
                query["timestamp"]["$lte"] = end_date.isoformat()

        cursor = (
            self.db[self.COLLECTION_NAME]
            .find(query)
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )

        events = []
        async for event in cursor:
            events.append(event)

        return events

    async def get_dataset_events(
        self, dataset_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all privacy events for a dataset."""
        cursor = (
            self.db[self.COLLECTION_NAME]
            .find({"dataset_id": dataset_id})
            .sort("timestamp", -1)
            .limit(limit)
        )

        events = []
        async for event in cursor:
            events.append(event)

        return events

    async def get_event_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get privacy event statistics for a user.

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            Statistics dictionary
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "timestamp": {"$gte": start_date.isoformat()},
                }
            },
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        cursor = self.db[self.COLLECTION_NAME].aggregate(pipeline)
        stats = {}
        total = 0
        async for doc in cursor:
            event_type = doc["_id"]
            count = doc["count"]
            stats[event_type] = count
            total += count

        stats["total_events"] = total
        stats["period_days"] = days

        return stats

    async def cleanup_old_events(self, retention_days: int = None):
        """
        Delete privacy events older than retention period.

        Args:
            retention_days: Number of days to retain (default: 90)
        """
        if retention_days is None:
            retention_days = self.DEFAULT_RETENTION_DAYS

        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        result = await self.db[self.COLLECTION_NAME].delete_many(
            {"timestamp": {"$lt": cutoff.isoformat()}}
        )

        logger.info(
            f"Cleaned up {result.deleted_count} privacy audit events older than {retention_days} days"
        )
        return result.deleted_count

    async def export_user_events(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Export privacy events for a user (GDPR compliance).

        Args:
            user_id: User identifier
            start_date: Start of date range (default: 1 year ago)
            end_date: End of date range (default: now)

        Returns:
            Export dictionary
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.utcnow()

        events = await self.get_user_events(
            user_id=user_id, start_date=start_date, end_date=end_date, limit=10000
        )

        return {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_events": len(events),
            "events": events,
        }


# Singleton instance
privacy_audit_service = PrivacyAuditService()
