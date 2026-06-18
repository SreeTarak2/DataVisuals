"""
Fallback Handler - Handles low-confidence cases gracefully
============================================================

When evidence is weak, the system uses safe fallback labels instead of
making potentially incorrect classifications.

Uses ColumnRole (universal structural types) for fallback logic.
EntityCandidate.entity_type is populated via column_role_to_legacy_entity_type
for backward compatibility.
"""

import logging
from typing import Optional, List

from .models import (
    ColumnProfile,
    ColumnRole,
    EntityType,
    EntityCandidate,
    SignalResult,
    column_role_to_legacy_entity_type,
)

logger = logging.getLogger(__name__)


class FallbackHandler:
    """
    Handles cases where column classification is uncertain.

    Provides safe fallback roles with full context.
    """

    # Fallback mapping based on column properties: (data_type, cardinality) -> ColumnRole
    FALLBACK_ROLE_MAP = {
        ("string", "high"): ColumnRole.IDENTIFIER,
        ("string", "low"): ColumnRole.CATEGORY,
        ("string", "medium"): ColumnRole.TEXT,
        ("integer", "any"): ColumnRole.QUANTITY,
        ("decimal", "any"): ColumnRole.AMOUNT,
        ("unknown", "any"): ColumnRole.UNKNOWN,
        ("boolean", "any"): ColumnRole.BOOLEAN,
        ("date", "any"): ColumnRole.DATE,
        ("timestamp", "any"): ColumnRole.TIMESTAMP,
    }

    def __init__(self):
        pass

    def get_fallback(
        self, column: ColumnProfile, reason: str, signals: Optional[List[SignalResult]] = None
    ) -> EntityCandidate:
        """
        Generate a fallback entity candidate.

        Args:
            column: Column profile
            reason: Why fallback is needed
            signals: Optional signals that were attempted

        Returns:
            EntityCandidate with fallback ColumnRole and legacy EntityType
        """
        fallback_role, fallback_legacy_type = self._determine_fallback(column)
        explanation = self._generate_explanation(column, reason, signals)
        confidence = self._calculate_fallback_confidence(column, signals)

        return EntityCandidate(
            column_name=column.name,
            column_role=fallback_role,
            entity_type=fallback_legacy_type,
            confidence=confidence,
            rationale=explanation,
            signals=signals or [],
            needs_review=True,
            alternatives=self._suggest_alternatives(column),
        )

    def _determine_fallback(self, column: ColumnProfile) -> tuple[ColumnRole, EntityType]:
        data_type = column.data_type

        if column.distinct_ratio > 0.9:
            cardinality = "high"
        elif column.distinct_ratio < 0.1:
            cardinality = "low"
        else:
            cardinality = "medium"

        key = (data_type, cardinality)
        if key in self.FALLBACK_ROLE_MAP:
            role = self.FALLBACK_ROLE_MAP[key]
            return role, column_role_to_legacy_entity_type(role)

        generic_key = (data_type, "any")
        if generic_key in self.FALLBACK_ROLE_MAP:
            role = self.FALLBACK_ROLE_MAP[generic_key]
            return role, column_role_to_legacy_entity_type(role)

        return ColumnRole.UNKNOWN, EntityType.GENERIC_ENTITY

    def _generate_explanation(
        self, column: ColumnProfile, reason: str, signals: object = None
    ) -> str:
        """Generate detailed explanation for why fallback was used"""

        parts = [f"Fallback: {reason}"]

        # Add column context
        parts.append(f"Column: {column.name} ({column.data_type})")

        # Add distinct count info
        parts.append(f"Distinct: {column.distinct_count} ({column.distinct_ratio:.1%})")

        # Add null ratio
        parts.append(f"Null: {column.null_ratio:.1%}")

        # Add what would help
        help_text = self._what_would_help(column)
        if help_text:
            parts.append(f"Would help: {help_text}")

        return " | ".join(parts)

    def _what_would_help(self, column: ColumnProfile) -> str:
        """Suggest what additional context would help classification"""

        suggestions = []

        # Suggest based on data type
        if column.data_type == "string" and column.distinct_ratio > 0.5:
            suggestions.append("check actual values for pattern")

        if column.data_type == "string" and not column.sample_values:
            suggestions.append("provide sample values")

        # Suggest based on column name patterns
        col_lower = column.name.lower()
        if not any(p in col_lower for p in ["id", "name", "date", "amount", "type", "status"]):
            suggestions.append("more descriptive column name")

        # Suggest based on sample values
        if column.sample_values:
            # Check if values look like specific patterns
            sample_str = " ".join(str(v) for v in column.sample_values[:3])
            if any(p in sample_str.lower() for p in ["@", "www", "http"]):
                suggestions.append("appears to contain contact/URL data")
            elif any(c.isdigit() for c in sample_str) and any(c.isalpha() for c in sample_str):
                suggestions.append("appears to be alphanumeric code")

        return "; ".join(suggestions[:2])  # Limit to 2 suggestions

    def _calculate_fallback_confidence(self, column: ColumnProfile, signals: list = None) -> float:
        """Calculate confidence for fallback (always low)"""

        base_confidence = 0.25

        # Slightly higher if we had some signals but they were weak
        if signals and len(signals) > 0:
            max_signal_conf = max(s.confidence for s in signals) if signals else 0
            if max_signal_conf > 0.3:
                base_confidence = 0.35

        # Lower if column has issues
        if column.null_ratio > 0.5:
            base_confidence -= 0.1

        return max(0.15, min(0.4, base_confidence))

    def _suggest_alternatives(self, column: ColumnProfile) -> list:
        """Suggest possible entity types for user consideration"""

        suggestions = []

        # Based on column name patterns
        col_lower = column.name.lower()

        if "_id" in col_lower:
            # Could be various entity references
            suggestions.extend(
                [
                    {"entity_type": "Customer", "confidence": 0.4},
                    {"entity_type": "Product", "confidence": 0.4},
                    {"entity_type": "Order", "confidence": 0.3},
                ]
            )

        if "name" in col_lower:
            suggestions.extend(
                [
                    {"entity_type": "Customer", "confidence": 0.5},
                    {"entity_type": "Product", "confidence": 0.5},
                    {"entity_type": "Person", "confidence": 0.4},
                ]
            )

        if "amount" in col_lower or "price" in col_lower:
            suggestions.append({"entity_type": "Metric", "confidence": 0.6})

        # Based on data type
        if column.data_type in ("date", "timestamp"):
            suggestions.append({"entity_type": "TimeDimension", "confidence": 0.5})

        if column.data_type == "boolean":
            suggestions.append({"entity_type": "Indicator", "confidence": 0.5})

        # Deduplicate and limit
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s["entity_type"] not in seen:
                seen.add(s["entity_type"])
                unique_suggestions.append(s)

        return unique_suggestions[:3]

    def is_fallback_acceptable(self, column: ColumnProfile, threshold: float = 0.4) -> bool:
        """
        Check if fallback classification is acceptable.

        Fallbacks are acceptable if:
        - Column has high null ratio (data quality issue)
        - Column has very few distinct values (irrelevant)
        - Data type is unknown
        """
        # Acceptable if high null ratio
        if column.null_ratio > 0.8:
            return True

        # Acceptable if very few distinct values (likely metadata)
        if column.distinct_count <= 2:
            return True

        # Acceptable if unknown type
        if column.data_type == "unknown":
            return True

        return False


# Singleton instance
fallback_handler = FallbackHandler()

__all__ = ["FallbackHandler", "fallback_handler"]
