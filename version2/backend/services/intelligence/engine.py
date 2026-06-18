"""
intelligence/engine.py — Intelligence Engine Orchestrator (Layer 2+3)

Takes RawProfilingResult (pure facts) and adds:
  - Semantic classification (roles, categories)
  - Aggregation rules (sum_allowed, additive type)
  - Entity detection
  - Geo detection
  - Hierarchy detection
  - Relationship detection
  - Domain hypotheses

Returns UnifiedIntelligenceResult — the complete semantic understanding.
"""

from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from services.profiling.models import RawProfilingResult

from .models import (
    AggregationSuitability,
    ColumnIntelligence,
    UnifiedIntelligenceResult,
)
from .semantic_classifier import semantic_classifier, SemanticClassifier
from .aggregation_engine import aggregation_engine, AggregationEngine
from .entity_detector import entity_detector, EntityDetector
from .geo_engine import geo_engine, GeoEngine
from .hierarchy_detector import hierarchy_detector, HierarchyDetector
from .relationship_detector import relationship_detector, RelationshipDetector
from .domain_hypothesis import domain_hypothesis_engine, DomainHypothesisEngine

logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """Orchestrates all intelligence sub-engines.

    Usage:
        intelligence = await intelligence_engine.run(profiling_result, df)
        # intelligence is UnifiedIntelligenceResult
    """

    def __init__(
        self,
        classifier: Optional[SemanticClassifier] = None,
        agg_engine: Optional[AggregationEngine] = None,
        entity: Optional[EntityDetector] = None,
        geo: Optional[GeoEngine] = None,
        hierarchy: Optional[HierarchyDetector] = None,
        relationship: Optional[RelationshipDetector] = None,
        domain: Optional[DomainHypothesisEngine] = None,
    ):
        self.classifier = classifier or semantic_classifier
        self.agg_engine = agg_engine or aggregation_engine
        self.entity = entity or entity_detector
        self.geo = geo or geo_engine
        self.hierarchy = hierarchy or hierarchy_detector
        self.relationship = relationship or relationship_detector
        self.domain = domain or domain_hypothesis_engine

    def run(
        self,
        profiling_result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> UnifiedIntelligenceResult:
        """Run all intelligence engines and return unified result.

        Args:
            profiling_result: RawProfilingResult from the profiling layer.
            df: Optional DataFrame for entity stats and relationship detection.

        Returns:
            UnifiedIntelligenceResult with all semantic classifications.
        """
        # ── 1. Classify every column ──
        column_intel: list[ColumnIntelligence] = []
        for col_profile in profiling_result.columns:
            classification = self.classifier.classify(col_profile)
            agg = self.agg_engine.compute(
                col_profile,
                classification.semantic_role,
                classification.behavioral_role,
            )
            classification.aggregation_suitability = agg
            column_intel.append(classification)

        # ── 2. Detect entities + temporal structure ──
        entities, temporal = self.entity.detect(profiling_result, df)

        # ── 3. Detect geographic columns ──
        geo = self.geo.detect(profiling_result, df)

        # Tag geo roles onto column intelligence
        for intel in column_intel:
            if intel.name == geo.latitude:
                intel.geo_role = "latitude"
            elif intel.name == geo.longitude:
                intel.geo_role = "longitude"
            elif intel.name == geo.country:
                intel.geo_role = "country"
            elif intel.name == geo.state:
                intel.geo_role = "state"
            elif intel.name == geo.city:
                intel.geo_role = "city"
            elif intel.name == geo.postal_code:
                intel.geo_role = "postal_code"

        # Tag entity info onto column intelligence
        entity_by_col = {e.entity_column: e for e in entities}
        for intel in column_intel:
            if intel.name in entity_by_col:
                intel.entity_info = entity_by_col[intel.name]

        # ── 4. Detect hierarchies ──
        hierarchies = self.hierarchy.detect(profiling_result, df)

        # ── 5. Detect relationships ──
        relationships = self.relationship.detect(profiling_result, df)

        # ── 6. Match domain (hypotheses, not facts) ──
        domain_result = self.domain.match(profiling_result)

        return UnifiedIntelligenceResult(
            columns=column_intel,
            entities=entities,
            hierarchies=hierarchies,
            geo=geo,
            temporal=temporal,
            relationships=relationships,
            domain=domain_result,
        )


# Singleton
intelligence_engine = IntelligenceEngine()
