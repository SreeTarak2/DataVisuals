"""
Knowledge Graph Models - Pydantic Data Models for Entity Extraction
====================================================================

Defines all data structures used across the entity extraction pipeline.

Architecture:
  Layer 1: ColumnRole (universal structural type — finite enum, never grows)
  Layer 2: SemanticCandidate (business label hint — dynamic, dataset-specific)
  Layer 3: EntityCluster (grouped columns with validated roles)
  Layer 4: DiscoveredEntity (validated business entity)
"""

import logging
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ColumnRole(str, Enum):
    """Universal structural column roles — finite, domain-agnostic, never grows.

    These describe WHAT a column IS structurally, not which business entity
    it belongs to. Every column maps to exactly one role.
    """

    IDENTIFIER = "IDENTIFIER"
    NAME = "NAME"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    AMOUNT = "AMOUNT"
    QUANTITY = "QUANTITY"
    PERCENTAGE = "PERCENTAGE"
    STATUS = "STATUS"
    CATEGORY = "CATEGORY"
    LOCATION = "LOCATION"
    BOOLEAN = "BOOLEAN"
    URL = "URL"
    CODE = "CODE"
    TEXT = "TEXT"
    UNKNOWN = "UNKNOWN"


class EvidenceReliability(str, Enum):
    """Reliability of an evidence source — used to weight signals."""

    HIGH = "high"  # Column name match, data type match
    MEDIUM = "medium"  # Cardinality analysis, value pattern
    LOW = "low"  # Table name hint, abbreviation expansion


class SemanticCandidate(BaseModel):
    """A candidate business label for a column — dynamic, not an enum.

    This is evidence, not truth. The label only becomes an entity if
    the grouping + validation pipeline confirms it.

    Example:
        column "patient_id" → SemanticCandidate(label="patient", confidence=0.72, source="column_prefix")
    """

    label: str = Field(..., description="Candidate business label (e.g. 'patient', 'customer')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this label")
    source: str = Field(
        ...,
        description="Source of this candidate: column_prefix | table_name | abbreviation | value_pattern",
    )


class EvidenceSource(BaseModel):
    """A single piece of evidence with reliability weight."""

    source_type: str = Field(
        ...,
        description="Type of evidence: column_name | data_type | cardinality | value_pattern | table_name | abbreviation",
    )
    value: str = Field(..., description="The evidence value (e.g. matched pattern, detected type)")
    reliability: EvidenceReliability = Field(
        default=EvidenceReliability.MEDIUM, description="Reliability of this evidence source"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence contribution from this evidence"
    )
    detail: str = Field(default="", description="Human-readable explanation")


class EntityType(str, Enum):
    """Original entity types — DEPRECATED. Use ColumnRole + SemanticCandidate + EntityCluster instead.

    Kept for backward compatibility with existing code and correction memory.
    New code should NOT reference this enum directly.
    """

    TRANSACTION = "Transaction"
    CUSTOMER = "Customer"
    PRODUCT = "Product"
    ORDER = "Order"
    INVOICE = "Invoice"
    PERSON = "Person"
    EMPLOYEE = "Employee"
    PATIENT = "Patient"
    ORGANIZATION = "Organization"
    COMPANY = "Company"
    VENDOR = "Vendor"
    SUPPLIER = "Supplier"
    TIMEDIMENSION = "TimeDimension"
    GEOGRAPHY = "Geography"
    FACILITY = "Facility"
    DEPARTMENT = "Department"
    METRIC = "Metric"
    AMOUNT = "Amount"
    QUANTITY = "Quantity"
    CLASSIFICATION = "Classification"
    CATEGORY = "Category"
    STATUS = "Status"
    INDICATOR = "Indicator"
    CODE = "Code"
    GENERIC_ENTITY = "GenericEntity"
    GENERIC_REFERENCE = "GenericReference"
    GENERIC_ATTRIBUTE = "GenericAttribute"


class SignalType(str, Enum):
    """Types of signals used for entity classification"""

    COLUMN_NAME = "column_name"
    DATA_TYPE = "data_type"
    SAMPLE_VALUES = "sample_values"
    CARDINALITY = "cardinality"
    DOMAIN_CONTEXT = "domain_context"
    PATTERN_MATCH = "pattern_match"


class ConfidenceLevel(str, Enum):
    """Confidence level categories"""

    STRONG = "strong"  # 0.90-1.00
    GOOD = "good"  # 0.70-0.89
    TENTATIVE = "tentative"  # 0.50-0.69
    UNCERTAIN = "uncertain"  # <0.50


class ColumnProfile(BaseModel):
    """Profile of a single column from the dataset"""

    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="Inferred data type")
    null_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Ratio of null values")
    distinct_count: int = Field(default=0, ge=0, description="Number of distinct values")
    distinct_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ratio of distinct to total"
    )
    sample_values: List[str] = Field(
        default_factory=list, description="Representative sample values"
    )
    is_unique: bool = Field(default=False, description="Whether values are unique")
    is_primary_key: bool = Field(default=False, description="Likely primary key")
    min_value: Optional[Any] = Field(default=None, description="Minimum value for numeric")
    max_value: Optional[Any] = Field(default=None, description="Maximum value for numeric")
    avg_length: Optional[float] = Field(default=None, description="Average string length")

    @field_validator("data_type")
    @classmethod
    def normalize_data_type(cls, v: str) -> str:
        """Normalize data type to standard categories"""
        v_lower = v.lower().strip()

        # Map to standard types
        type_mappings = {
            "int": "integer",
            "int8": "integer",
            "int16": "integer",
            "int32": "integer",
            "int64": "integer",
            "uint32": "integer",
            "uint64": "integer",
            "bigint": "integer",
            "smallint": "integer",
            "tinyint": "integer",
            "float": "decimal",
            "float32": "decimal",
            "float64": "decimal",
            "double": "decimal",
            "numeric": "decimal",
            "decimal": "decimal",
            "varchar": "string",
            "text": "string",
            "char": "string",
            "nvarchar": "string",
            "utf8": "string",
            "str": "string",
            "date": "date",
            "datetime": "timestamp",
            "datetime64": "timestamp",
            "timestamp": "timestamp",
            "time": "time",
            "bool": "boolean",
            "boolean": "boolean",
            "bool_": "boolean",
            "null": "unknown",
            "uuid": "uuid",
        }
        return type_mappings.get(v_lower, v_lower)


class SchemaProfile(BaseModel):
    """Complete schema profile for a dataset"""

    table_name: str = Field(..., description="Table or file name")
    columns: List[ColumnProfile] = Field(..., description="List of column profiles")
    row_count: int = Field(default=0, ge=0, description="Total number of rows")
    profile_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def numeric_columns(self) -> List[ColumnProfile]:
        return [c for c in self.columns if c.data_type in ("integer", "decimal")]

    @property
    def string_columns(self) -> List[ColumnProfile]:
        return [c for c in self.columns if c.data_type == "string"]

    @property
    def date_columns(self) -> List[ColumnProfile]:
        return [c for c in self.columns if c.data_type in ("date", "timestamp")]


class SignalResult(BaseModel):
    """Result from a single signal extractor"""

    signal_type: SignalType
    matched_pattern: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str = Field(..., description="Human-readable evidence")
    raw_match: Optional[Dict[str, Any]] = None

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.90:
            return ConfidenceLevel.STRONG
        elif self.confidence >= 0.70:
            return ConfidenceLevel.GOOD
        elif self.confidence >= 0.50:
            return ConfidenceLevel.TENTATIVE
        return ConfidenceLevel.UNCERTAIN


class EntityCandidate(BaseModel):
    """A single column classification result.

    Now includes column_role and semantic_candidates alongside the legacy
    entity_type field for backward compatibility.
    """

    column_name: str = Field(..., description="Source column name")
    # NEW: structural role (preferred)
    column_role: ColumnRole = Field(
        default=ColumnRole.UNKNOWN, description="Universal structural column role"
    )
    # NEW: semantic business label candidates
    semantic_candidates: List[SemanticCandidate] = Field(
        default_factory=list, description="Business label candidates"
    )
    # NEW: evidence tracking
    evidence_sources: List[EvidenceSource] = Field(
        default_factory=list, description="All evidence with reliability weights"
    )
    # NEW: raw signals (kept for backward compat)
    signals: List[SignalResult] = Field(default_factory=list, description="All signals used")
    # DEPRECATED: kept for backward compatibility with correction memory and graph
    entity_type: EntityType = Field(
        default=EntityType.GENERIC_ENTITY,
        description="[DEPRECATED] Detected entity type — prefer column_role + semantic_candidates",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    rationale: str = Field(..., description="Human-readable explanation")
    needs_review: bool = Field(default=False, description="Requires user confirmation")
    alternatives: List[Dict[str, Any]] = Field(
        default_factory=list, description="Alternative interpretations with confidence"
    )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.90:
            return ConfidenceLevel.STRONG
        elif self.confidence >= 0.70:
            return ConfidenceLevel.GOOD
        elif self.confidence >= 0.50:
            return ConfidenceLevel.TENTATIVE
        return ConfidenceLevel.UNCERTAIN

    @property
    def is_fallback(self) -> bool:
        return self.entity_type in (
            EntityType.GENERIC_ENTITY,
            EntityType.GENERIC_REFERENCE,
            EntityType.GENERIC_ATTRIBUTE,
        )


class EntityCluster(BaseModel):
    """A group of columns that share a common business entity.

    Produced by the grouping engine from individual column classifications.
    Still requires validation before becoming a DiscoveredEntity.
    """

    label: str = Field(..., description="Proposed entity label (e.g. 'patient', 'customer')")
    columns: List[str] = Field(..., description="Column names in this cluster")
    roles: List[ColumnRole] = Field(..., description="Structural roles of columns in cluster")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Cluster confidence from grouping"
    )
    candidates: List[SemanticCandidate] = Field(
        default_factory=list, description="Aggregated semantic candidates"
    )
    has_identifier: bool = Field(
        default=False, description="Whether cluster contains an IDENTIFIER column"
    )
    source: str = Field(
        default="prefix",
        description="How this cluster was formed: prefix | edit_distance | abbreviation | table_name",
    )


class DiscoveredEntity(BaseModel):
    """A validated business entity discovered from column clustering.

    Produced by the validation pipeline after EntityCluster passes
    generic business object validation.

    Confidence model:
      - role_confidence: How confident we are in the ColumnRole assignments
        (based on signal strength for the assigned roles)
      - candidate_confidence: How confident we are in the semantic label
        (based on grouping source: prefix > abbreviation > table_name)
      - entity_confidence: How confident this is a real business entity
        (based on identifier presence, attribute coverage, cluster size)
      - confidence: Overall combined confidence (backward compat, = entity_confidence)
    """

    label: str = Field(..., description="Entity label")
    columns: List[str] = Field(..., description="Columns belonging to this entity")
    identifier_column: Optional[str] = Field(
        default=None, description="The IDENTIFIER column for this entity"
    )
    role_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of each ColumnRole in this entity"
    )
    role_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in ColumnRole assignments"
    )
    candidate_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in the semantic label"
    )
    entity_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence this is a real business entity"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence after validation (backward compat)"
    )
    validation_notes: List[str] = Field(
        default_factory=list, description="Notes from validation pass"
    )
    is_valid: bool = Field(default=False, description="Whether this entity passed validation")


class DatasetUnderstandingReport(BaseModel):
    """Top-level output of the entity discovery pipeline.

    This is the deliverable: automatically generated understanding
    of a dataset, including entities, relationships, and quality scores.
    """

    table_name: str = Field(..., description="Table/file name")
    entities: List[DiscoveredEntity] = Field(
        default_factory=list, description="Discovered entities"
    )
    unknown_columns: List[str] = Field(
        default_factory=list, description="Columns that couldn't be assigned to any entity"
    )
    data_quality_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Overall data quality score (0-100)"
    )
    trust_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall trust score based on evidence reliability (0-100)",
    )
    column_count: int = Field(default=0, description="Total columns in dataset")
    entity_count: int = Field(default=0, description="Number of entities discovered")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AlternativeCandidate(BaseModel):
    """A secondary entity that could plausibly be the primary object.

    Surfaces the system's uncertainty — the primary selection may be correct,
    but these alternatives are close enough that a different interpretation
    is possible.
    """

    label: str = Field(..., description="Entity label of the alternative")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Combined confidence score for this alternative"
    )
    table_name_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Score from table name match"
    )
    column_dominance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Score from column count / structural dominance"
    )
    entity_confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Score from entity validation confidence"
    )
    evidence_columns: List[str] = Field(
        default_factory=list,
        description="Columns that contributed to this entity's score",
    )


class AmbiguityAnalysis(BaseModel):
    """Quantification of uncertainty in the primary object selection.

    Higher scores mean the system is less certain — the top candidate
    is not clearly dominant over alternatives.

    Thresholds:
      - low (< 0.30): clear winner, low uncertainty
      - medium (0.30-0.55): moderate uncertainty, worth reviewing
      - high (> 0.55): multiple plausible candidates, definitely review
    """

    score: float = Field(
        ..., ge=0.0, le=1.0, description="Ambiguity score (0=perfectly certain, 1=maximally ambiguous)"
    )
    level: str = Field(
        ..., description="Ambiguity level: low | medium | high"
    )
    top_gap: float = Field(
        ..., ge=0.0, le=1.0, description="Gap between top and second candidate scores (smaller = more ambiguous)"
    )
    alternative_count: int = Field(
        ..., ge=0, description="Number of valid alternative candidates"
    )
    has_alternatives: bool = Field(
        default=False, description="Whether there are viable alternatives"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"level must be one of {allowed}")
        return v


class EvidenceTraceItem(BaseModel):
    """A single column's contribution to the primary object score.

    Answers: why did Signal think this entity is the primary object?
    Each column in the entity contributes to the column_dominance_score.
    """

    column_name: str = Field(..., description="Column name")
    role: str = Field(
        ..., description="Column role: IDENTIFIER | NAME | AMOUNT | QUANTITY | STATUS | ..."
    )
    contribution: float = Field(
        ..., ge=0.0, le=1.0, description="This column's contribution to the combined score"
    )


class PrimaryObjectResult(BaseModel):
    """Result of primary business object discovery — identifies what the dataset is about.

    The primary object is the dominant business entity in the dataset. For example,
    in an orders table, Order is the primary object; Customer and Product participate.

    The `evidence_strength` field measures how much evidence supports this conclusion.
    It is NOT a probability of being correct — it quantifies the strength of
    supporting evidence from column names, structural dominance, and entity validation.

    A calibration study on 92 datasets showed the system is systematically
    underconfident if interpreted as a probability (~40 percentage points).
    This is by design: the score measures evidence accumulation, not probabilistic certainty.

    Includes alternatives, ambiguity analysis, and evidence traces so consumers can
    answer: "Why did Signal think this is the primary object?"
    """

    label: str = Field(..., description="Entity label of the primary object")
    evidence_strength: float = Field(
        ..., ge=0.0, le=1.0, description="Evidence strength supporting this conclusion (NOT probability)"
    )
    table_name_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Score contribution from table name signal"
    )
    column_dominance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score contribution from column count / structural dominance",
    )
    entity_confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score contribution from underlying entity validation confidence",
    )
    entity_label: str = Field(..., description="Entity label of the selected primary object")
    is_valid: bool = Field(
        default=False, description="Whether the primary object meets minimum confidence"
    )
    alternatives: List[AlternativeCandidate] = Field(
        default_factory=list,
        description="Alternative primary candidates with scores (sorted by confidence, descending)",
    )
    ambiguity: Optional[AmbiguityAnalysis] = Field(
        default=None,
        description="Ambiguity analysis quantifying uncertainty in this selection",
    )
    evidence_trace: List[EvidenceTraceItem] = Field(
        default_factory=list,
        description="Per-column contribution to the combined score",
    )

    @property
    def confidence(self) -> float:
        """Backward-compatible alias for evidence_strength.

        DEPRECATED: Use evidence_strength instead. This field measures
        evidence accumulation, not probabilistic certainty.
        """
        return self.evidence_strength


class ParticipatingEntity(BaseModel):
    """An entity that participates in the primary object's transactions.

    Not the primary object itself — but referenced BY it. For example, in an
    orders table Product is a participating entity (referenced via product_id).

    Confidence model:
      participation_score = 0.60 * naming_evidence + 0.40 * entity_confidence
    """

    label: str = Field(..., description="Entity label")
    identifier_column: str = Field(
        ..., description="The foreign-key-style column referencing this entity"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence (backward compat)"
    )
    participation_score: float = Field(
        ..., ge=0.0, le=1.0, description="Composite participation score (min 0.50 to be valid)"
    )
    entity_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Entity validation confidence from entity_discovery"
    )
    naming_evidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence from column naming pattern alone"
    )
    is_valid: bool = Field(
        default=False, description="Whether participation score meets minimum threshold"
    )



class ReferenceSignal(BaseModel):
    """
    A structured reference signal between two business entities within a table.

    Built on top of participation discovery — adds evidence tracing, cardinality
    inference, and value overlap analysis.

    For example, in an orders table:
      - source: order (primary object)
      - target: customer (participant)
      - reference_column: customer_id
      - cardinality: many_to_one (many orders → one customer)
      - value_overlap: True (customer_id values in orders match customer ID format)
    """

    source_entity: str = Field(..., description="Primary entity label")
    target_entity: str = Field(..., description="Referenced entity label")
    reference_column: str = Field(..., description="The FK-style column carrying the reference")
    cardinality: str = Field(
        default="unknown",
        description="Inferred cardinality: one_to_one | one_to_many | many_to_one | many_to_many | unknown",
    )
    naming_evidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence from column naming pattern match"
    )
    entity_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the target entity's validation"
    )
    value_overlap: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of reference values that match expected ID format (0.0 if not measured)",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Combined confidence in this reference signal"
    )
    is_valid: bool = Field(
        default=False, description="Whether this reference meets the minimum confidence threshold"
    )


class RelationshipReport(BaseModel):
    """
    Complete relationship analysis for a single table.

    Aggregates reference signals between the primary object and all detected
    participants, plus any intra-table relationships.
    """

    primary_entity: str = Field(default="", description="The primary object entity label")
    reference_signals: List[ReferenceSignal] = Field(
        default_factory=list, description="Reference signals from primary to participants"
    )
    precision: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of valid reference signals"
    )
    reference_count: int = Field(
        default=0, description="Number of valid reference signals detected"
    )


def column_role_to_legacy_entity_type(role: ColumnRole) -> EntityType:
    mapping = {
        ColumnRole.IDENTIFIER: EntityType.GENERIC_REFERENCE,
        ColumnRole.NAME: EntityType.GENERIC_ENTITY,
        ColumnRole.EMAIL: EntityType.PERSON,
        ColumnRole.PHONE: EntityType.PERSON,
        ColumnRole.DATE: EntityType.TIMEDIMENSION,
        ColumnRole.TIMESTAMP: EntityType.TIMEDIMENSION,
        ColumnRole.AMOUNT: EntityType.AMOUNT,
        ColumnRole.QUANTITY: EntityType.QUANTITY,
        ColumnRole.PERCENTAGE: EntityType.METRIC,
        ColumnRole.STATUS: EntityType.STATUS,
        ColumnRole.CATEGORY: EntityType.CLASSIFICATION,
        ColumnRole.LOCATION: EntityType.GEOGRAPHY,
        ColumnRole.BOOLEAN: EntityType.INDICATOR,
        ColumnRole.URL: EntityType.GENERIC_ENTITY,
        ColumnRole.CODE: EntityType.CODE,
        ColumnRole.TEXT: EntityType.GENERIC_ATTRIBUTE,
        ColumnRole.UNKNOWN: EntityType.GENERIC_ENTITY,
    }
    return mapping.get(role, EntityType.GENERIC_ENTITY)


class ExtractionResult(BaseModel):
    """Complete extraction result for a schema"""

    table_name: str
    entities: List[EntityCandidate] = Field(..., description="All detected entities")
    fallback_count: int = Field(default=0, description="Number of fallback classifications")
    review_required: List[str] = Field(
        default_factory=list, description="Columns requiring user review"
    )
    strong_confidence_count: int = Field(default=0)
    good_confidence_count: int = Field(default=0)
    tentative_confidence_count: int = Field(default=0)
    uncertain_confidence_count: int = Field(default=0)
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

    def model_post_init(self, __context):
        """Calculate statistics after initialization"""
        for entity in self.entities:
            if entity.confidence >= 0.90:
                self.strong_confidence_count += 1
            elif entity.confidence >= 0.70:
                self.good_confidence_count += 1
            elif entity.confidence >= 0.50:
                self.tentative_confidence_count += 1
            else:
                self.uncertain_confidence_count += 1

            if entity.needs_review:
                self.review_required.append(entity.column_name)

            if entity.is_fallback:
                self.fallback_count += 1


class ColumnAnalysisRequest(BaseModel):
    """Request to analyze a single column"""

    column_name: str
    data_type: str
    sample_values: List[str] = Field(default_factory=list)
    table_name: Optional[str] = None
    neighboring_columns: List[str] = Field(default_factory=list)


class EntityCorrection(BaseModel):
    """User correction for entity classification"""

    dataset_id: str
    table_name: str
    column_name: str
    original_entity: EntityType
    corrected_entity: EntityType
    original_confidence: float
    correction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None

    @field_validator("original_entity", "corrected_entity", mode="before")
    @classmethod
    def normalize_entity_type(cls, v):
        if isinstance(v, str):
            return EntityType(v)
        return v


class CorrectionMemory(BaseModel):
    """Storage for user corrections to improve future inference"""

    corrections: List[EntityCorrection] = Field(default_factory=list)
    _persistence_path: Optional[str] = None

    def configure_persistence(self, path: str):
        """Enable JSON file persistence for corrections"""
        self._persistence_path = path
        self._load_from_disk()

    def add_correction(self, correction: EntityCorrection):
        self.corrections.append(correction)
        self._save_to_disk()

    def get_correction(self, dataset_id: str, column_name: str) -> Optional[EntityCorrection]:
        """Get most recent correction for a column"""
        matching = [
            c
            for c in reversed(self.corrections)
            if c.dataset_id == dataset_id and c.column_name == column_name
        ]
        return matching[0] if matching else None

    def get_prior_entity(self, dataset_id: str, column_name: str) -> Optional[EntityType]:
        """Get prior entity type from corrections"""
        correction = self.get_correction(dataset_id, column_name)
        return correction.corrected_entity if correction else None

    def get_corrections_for_dataset(self, dataset_id: str) -> List[EntityCorrection]:
        """Get all corrections for a specific dataset"""
        return [c for c in self.corrections if c.dataset_id == dataset_id]

    def get_dataset_priors(self, dataset_id: str) -> Dict[str, EntityType]:
        """Get all prior entity corrections for a dataset"""
        priors: Dict[str, EntityType] = {}
        for c in self.corrections:
            if c.dataset_id == dataset_id:
                priors[c.column_name] = c.corrected_entity
        return priors

    def clear_dataset_corrections(self, dataset_id: str) -> int:
        """Clear all corrections for a dataset"""
        before = len(self.corrections)
        self.corrections = [c for c in self.corrections if c.dataset_id != dataset_id]
        removed = before - len(self.corrections)
        self._save_to_disk()
        return removed

    def _save_to_disk(self):
        """Persist corrections to JSON file"""
        if not self._persistence_path:
            return
        try:
            import json
            import os

            os.makedirs(os.path.dirname(self._persistence_path) or ".", exist_ok=True)
            with open(self._persistence_path, "w") as f:
                # Convert to serializable dicts
                data = []
                for c in self.corrections:
                    data.append(
                        {
                            "dataset_id": c.dataset_id,
                            "table_name": c.table_name,
                            "column_name": c.column_name,
                            "original_entity": c.original_entity.value,
                            "corrected_entity": c.corrected_entity.value,
                            "original_confidence": c.original_confidence,
                            "correction_timestamp": c.correction_timestamp.isoformat(),
                            "user_id": c.user_id,
                        }
                    )
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist corrections: {e}")

    def _load_from_disk(self):
        """Load corrections from JSON file"""
        if not self._persistence_path:
            return
        try:
            import json
            import os

            if not os.path.exists(self._persistence_path):
                return
            with open(self._persistence_path, "r") as f:
                data = json.load(f)
            for item in data:
                try:
                    correction = EntityCorrection(
                        dataset_id=item["dataset_id"],
                        table_name=item["table_name"],
                        column_name=item["column_name"],
                        original_entity=EntityType(item["original_entity"]),
                        corrected_entity=EntityType(item["corrected_entity"]),
                        original_confidence=item.get("original_confidence", 1.0),
                        user_id=item.get("user_id"),
                    )
                    self.corrections.append(correction)
                except Exception as e:
                    logger.warning(f"Failed to load correction entry: {e}")
        except Exception as e:
            logger.warning(f"Failed to load corrections from disk: {e}")


# Export all models
__all__ = [
    # NEW: Structural + Semantic models
    "ColumnRole",
    "EvidenceReliability",
    "SemanticCandidate",
    "EvidenceSource",
    "EntityCluster",
    "DiscoveredEntity",
    "DatasetUnderstandingReport",
    "PrimaryObjectResult",
    "EvidenceTraceItem",
    "AlternativeCandidate",
    "AmbiguityAnalysis",
    "ParticipatingEntity",
    "ReferenceSignal",
    "RelationshipReport",
    # DEPRECATED: kept for backward compatibility
    "EntityType",
    # Shared
    "SignalType",
    "ConfidenceLevel",
    "ColumnProfile",
    "SchemaProfile",
    "SignalResult",
    "EntityCandidate",
    "ExtractionResult",
    "ColumnAnalysisRequest",
    "EntityCorrection",
    "CorrectionMemory",
    "column_role_to_legacy_entity_type",
]
