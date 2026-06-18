"""
Participating Entity Discovery
================================

Identifies entities that participate in the primary business object's transactions.

For example, in an orders table:
  - Order is the primary object
  - Product participates (referenced via product_id)
  - Customer participates (referenced via customer_id)

Scoring model:
  participation_score = 0.60 * naming_evidence + 0.40 * entity_confidence

This replaces the old multiplicative model (naming_evidence * entity_confidence)
which was too punitive for entities with moderate entity_confidence.

Naming evidence is derived from SignalEngine patterns (single source of truth),
not duplicated here. Abbreviation expansion reuses the grouping engine's
abbreviation dictionary for indirect matches.
"""

import logging
import re
from typing import Dict, List, Optional

from .models import DiscoveredEntity, ParticipatingEntity, PrimaryObjectResult
from .signal_engine import signal_engine
from .grouping_engine import ABBREVIATIONS

logger = logging.getLogger(__name__)

PARTICIPATION_MIN = 0.50
NAMING_WEIGHT = 0.60
ENTITY_CONF_WEIGHT = 0.40

_GENERIC_SUFFIXES = ["_id", "_code", "_number", "_ref", "_key", "_fk", "fk_"]


class ParticipationDiscovery:
    """
    Discovers entities that participate in the primary object's domain.

    Uses a weighted sum model (not multiplicative) so that strong naming signals
    are not crushed by moderate entity validation confidence.

    Naming evidence pipeline (in order):
    1. Explicit column_naming_conf mapping (caller-supplied)
    2. Direct SignalEngine name pattern match
    3. Abbreviation expansion + SignalEngine pattern match
    4. Substring match (entity label in column name)
    5. Generic suffix detection (_id, _code, _ref, etc.)
    6. Fallback (0.30)
    """

    def __init__(self):
        self.min_score = PARTICIPATION_MIN
        self.naming_weight = NAMING_WEIGHT
        self.entity_conf_weight = ENTITY_CONF_WEIGHT
        self._abbreviations = ABBREVIATIONS

    def discover(
        self,
        entities: List[DiscoveredEntity],
        primary_object: PrimaryObjectResult,
        column_naming_conf: Optional[Dict[str, float]] = None,
    ) -> List[ParticipatingEntity]:
        """
        Discover entities that participate in the primary object's domain.

        Args:
            entities: All validated entities from entity discovery pipeline
            primary_object: The primary business object result
            column_naming_conf: Optional mapping of column_name to naming
                pattern confidence (from signal_engine name pattern match).
                If provided, this is used as-is with highest priority.

        Returns:
            List of ParticipatingEntity objects, sorted by participation_score desc
        """
        if not entities or not primary_object.is_valid:
            return []

        primary_label = primary_object.label.lower()
        participants: List[ParticipatingEntity] = []

        for entity in entities:
            entity_label_lower = entity.label.lower()

            # Skip the primary object itself
            if entity_label_lower == primary_label:
                continue

            # Only entities with an identifier column can participate
            if not entity.identifier_column:
                continue

            # Entities must have at least minimum validation confidence
            if entity.entity_confidence < 0.10:
                continue

            id_col = entity.identifier_column
            naming_evidence = self._get_naming_evidence(id_col, entity.label, column_naming_conf)
            entity_confidence = entity.entity_confidence

            participation_score = (
                self.naming_weight * naming_evidence + self.entity_conf_weight * entity_confidence
            )
            participation_score = round(min(1.0, max(0.0, participation_score)), 3)

            is_valid = participation_score >= self.min_score

            participants.append(
                ParticipatingEntity(
                    label=entity.label,
                    identifier_column=id_col,
                    confidence=participation_score,
                    participation_score=participation_score,
                    entity_confidence=entity_confidence,
                    naming_evidence=round(naming_evidence, 3),
                    is_valid=is_valid,
                )
            )

        participants.sort(key=lambda p: p.participation_score, reverse=True)
        return participants

    def _get_naming_evidence(
        self,
        column_name: str,
        entity_label: str,
        column_naming_conf: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Get naming evidence for how well the column name identifies the entity.

        Pipeline:
        1. Explicit column_naming_conf mapping (highest priority)
        2. Direct SignalEngine name pattern match
        3. Abbreviation expansion + SignalEngine match (discounted)
        4. Substring match (entity_label in column_name)
        5. Generic suffix detection (_id, _code, _ref, etc.)
        6. Fallback (0.30)
        """
        # 1. Explicit mapping — caller knows best
        if column_naming_conf and column_name in column_naming_conf:
            return column_naming_conf[column_name]

        name_lower = column_name.lower()
        entity_lower = entity_label.lower()

        # 2. Direct SignalEngine match
        hint = self._match_via_signal_engine(column_name, entity_lower)
        if hint is not None:
            return hint

        # 3. Abbreviation expansion
        expanded = self._expand_abbreviation(column_name)
        if expanded:
            hint = self._match_via_signal_engine(expanded, entity_lower)
            if hint is not None:
                # Discount for indirect match via abbreviation
                return round(hint * 0.85, 3)
            # Even without SignalEngine hint, check expanded name for substring
            if entity_lower in expanded.lower():
                return 0.55

        # 4. Substring match on original name
        if entity_lower in name_lower:
            return 0.55

        # 5. Generic suffix patterns (common FK-style endings)
        if self._matches_generic_suffix(name_lower):
            return 0.60

        return 0.30

    def _match_via_signal_engine(self, column_name: str, entity_label: str) -> Optional[float]:
        """
        Check if SignalEngine's name patterns produce an entity hint
        matching the given entity_label. Returns confidence if matched.
        """
        _, hint, conf, _ = signal_engine._classify_name(column_name)
        if hint and hint == entity_label:
            return conf
        return None

    def _expand_abbreviation(self, column_name: str) -> Optional[str]:
        """
        Expand known abbreviations in the column name prefix.

        Examples:
            cust_id     → customer_id
            emp_name    → employee_name
            prod_code   → product_code
            vend_ref    → vendor_ref
        """
        name = column_name.lower()
        parts = name.split("_")
        if not parts:
            return None
        prefix = parts[0]
        if prefix in self._abbreviations:
            expanded_prefix = self._abbreviations[prefix]
            rest = "_".join(parts[1:])
            if rest:
                return f"{expanded_prefix}_{rest}"
            return expanded_prefix
        return None

    def _matches_generic_suffix(self, column_name: str) -> bool:
        """Check if column name matches common foreign-key-style suffixes."""
        for suffix in _GENERIC_SUFFIXES:
            if suffix in column_name:
                return True
        return False


participation_discovery = ParticipationDiscovery()

__all__ = [
    "ParticipationDiscovery",
    "participation_discovery",
    "PARTICIPATION_MIN",
    "NAMING_WEIGHT",
    "ENTITY_CONF_WEIGHT",
]
