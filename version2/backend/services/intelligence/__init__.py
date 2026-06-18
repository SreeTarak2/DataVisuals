"""
intelligence — Layer 2+3: Semantic meaning + cross-column reasoning
==================================================================

Consumes RawProfilingResult (pure facts from profiling/) and adds:
  - Semantic roles (MEASURE, DIMENSION, TIME, IDENTITY, RATE, COUNT)
  - Behavioral roles (ADDITIVE, SEMI_ADDITIVE, NON_ADDITIVE, GEO, STATUS, BOOLEAN)
  - Business categories (revenue, cost, churn, users, etc.)
  - Aggregation suitability (sum_allowed, avg_allowed, etc.)
  - Entity detection
  - Geo detection
  - Hierarchy detection
  - Cross-column relationships
  - Domain hypotheses (with scores, NOT single answers)

No LLM calls. Every classification is deterministic.
"""

from .models import (
    SemanticRole,
    BehavioralRole,
    BusinessCategory,
    AggregationSuitability,
    EntityInfo,
    GeoInfo,
    HierarchyInfo,
    RelationshipInfo,
    DomainCandidate,
    DomainHypothesisResult,
    LLMDomainVerdict,
    UnifiedIntelligenceResult,
    ColumnIntelligence,
)
from .engine import IntelligenceEngine, intelligence_engine
from .domain_detector_llm import LLMDomainDetector, llm_domain_detector

__all__ = [
    "SemanticRole",
    "BehavioralRole",
    "BusinessCategory",
    "AggregationSuitability",
    "EntityInfo",
    "GeoInfo",
    "HierarchyInfo",
    "RelationshipInfo",
    "DomainCandidate",
    "DomainHypothesisResult",
    "LLMDomainVerdict",
    "UnifiedIntelligenceResult",
    "ColumnIntelligence",
    "IntelligenceEngine",
    "intelligence_engine",
    "LLMDomainDetector",
    "llm_domain_detector",
]
