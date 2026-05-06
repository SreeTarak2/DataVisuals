from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import logging

from services.feedback.context_store import context_store
from db.schemas_context import SignalType

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    QUERY = "query"
    RESPONSE = "response"
    REGENERATE = "regenerate"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    CORRECTION = "correction"
    EXPORT = "export"
    SHARE = "share"
    SAVE = "save"
    CHART_EDIT = "chart_edit"
    FILTER_CHANGE = "filter_change"
    METRIC_CHANGE = "metric_change"
    DATE_RANGE_CHANGE = "date_range_change"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    ABANDON = "abandon"


class EventLogger:
    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.current_user_id: Optional[str] = None
        self.current_workspace_id: Optional[str] = None
        self.last_query: Optional[str] = None
        self.last_response: Optional[str] = None
        self.last_query_time: Optional[datetime] = None

    def start_session(
        self,
        user_id: str,
        workspace_id: str,
        session_id: Optional[str] = None,
    ):
        self.current_user_id = user_id
        self.current_workspace_id = workspace_id
        self.current_session_id = session_id or str(datetime.utcnow().timestamp())
        logger.info(f"Session started: {self.current_session_id}")

    def end_session(self):
        if self.current_session_id:
            logger.info(f"Session ended: {self.current_session_id}")
            self.current_session_id = None

    async def log_query(
        self,
        query_text: str,
        response_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.current_user_id or not self.current_workspace_id:
            logger.warning("Session not initialized")
            return

        self.last_query = query_text
        self.last_response = response_text
        self.last_query_time = datetime.utcnow()

        await context_store.log_interaction_event(
            user_id=self.current_user_id,
            workspace_id=self.current_workspace_id,
            query_text=query_text,
            event_type=EventType.QUERY,
            response_text=response_text,
            metadata=metadata or {},
        )

    async def log_regenerate(self, metadata: Optional[Dict[str, Any]] = None):
        if (
            not self.last_query
            or not self.last_query_time
            or not self.current_user_id
            or not self.current_workspace_id
        ):
            return 0.0

        time_since_last = (datetime.utcnow() - self.last_query_time).total_seconds()
        metadata = metadata or {}
        metadata["time_since_last_query"] = time_since_last
        metadata["previous_query"] = self.last_query

        await context_store.log_interaction_event(
            user_id=self.current_user_id,
            workspace_id=self.current_workspace_id,
            query_text=self.last_query,
            event_type=EventType.REGENERATE,
            response_text=self.last_response,
            metadata=metadata,
        )

        return time_since_last

    async def log_follow_up(
        self, follow_up_text: str, metadata: Optional[Dict[str, Any]] = None
    ):
        if not self.current_user_id:
            return

        metadata = metadata or {}
        metadata["previous_query"] = self.last_query

        await context_store.log_interaction_event(
            user_id=self.current_user_id,
            workspace_id=self.current_workspace_id or "",
            query_text=follow_up_text,
            event_type=EventType.FOLLOW_UP,
            metadata=metadata,
        )

    async def log_correction(
        self,
        correction_text: str,
        original_query: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self.current_user_id:
            return

        metadata = metadata or {}
        metadata["original_query"] = original_query or self.last_query

        await context_store.log_interaction_event(
            user_id=self.current_user_id or "",
            workspace_id=self.current_workspace_id or "",
            query_text=correction_text,
            event_type=EventType.CORRECTION,
            metadata=metadata,
        )

    async def log_export(self, format: str, metadata: Optional[Dict[str, Any]] = None):
        await self._log_event(EventType.EXPORT, {"format": format} | (metadata or {}))

    async def log_share(self, metadata: Optional[Dict[str, Any]] = None):
        await self._log_event(EventType.SHARE, metadata or {})

    async def log_save(self, item_type: str, metadata: Optional[Dict[str, Any]] = None):
        await self._log_event(
            EventType.SAVE, {"item_type": item_type} | (metadata or {})
        )

    async def log_chart_edit(
        self,
        edit_type: str,
        old_value: Any,
        new_value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        await self._log_event(
            EventType.CHART_EDIT,
            {"edit_type": edit_type, "old_value": old_value, "new_value": new_value}
            | (metadata or {}),
        )

    async def log_filter_change(
        self,
        filter_field: str,
        old_value: Any,
        new_value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        await self._log_event(
            EventType.FILTER_CHANGE,
            {
                "filter_field": filter_field,
                "old_value": old_value,
                "new_value": new_value,
            }
            | (metadata or {}),
        )

    async def log_metric_change(
        self,
        old_metric: str,
        new_metric: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        await self._log_event(
            EventType.METRIC_CHANGE,
            {"old_metric": old_metric, "new_metric": new_metric} | (metadata or {}),
        )

    async def log_date_range_change(
        self,
        old_range: str,
        new_range: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        await self._log_event(
            EventType.DATE_RANGE_CHANGE,
            {"old_range": old_range, "new_range": new_range} | (metadata or {}),
        )

    async def log_abandon(self, metadata: Optional[Dict[str, Any]] = None):
        await self._log_event(EventType.ABANDON, metadata or {})

    async def _log_event(
        self,
        event_type: EventType,
        metadata: Dict[str, Any],
    ):
        if not self.current_user_id or not self.current_workspace_id:
            return

        await context_store.log_interaction_event(
            user_id=self.current_user_id,
            workspace_id=self.current_workspace_id or "",
            query_text=self.last_query or "",
            event_type=event_type,
            response_text=metadata.get("response_text"),
            metadata=metadata,
        )

    def detect_correction_phrase(self, text: str) -> bool:
        correction_patterns = [
            r"^no[,\.\s]",
            r"^not this",
            r"^wrong",
            r"^incorrect",
            r"^I mean",
            r"^actually",
            r"^wait",
            r"^hold on",
            r"^that's not right",
            r"^that doesn't look",
            r"this is wrong",
            r"not what I wanted",
            r"wanted.*instead",
            r"should be",
            r"can you.*instead",
            r"no,.*should be",
            r"revenue.*not",
            r"(mrr|arr|revenue).*(bookings|recogni)",
        ]
        import re

        text_lower = text.lower().strip()
        for pattern in correction_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def detect_negative_sentiment(self, text: str) -> bool:
        negative_patterns = [
            r"\b(wrong|incorrect|error|bad|stupid|dumb|terrible|awful)\b",
            r"\b(don't|doesn'?t|won'?t|can'?t)\b.*\b(work|understand|get it)\b",
            r"this makes no sense",
            r"are you sure\?",
            r"try again",
        ]
        import re

        text_lower = text.lower()
        for pattern in negative_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def detect_positive_sentiment(self, text: str) -> bool:
        positive_patterns = [
            r"\b(thanks|thank you|perfect|correct|exactly|great|nice|yep|yes|got it)\b",
            r"that'?s (right|what I wanted|perfect)",
            r"exactly what I needed",
        ]
        import re

        text_lower = text.lower()
        for pattern in positive_patterns:
            if re.search(pattern, text_lower):
                return True
        return False


event_logger = EventLogger()
