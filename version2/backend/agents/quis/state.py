from typing import TypedDict, List, Optional, Dict, Any, Annotated
from dataclasses import dataclass, field
import operator
from datetime import datetime, timezone

def add_messages(left: List[Dict], right: List[Dict]) -> List[Dict]:
    """Reducer for message history - appends new messages."""
    return left + right

def replace_value(left: Any, right: Any) -> Any:
    """Reducer that replaces old value with new value."""
    return right

class QuestionState(TypedDict):
    question: str
    question_type: str
    target_columns: List[str]
    filter_column: Optional[str]
    priority: float

class InsightState(TypedDict):
    insight_type: str
    description: str
    columns: List[str]
    subspace: Optional[Dict[str, Any]]
    statistic: float
    p_value: float
    effect_size: float
    effect_interpretation: str
    sample_size: int
    is_simpson_paradox: bool
    novelty_score: float
    overall_score: float

class CritiqueState(TypedDict):
    score: float
    passed: bool
    feedback: str
    issues: List[str]
    suggestions: List[str]

class AgentState(TypedDict):
    messages: Annotated[List[Dict[str, Any]], add_messages]
    dataset_id: str
    data_schema: str
    sample_rows: str
    row_count: int
    column_count: int
    user_id: str
    tenant_id: str  # Multi-tenant isolation key
    questions: List[QuestionState]
    current_question_idx: int
    current_insights: List[InsightState]  # ALL insights from current question (FIX: was only insights[0])
    plan: List[str]
    current_code: str
    execution_result: str
    error_count: int
    max_retries: int
    last_error: Optional[str]
    critique: Optional[CritiqueState]
    active_beliefs: List[str]  # User's ACTUAL business rules (immutable input) — NEVER overwritten
    seen_insights: List[str]  # Documents similar to current insight (output context only)
    belief_context: List[str]  # DEPRECATED: Kept for backward compat, use active_beliefs
    semantic_surprisal: float
    bayesian_surprise: float
    hybrid_novelty_score: float
    novelty_threshold: float
    is_novel: bool
    alpha: float  # Adaptive weight for hybrid score (Paper Eq. 8)
    approved_insights: List[InsightState]
    rejected_insights: List[InsightState]  # Now actually populated (FIX §5.5)
    boring_insights: List[InsightState]
    raw_insight_pvalues: List[Dict[str, Any]]  # Every hypothesis tested (run_id, family, p_value) for FDR
    fdr_surviving_ids: List[str]  # run_ids that survive within-family Benjamini-Hochberg
    fdr_dropped_count: int
    final_response: Optional[str]
    viz_configs: List[Dict[str, Any]]  # Plotly chart configurations
    iteration_count: int
    max_iterations: int
    start_time: Optional[str]
    end_time: Optional[str]

def create_initial_state(
    dataset_id: str,
    user_id: str,
    data_schema: str,
    sample_rows: str,
    row_count: int,
    column_count: int,
    novelty_threshold: float = 0.35,
    max_retries: int = 3,
    max_iterations: int = 50,
    tenant_id: Optional[str] = None,
) -> AgentState:
    """
    Create and return a properly initialized AgentState for the QUIS agent workflow.

    This factory function sets up the shared state object used across all LangGraph nodes,
    including conversation history, dataset context, planning questions, execution tracking,
    critique results, novelty filtering, accumulated insights, and execution metadata.

    FIX: Added fields for multi-tenant isolation, active_beliefs (separate from seen_insights),
    current_insights (all insights, not just the first one), and populated rejected_insights.

    Args:
        dataset_id: Unique identifier for the dataset being analyzed
        user_id: User ID for retrieving user-specific belief context
        data_schema: JSON string describing column names and types
        sample_rows: Text representation of the first few rows for LLM context
        row_count: Total number of rows in the dataset
        column_count: Total number of columns in the dataset
        novelty_threshold: Minimum novelty score required to present an insight (default: 0.35)
        max_retries: Maximum retry attempts per question on execution error (default: 3)
        max_iterations: Safety limit on total graph iterations (default: 50)
        tenant_id: Optional tenant ID for multi-tenant cache scoping

    Returns:
        Fully initialized AgentState dictionary ready for graph execution
    """
    return AgentState(
        messages=[],
        dataset_id=dataset_id,
        data_schema=data_schema,
        sample_rows=sample_rows,
        row_count=row_count,
        column_count=column_count,
        user_id=user_id,
        tenant_id=tenant_id or user_id,  # Default to user_id if not provided
        questions=[],
        current_question_idx=0,
        current_insights=[],
        plan=[],
        current_code="",
        execution_result="",
        error_count=0,
        max_retries=max_retries,
        last_error=None,
        critique=None,
        active_beliefs=[],  # User's business rules — immutable input, NEVER overwritten
        seen_insights=[],  # Similar beliefs from filter — output context only
        belief_context=[],  # DEPRECATED: kept for backward compat
        semantic_surprisal=0.0,
        bayesian_surprise=0.0,
        hybrid_novelty_score=0.0,
        novelty_threshold=novelty_threshold,
        is_novel=True,
        alpha=0.6,  # Default per paper §III.C
        approved_insights=[],
        rejected_insights=[],  # Now actually populated (FIX §5.5)
        boring_insights=[],
        raw_insight_pvalues=[],
        fdr_surviving_ids=[],
        fdr_dropped_count=0,
        final_response=None,
        viz_configs=[],
        iteration_count=0,
        max_iterations=max_iterations,
        start_time=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        end_time=None
    )