"""
guards — Prompt Guardrails & Off-Topic Detection
====================================================

Extracted from services/chat/guards.py.
First line of defense BEFORE any LLM call.
Uses vocabulary-based matching — zero LLM cost.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# GUARD RESULT MODEL
# =============================================================================

from pydantic import BaseModel


class GuardResult(BaseModel):
    """Result of a guard check. If should_redirect=True, the query is off-topic."""

    should_redirect: bool = False
    redirect_message: str = ""
    reason: str = ""


# =============================================================================
# OFF-TOPIC DETECTION
# =============================================================================

_OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(hello|hi|hey|howdy)\b"),
    re.compile(r"\bgood\s+(morning|evening|afternoon|night)\b"),
    re.compile(r"\bhow\s+are\s+you\b"),
    re.compile(r"\bthank\s*(you|s)\b"),
    re.compile(r"\b(bye|goodbye|see\s+you)\b"),
    re.compile(r"\bwho\s+is\b"),
    re.compile(r"\bwhat\s+is\s+the\s+capital\b"),
    re.compile(r"\b(prime\s+minister|president)\b"),
    re.compile(r"\b(weather|joke|news)\b"),
    re.compile(r"\btell\s+me\s+a\b"),
    re.compile(r"\bwhat\s+time\b"),
    re.compile(r"\bstock\s+(price|market)\b"),
    re.compile(r"\bwho\s+are\s+you\b"),
    re.compile(r"\bwhat\s+can\s+you\s+do\b"),
]

_CONVERSATIONAL_VOCAB: frozenset = frozenset({
    "hello", "hi there", "hey there", "how are you",
    "what's up", "good morning", "good evening", "good night",
    "tell me a joke", "who are you", "what is your name",
    "who made you", "what can you do",
})

_METADATA_VOCAB: frozenset = frozenset({
    "column", "columns", "field", "fields", "schema", "structure",
    "data type", "data types", "dtype", "dtypes", "describe",
    "what data", "what information", "what variables", "attributes",
    "header", "headers", "available data", "what columns",
    "column name", "column names", "what fields", "list of columns",
    "list columns", "what can i ask", "what can you tell",
})


def _is_off_topic(query_lower: str) -> bool:
    """Check if query is off-topic using word-boundary regex matching."""
    if len(query_lower.strip()) < 5:
        return True
    return any(p.search(query_lower) for p in _OFF_TOPIC_PATTERNS)


def _is_metadata_question(query: str) -> bool:
    """Vocabulary-based metadata detection — runs in microseconds, no LLM."""
    q = query.lower()
    return any(term in q for term in _METADATA_VOCAB)


# =============================================================================
# PUBLIC API
# =============================================================================


def check_off_topic(query: str) -> GuardResult:
    """
    Check if query is greetings, chit-chat, or completely unrelated.

    Called at the edge before any LLM or service call.
    Returns GuardResult with redirect message if off-topic.
    """
    query_lower = query.strip().lower()

    # Check full-phrase conversational vocabulary first
    for phrase in _CONVERSATIONAL_VOCAB:
        if phrase in query_lower:
            return GuardResult(
                should_redirect=True,
                redirect_message=(
                    "I'm a specialized data analytics assistant. I can help with trends, "
                    "charts, forecasts, correlations, or insights from your dataset.\n\n"
                    'Try asking: "Show top products by revenue" or '
                    '"What is the sales trend over time?"'
                ),
                reason=f"Conversational phrase detected: '{phrase}'",
            )

    # Check regex patterns for off-topic queries
    if _is_off_topic(query_lower):
        return GuardResult(
            should_redirect=True,
            redirect_message=(
                "I'm a specialized data analytics assistant. I can help with trends, "
                "charts, forecasts, correlations, or insights from your dataset.\n\n"
                'Try asking: "Show top products by revenue" or '
                '"What is the sales trend over time?"'
            ),
            reason="Off-topic pattern detected",
        )

    return GuardResult(should_redirect=False)


def check_scope(query: str, dataset_id: str, column_names: Optional[list] = None) -> GuardResult:
    """
    Verify query is within scope of the dataset.

    If the query doesn't reference any known columns or data terms,
    redirect the user. This catches queries like "who is the PM"
    that slip past the off-topic guard.
    """
    query_lower = query.lower().strip()

    data_terms = {
        "show", "compare", "analyze", "trend", "chart", "graph",
        "revenue", "sales", "profit", "growth", "decline",
        "top", "bottom", "average", "total", "sum", "count",
        "highest", "lowest", "most", "least", "best", "worst",
        "metric", "metrics", "kpi", "kpis", "insight", "insights",
        "breakdown", "distribution", "over time", "by month",
        "by region", "by category", "filter", "segment",
        "forecast", "predict", "pattern", "anomaly",
    }

    if any(term in query_lower for term in data_terms):
        return GuardResult(should_redirect=False)

    if column_names:
        for col in column_names:
            col_lower = col.lower().replace("_", " ")
            if col_lower in query_lower:
                return GuardResult(should_redirect=False)

    if len(query_lower.split()) <= 6:
        return GuardResult(
            should_redirect=True,
            redirect_message=(
                "I can only answer questions about your data. "
                "Try asking about specific metrics, trends, or patterns "
                "in your dataset."
            ),
            reason="Query out of scope — no data-related terms found",
        )

    return GuardResult(should_redirect=False)


__all__ = [
    "check_off_topic",
    "check_scope",
    "GuardResult",
]
