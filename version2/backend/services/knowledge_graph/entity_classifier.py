"""
Entity Classifier - Maps signals to entity labels with confidence
===================================================================

Takes all signals from SignalEngine and produces entity type predictions
with confidence scores and rationales.

This is the core classification logic that combines multi-signal evidence.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

from .models import (
    ColumnProfile,
    SchemaProfile,
    SignalResult,
    SignalType,
    EntityType,
    EntityCandidate,
    ConfidenceLevel,
)
from .signal_engine import signal_engine

logger = logging.getLogger(__name__)


class EntityClassificationError(Exception):
    """Raised when entity classification fails"""

    pass


class EntityClassifier:
    """
    Maps classification signals to entity labels.

    Key logic:
    1. Aggregate evidence from all signals
    2. Weight signals appropriately
    3. Handle conflicts (multiple entity type matches)
    4. Generate alternatives for ambiguous cases
    """

    # Signal weights for different entity categories
    SIGNAL_WEIGHTS = {
        SignalType.COLUMN_NAME: 0.40,  # Highest - names are most informative
        SignalType.DATA_TYPE: 0.25,  # Type is strong secondary signal
        SignalType.SAMPLE_VALUES: 0.20,  # Values disambiguate
        SignalType.CARDINALITY: 0.10,  # Provides context
        SignalType.DOMAIN_CONTEXT: 0.05,  # Weakest - only used with other signals
    }

    # Entity type hierarchy for fallback mapping
    ENTITY_HIERARCHY = {
        # Specific → Generic fallbacks
        EntityType.CUSTOMER: [EntityType.PERSON, EntityType.GENERIC_REFERENCE],
        EntityType.EMPLOYEE: [EntityType.PERSON, EntityType.GENERIC_REFERENCE],
        EntityType.PATIENT: [EntityType.PERSON, EntityType.GENERIC_REFERENCE],
        EntityType.VENDOR: [EntityType.ORGANIZATION, EntityType.GENERIC_REFERENCE],
        EntityType.SUPPLIER: [EntityType.ORGANIZATION, EntityType.GENERIC_REFERENCE],
        EntityType.PRODUCT: [EntityType.GENERIC_ENTITY],
        EntityType.ORDER: [EntityType.TRANSACTION, EntityType.GENERIC_ENTITY],
        EntityType.INVOICE: [EntityType.TRANSACTION, EntityType.GENERIC_ENTITY],
        EntityType.DEPARTMENT: [EntityType.FACILITY, EntityType.GENERIC_ENTITY],
        EntityType.STATUS: [EntityType.CLASSIFICATION],
        EntityType.CODE: [EntityType.CLASSIFICATION],
    }

    def __init__(self):
        self.signal_engine = signal_engine

    async def classify_column(
        self, column: ColumnProfile, schema: Optional[SchemaProfile] = None
    ) -> EntityCandidate:
        """
        Classify a single column into an entity type.

        Args:
            column: Column profile
            schema: Optional schema context

        Returns:
            EntityCandidate with type, confidence, rationale
        """
        # Extract all signals
        signals = self.signal_engine.extract_all_signals(column, schema)

        if not signals:
            # No signals - use fallback
            return self._create_fallback_candidate(
                column=column, reason="No signals could be extracted"
            )

        # Aggregate signals into entity predictions
        entity_scores = self._aggregate_signals(signals)

        if not entity_scores:
            return self._create_fallback_candidate(
                column=column, reason="No entity pattern matched"
            )

        # Get best entity type
        best_entity, best_confidence = max(entity_scores.items(), key=lambda x: x[1])

        # Generate rationale
        rationale = self._generate_rationale(signals, best_entity)

        # Get alternatives
        alternatives = self._get_alternatives(entity_scores, best_entity)

        # Determine if review is needed
        needs_review = best_confidence < 0.70

        return EntityCandidate(
            column_name=column.name,
            entity_type=best_entity,
            confidence=best_confidence,
            rationale=rationale,
            signals=signals,
            needs_review=needs_review,
            alternatives=alternatives,
        )

    async def classify_schema(self, schema: SchemaProfile) -> List[EntityCandidate]:
        """
        Classify all columns in a schema.

        Args:
            schema: Complete schema profile

        Returns:
            List of EntityCandidates for all columns
        """
        candidates = []

        for column in schema.columns:
            try:
                candidate = await self.classify_column(column, schema)
                candidates.append(candidate)
            except Exception as e:
                logger.warning(f"Failed to classify column {column.name}: {e}")
                # Create fallback for failed classifications
                candidates.append(
                    self._create_fallback_candidate(
                        column=column, reason=f"Classification failed: {str(e)}"
                    )
                )

        return candidates

    def _aggregate_signals(self, signals: List[SignalResult]) -> Dict[EntityType, float]:
        """
        Aggregate signals into entity type confidence scores.

        Uses weighted scoring based on signal type.
        """
        entity_scores: Dict[EntityType, float] = defaultdict(float)
        entity_counts: Dict[EntityType, int] = defaultdict(int)

        for signal in signals:
            weight = self.SIGNAL_WEIGHTS.get(signal.signal_type, 0.1)

            # Extract entity types from signal
            entity_types = self._extract_entity_types_from_signal(signal)

            for entity_type in entity_types:
                # Add weighted confidence
                entity_scores[entity_type] += signal.confidence * weight
                entity_counts[entity_type] += 1

        # NOTE: Weighted sum is not normalized by count.
        # The weights already sum to 1.0, so the weighted sum is the
        # correct confidence. Dividing by count would collapse the
        # scale (e.g. two strong signals → ~50% instead of ~90%).

        # Apply boost for multiple strong signals
        for entity_type, count in entity_counts.items():
            if count >= 3 and entity_scores[entity_type] >= 0.7:
                # Multiple signals agree - boost confidence
                entity_scores[entity_type] = min(0.99, entity_scores[entity_type] * 1.1)

        return dict(entity_scores)

    def _extract_entity_types_from_signal(self, signal: SignalResult) -> List[EntityType]:
        """Extract entity types from signal raw_match data"""
        entity_types = []

        raw_match = signal.raw_match or {}

        # Check for entity_types in raw_match
        if "entity_types" in raw_match:
            for et in raw_match["entity_types"]:
                try:
                    entity_types.append(EntityType(et))
                except ValueError:
                    pass

        # Also infer from matched patterns
        if signal.matched_pattern:
            inferred = self._infer_entity_from_pattern(signal.signal_type, signal.matched_pattern)
            if inferred:
                entity_types.append(inferred)

        # If no types found, use signal confidence as entity indicator
        if not entity_types:
            # Create generic based on confidence level
            if signal.confidence >= 0.8:
                entity_types.append(EntityType.GENERIC_ENTITY)
            elif signal.confidence >= 0.5:
                entity_types.append(EntityType.GENERIC_ATTRIBUTE)
            else:
                entity_types.append(EntityType.GENERIC_ENTITY)

        return entity_types

    def _infer_entity_from_pattern(
        self, signal_type: SignalType, pattern: str
    ) -> Optional[EntityType]:
        """Infer entity type from pattern string"""

        pattern_lower = pattern.lower() if pattern else ""

        # Data type based inference
        if signal_type == SignalType.DATA_TYPE:
            mapping = {
                "uuid": EntityType.GENERIC_REFERENCE,
                "boolean": EntityType.INDICATOR,
                "date": EntityType.TIMEDIMENSION,
                "timestamp": EntityType.TIMEDIMENSION,
                "integer": EntityType.METRIC,
                "decimal": EntityType.METRIC,
            }
            return mapping.get(pattern_lower)

        # Cardinality based inference
        if signal_type == SignalType.CARDINALITY:
            if pattern == "unique":
                return EntityType.GENERIC_REFERENCE
            if pattern == "low_cardinality":
                return EntityType.CLASSIFICATION

        return None

    def _generate_rationale(self, signals: List[SignalResult], entity_type: EntityType) -> str:
        """Generate human-readable rationale for classification"""
        parts = []

        # Find strongest signals for this entity
        relevant_signals = [
            s
            for s in signals
            if s.raw_match
            and "entity_types" in s.raw_match
            and entity_type.value in s.raw_match.get("entity_types", [])
        ]

        if relevant_signals:
            # Sort by confidence
            relevant_signals.sort(key=lambda x: x.confidence, reverse=True)

            for signal in relevant_signals[:2]:  # Top 2
                parts.append(f"{signal.signal_type.value}: {signal.evidence}")

        # Add summary
        if not parts:
            # Use highest confidence signals
            signals.sort(key=lambda x: x.confidence, reverse=True)
            for signal in signals[:2]:
                parts.append(f"{signal.signal_type.value}: {signal.evidence[:50]}")

        return (
            " | ".join(parts)
            if parts
            else f"Classified as {entity_type.value} based on available signals"
        )

    def _get_alternatives(
        self,
        entity_scores: Dict[EntityType, float],
        best_entity: EntityType,
        max_alternatives: int = 3,
    ) -> List[Dict[str, Any]]:
        """Get alternative entity type interpretations"""

        # Sort by score
        sorted_entities = sorted(entity_scores.items(), key=lambda x: x[1], reverse=True)

        alternatives = []
        for entity, score in sorted_entities:
            if entity != best_entity and score > 0.3:
                alternatives.append({"alt_type": entity.value, "score": round(score, 3)})
                if len(alternatives) >= max_alternatives:
                    break

        return alternatives

    def _create_fallback_candidate(self, column: ColumnProfile, reason: str) -> EntityCandidate:
        """Create fallback entity candidate for failed/unclassifiable columns"""

        # Choose appropriate fallback based on column properties
        if column.distinct_ratio > 0.9:
            fallback_type = EntityType.GENERIC_REFERENCE
        elif column.data_type in ("integer", "decimal"):
            fallback_type = EntityType.GENERIC_ATTRIBUTE
        else:
            fallback_type = EntityType.GENERIC_ENTITY

        return EntityCandidate(
            column_name=column.name,
            entity_type=fallback_type,
            confidence=0.25,  # Low confidence - fallback
            rationale=f"Fallback: {reason}. Cannot determine specific entity type.",
            signals=[],
            needs_review=True,  # Always require review for fallbacks
            alternatives=[],
        )

    def apply_correction(
        self, candidate: EntityCandidate, corrected_type: EntityType
    ) -> EntityCandidate:
        """
        Apply user correction to entity candidate.

        Returns a new candidate with corrected type and updated confidence.
        """
        return EntityCandidate(
            column_name=candidate.column_name,
            entity_type=corrected_type,
            confidence=1.0,  # User confirmed - 100% confidence
            rationale=f"User corrected: {candidate.entity_type.value} → {corrected_type.value}",
            signals=candidate.signals,
            needs_review=False,  # User confirmed - no review needed
            alternatives=[],
        )


# Singleton instance
entity_classifier = EntityClassifier()

__all__ = ["EntityClassifier", "EntityClassificationError", "entity_classifier"]
