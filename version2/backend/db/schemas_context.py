from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum


class SignalType(str, Enum):
    FRICTION = "friction"
    DELIGHT = "delight"
    NEUTRAL = "neutral"
    CONFUSION = "confusion"
    CORRECTION = "correction"


class CorrectionScope(str, Enum):
    MESSAGE = "message"
    CONVERSATION = "conversation"
    DATASET = "dataset"
    WORKSPACE = "workspace"


class MetricSemantic(BaseModel):
    """Semantic definition of a metric captured from user corrections."""

    metric_name: str
    definition: str
    formula: Optional[str] = None
    source_columns: List[str] = []
    aggregation: Optional[str] = None
    business_context: Optional[str] = None


class ValidationRule(BaseModel):
    """Pre-execution validation rule for a metric."""

    rule_type: str
    expression: str
    threshold: Optional[float] = None
    fail_message: str


class SemanticCorrection(BaseModel):
    """Fields added to CorrectionRule for semantic corrections."""

    metric_semantic: Optional[MetricSemantic] = None
    validation_rules: List[ValidationRule] = []
    applies_to_queries: List[str] = []
    is_explicit_semantic: bool = False


class CorrectionRule(BaseModel):
    id: Optional[str] = None
    original_term: str
    corrected_term: str
    interpretation: str
    scope: CorrectionScope
    workspace_id: str
    user_id: str
    confidence: float = 1.0
    usage_count: int = 0
    metric_semantic: Optional[MetricSemantic] = None
    validation_rules: List[ValidationRule] = []
    applies_to_queries: List[str] = []
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class MetricMapping(BaseModel):
    id: Optional[str] = None
    term: str
    definition: str
    source_column: Optional[str] = None
    formula: Optional[str] = None
    workspace_id: str
    user_id: str
    is_default: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class UserQuery(BaseModel):
    id: Optional[str] = None
    text: str
    workspace_id: str
    user_id: str
    dataset_id: Optional[str] = None
    interpreted_terms: Dict[str, str] = {}
    response_text: Optional[str] = None
    was_satisfactory: Optional[bool] = None
    signal_type: Optional[SignalType] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class UserMemory(BaseModel):
    id: Optional[str] = None
    workspace_id: str
    user_id: str
    frequent_terms: Dict[str, int] = {}
    preferred_metrics: List[str] = []
    query_count: int = 0
    correction_count: int = 0
    last_query_at: Optional[datetime] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class InteractionEvent(BaseModel):
    id: Optional[str] = None
    user_id: str
    workspace_id: str
    query_text: str
    response_text: Optional[str] = None
    event_type: str
    metadata: Dict[str, Any] = {}
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
