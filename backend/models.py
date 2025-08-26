from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum


class PersonaType(str, Enum):
    NORMAL = "normal"
    EXPERT = "expert"


class DatasetUpload(BaseModel):
    filename: str
    size: int
    content_type: str


class DatasetInfo(BaseModel):
    id: str
    filename: str
    size: int
    row_count: int
    column_count: int
    upload_date: datetime
    columns: List[Dict[str, Any]]
    summary_stats: Dict[str, Any]


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_count: int
    unique_count: int
    sample_values: List[Any]
    is_numeric: bool
    is_temporal: bool
    is_categorical: bool


class VisualizationRecommendation(BaseModel):
    chart_type: str
    title: str
    description: str
    fields: List[str]
    reasoning: str
    persona_insights: Dict[PersonaType, str]


class LLMRequest(BaseModel):
    dataset_id: str
    query: str
    persona: PersonaType = PersonaType.NORMAL
    context: Optional[str] = None


class LLMResponse(BaseModel):
    response: str
    confidence: float
    reasoning: str
    suggested_actions: List[str]
    persona_adapted: bool


class DashboardTemplate(BaseModel):
    id: str
    name: str
    description: str
    template_type: str
    layout: List[Dict[str, Any]]
    recommended_datasets: List[str]
    persona_adaptations: Dict[PersonaType, Dict[str, Any]]


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    database: str
    llm_service: str
    version: str = "1.0.0"


