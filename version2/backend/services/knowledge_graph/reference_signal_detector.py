"""
Reference Signal Detector
==========================

Enriches participation discovery with structured relationship metadata:

1. Evidence tracing — record which signals (column name, abbreviation, substring)
   contributed to the reference detection, not just final scores
2. Cardinality inference — is this one-to-many, many-to-one, or many-to-many?
3. Value overlap analysis — do the reference column values match expected ID format?

This is Layer 3 of the entity understanding pipeline, built on top of
the entities (Layer 1), primary object (Layer 2a), and participation (Layer 2b).

Output: List[ReferenceSignal] — structured signals consumable by graph storage,
analysis engines, and the benchmark suite.
"""

import logging
import re
from typing import List, Optional

from .models import (
    DiscoveredEntity,
    PrimaryObjectResult,
    ParticipatingEntity,
    ReferenceSignal,
    RelationshipReport,
    ColumnProfile,
)

logger = logging.getLogger(__name__)

REFERENCE_MIN_CONFIDENCE = 0.40

# Patterns that indicate valid ID formats for value overlap check
_ID_VALUE_PATTERNS = [
    re.compile(r"^\d+$"),                    # "12345"
    re.compile(r"^[A-Z]{2,}\d{2,}$", re.I),  # "CUST001", "PRD0001"
    re.compile(r"^[A-Z]+-\d+$", re.I),       # "ORD-001"
    re.compile(r"^[A-Z]+_\d+$", re.I),       # "INV_001"
    re.compile(r"^\w{8,12}$"),               # "TXN000001" (generic alphanumeric)
    re.compile(r"^UID-\w{6,}$", re.I),       # "UID-abc123"
]


class ReferenceSignalDetector:
    """
    Detects and enriches reference signals between entities.

    Takes participation discovery output and adds:
    - Evidence traceability (which signals fired)
    - Cardinality inference (ratio-based)
    - Value overlap analysis (format matching)
    """

    def __init__(self):
        self.min_confidence = REFERENCE_MIN_CONFIDENCE

    def detect(
        self,
        primary: PrimaryObjectResult,
        participants: List[ParticipatingEntity],
        entities: List[DiscoveredEntity],
        profiles: Optional[List[ColumnProfile]] = None,
    ) -> List[ReferenceSignal]:
        """
        Build structured ReferenceSignal from participation output.

        Args:
            primary: Primary object result
            participants: Valid and invalid participants from participation discovery
            entities: All validated entities
            profiles: Optional column profiles for value overlap analysis

        Returns:
            List of ReferenceSignal objects, sorted by confidence desc
        """
        if not primary.is_valid:
            return []

        signals: List[ReferenceSignal] = []

        for participant in participants:
            if not participant.is_valid:
                continue

            # Cardinality inference
            cardinality = self._infer_cardinality(
                primary.label, participant.label,
                participant.identifier_column, entities, profiles
            )

            # Value overlap analysis
            value_overlap = self._check_value_overlap(
                participant.identifier_column, profiles
            ) if profiles else 0.0

            # Combined confidence: weighted sum of evidence sources
            naming_weight = 0.50
            entity_weight = 0.30
            overlap_weight = 0.20

            combined = (
                naming_weight * participant.naming_evidence
                + entity_weight * participant.entity_confidence
                + overlap_weight * value_overlap
            )
            combined = round(min(1.0, max(0.0, combined)), 3)
            is_valid = combined >= self.min_confidence

            signals.append(ReferenceSignal(
                source_entity=primary.label,
                target_entity=participant.label,
                reference_column=participant.identifier_column,
                cardinality=cardinality,
                naming_evidence=participant.naming_evidence,
                entity_confidence=participant.entity_confidence,
                value_overlap=value_overlap,
                confidence=combined,
                is_valid=is_valid,
            ))

        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def build_report(
        self,
        primary: PrimaryObjectResult,
        signals: List[ReferenceSignal],
    ) -> RelationshipReport:
        """
        Build a complete RelationshipReport from reference signals.

        The RelationshipReport aggregates all reference signals and computes
        aggregate metrics like precision and reference_count.
        """
        valid_signals = [s for s in signals if s.is_valid]
        precision = len(valid_signals) / len(signals) if signals else 1.0

        return RelationshipReport(
            primary_entity=primary.label if primary.is_valid else "",
            reference_signals=signals,
            precision=round(precision, 3),
            reference_count=len(valid_signals),
        )

    def _infer_cardinality(
        self,
        source_label: str,
        target_label: str,
        reference_column: str,
        entities: List[DiscoveredEntity],
        profiles: Optional[List[ColumnProfile]] = None,
    ) -> str:
        """
        Infer cardinality between source and target entities.

        Strategy:
        - If the reference column has many distinct values relative to total rows
          (distinct_ratio > 0.5), it's many_to_one (many source rows reference many targets).
        - If distinct_ratio is low (< 0.05), it's one_to_many (few targets referenced by many rows).
        - Default: many_to_one (most common FK relationship).
        """
        if not profiles:
            return "many_to_one"

        # Find the profile for the reference column
        ref_profile = next((p for p in profiles if p.name == reference_column), None)
        if not ref_profile:
            return "many_to_one"

        ratio = ref_profile.distinct_ratio

        if ratio < 0.05:
            return "many_to_one"  # Few distinct values → many rows per target
        elif ratio > 0.90:
            return "one_to_one"   # Near-unique → possibly one-to-one mapping
        else:
            return "many_to_one"  # Default: standard FK relationship

    def _check_value_overlap(
        self,
        column_name: str,
        profiles: Optional[List[ColumnProfile]],
    ) -> float:
        """
        Check whether reference column values match expected ID formats.

        A value overlap score of 1.0 means all sample values look like valid IDs.
        This confirms the column is a proper reference, not a misclassified attribute.

        Returns:
            Fraction of sample values matching common ID patterns, or 0.0 if
            no profiles available or no non-null sample values exist.
        """
        if not profiles:
            return 0.0

        profile = next((p for p in profiles if p.name == column_name), None)
        if not profile or not profile.sample_values:
            return 0.0

        sample_values = [v for v in profile.sample_values if v]
        if not sample_values:
            return 0.0

        matches = 0
        for val in sample_values:
            cleaned = val.strip()
            if any(p.match(cleaned) for p in _ID_VALUE_PATTERNS):
                matches += 1

        return round(matches / len(sample_values), 3)


reference_signal_detector = ReferenceSignalDetector()

__all__ = [
    "ReferenceSignalDetector",
    "reference_signal_detector",
    "REFERENCE_MIN_CONFIDENCE",
]
