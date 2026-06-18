"""
intelligence/aggregation_engine.py — Aggregation suitability & metric semantics

Determines which aggregations are semantically valid for each column:
  - sum_allowed / avg_allowed / min_allowed / max_allowed / count_allowed
  - additive_type (additive / semi_additive / non_additive)
  - recommended_aggregation + rationale

Rules:
  - Revenue / cost / volume → SUM (additive)
  - Balance / inventory → SUM across products, NOT across time (semi-additive)
  - Age / temperature / score → AVG only (non-additive)
  - Rate / ratio / percentage → MEDIAN if skewed, else MEAN
  - ID columns → COUNT_DISTINCT only
  - Dimensions → COUNT only

No LLM calls.
"""

from __future__ import annotations

import logging
import re

from services.profiling.models import RawColumnProfile

from .models import (
    SemanticRole,
    BehavioralRole,
    AdditiveType,
    AggregationSuitability,
    ColumnIntelligence,
)

logger = logging.getLogger(__name__)


class AggregationEngine:
    """Determines aggregation suitability and metric semantics."""

    # Name patterns that suggest specific metric types
    _TOTAL_PATTERN = re.compile(
        r"\b(revenue|sales|cost|expense|amount|value|profit|income|gmv|total)\b", re.I
    )
    _PRICE_PATTERN = re.compile(
        r"\b(price|aov|arpu|arpc|ltv|cac|average|avg|salary|wage)\b", re.I
    )
    _SEMI_ADDITIVE_PATTERN = re.compile(
        r"\b(balance|inventory|stock|level|headcount)\b", re.I
    )
    _NON_ADDITIVE_PATTERN = re.compile(
        r"\b(age|temperature|score|rating|gpa|index|elevation)\b", re.I
    )

    def compute(
        self,
        profile: RawColumnProfile,
        semantic_role: SemanticRole,
        behavioral_role: BehavioralRole,
    ) -> AggregationSuitability:
        """Compute aggregation suitability for a column.

        Args:
            profile: Raw column profile (stats, cardinality)
            semantic_role: Classified semantic role
            behavioral_role: Classified behavioral role

        Returns:
            AggregationSuitability with rules for this column.
        """
        name = profile.name.lower()
        stats = profile.stats

        # ── Default: all disabled ──
        result = AggregationSuitability(
            sum_allowed=False,
            avg_allowed=False,
            min_allowed=True,
            max_allowed=True,
            count_allowed=True,
            count_distinct_allowed=True,
            median_allowed=True,
            additive_type=AdditiveType.NON_ADDITIVE,
            recommended_aggregation="count",
            aggregation_rationale="Default: count only",
        )

        # ── By Semantic Role ──
        if semantic_role == SemanticRole.IDENTITY:
            result.sum_allowed = False
            result.avg_allowed = False
            result.count_allowed = True
            result.count_distinct_allowed = True
            result.recommended_aggregation = "count_distinct"
            result.aggregation_rationale = f"'{profile.name}' is an identifier; only distinct counts are meaningful"
            return result

        if semantic_role == SemanticRole.TIME:
            result.count_allowed = True
            result.count_distinct_allowed = True
            result.recommended_aggregation = "min"
            result.aggregation_rationale = f"'{profile.name}' is a time column; min/max show date range"
            return result

        if semantic_role == SemanticRole.DIMENSION:
            result.count_allowed = True
            result.count_distinct_allowed = True
            result.recommended_aggregation = "count"
            result.aggregation_rationale = f"'{profile.name}' is a dimension; only counts are meaningful"
            return result

        # ── Numeric: Measure / Rate / Count ──
        if not stats:
            return result

        skewness = abs(stats.skewness or 0.0)
        cv = stats.cv or 0.0

        # ── By Behavioral Role (metric semantics) ──
        if behavioral_role == BehavioralRole.RATE_MEASURE:
            result.sum_allowed = False
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.NON_ADDITIVE
            if skewness > 1.5:
                result.recommended_aggregation = "median"
                result.aggregation_rationale = f"Rate column with skew {skewness:.1f}; median is robust"
            else:
                result.recommended_aggregation = "mean"
                result.aggregation_rationale = f"Rate column; mean is appropriate (skew={skewness:.1f})"
            return result

        if behavioral_role == BehavioralRole.COUNT_MEASURE:
            result.sum_allowed = True
            result.avg_allowed = True
            result.additive_type = AdditiveType.ADDITIVE
            result.recommended_aggregation = "sum"
            result.aggregation_rationale = "Count column; sum gives total volume"
            return result

        if behavioral_role == BehavioralRole.NON_ADDITIVE_MEASURE:
            result.sum_allowed = False
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.NON_ADDITIVE
            result.recommended_aggregation = "mean" if skewness < 1.5 else "median"
            result.aggregation_rationale = f"Non-additive measure; use average (skew={skewness:.1f})"
            return result

        if behavioral_role == BehavioralRole.SEMI_ADDITIVE_MEASURE:
            result.sum_allowed = True
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.SEMI_ADDITIVE
            result.recommended_aggregation = "last"
            result.aggregation_rationale = "Semi-additive measure; use LAST for point-in-time, SUM for totals"
            return result

        if behavioral_role == BehavioralRole.DURATION:
            result.sum_allowed = True
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.ADDITIVE if cv > 0.5 else AdditiveType.SEMI_ADDITIVE
            result.recommended_aggregation = "median" if skewness > 1.5 else "mean"
            result.aggregation_rationale = f"Duration column; mean/median depending on skew ({skewness:.1f})"
            return result

        # ── Default: MEASURE (generic numeric) ──
        # Check name patterns for aggregation hints
        if self._TOTAL_PATTERN.search(name):
            result.sum_allowed = True
            result.avg_allowed = True
            result.additive_type = AdditiveType.ADDITIVE
            result.recommended_aggregation = "sum"
            result.aggregation_rationale = f"'{profile.name}' looks like a total; sum is recommended"
        elif self._PRICE_PATTERN.search(name):
            result.sum_allowed = True
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.ADDITIVE
            result.recommended_aggregation = "median" if skewness > 1.5 else "mean"
            result.aggregation_rationale = f"Price-like column; {'median (skewed)' if skewness > 1.5 else 'mean'} is appropriate"
        else:
            # Generic measure
            result.sum_allowed = True
            result.avg_allowed = True
            result.median_allowed = True
            result.additive_type = AdditiveType.ADDITIVE
            if cv > 0.8:
                result.recommended_aggregation = "sum"
                result.aggregation_rationale = f"High variance (CV={cv:.1f}); sum captures total"
            else:
                result.recommended_aggregation = "mean"
                result.aggregation_rationale = f"Stable measure (CV={cv:.1f}); mean is appropriate"

        return result


# Singleton
aggregation_engine = AggregationEngine()
