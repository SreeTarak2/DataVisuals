"""
Entity Validator — Generic Business Object Validation
=======================================================

Validates EntityCluster objects against generic business object rules.

No entity-specific signatures. Only checks:
- Does the cluster contain an IDENTIFIER?
- Does it have descriptive attributes (NAME, DATE, CATEGORY)?
- Are the roles coherent (no structural conflicts)?
- Is there sufficient evidence to call this a real entity?

Unknown is always a valid output.
"""

import logging
from typing import List

from .models import ColumnRole, EntityCluster, DiscoveredEntity

logger = logging.getLogger(__name__)


_ATTRIBUTE_ROLES = {
    ColumnRole.NAME,
    ColumnRole.DATE,
    ColumnRole.CATEGORY,
    ColumnRole.STATUS,
    ColumnRole.LOCATION,
    ColumnRole.EMAIL,
    ColumnRole.PHONE,
}
_MEASURE_ROLES = {ColumnRole.AMOUNT, ColumnRole.QUANTITY, ColumnRole.PERCENTAGE}
_IDENTIFIER_ROLES = {ColumnRole.IDENTIFIER, ColumnRole.CODE}

# Roles that indicate strong evidence (structural, not generic)
_IDENTIFIER_ROLES = {ColumnRole.IDENTIFIER, ColumnRole.CODE}
_STRONG_ROLES = {
    ColumnRole.IDENTIFIER,
    ColumnRole.NAME,
    ColumnRole.EMAIL,
    ColumnRole.PHONE,
    ColumnRole.AMOUNT,
    ColumnRole.QUANTITY,
    ColumnRole.PERCENTAGE,
    ColumnRole.DATE,
    ColumnRole.TIMESTAMP,
    ColumnRole.LOCATION,
    ColumnRole.BOOLEAN,
    ColumnRole.URL,
    ColumnRole.CODE,
}
_WEAK_ROLES = {ColumnRole.TEXT, ColumnRole.UNKNOWN}

# Source-based candidate confidence weights
_SOURCE_CANDIDATE_CONF = {
    "prefix": 0.75,
    "edit_distance": 0.60,
    "abbreviation": 0.45,
    "table_name": 0.50,
}


class EntityValidator:
    """
    Validates entity clusters using generic business object rules.

    Validation criteria:
    1. IDENTIFIER check: A valid entity must have at least one IDENTIFIER column.
    2. Attribute check: A valid entity should have descriptive attributes.
    3. Coherence check: Roles within the cluster don't structurally conflict.
    4. Size check: Single-column clusters without strong evidence are weakened.
    """

    def validate(self, cluster: EntityCluster) -> DiscoveredEntity:
        """
        Validate an EntityCluster and produce a DiscoveredEntity
        with three separate confidence scores.

        Args:
            cluster: Entity cluster to validate

        Returns:
            DiscoveredEntity with role_confidence, candidate_confidence,
            entity_confidence, and backward-compat confidence
        """
        notes: List[str] = []
        role_counts: dict = self._count_roles(cluster)
        has_id = any(role_counts.get(r.value, 0) > 0 for r in _IDENTIFIER_ROLES)
        has_attr = any(role_counts.get(r.value, 0) > 0 for r in _ATTRIBUTE_ROLES)
        has_measure = any(role_counts.get(r.value, 0) > 0 for r in _MEASURE_ROLES)
        single_col = len(cluster.columns) == 1
        id_col = next((c for c, r in zip(cluster.columns, cluster.roles) if r in _IDENTIFIER_ROLES), None) if has_id else None

        # Clusters sourced from table name fallback are not real business entities.
        # They're just leftover columns grouped under the table name. Never validate them.
        if cluster.source == "table_name":
            notes.append(f"Table name fallback cluster — not a real entity")
            return DiscoveredEntity(
                label=cluster.label,
                columns=cluster.columns,
                identifier_column=None,
                role_counts=role_counts,
                role_confidence=0.10,
                candidate_confidence=0.10,
                entity_confidence=0.10,
                confidence=0.10,
                validation_notes=notes,
                is_valid=False,
            )

        # ── Role confidence: how strong are the ColumnRole assignments? ──
        all_roles = [ColumnRole(r) for r in role_counts.keys()]
        total = len(all_roles) if all_roles else 1
        strong = sum(1 for r in all_roles if r in _STRONG_ROLES)
        weak = sum(1 for r in all_roles if r in _WEAK_ROLES)
        role_confidence = round((strong + (total - weak) * 0.5) / total, 3) if total > 0 else 0.5
        # Clamp: when all roles are strong or present-specific types → high
        role_confidence = min(0.99, max(0.10, role_confidence))

        # ── Candidate confidence: how reliable is the entity label? ──
        source = cluster.source or "prefix"
        candidate_confidence = _SOURCE_CANDIDATE_CONF.get(source, 0.50)

        if source == "prefix":
            candidate_confidence = round(max(candidate_confidence, cluster.confidence * 0.85), 3)
        elif source == "table_name" and cluster.confidence > 0.50:
            candidate_confidence = round((candidate_confidence + cluster.confidence * 0.6) / 2, 3)

        candidate_confidence = min(0.99, max(0.10, candidate_confidence))

        # ── Entity confidence: is this a real business entity? ──
        if not has_id:
            if single_col:
                entity_confidence = 0.15
                notes.append(
                    "Single column without identifier — insufficient evidence to form entity"
                )
            elif has_attr:
                entity_confidence = 0.25
                notes.append("No identifier — attribute fragment, not a complete entity")
            else:
                entity_confidence = 0.10
                notes.append("No identifier or attributes — cannot validate")
        else:
            if has_attr:
                notes.append(
                    "Identifier present with descriptive attributes — strong entity signal"
                )
                base_conf = cluster.confidence
            elif has_measure:
                notes.append("Identifier present with measures — transactional entity")
                base_conf = cluster.confidence * 0.9
            else:
                notes.append("Identifier present but no attributes or measures — weak entity")
                base_conf = cluster.confidence * 0.75

            if single_col:
                notes.append("Single-column entity — limited structural evidence")
                base_conf *= 0.8

            if cluster.confidence < 0.50:
                notes.append("Low cluster confidence — validation is tentative")

            entity_confidence = round(min(0.99, max(0.0, base_conf)), 3)

        is_valid = entity_confidence >= 0.40

        return DiscoveredEntity(
            label=cluster.label,
            columns=cluster.columns,
            identifier_column=id_col,
            role_counts=role_counts,
            role_confidence=role_confidence,
            candidate_confidence=candidate_confidence,
            entity_confidence=entity_confidence,
            confidence=entity_confidence,
            validation_notes=notes,
            is_valid=is_valid,
        )

    def _count_roles(self, cluster: EntityCluster) -> dict:
        counts = {}
        for role in cluster.roles:
            key = role.value
            counts[key] = counts.get(key, 0) + 1
        return counts


entity_validator = EntityValidator()

__all__ = ["EntityValidator", "entity_validator"]
