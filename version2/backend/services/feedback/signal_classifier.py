from typing import Optional, List, Dict, Any, Tuple
import re
import logging
from datetime import datetime, timedelta, timezone

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

    # Function words that signal a regex over-consumed the corrected term
    # ("is recognized", "the revenue", "should be"). These can never start a
    # real metric definition, unlike legitimate modifiers like "total revenue".
    _LEADING_FUNCTION_WORDS = frozenset(
        {
            "the", "a", "an", "this", "that", "these", "those", "it", "its",
            "is", "are", "was", "were", "be", "been", "being", "am",
            "my", "your", "our", "their", "you", "i", "we", "they", "he", "she",
            "should", "would", "could", "will", "can", "shall", "may", "might",
            "want", "need", "show", "please", "no", "not", "and", "or", "but",
            "with", "for", "of", "in", "on", "at", "to", "from", "as", "by",
            "what", "why", "how", "when", "where", "who", "which", "there", "here",
        }
    )

    # Words that are never valid subject terms for a stored correction rule.
    _TERM_STOPWORDS = frozenset(
        {
            "the", "this", "that", "it", "its", "is", "are", "was", "were", "be", "been",
            "my", "your", "our", "their", "you", "i", "we", "they", "he", "she",
            "show", "please", "can", "could", "would", "should", "will", "want", "need",
            "a", "an", "and", "or", "but", "not", "no", "with", "for", "of", "in",
            "on", "at", "to", "from", "what", "why", "how", "when", "where", "who",
            "which", "these", "those", "there", "here", "data", "row", "rows",
            "column", "columns", "value", "values", "table", "metric", "metrics",
            "answer", "question", "number", "total", "average", "mean", "sum", "count",
        }
    )

    @staticmethod
    def _is_valid_term(term: str) -> bool:
        """
        Guard against garbage extractions ("the", "metric", "x", "no").

        A valid term is 3-60 chars, alphabetic words (2+ letters each), and
        not a pure function/stopword for single-word subjects.
        """
        if not term or len(term) < 3 or len(term) > 60:
            return False
        # Allow formulas: "total revenue - cogs" (hyphens/slashes don't break
        # word-boundary matching or re.sub replacements).
        if not re.fullmatch(r"[a-z][a-z0-9 \-/]*", term):
            return False
        words = term.split()
        # Only letter-bearing tokens must be ≥2 chars (formula operators like
        # "-" in "total revenue - cogs" are allowed as standalone tokens).
        if any(len(w) < 2 for w in words if re.search(r"[a-z]", w)):
            return False
        if len(words) == 1 and words[0] in SignalClassifier._TERM_STOPWORDS:
            return False
        return True

    def extract_correction_term(
        self,
        correction_text: str,
        response_text: str,
    ) -> Optional[Tuple[str, str, str]]:
        """
        Extract ``(original_term, corrected_term, interpretation)`` from a
        user correction message.

        Supported patterns (case-insensitive):
          - "no, revenue is recognized revenue"    → revenue → recognized revenue
          - "revenue means recognized revenue"      → revenue → recognized revenue
          - "revenue refers to recognized revenue"  → revenue → recognized revenue
          - "revenue = recognized revenue"          → revenue → recognized revenue
          - "revenue should be recognized revenue"  → revenue → recognized revenue
          - "the metric is MRR, not ARR"            → metric → mrr (scope: metric)

        Returns ``None`` when no confident term pair can be extracted — the
        caller must NOT persist a rule in that case.
        """
        text = (correction_text or "").strip().lower()
        if not text:
            return None

        # NOTE: alternation must list the longest literal first ("refers to",
        # "is defined as") before "is" so regex doesn't truncate the corrected
        # term at the first "is".
        patterns = [
            # "no, revenue is recognized revenue" / "actually revenue refers to X"
            r"^(?:no|wrong|actually|correction|wait|hold on|not this|that's wrong)[,.:!]?\s*"
            r"(?:the\s+)?([a-z][a-z0-9_ ]{1,40}?)\s+"
            r"(?:refers to|is defined as|means?|represents?|should be|is|=)\s+(.+)$",
            # plain "revenue means recognized revenue" / "churn should be X"
            r"^([a-z][a-z0-9_ ]{1,40}?)\s+"
            r"(?:refers to|is defined as|means?|represents?|should be|is|=)\s+(.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            groups = match.groups()
            if len(groups) < 2:
                continue

            original_term = re.sub(r"^(?:the|a|an)\s+", "", groups[0].strip()).rstrip(".,!?;:")
            corrected_term = re.sub(r"\s+", " ", groups[1].strip()).rstrip(".,!?;:")

            # "mrr, not arr" → "mrr" (the rejected alternative is noise)
            alt = re.match(r"^(.+?)\s*,\s*not\s+.+$", corrected_term)
            if alt:
                corrected_term = alt.group(1).strip()

            if not self._is_valid_term(original_term) or not self._is_valid_term(corrected_term):
                continue

            # A corrected term starting with a function word ("is recognized",
            # "the revenue") means the regex over-consumed — reject the parse.
            first_word = corrected_term.split()[0]
            if first_word in SignalClassifier._LEADING_FUNCTION_WORDS:
                continue

            return (original_term, corrected_term, f"{original_term} = {corrected_term}")

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

        # Terms that are unambiguously business metrics → workspace-scoped rule
        # (applied to every future query in the workspace). Anything else is
        # scoped to the conversation only, so one-off phrasing can't poison
        # other sessions.
        term_patterns = [
            r"revenue", r"mrr", r"arr", r"nrr", r"gmv", r"aov", r"sales",
            r"bookings", r"booked", r"recognized", r"churn", r"retention",
            r"profit", r"margin", r"gross", r"net", r"growth", r"spend",
            r"cost", r"cogs", r"users", r"customers", r"subscribers",
            r"conversion", r"cac", r"ltv", r"refund", r"refunds",
        ]
        is_metric = any(re.search(p, original_term) for p in term_patterns)

        return {
            "original_term": original_term,
            "corrected_term": corrected_term,
            "interpretation": interpretation,
            "is_metric_term": is_metric,
            "scope": "workspace" if is_metric else "conversation",
        }

    async def get_friction_patterns(
        self,
        workspace_id: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        from datetime import datetime, timedelta

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

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
