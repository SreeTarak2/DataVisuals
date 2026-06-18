"""
intelligence/models.py — Semantic + intelligence data models (Layer 2+3)

These models are layered on top of profiling/models.py (RawProfilingResult).
They add interpretation, classification, and cross-column reasoning.

Naming convention:
  - Unified* models are the final output consumed by process.py and the frontend.
  - Raw* models are intermediate outputs from individual engines.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class SemanticRole(str, Enum):
    """High-level column role — the first layer of interpretation."""

    MEASURE = "measure"        # Numeric, summable — revenue, cost, salary
    RATE = "rate"              # Numeric ratio/pct — conversion_rate, margin
    COUNT = "count"            # Integer counts — order_count, num_users
    DIMENSION = "dimension"    # Categorical — region, product, status
    TIME = "time"              # Datetime — date, created_at
    IDENTITY = "identity"      # IDs, skip — customer_id, uuid


class BehavioralRole(str, Enum):
    """Fine-grained behavioral role — second layer of interpretation."""

    # Measures
    ADDITIVE_MEASURE = "additive_measure"           # Summable across all dims
    SEMI_ADDITIVE_MEASURE = "semi_additive_measure" # Summable, but not across time
    NON_ADDITIVE_MEASURE = "non_additive_measure"   # Never sum, use avg
    RATE_MEASURE = "rate_measure"                   # Ratio or percentage
    COUNT_MEASURE = "count_measure"                 # Integer count

    # Dimensions
    CATEGORY = "category"                           # Low-card categorical
    STATUS = "status"                               # Boolean-like status
    BOOLEAN_FLAG = "boolean_flag"                   # True/false indicator
    HIERARCHY = "hierarchy"                         # Multi-level (country > state > city)

    # Temporal
    DATE = "date"                                   # Point-in-time date
    TIMESTAMP = "timestamp"                         # Precise timestamp
    DURATION = "duration"                           # Time span

    # Geo
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    COUNTRY = "country"
    STATE = "state"
    CITY = "city"
    POSTAL_CODE = "postal_code"

    # Special
    IDENTIFIER = "identifier"                       # Primary key
    ENTITY_REFERENCE = "entity_reference"           # Foreign key
    INTERNAL_KEY = "internal_key"                   # Row_id, index, seq
    FREE_TEXT = "free_text"                         # Long descriptive text
    PII = "pii"                                     # Personally identifiable

    UNKNOWN = "unknown"


class BusinessCategory(str, Enum):
    """Business domain category for a column."""

    REVENUE = "revenue"
    COST = "cost"
    VOLUME = "volume"
    USERS = "users"
    RATE_METRIC = "rate_metric"
    CHURN_RISK = "churn_risk"
    PRICE = "price"
    PERFORMANCE = "performance"
    DURATION = "duration"
    QUANTITY = "quantity"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AdditiveType(str, Enum):
    """Additive / semi-additive / non-additive classification."""

    ADDITIVE = "additive"               # Sum across any dimension
    SEMI_ADDITIVE = "semi_additive"     # Sum across most, not time
    NON_ADDITIVE = "non_additive"       # Never sum (avg only)


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregation Suitability
# ═══════════════════════════════════════════════════════════════════════════════


class AggregationSuitability(BaseModel):
    """Which aggregations are semantically valid for this column."""

    sum_allowed: bool = False
    avg_allowed: bool = False
    min_allowed: bool = True
    max_allowed: bool = True
    count_allowed: bool = True
    count_distinct_allowed: bool = True
    median_allowed: bool = True

    additive_type: AdditiveType = AdditiveType.ADDITIVE
    recommended_aggregation: str = "count"
    aggregation_rationale: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Entity Info
# ═══════════════════════════════════════════════════════════════════════════════


class EntityInfo(BaseModel):
    """Information about a detected entity column."""

    entity_column: str                           # e.g. "customer_id"
    entity_type: str                             # e.g. "Customer", "Product", "Patient"
    unique_count: int = 0
    total_count: int = 0
    avg_records_per_entity: float = 0.0
    confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Geo Info
# ═══════════════════════════════════════════════════════════════════════════════


class GeoInfo(BaseModel):
    """Geographic columns detected in the dataset."""

    latitude: Optional[str] = None      # Column name
    longitude: Optional[str] = None     # Column name
    country: Optional[str] = None       # Column name
    state: Optional[str] = None         # Column name
    city: Optional[str] = None          # Column name
    postal_code: Optional[str] = None   # Column name
    address: Optional[str] = None       # Column name
    has_geo: bool = False

    @property
    def lat_lng_pair(self) -> bool:
        """True if both latitude AND longitude are detected."""
        return self.latitude is not None and self.longitude is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Hierarchy Info
# ═══════════════════════════════════════════════════════════════════════════════


class HierarchyInfo(BaseModel):
    """A multi-level hierarchy detected within a single table."""

    columns: list[str]         # e.g. ["country", "state", "city"]
    hierarchy_type: str        # "geo", "category", "date", "org"
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Relationship Info
# ═══════════════════════════════════════════════════════════════════════════════


class RelationshipInfo(BaseModel):
    """A detected relationship between two columns."""

    source_column: str
    target_column: str
    relationship_type: str       # "foreign_key", "derived", "hierarchy"
    confidence: float = 0.0
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Hypothesis
# ═══════════════════════════════════════════════════════════════════════════════


class DomainCandidate(BaseModel):
    """A single domain hypothesis with score."""

    domain_id: str            # e.g. "ecommerce-metrics"
    domain_name: str          # e.g. "E-Commerce"
    score: float              # 0-100
    matched_columns: list[str] = Field(default_factory=list)
    matched_required: int = 0
    matched_optional: int = 0
    total_required: int = 0


class LLMDomainVerdict(BaseModel):
    """LLM's domain classification verdict — enriches deterministic result.

    Produced by the LLM domain detector which reasons from actual data
    values (value ranges, sample values, categorical distributions), not
    just column names.
    """

    domain: str = ""                              # Short description, e.g. "vehicle listings"
    domain_id: str = "unknown"                     # Template ID or "unknown"
    confidence: float = 0.0                        # 0.0-1.0
    reasoning: str = ""                            # 1-2 sentence explanation
    column_mapping: dict[str, str] = Field(default_factory=dict)  # template_type -> column_name


class DomainHypothesisResult(BaseModel):
    """Result of domain matching, optionally enriched by LLM.

    The deterministic path produces candidates with scores.
    The LLM path enriches with a verdict on top.
    """

    candidates: list[DomainCandidate] = Field(default_factory=list)
    top_candidate: Optional[DomainCandidate] = None
    method: str = "pattern_match"   # "pattern_match" | "llm" | "unavailable"
    llm_verdict: Optional[LLMDomainVerdict] = None  # LLM enrichment, if available

    def is_domain_detected(self) -> bool:
        """True if a domain was detected with reasonable confidence."""
        return self.top_candidate is not None and self.top_candidate.score >= 30


# ═══════════════════════════════════════════════════════════════════════════════
# Temporal Info
# ═══════════════════════════════════════════════════════════════════════════════


class TemporalInfo(BaseModel):
    """Temporal structure detected in the dataset."""

    date_column: Optional[str] = None           # Primary date column
    date_range_days: Optional[int] = None       # Span in days
    grain: str = "unknown"                       # transaction / daily_agg / customer_period
    has_date_hierarchy: bool = False
    available_date_parts: list[str] = Field(default_factory=list)  # year, quarter, month, day
    has_gaps: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# Per-Column Intelligence Result
# ═══════════════════════════════════════════════════════════════════════════════


class ColumnIntelligence(BaseModel):
    """Everything the intelligence layer knows about a single column.

    This is built on top of RawColumnProfile (from profiling/).
    """

    name: str

    # Layer 2: Semantic interpretation
    semantic_role: SemanticRole = SemanticRole.DIMENSION
    behavioral_role: BehavioralRole = BehavioralRole.UNKNOWN
    business_category: BusinessCategory = BusinessCategory.UNKNOWN
    polarity: str = "higher_is_better"           # higher_is_better | lower_is_better

    # Layer 2: Aggregation rules
    aggregation_suitability: AggregationSuitability = Field(
        default_factory=AggregationSuitability
    )

    # Layer 2: Entity / Geo
    entity_info: Optional[EntityInfo] = None
    geo_role: Optional[str] = None               # "latitude", "country", etc.

    # Confidence
    classification_confidence: float = 0.0
    needs_review: bool = False                    # True if confidence < 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# Unified Intelligence Result
# ═══════════════════════════════════════════════════════════════════════════════


class UnifiedIntelligenceResult(BaseModel):
    """The complete output of the intelligence layer.

    This is what gets merged with RawProfilingResult to form the
    final UnifiedDatasetProfile for the frontend and downstream consumers.
    """

    columns: list[ColumnIntelligence] = Field(default_factory=list)
    entities: list[EntityInfo] = Field(default_factory=list)
    hierarchies: list[HierarchyInfo] = Field(default_factory=list)
    geo: GeoInfo = Field(default_factory=GeoInfo)
    temporal: TemporalInfo = Field(default_factory=TemporalInfo)
    relationships: list[RelationshipInfo] = Field(default_factory=list)
    domain: DomainHypothesisResult = Field(default_factory=DomainHypothesisResult)

    def columns_needing_review(self) -> list[str]:
        """Columns with low-confidence classifications."""
        return [
            c.name for c in self.columns
            if c.needs_review
        ]
