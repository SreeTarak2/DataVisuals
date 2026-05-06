from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MetricMapping(BaseModel):
    id: Optional[str] = None
    term: str
    definition: str
    source_column: Optional[str] = None
    formula: Optional[str] = None
    workspace_id: str
    user_id: str
    is_default: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserMemory(BaseModel):
    id: Optional[str] = None
    workspace_id: str
    user_id: str
    frequent_terms: Dict[str, int] = {}
    preferred_metrics: List[str] = []
    query_count: int = 0
    correction_count: int = 0
    last_query_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InteractionEvent(BaseModel):
    id: Optional[str] = None
    user_id: str
    workspace_id: str
    query_text: str
    response_text: Optional[str] = None
    event_type: str
    metadata: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)
