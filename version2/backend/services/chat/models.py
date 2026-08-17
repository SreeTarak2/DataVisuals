"""
Chat Pipeline — Shared Data Models
====================================

Data classes that flow through the pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class QueryContext:
    """Rich understanding of the user's query after initial processing."""

    original_query: str
    enriched_query: str
    what_i_understood: str
    archetype: str = "analyst"  # explorer | analyst | expert
    routing: str = "sql"  # sql | metadata | conversational
    failure_mode: Optional[str] = None  # underspecified | misspecified | vocabulary_gap | none
    needs_clarification: bool = False
    decision_at_stake: str = ""
    was_enriched: bool = False
    comparison_period: Optional[str] = None
    comparison_resolution: Optional[Dict[str, Any]] = None


@dataclass
class ContextPackage:
    """Everything gathered about the dataset for the agent."""

    dataset_metadata: Dict[str, Any] = field(default_factory=dict)
    dataset_context_str: str = ""
    rag_context: str = ""
    memory_context: MemoryContext = field(default_factory=lambda: MemoryContext())
    privacy_info: Dict[str, Any] = field(default_factory=dict)
    columns: List[str] = field(default_factory=list)
    cleaning_manifest: List[Dict[str, Any]] = field(default_factory=list)
    conversation_messages: List[Dict[str, Any]] = field(default_factory=list)
    conversation_id: Optional[str] = None


@dataclass
class MemoryContext:
    """Unified memory retrieval result."""

    memories: List[Dict[str, Any]] = field(default_factory=list)
    belief_context: str = ""
    instructions_override: Optional[str] = None


@dataclass
class ChatResult:
    """Final result from the chat pipeline (non-streaming path)."""

    response_text: str
    conversation_id: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    additional_charts: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_suggestions: List[str] = field(default_factory=list)
    query_context: Optional[QueryContext] = None
    quality_issues: List[str] = field(default_factory=list)
    corrections_applied: List[Dict[str, Any]] = field(default_factory=list)
    analysis_type: str = "standard"  # standard | deep_quis
    sql: Optional[str] = None
    result_table: Optional[Dict[str, Any]] = None
    confidence: str = "ai_analysis"
    reasoning_trace: Optional[List[Dict[str, Any]]] = None
    # Cleaning guard (Principle #0): set when the chat refused to analyze
    # data with un-approved, number-changing cleaning actions pending.
    redirect_to: Optional[str] = None  # e.g. "briefing"
    cleaning_pending_critical: int = 0


@dataclass
class GuardResult:
    """Result from the guard check."""

    should_redirect: bool
    redirect_message: str = ""
    reason: str = ""


class QueryComplexityAnalyzer:
    """
    Analyze query complexity to determine appropriate response format.
    Returns 'simple', 'moderate', or 'complex' to guide LLM formatting.
    """

    SIMPLE_PATTERNS = [
        r"^what is the (total|sum|average|mean|max|min|count)",
        r"^what's the (total|sum|average|mean|max|min|count)",
        r"^how many",
        r"^how much",
        r"^show me the (top|bottom) \d+",
        r"^what (is|was) the .+ (in|for|of|on)",
        r"^give me the",
        r"^tell me the",
    ]

    COMPLEX_PATTERNS = [
        r"(compare|versus|vs\.?|difference between)",
        r"(why|explain|analyze|breakdown|break down)",
        r"(trend|trends|forecast|predict|projection|over time)",
        r"(correlation|relationship|impact|affect|influence)",
        r"(top|bottom) \d+ .* (by|with|and|across)",
        r"(performance|analysis|overview|summary|report)",
        r"(all|every|each) .* (by|across|per)",
        r"(segment|segmentation|breakdown by)",
    ]

    @classmethod
    def classify(cls, query: str) -> str:
        if not query:
            return "simple"
        query_lower = query.lower().strip()

        for pattern in cls.SIMPLE_PATTERNS:
            if re.match(pattern, query_lower):
                complex_score = sum(
                    1 for p in cls.COMPLEX_PATTERNS if re.search(p, query_lower)
                )
                if complex_score == 0:
                    return "simple"

        complex_score = sum(
            1 for pattern in cls.COMPLEX_PATTERNS if re.search(pattern, query_lower)
        )

        if complex_score >= 2:
            return "complex"
        elif complex_score == 1:
            return "moderate"

        word_count = len(query_lower.split())
        question_count = query_lower.count("?")

        if question_count >= 2:
            return "complex"
        if word_count <= 8:
            return "simple"
        elif word_count <= 20:
            return "moderate"
        else:
            return "complex"
