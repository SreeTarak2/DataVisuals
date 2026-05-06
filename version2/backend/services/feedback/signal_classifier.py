from typing import Optional, List, Dict, Any, Tuple
import re
import logging
from datetime import datetime, timedelta

from db.schemas_context import SignalType
from services.feedback.context_store import context_store
from services.feedback.event_logger import event_logger, EventType

logger = logging.getLogger(__name__)

FRICTION_THRESHOLD_SECONDS = 20
HIGH_FRICTION_SECONDS = 10


class SignalClassifier:
    def __init__(self):
        pass

    def classify_implicit_signal(
        self,
        current_query: str,
        previous_query: Optional[str],
        event_type: str,
        time_since_last: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SignalType:
        metadata = metadata or {}
        query_lower = current_query.lower().strip()

        if event_type == EventType.REGENERATE:
            if time_since_last and time_since_last < HIGH_FRICTION_SECONDS:
                return SignalType.FRICTION
            elif time_since_last and time_since_last < FRICTION_THRESHOLD_SECONDS:
                return SignalType.CONFUSION
            return SignalType.NEUTRAL

        if event_type == EventType.FOLLOW_UP:
            if event_logger.detect_correction_phrase(query_lower):
                return SignalType.CORRECTION
            if event_logger.detect_negative_sentiment(query_lower):
                return SignalType.FRICTION
            if (
                time_since_last
                and previous_query
                and self._is_narrowing(previous_query, current_query)
            ):
                return SignalType.CONFUSION

        if event_type == EventType.CORRECTION:
            return SignalType.CORRECTION

        if event_type in (EventType.EXPORT, EventType.SHARE, EventType.SAVE):
            return SignalType.DELIGHT

        if event_type == EventType.ABANDON:
            return SignalType.FRICTION

        return SignalType.NEUTRAL

    def _is_narrowing(self, original: str, follow_up: str) -> bool:
        original_lower = original.lower()
        follow_up_lower = follow_up.lower()

        narrowing_patterns = [
            r"only\s+(for|in|with)",
            r"just\s+(for|in|with)",
            r"filter(ed)?\s+(by|to)",
            r"where\s+\w+\s*=",
            r"(more|fewer)\s+than",
            r"(greater|less)\s+than",
            r"\b(before|after)\s+\w+\s+\d+",
            r"from\s+\w+\s+to\s+\w+",
        ]

        for pattern in narrowing_patterns:
            if re.search(pattern, follow_up_lower):
                return True

        if len(follow_up) > len(original) * 1.3:
            return True

        return False

    def extract_correction_term(
        self,
        correction_text: str,
        response_text: str,
    ) -> Optional[Tuple[str, str, str]]:
        correction_lower = correction_text.lower()

        patterns = [
            (
                r"(?:no|wrong|not)\s+[:,]?\s*(?:the\s+)?(\w+)\s*(?:is|means|=)\s*(?:the\s+)?(\w+)",
                "corrected_term",
                "interpretation",
            ),
            (
                r"(\w+)\s+(?:not|means|is|=|represent(?:s)?)\s+(?:the\s+)?(\w+)",
                "corrected_term",
                "interpretation",
            ),
            (
                r"(mrr|arr|revenue|bookings)\s+(?:not|means|is|=|represent(?:s)?)\s+(?:the\s+)?(\w+)",
                "original_term",
                "corrected_term",
            ),
            (r"(?:i|i'm|i am)\s+(?:mean|meaning)\s+(\w+)", None, "corrected_term"),
            (r"(?:^|\s)(\w+)\s*,\s*not\s+(\w+)", "corrected_term", "original_term"),
        ]

        for pattern, first_group, second_group in patterns:
            match = re.search(pattern, correction_lower)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    if first_group and second_group:
                        continue
                    term1, term2 = groups[0], groups[1]
                    return (term1, term2, f"{term1}, not {term2}")
                elif len(groups) == 1:
                    return (groups[0], groups[0], groups[0])

        return None

    async def classify_and_store(
        self,
        user_id: str,
        workspace_id: str,
        query: str,
        response: Optional[str],
        event_type: str,
        time_since_last: Optional[float] = None,
    ) -> SignalType:
        signal = self.classify_implicit_signal(query, None, event_type, time_since_last)

        await context_store.log_interaction_event(
            user_id=user_id,
            workspace_id=workspace_id,
            query_text=query,
            event_type=event_type,
            response_text=response,
            metadata={"signal_type": signal.value},
        )

        return signal

    async def detect_reusable_correction(
        self,
        user_id: str,
        workspace_id: str,
        correction_text: str,
        original_response: str,
    ) -> Optional[Dict[str, Any]]:
        extracted = self.extract_correction_term(correction_text, original_response)

        if not extracted:
            return None

        original_term, corrected_term, interpretation = extracted

        term_patterns = [r"revenue", r"mrr", r"arr", r"sales", r"bookings"]
        is_metric = any(re.search(p, original_term) for p in term_patterns)

        return {
            "original_term": original_term,
            "corrected_term": corrected_term,
            "interpretation": interpretation,
            "is_metric_term": str(is_metric),
            "scope": "workspace" if is_metric else "conversation",
        }

    async def get_friction_patterns(
        self,
        workspace_id: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        events = await context_store.get_recent_events(workspace_id, "", limit=500)

        friction_queries = {}

        for event in events:
            if event.event_type == EventType.REGENERATE:
                metadata = event.metadata or {}
                time_since = metadata.get("time_since_last_query", 999)
                if time_since < FRICTION_THRESHOLD_SECONDS:
                    q = event.query_text
                    friction_queries[q] = friction_queries.get(q, 0) + 1

        return [
            {"query": q, "count": count}
            for q, count in sorted(
                friction_queries.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]


signal_classifier = SignalClassifier()
