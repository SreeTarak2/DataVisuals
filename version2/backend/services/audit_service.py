"""
Enterprise Audit Service
------------------------
GDPR-compliant audit logging for all chat interactions.

Features:
- Hashed query logging for privacy
- Full interaction tracking (user, dataset, conversation, latency)
- Data export for GDPR compliance
- Performance metrics aggregation
- Retention policy support

Usage:
    from services.audit_service import audit_service
    
    await audit_service.log_chat_interaction(
        user_id="...",
        dataset_id="...",
        conversation_id="...",
        query="...",
        response="...",
        latency_ms=150.5,
        success=True
    )
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from db.database import get_database

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""
    CHAT_MESSAGE = "chat_message"
    DEEP_ANALYSIS = "deep_analysis"
    CHART_GENERATION = "chart_generation"
    DASHBOARD_CREATE = "dashboard_create"
    DATASET_ACCESS = "dataset_access"
    EXPORT_REQUEST = "export_request"
    AUTH_EVENT = "auth_event"
    ERROR = "error"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditService:
    """
    Enterprise-grade audit logging service for compliance and monitoring.
    
    Implements:
    - GDPR right to data export
    - Query hashing for privacy protection
    - Structured logging for analytics
    - Retention policy management
    """
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        """Lazy database initialization."""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    # -----------------------------------------------------------
    # Core Logging Methods
    # -----------------------------------------------------------
    
    async def log_chat_interaction(
        self,
        user_id: str,
        dataset_id: str,
        conversation_id: Optional[str],
        query: str,
        response: str,
        latency_ms: float,
        success: bool,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
        chart_generated: bool = False,
        analysis_type: str = "standard"
    ) -> str:
        """
        Log a chat interaction with GDPR-compliant hashing.
        
        Args:
            user_id: User identifier
            dataset_id: Dataset being queried
            conversation_id: Conversation thread ID
            query: Original user query (hashed for storage)
            response: AI response (truncated for storage)
            latency_ms: Request processing time
            success: Whether the request succeeded
            model_used: LLM model that handled the request
            tokens_used: Approximate token count
            chart_generated: Whether a chart was created
            analysis_type: Type of analysis performed
            
        Returns:
            Audit log entry ID
        """
        try:
            # Hash query for privacy (GDPR compliance)
            query_hash = self._hash_content(query)
            
            # Truncate response for storage efficiency
            response_summary = response[:500] if response else ""
            
            audit_entry = {
                "timestamp": datetime.utcnow(),
                "event_type": AuditEventType.CHAT_MESSAGE,
                "severity": AuditSeverity.INFO if success else AuditSeverity.WARNING,
                "user_id": user_id,
                "dataset_id": dataset_id,
                "conversation_id": conversation_id,
                "query_hash": query_hash,
                "query_length": len(query) if query else 0,
                "response_summary": response_summary,
                "response_length": len(response) if response else 0,
                "latency_ms": round(latency_ms, 2),
                "success": success,
                "model_used": model_used,
                "tokens_used": tokens_used,
                "chart_generated": chart_generated,
                "analysis_type": analysis_type,
                "metadata": {
                    "hour_of_day": datetime.utcnow().hour,
                    "day_of_week": datetime.utcnow().weekday()
                }
            }
            
            result = await self.db.audit_logs.insert_one(audit_entry)
            
            # Log to standard logging as well
            logger.info(
                f"AUDIT: user={user_id[:8]}... dataset={dataset_id[:8]}... "
                f"latency={latency_ms:.0f}ms success={success}"
            )
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")
            # Don't raise - audit failures shouldn't break the app
            return ""
    
    async def log_deep_analysis(
        self,
        user_id: str,
        dataset_id: str,
        query: Optional[str],
        insights_generated: int,
        charts_generated: int,
        latency_ms: float,
        success: bool,
        stats: Optional[Dict] = None
    ) -> str:
        """Log deep QUIS analysis events."""
        try:
            audit_entry = {
                "timestamp": datetime.utcnow(),
                "event_type": AuditEventType.DEEP_ANALYSIS,
                "severity": AuditSeverity.INFO if success else AuditSeverity.ERROR,
                "user_id": user_id,
                "dataset_id": dataset_id,
                "query_hash": self._hash_content(query) if query else None,
                "insights_generated": insights_generated,
                "charts_generated": charts_generated,
                "latency_ms": round(latency_ms, 2),
                "success": success,
                "stats": stats or {}
            }
            
            result = await self.db.audit_logs.insert_one(audit_entry)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to log deep analysis audit: {e}")
            return ""
    
    async def log_error(
        self,
        user_id: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None
    ) -> str:
        """Log error events for debugging and monitoring."""
        try:
            audit_entry = {
                "timestamp": datetime.utcnow(),
                "event_type": AuditEventType.ERROR,
                "severity": AuditSeverity.ERROR,
                "user_id": user_id,
                "error_type": error_type,
                "error_message": error_message[:500],
                "context": context or {},
                "success": False
            }
            
            result = await self.db.audit_logs.insert_one(audit_entry)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to log error audit: {e}")
            return ""
    
    # -----------------------------------------------------------
    # GDPR Compliance Methods
    # -----------------------------------------------------------
    
    async def export_user_data(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """
        GDPR: Export all audit data for a user.
        
        Users have the right to request their data. This method
        returns all audit logs associated with a user.
        
        Args:
            user_id: User requesting their data
            start_date: Optional start filter
            end_date: Optional end filter
            limit: Maximum records to return
            
        Returns:
            List of audit records
        """
        try:
            query = {"user_id": user_id}
            
            if start_date or end_date:
                query["timestamp"] = {}
                if start_date:
                    query["timestamp"]["$gte"] = start_date
                if end_date:
                    query["timestamp"]["$lte"] = end_date
            
            cursor = self.db.audit_logs.find(
                query,
                # Exclude internal fields
                {"_id": 0, "query_hash": 0}
            ).sort("timestamp", -1).limit(limit)
            
            records = await cursor.to_list(length=limit)
            
            # Log the export request itself
            await self._log_gdpr_export(user_id, len(records))
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to export user data: {e}")
            return []
    
    async def delete_user_data(
        self,
        user_id: str,
        before_date: Optional[datetime] = None
    ) -> int:
        """
        GDPR: Delete user's audit data (right to be forgotten).
        
        Args:
            user_id: User requesting deletion
            before_date: Only delete records before this date
            
        Returns:
            Number of records deleted
        """
        try:
            query = {"user_id": user_id}
            if before_date:
                query["timestamp"] = {"$lt": before_date}
            
            result = await self.db.audit_logs.delete_many(query)
            
            logger.info(f"GDPR: Deleted {result.deleted_count} audit records for user {user_id[:8]}...")
            
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete user data: {e}")
            return 0
    
    # -----------------------------------------------------------
    # Analytics & Monitoring
    # -----------------------------------------------------------
    
    async def get_user_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a user.
        
        Returns:
            - total_queries: Number of queries
            - successful_queries: Number of successful queries
            - avg_latency_ms: Average response time
            - charts_generated: Number of charts created
            - most_active_hour: Most active hour of day
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "timestamp": {"$gte": start_date},
                        "event_type": AuditEventType.CHAT_MESSAGE
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_queries": {"$sum": 1},
                        "successful_queries": {
                            "$sum": {"$cond": ["$success", 1, 0]}
                        },
                        "avg_latency_ms": {"$avg": "$latency_ms"},
                        "charts_generated": {
                            "$sum": {"$cond": ["$chart_generated", 1, 0]}
                        },
                        "total_tokens": {"$sum": {"$ifNull": ["$tokens_used", 0]}}
                    }
                }
            ]
            
            results = await self.db.audit_logs.aggregate(pipeline).to_list(1)
            
            if results:
                stats = results[0]
                stats.pop("_id", None)
                stats["avg_latency_ms"] = round(stats.get("avg_latency_ms", 0), 2)
                stats["success_rate"] = (
                    round(stats["successful_queries"] / max(stats["total_queries"], 1) * 100, 1)
                )
                return stats
            
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "avg_latency_ms": 0,
                "charts_generated": 0,
                "total_tokens": 0,
                "success_rate": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {}
    
    async def get_system_health(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get system-wide health metrics for monitoring.
        
        Returns:
            - total_requests: Total requests in time window
            - error_rate: Percentage of failed requests
            - avg_latency_ms: Average response time
            - p95_latency_ms: 95th percentile latency
            - active_users: Unique users in period
        """
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            pipeline = [
                {
                    "$match": {
                        "timestamp": {"$gte": start_time}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_requests": {"$sum": 1},
                        "failed_requests": {
                            "$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}
                        },
                        "avg_latency_ms": {"$avg": "$latency_ms"},
                        "p95_latency_ms": {
                            "$percentile": {
                                "input": "$latency_ms",
                                "p": [0.95],
                                "method": "approximate"
                            }
                        },
                        "active_users": {"$addToSet": "$user_id"}
                    }
                }
            ]
            
            results = await self.db.audit_logs.aggregate(pipeline).to_list(1)
            
            if results:
                result = results[0]
                p95_value = result.get("p95_latency_ms")
                # $percentile returns a list; extract first element
                if isinstance(p95_value, list):
                    p95_value = p95_value[0] if p95_value else 0
                
                return {
                    "total_requests": result.get("total_requests", 0),
                    "error_rate": round(
                        result.get("failed_requests", 0) / max(result.get("total_requests", 1), 1) * 100, 2
                    ),
                    "avg_latency_ms": round(result.get("avg_latency_ms", 0), 2),
                    "p95_latency_ms": round(p95_value or 0, 2),
                    "active_users": len(result.get("active_users", []))
                }
            
            return {
                "total_requests": 0,
                "error_rate": 0,
                "avg_latency_ms": 0,
                "p95_latency_ms": 0,
                "active_users": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {}
    
    # -----------------------------------------------------------
    # Retention Policy
    # -----------------------------------------------------------
    
    async def cleanup_old_logs(
        self,
        retention_days: int = 90,
        batch_size: int = 1000
    ) -> int:
        """
        Clean up audit logs older than retention period.
        
        Should be run periodically (e.g., daily cron job).
        
        Args:
            retention_days: Days to keep logs
            batch_size: Max records to delete per run
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find old records
            old_ids = await self.db.audit_logs.find(
                {"timestamp": {"$lt": cutoff_date}},
                {"_id": 1}
            ).limit(batch_size).to_list(batch_size)
            
            if not old_ids:
                return 0
            
            ids_to_delete = [doc["_id"] for doc in old_ids]
            result = await self.db.audit_logs.delete_many(
                {"_id": {"$in": ids_to_delete}}
            )
            
            logger.info(f"Cleaned up {result.deleted_count} old audit logs")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    # -----------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------
    
    def _hash_content(self, content: str) -> str:
        """Create a privacy-preserving hash of content."""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    async def _log_gdpr_export(self, user_id: str, record_count: int):
        """Log that a GDPR export was performed."""
        try:
            await self.db.audit_logs.insert_one({
                "timestamp": datetime.utcnow(),
                "event_type": AuditEventType.EXPORT_REQUEST,
                "severity": AuditSeverity.INFO,
                "user_id": user_id,
                "records_exported": record_count,
                "success": True
            })
        except Exception:
            pass  # Don't fail on meta-logging


# Create singleton instance
audit_service = AuditService()


# -----------------------------------------------------------
# Index Recommendations (run once on deployment)
# -----------------------------------------------------------
async def create_audit_indexes():
    """
    Create indexes for efficient audit queries.
    Run this during deployment/migration.
    """
    db = get_database()
    
    # Index for user queries (GDPR exports)
    await db.audit_logs.create_index([("user_id", 1), ("timestamp", -1)])
    
    # Index for time-based cleanup
    await db.audit_logs.create_index([("timestamp", 1)])
    
    # Index for analytics
    await db.audit_logs.create_index([
        ("event_type", 1),
        ("timestamp", -1),
        ("success", 1)
    ])
    
    logger.info("Audit indexes created successfully")
