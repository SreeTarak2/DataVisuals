"""
Confidence Scorer - Calculates final confidence using weighted evidence
=========================================================================

Implements the confidence model from the production plan:
- Score bands: 0.90+ (strong), 0.70-0.89 (good), 0.50-0.69 (tentative), <0.50 (uncertain)
- Weighted scoring: name (40%), type (25%), value (20%), context (15%)
- Confidence rules: strong matches can only be lowered, ties resolve to safer labels
"""

import logging
from typing import List, Dict, Optional, Any
from collections import Counter

from .models import (
    SignalResult,
    SignalType,
    EntityType,
    EntityCandidate,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)


class ConfidenceScoringError(Exception):
    """Raised when confidence scoring fails"""

    pass


class ConfidenceScorer:
    """
    Calculates weighted confidence scores for entity classification.

    Confidence Model:
    - 0.90-1.00: Strong, actionable confidence
    - 0.70-0.89: Good, likely correct (auto-accept if no contradictions)
    - 0.50-0.69: Tentative, surface for review when important
    - <0.50: Uncertain, use generic fallback

    Weight Distribution:
    - Column name match: 40%
    - Type/profile match: 25%
    - Sample value match: 20%
    - Domain/context match: 15%
    """

    # Weight configuration
    WEIGHTS = {
        SignalType.COLUMN_NAME: 0.40,
        SignalType.DATA_TYPE: 0.25,
        SignalType.SAMPLE_VALUES: 0.20,
        SignalType.CARDINALITY: 0.10,
        SignalType.DOMAIN_CONTEXT: 0.05,
    }

    # Score thresholds
    STRONG_THRESHOLD = 0.90
    GOOD_THRESHOLD = 0.70
    TENTATIVE_THRESHOLD = 0.50

    # Contradiction detection thresholds
    CONTRADICTION_WEIGHT_PENALTY = 0.3

    def __init__(self):
        pass

    def calculate_confidence(self, signals: List[SignalResult]) -> float:
        """
        Calculate overall confidence from signals.

        Args:
            signals: List of signal results

        Returns:
            Confidence score between 0 and 1
        """
        if not signals:
            return 0.0

        # Step 1: Weighted sum of signal confidences
        weighted_sum = 0.0
        total_weight = 0.0

        for signal in signals:
            weight = self.WEIGHTS.get(signal.signal_type, 0.1)
            weighted_sum += signal.confidence * weight
            total_weight += weight

        base_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Step 2: Check for contradictions (multiple conflicting signals)
        contradiction_penalty = self._detect_contradictions(signals)

        # Step 3: Apply signal agreement bonus
        agreement_bonus = self._calculate_agreement_bonus(signals)

        # Final confidence calculation
        final_confidence = base_confidence - contradiction_penalty + agreement_bonus

        # Clamp to valid range
        final_confidence = max(0.0, min(1.0, final_confidence))

        return round(final_confidence, 3)

    def _detect_contradictions(self, signals: List[SignalResult]) -> float:
        """
        Detect contradictions between signals.

        Example contradiction:
        - Column name suggests Customer (high)
        - Data type suggests Metric (conflicting)

        Returns penalty to subtract from confidence.
        """
        # Group signals by type category
        name_signals = [s for s in signals if s.signal_type == SignalType.COLUMN_NAME]
        type_signals = [s for s in signals if s.signal_type == SignalType.DATA_TYPE]
        value_signals = [s for s in signals if s.signal_type == SignalType.SAMPLE_VALUES]

        # Check for high-name + metric-type contradiction
        if name_signals:
            name_conf = max(s.confidence for s in name_signals)
            name_match = name_signals[0].matched_pattern or ""

            # High confidence name pattern suggesting ID/Entity
            if name_conf >= 0.8 and any(p in name_match.lower() for p in ["_id", "name"]):
                # Check if type signals suggest Metric (contradiction)
                if type_signals:
                    type_conf = max(s.confidence for s in type_signals)
                    if type_conf >= 0.7 and "metric" in str(type_signals[0].raw_match).lower():
                        return self.CONTRADICTION_WEIGHT_PENALTY

        # Check for name says Classification but cardinality says unique
        if name_signals and type_signals:
            name_conf = max(s.confidence for s in name_signals)
            name_match = name_signals[0].matched_pattern or ""

            if "status" in name_match.lower() or "category" in name_match.lower():
                # Check cardinality signals
                card_signals = [s for s in signals if s.signal_type == SignalType.CARDINALITY]
                if card_signals:
                    card_match = card_signals[0].matched_pattern or ""
                    if "unique" in card_match:
                        # Status should NOT be unique - contradiction
                        return 0.15

        return 0.0

    def _calculate_agreement_bonus(self, signals: List[SignalResult]) -> float:
        """
        Calculate bonus for strong signal agreement.

        Multiple strong signals pointing to same conclusion = higher confidence.
        """
        # Count strong signals
        strong_count = sum(1 for s in signals if s.confidence >= 0.80)

        if strong_count >= 3:
            return 0.08  # Strong agreement bonus
        elif strong_count == 2:
            return 0.04

        return 0.0

    def score_entity_candidate(self, candidate: EntityCandidate) -> EntityCandidate:
        """
        Score and potentially adjust an entity candidate.

        This recalculates confidence and may downgrade if contradictions found.
        """
        # Recalculate confidence from signals
        recalculated_confidence = self.calculate_confidence(candidate.signals)

        # Check if we need to update the candidate
        if abs(candidate.confidence - recalculated_confidence) > 0.1:
            # Significant difference - update confidence
            candidate.confidence = recalculated_confidence

            # Update needs_review based on new confidence
            if recalculated_confidence < self.GOOD_THRESHOLD:
                candidate.needs_review = True

            # Update rationale if changed significantly
            if recalculated_confidence < 0.5:
                candidate.rationale += " | Note: Low confidence after signal validation."

        return candidate

    def get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level category from score"""
        if confidence >= self.STRONG_THRESHOLD:
            return ConfidenceLevel.STRONG
        elif confidence >= self.GOOD_THRESHOLD:
            return ConfidenceLevel.GOOD
        elif confidence >= self.TENTATIVE_THRESHOLD:
            return ConfidenceLevel.TENTATIVE
        return ConfidenceLevel.UNCERTAIN

    def should_auto_accept(self, candidate: EntityCandidate) -> bool:
        """
        Determine if candidate should be auto-accepted.

        Auto-accept criteria:
        - Strong confidence (>= 0.90), OR
        - Good confidence (>= 0.70) with no contradictions
        """
        if candidate.confidence >= self.STRONG_THRESHOLD:
            return True

        if candidate.confidence >= self.GOOD_THRESHOLD:
            # Check for contradictions
            contradiction_penalty = self._detect_contradictions(candidate.signals)
            return contradiction_penalty == 0.0

        return False

    def should_require_review(self, candidate: EntityCandidate) -> bool:
        """
        Determine if candidate requires user review.

        Review criteria:
        - Tentative or uncertain (confidence < 0.70)
        - Fallback entities (Generic*)
        - Has contradictions
        """
        if candidate.confidence < self.GOOD_THRESHOLD:
            return True

        if candidate.entity_type in (
            EntityType.GENERIC_ENTITY,
            EntityType.GENERIC_REFERENCE,
            EntityType.GENERIC_ATTRIBUTE,
        ):
            return True

        # Check for high contradictions
        contradiction_penalty = self._detect_contradictions(candidate.signals)
        if contradiction_penalty >= 0.2:
            return True

        return False

    def explain_confidence(self, candidate: EntityCandidate) -> Dict[str, Any]:
        """
        Provide detailed explanation of confidence calculation.

        Returns breakdown of factors affecting confidence.
        """
        breakdown = {
            "overall_confidence": candidate.confidence,
            "confidence_level": self.get_confidence_level(candidate.confidence).value,
            "signal_count": len(candidate.signals),
            "signals": [],
            "should_review": self.should_require_review(candidate),
            "auto_accept": self.should_auto_accept(candidate),
        }

        # Add signal breakdown
        for signal in candidate.signals:
            weight = self.WEIGHTS.get(signal.signal_type, 0.1)
            breakdown["signals"].append(
                {
                    "type": signal.signal_type.value,
                    "confidence": signal.confidence,
                    "weight": weight,
                    "weighted_contribution": signal.confidence * weight,
                    "evidence": signal.evidence[:100],
                }
            )

        # Calculate theoretical max (if all signals strong and agreeing)
        breakdown["theoretical_max"] = sum(
            self.WEIGHTS.get(s.signal_type, 0.1) * 1.0 for s in candidate.signals
        )

        return breakdown


# Singleton instance
confidence_scorer = ConfidenceScorer()

__all__ = ["ConfidenceScorer", "ConfidenceScoringError", "confidence_scorer"]
