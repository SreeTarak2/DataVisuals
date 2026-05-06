from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class SemanticRole(str, Enum):
    entity_id = "entity_id"
    measure = "measure"
    dimension = "dimension"
    time = "time"
    internal_key = "internal_key"
    unknown = "unknown"


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic: SemanticRole
    null_rate: float
    cardinality: int
    cardinality_ratio: float
    sample_values: list[str]


class StructureFlags(BaseModel):
    has_entity_id: bool
    has_time: bool
    has_measure: bool
    has_dimension: bool
    has_margin_col: bool
    has_stage_col: bool
    entity_cols: list[str]
    time_cols: list[str]
    measure_cols: list[str]
    dimension_cols: list[str]


class DatasetProfile(BaseModel):
    source_type: Literal["file", "db_table", "db_join"] = "file"
    row_count: int
    columns: list[ColumnProfile]
    structures: StructureFlags
    grain: Literal["transaction", "daily_agg", "customer_period", "unknown"]
    date_range_days: Optional[int] = None
    domain_signal: str = "general"
    domain_confidence: float = 0.0
    schema_hash: str


class PrimitiveType(str, Enum):
    entity_concentration = "entity_concentration"
    period_delta = "period_delta"
    segment_mix = "segment_mix"
    trend_stability = "trend_stability"
    cohort_behavior = "cohort_behavior"
    coverage_quality = "coverage_quality"
    anomaly_detection = "anomaly_detection"


class TimeGrain(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class ComparisonType(str, Enum):
    prior_period = "prior_period"
    prior_year = "prior_year"
    none = "none"


class PrimitiveSpec(BaseModel):
    primitive: PrimitiveType
    kpi_id: str
    entity_col: Optional[str] = None
    measure_col: str
    dimension_col: Optional[str] = None
    time_col: Optional[str] = None
    grain: Optional[TimeGrain] = None
    comparison: ComparisonType = ComparisonType.none
    filters: list[str] = []
    top_n: int = 10


class CriticStatus(str, Enum):
    pass_ = "pass"
    warning = "warning"
    fail = "fail"


class CriticCheck(BaseModel):
    name: str
    status: CriticStatus
    detail: Optional[str] = None


class ComputeResult(BaseModel):
    kpi_id: str
    primitive: PrimitiveType
    current_value: Optional[float] = None
    comparison_value: Optional[float] = None
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    cov: Optional[float] = None
    coverage_pct: float = 0.0
    row_count: int = 0
    segment_breakdown: Optional[dict] = None
    compute_error: Optional[str] = None
    critic_checks: list[CriticCheck] = []


class CardConfidence(str, Enum):
    high = "high"
    moderate = "moderate"
    low = "low"


class Card(BaseModel):
    kpi_id: str
    primitive: PrimitiveType
    title: str
    headline: str
    metric_value: Optional[float] = None
    comparison_value: Optional[float] = None
    delta_narrative: Optional[str] = None
    key_insight: Optional[str] = None
    confidence: CardConfidence = CardConfidence.moderate
    segment_breakdown: Optional[dict] = None
    category: Literal["performance", "diagnostic", "risk", "opportunity"] = "diagnostic"
    caveats: list[str] = []
    template_id: str = ""
