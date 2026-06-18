"""
intelligence/semantic_classifier.py — Column role classification (Layer 2)

Deterministically classifies columns into:
  - SemanticRole (MEASURE / RATE / COUNT / DIMENSION / TIME / IDENTITY)
  - BehavioralRole (ADDITIVE_MEASURE / GEO / STATUS / etc.)
  - BusinessCategory (revenue / cost / users / churn / etc.)
  - Polarity (higher_is_better / lower_is_better)

Every classification produces a confidence score.
Low-confidence items are flagged as needs_review.
No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from services.profiling.models import RawColumnProfile

from .models import (
    SemanticRole,
    BehavioralRole,
    BusinessCategory,
    ColumnIntelligence,
)

logger = logging.getLogger(__name__)


# ── Column Name Patterns ──────────────────────────────────────────────────────

_ID_RE = re.compile(
    r"\b(id|uuid|guid|key|hash|token|code|zip|postal|phone|ip|sku|barcode)\b", re.I
)
_TIME_RE = re.compile(
    r"\b(date|time|year|month|day|created|updated|timestamp|period|week|quarter)\b", re.I
)
_RATE_RE = re.compile(
    r"\b(rate|ratio|percent|pct|margin|efficiency|factor|score|index|grade|"
    r"accuracy|precision|recall|auc|ctr)\b", re.I
)
_COUNT_RE = re.compile(
    r"\b(count|num|number|qty|quantity|units|items|orders|transactions|"
    r"sessions|visits|clicks|impressions|requests)\b", re.I
)
_ENTITY_ID_SUFFIX = re.compile(r"(_id|_key|_uuid|_guid)$", re.I)


# ── Business Category → Polarity Mapping ──────────────────────────────────────

_CATEGORY_PATTERNS: list[tuple[BusinessCategory, str, str]] = [
    (BusinessCategory.REVENUE,
     r"\b(revenue|sales|gmv|income|earnings|gross|mrr|arr|net_sales|turnover|proceeds|receipts)\b",
     "higher_is_better"),
    (BusinessCategory.COST,
     r"\b(cost|expense|opex|capex|cogs|spend|expenditure|loss|burn|overhead|tax|fee|charge|penalty)\b",
     "lower_is_better"),
    (BusinessCategory.VOLUME,
     r"\b(orders|transactions|purchases|bookings|units|items|shipments|deliveries|installs)\b",
     "higher_is_better"),
    (BusinessCategory.USERS,
     r"\b(users|customers|subscribers|members|accounts|clients|visitors|leads|prospects|buyers)\b",
     "higher_is_better"),
    (BusinessCategory.RATE_METRIC,
     r"\b(rate|ratio|percent|pct|margin|conversion|retention|satisfaction|engagement|utilization)\b",
     "higher_is_better"),
    (BusinessCategory.CHURN_RISK,
     r"\b(churn|attrition|cancellation|dropout|refund|return|complaint|defect|error|failure|bug|issue)\b",
     "lower_is_better"),
    (BusinessCategory.PRICE,
     r"\b(price|amount|value|aov|arpu|arpc|ltv|cac|worth|bid|ask)\b",
     "higher_is_better"),
    (BusinessCategory.PERFORMANCE,
     r"\b(score|rating|nps|csat|satisfaction|quality|performance|rank|grade)\b",
     "higher_is_better"),
    (BusinessCategory.DURATION,
     r"\b(duration|latency|age|tenure|days|hours|minutes|seconds|ms|response_time|wait_time|cycle_time)\b",
     "lower_is_better"),
    (BusinessCategory.QUANTITY,
     r"\b(count|num|qty|quantity|volume|capacity|inventory|stock|supply)\b",
     "higher_is_better"),
]


class SemanticClassifier:
    """Deterministic column role classifier.

    Takes raw profiling data (RawColumnProfile) and adds semantic meaning.
    """

    def classify(
        self, profile: RawColumnProfile
    ) -> ColumnIntelligence:
        """Classify a single column into semantic roles.

        Args:
            profile: Raw column profile from the profiling layer.

        Returns:
            ColumnIntelligence with all semantic classifications.
        """
        norm = profile.name.lower().replace("_", " ").replace("-", " ")
        is_numeric = profile.stats is not None
        card = profile.cardinality
        n_rows = max(card.total_count, 1)
        card_ratio = card.cardinality_ratio

        # Compute bounded_01 and integer_valued from stats
        is_bounded_01 = bool(profile.stats and profile.stats.is_bounded_01)
        is_integer_valued = bool(profile.stats and profile.stats.is_integer_valued)

        # ── 1. Semantic Role ──
        semantic_role = self._classify_semantic_role(
            profile.name, profile.dtype, norm, is_numeric,
            card_ratio, n_rows, card.unique_count,
            is_bounded_01=is_bounded_01,
            is_integer_valued=is_integer_valued,
        )

        # ── 2. Behavioral Role ──
        behavioral_role = self._classify_behavioral_role(
            profile.name, norm, is_numeric, semantic_role,
            card_ratio,
        )

        # ── 3. Business Category + Polarity ──
        category, polarity = self._classify_business_category(norm)

        # ── 4. Confidence ──
        confidence = self._compute_confidence(
            semantic_role, behavioral_role, card_ratio, profile
        )
        needs_review = confidence < 0.7

        return ColumnIntelligence(
            name=profile.name,
            semantic_role=semantic_role,
            behavioral_role=behavioral_role,
            business_category=category,
            polarity=polarity,
            classification_confidence=round(confidence, 4),
            needs_review=needs_review,
        )

    def _classify_semantic_role(
        self,
        name: str,
        dtype: str,
        norm: str,
        is_numeric: bool,
        card_ratio: float,
        n_rows: int,
        unique_count: int,
        is_bounded_01: bool = False,
        is_integer_valued: bool = False,
    ) -> SemanticRole:
        """Classify the high-level semantic role."""
        is_datetime = any(t in dtype for t in ("Date", "Datetime", "Duration"))

        # TIME: datetime dtypes OR time-like name
        if is_datetime or _TIME_RE.search(norm):
            return SemanticRole.TIME

        # IDENTITY: id-named with high cardinality
        if _ID_RE.search(norm):
            if not is_numeric or card_ratio > 0.5:
                return SemanticRole.IDENTITY

        # Non-numeric
        if not is_numeric:
            if card_ratio > 0.5:
                return SemanticRole.IDENTITY
            return SemanticRole.DIMENSION

        # Numeric → sub-classify
        # RATE: bounded 0-1 or percentage-like name
        if is_bounded_01:
            return SemanticRole.RATE
        if _RATE_RE.search(norm):
            return SemanticRole.RATE

        # COUNT: integer-valued count-like
        if _COUNT_RE.search(norm) and is_integer_valued:
            return SemanticRole.COUNT

        # Low cardinality numeric → ordinal dimension
        if n_rows >= 50 and unique_count <= 10 and card_ratio < 0.05:
            return SemanticRole.DIMENSION

        return SemanticRole.MEASURE

    def _classify_behavioral_role(
        self,
        name: str,
        norm: str,
        is_numeric: bool,
        semantic_role: SemanticRole,
        card_ratio: float,
    ) -> BehavioralRole:
        """Classify the fine-grained behavioral role."""
        if semantic_role == SemanticRole.TIME:
            if "timestamp" in name.lower() or "datetime" in name.lower():
                return BehavioralRole.TIMESTAMP
            return BehavioralRole.DATE

        if semantic_role == SemanticRole.IDENTITY:
            if card_ratio >= 0.95:
                return BehavioralRole.IDENTIFIER
            if _ENTITY_ID_SUFFIX.search(name):
                return BehavioralRole.ENTITY_REFERENCE
            return BehavioralRole.INTERNAL_KEY

        if semantic_role == SemanticRole.DIMENSION:
            # Check for geo patterns
            if re.search(r"\b(lat|latitude)\b", norm):
                return BehavioralRole.LATITUDE
            if re.search(r"\b(lng|lon|longitude|long_)\b", norm):
                return BehavioralRole.LONGITUDE
            if re.search(r"\b(country|nation|region)\b", norm):
                return BehavioralRole.COUNTRY
            if re.search(r"\b(state|province|territory)\b", norm):
                return BehavioralRole.STATE
            if re.search(r"\b(city|town|locality)\b", norm):
                return BehavioralRole.CITY
            if re.search(r"\b(zip|postal|postcode|pin)\b", norm):
                return BehavioralRole.POSTAL_CODE
            # Check for status/boolean
            if re.search(r"\b^is_|^has_|_flag$|_yn$|(active|enabled|status)\b", name.lower()):
                return BehavioralRole.STATUS if "status" in name.lower() else BehavioralRole.BOOLEAN_FLAG
            return BehavioralRole.CATEGORY

        if semantic_role == SemanticRole.RATE:
            return BehavioralRole.RATE_MEASURE

        if semantic_role == SemanticRole.COUNT:
            return BehavioralRole.COUNT_MEASURE

        if semantic_role == SemanticRole.MEASURE:
            # Determine additive type based on name and stats
            if any(t in name.lower() for t in ("age", "temperature", "score", "rating", "gpa")):
                return BehavioralRole.NON_ADDITIVE_MEASURE
            if any(t in name.lower() for t in ("balance", "inventory", "stock", "level")):
                return BehavioralRole.SEMI_ADDITIVE_MEASURE
            if any(t in name.lower() for t in ("duration", "latency", "days", "hours", "tenure")):
                return BehavioralRole.DURATION
            return BehavioralRole.ADDITIVE_MEASURE

        return BehavioralRole.UNKNOWN

    def _classify_business_category(
        self, norm: str
    ) -> tuple[BusinessCategory, str]:
        """Classify business category and polarity from column name."""
        for cat, pattern, polarity in _CATEGORY_PATTERNS:
            if re.search(pattern, norm, re.I):
                return cat, polarity
        return BusinessCategory.UNKNOWN, "higher_is_better"

    def _compute_confidence(
        self,
        semantic_role: SemanticRole,
        behavioral_role: BehavioralRole,
        card_ratio: float,
        profile: RawColumnProfile,
    ) -> float:
        """Compute classification confidence (0-1).

        Strong classifiers:
          - TIME with datetime dtype → 0.97
          - IDENTITY with _id suffix + high cardinality → 0.95
          - Measure with clear name pattern → 0.90+

        Weak classifiers:
          - No name pattern match → 0.60
          - Conflicting signals → 0.50-0.70
        """
        base = 0.85  # Default confidence

        # Boost for strong signals
        if semantic_role == SemanticRole.TIME:
            if any(t in profile.dtype for t in ("Date", "Datetime")):
                base = 0.97
        elif semantic_role == SemanticRole.IDENTITY:
            if _ENTITY_ID_SUFFIX.search(profile.name):
                base = 0.95
            elif card_ratio > 0.95:
                base = 0.92
        elif semantic_role in (SemanticRole.RATE, SemanticRole.COUNT):
            base = 0.90

        # Penalize for ambiguity
        if behavioral_role == BehavioralRole.UNKNOWN:
            base -= 0.15
        if profile.cardinality.null_pct > 30:
            base -= 0.10

        return max(0.30, min(0.99, base))


# Singleton
semantic_classifier = SemanticClassifier()
