"""
Primary Business Object Discovery
===================================

Determines what the dataset is "about" at a table level.

Scoring model:
  - TABLE_NAME (0.10): entity label matches table/file name
  - COLUMN_DOMINANCE (0.45): entity has the strongest structural presence
  - ENTITY_CONFIDENCE (0.45): entity validation confidence

The entity with the highest weighted score is the primary business object.
"""

import logging
import re
from typing import List, Optional

from .models import DiscoveredEntity, PrimaryObjectResult, AlternativeCandidate, AmbiguityAnalysis, EvidenceTraceItem

logger = logging.getLogger(__name__)

PRIMARY_OBJECT_WEIGHTS = {
    "TABLE_NAME": 0.10,
    "COLUMN_DOMINANCE": 0.45,
    "ENTITY_CONFIDENCE": 0.45,
}

PRIMARY_OBJECT_MIN_CONFIDENCE = 0.30

# Ambiguity thresholds
# When top_2_gap < AMBIGUITY_LOW, ambiguity is high (close contenders)
AMBIGUITY_LOW_GAP = 0.12  # gap < 12% → high ambiguity
AMBIGUITY_MEDIUM_GAP = 0.25  # gap < 25% → medium ambiguity
# else → low ambiguity


class PrimaryObjectDiscovery:
    """
    Identifies the primary business object in a dataset.

    Uses a weighted scoring model to determine which discovered entity
    represents the main subject of the dataset.
    """

    def __init__(self):
        self.weights = PRIMARY_OBJECT_WEIGHTS
        self.min_confidence = PRIMARY_OBJECT_MIN_CONFIDENCE

    def discover(
        self,
        entities: List[DiscoveredEntity],
        table_name: str = "",
        total_columns: int = 0,
    ) -> PrimaryObjectResult:
        """
        Identify the primary business object from discovered entities.

        Args:
            entities: List of validated entities from entity discovery
            table_name: Table/file name for context
            total_columns: Total number of columns in the dataset

        Returns:
            PrimaryObjectResult with the winning entity and score breakdown
        """
        if not entities:
            return PrimaryObjectResult(
                label="unknown",
                entity_label="unknown",
                evidence_strength=0.0,
                is_valid=False,
            )

        table_label = self._table_name_to_label(table_name) if table_name else ""

        # ── Score ALL entities ───────────────────────────────────────────────
        has_multiple_entities = len([e for e in entities if e.is_valid]) > 1
        scored_candidates: list[dict] = []  # {entity, combined, tn, dom, ec}

        for entity in entities:
            tn_score = self._score_table_name(entity, table_label)
            dom_score = self._score_column_dominance(entity, total_columns)
            ec_score = entity.entity_confidence

            combined = (
                self.weights["TABLE_NAME"] * tn_score
                + self.weights["COLUMN_DOMINANCE"] * dom_score
                + self.weights["ENTITY_CONFIDENCE"] * ec_score
            )

            # Single-entity bonus
            if not has_multiple_entities and entity.is_valid and entity.identifier_column and entity.candidate_confidence > 0.50:
                combined += 0.10

            combined = min(0.99, combined)

            scored_candidates.append({
                "entity": entity,
                "combined": combined,
                "tn": tn_score,
                "dom": dom_score,
                "ec": ec_score,
            })

        # Sort by combined score descending
        scored_candidates.sort(key=lambda c: c["combined"], reverse=True)

        if not scored_candidates:
            return PrimaryObjectResult(
                label="unknown",
                entity_label="unknown",
                evidence_strength=0.0,
                is_valid=False,
            )

        # ── Extract winner ───────────────────────────────────────────────────
        winner = scored_candidates[0]
        best_entity = winner["entity"]
        best_score = winner["combined"]

        # ── Build alternatives ───────────────────────────────────────────────
        alternatives: list[AlternativeCandidate] = []
        for c in scored_candidates[1:]:
            ent = c["entity"]
            # Only include valid entities with non-trivial scores
            if c["combined"] < 0.10:
                continue
            alternatives.append(AlternativeCandidate(
                label=ent.label,
                confidence=round(c["combined"], 3),
                table_name_score=round(c["tn"], 3),
                column_dominance_score=round(c["dom"], 3),
                entity_confidence_score=round(c["ec"], 3),
                evidence_columns=ent.columns,
            ))

        # ── Compute ambiguity ────────────────────────────────────────────────
        ambiguity = self._compute_ambiguity(scored_candidates)

        # ── Evidence trace: per-column contribution breakdown ────────────
        evidence_trace = self._compute_evidence_trace(
            best_entity, total_columns
        )

        return PrimaryObjectResult(
            label=best_entity.label,
            evidence_strength=round(best_score, 3),
            table_name_score=round(winner["tn"], 3),
            column_dominance_score=round(winner["dom"], 3),
            entity_confidence_score=round(winner["ec"], 3),
            entity_label=best_entity.label,
            is_valid=best_score >= self.min_confidence,
            alternatives=alternatives,
            ambiguity=ambiguity,
            evidence_trace=evidence_trace,
        )

    def _compute_ambiguity(
        self, scored_candidates: list[dict]
    ) -> Optional[AmbiguityAnalysis]:
        """Compute ambiguity score from scored candidates.

        Ambiguity is based on the gap between the top two candidates:
          - Large gap → low ambiguity (clear winner)
          - Small gap → high ambiguity (close contenders)

        Score formula:
          ambiguity = 1.0 - (top_gap / AMBIGUITY_MEDIUM_GAP)
          clamped to [0.0, 1.0]

        Only computed when at least 2 valid scored candidates exist.
        """
        if len(scored_candidates) < 2:
            return AmbiguityAnalysis(
                score=0.0,
                level="low",
                top_gap=1.0,
                alternative_count=0,
                has_alternatives=False,
            )

        top_score = scored_candidates[0]["combined"]
        second_score = scored_candidates[1]["combined"]
        top_gap = top_score - second_score

        # Count viable alternatives (confidence > 0.10)
        alt_count = sum(1 for c in scored_candidates[1:] if c["combined"] >= 0.10)

        # Normalize gap to ambiguity score
        # gap >= AMBIGUITY_MEDIUM_GAP → ambiguity 0.0 (clear win)
        # gap <= AMBIGUITY_LOW_GAP → ambiguity 1.0 (maximally ambiguous)
        if top_gap >= AMBIGUITY_MEDIUM_GAP:
            raw = 0.0
        elif top_gap <= AMBIGUITY_LOW_GAP:
            raw = 1.0
        else:
            # Linear interpolation in [LOW_GAP, MEDIUM_GAP]
            raw = 1.0 - (top_gap - AMBIGUITY_LOW_GAP) / (AMBIGUITY_MEDIUM_GAP - AMBIGUITY_LOW_GAP)

        # Determine level
        if raw < 0.30:
            level = "low"
        elif raw < 0.55:
            level = "medium"
        else:
            level = "high"

        return AmbiguityAnalysis(
            score=round(raw, 3),
            level=level,
            top_gap=round(top_gap, 3),
            alternative_count=alt_count,
            has_alternatives=alt_count > 0,
        )

    def _score_table_name(self, entity: DiscoveredEntity, table_label: str) -> float:
        """Score how well the entity label matches the table name.

        Exact match → 1.0
        Entity label appears in table name → 0.8
        No match → 0.0
        """
        if not table_label:
            return 0.0

        entity_lower = entity.label.lower()
        table_lower = table_label.lower()

        if entity_lower == table_lower:
            return 1.0
        if entity_lower in table_lower or table_lower in entity_lower:
            return 0.8
        return 0.0

    def _score_column_dominance(self, entity: DiscoveredEntity, total_columns: int) -> float:
        """Score how structurally dominant this entity is in the dataset.

        Based on:
        - Proportion of columns belonging to this entity
        - Presence of identifier (strong structural anchor)
        - Presence of measures (transactional entities dominate)
        """
        if total_columns <= 0:
            return 0.0

        col_ratio = len(entity.columns) / total_columns

        has_id = entity.role_counts.get("IDENTIFIER", 0) > 0
        id_bonus = 0.15 if has_id else 0.0

        has_measure = any(
            entity.role_counts.get(r, 0) > 0 for r in ("AMOUNT", "QUANTITY", "PERCENTAGE")
        )
        measure_bonus = 0.10 if has_measure else 0.0

        raw = (col_ratio + id_bonus + measure_bonus) * entity.entity_confidence
        return min(1.0, raw)

    def _compute_evidence_trace(
        self,
        entity: DiscoveredEntity,
        total_columns: int,
    ) -> list[EvidenceTraceItem]:
        """Decompose the combined score into per-column contributions.

        The combined score is:
          0.10 * table_name_score  (not per-column)
        + 0.45 * column_dominance_score  (decomposed per column)
        + 0.45 * entity_confidence_score  (not per-column)

        The column_dominance_score decomposes as:
          - Base per column: (1 / total_columns) * entity_confidence
          - Identifier bonus: +0.15 * entity_confidence (distributed equally to ALL columns
            since every column benefits structurally from having an identifier)
          - Measure bonus: +0.10 * entity_confidence (distributed equally to ALL columns)

        Each per-column contribution is weighted by the 0.45 dominance weight.
        The per-column contributions will sum to exactly 0.45 * dom_score.
        """
        if total_columns <= 0 or not entity.columns:
            return []

        ec = entity.entity_confidence
        num_cols = len(entity.columns)
        base_per_col = 1.0 / total_columns * ec

        has_id = entity.role_counts.get("IDENTIFIER", 0) > 0
        has_measure = any(
            entity.role_counts.get(r, 0) > 0 for r in ("AMOUNT", "QUANTITY", "PERCENTAGE")
        )

        # Distribute both bonuses equally across all columns
        # This avoids needing per-column role data that DiscoveredEntity doesn't expose
        id_bonus_per_col = (0.15 * ec) / num_cols if has_id else 0.0
        measure_bonus_per_col = (0.10 * ec) / num_cols if has_measure else 0.0

        trace: list[EvidenceTraceItem] = []
        for col in entity.columns:
            contribution = 0.45 * (base_per_col + id_bonus_per_col + measure_bonus_per_col)
            trace.append(EvidenceTraceItem(
                column_name=col,
                role=self._infer_column_role(col, entity),
                contribution=round(contribution, 4),
            ))

        return trace

    def _infer_column_role(self, column: str, entity: DiscoveredEntity) -> str:
        """Infer the role of a column for evidence trace display."""
        col_lower = column.lower()

        if entity.identifier_column and column == entity.identifier_column:
            return "IDENTIFIER"
        if col_lower.endswith("_id") or col_lower.endswith("_num") or col_lower.endswith("_no"):
            return "IDENTIFIER"
        if any(m in col_lower for m in ("amount", "price", "cost", "revenue", "profit",
                                         "total", "sum", "count", "rate", "fee", "tax",
                                         "value", "score", "premium", "salary", "wage", "income")):
            return "AMOUNT"
        if any(m in col_lower for m in ("name", "title", "label", "desc")):
            return "NAME"
        if any(m in col_lower for m in ("date", "time", "timestamp", "created", "updated")):
            return "DATE"
        if any(m in col_lower for m in ("status", "type", "category", "class")):
            return "STATUS"
        return "ATTRIBUTE"

    def _table_name_to_label(self, table_name: str) -> str:
        """Extract candidate label from table/file name.

        Scans ALL parts for known entity labels, not just the first part.
        Examples:
            orders.csv                 → "order"
            customers_2024             → "customer"
            adv_hard_mixed_claims      → "claim"
        """
        name = table_name.lower()
        name = re.sub(r"\.[a-z]+$", "", name)
        name = re.sub(r"[_\-\.]?(20\d{2}|q[1-4]|v\d+|export|backup)$", "", name)
        parts = re.split(r"[_\-\.\s]+", name)
        if not parts:
            return ""

        singular_overrides = {
            "customers": "customer",
            "users": "user",
            "products": "product",
            "items": "item",
            "orders": "order",
            "transactions": "transaction",
            "employees": "employee",
            "patients": "patient",
            "companies": "company",
            "invoices": "invoice",
            "students": "student",
            "drugs": "drug",
            "participants": "participant",
            "surveys": "survey",
            "claims": "claim",
            "policies": "policy",
            "appointments": "appointment",
            "leads": "lead",
            "accounts": "account",
            "contacts": "contact",
            "suppliers": "supplier",
            "warehouses": "warehouse",
            "merchants": "merchant",
            "enrollments": "enrollment",
            "providers": "provider",
            "opportunities": "opportunity",
            "shipments": "shipment",
        }

        # Scan backwards — the last meaningful part is most specific
        for part in reversed(parts):
            if part in singular_overrides:
                return singular_overrides[part]

        # Fall back to first part
        first = parts[0]
        if first in singular_overrides:
            return singular_overrides[first]
        return parts[-1]


primary_object_discovery = PrimaryObjectDiscovery()

__all__ = [
    "PrimaryObjectDiscovery",
    "primary_object_discovery",
    "PRIMARY_OBJECT_WEIGHTS",
    "PRIMARY_OBJECT_MIN_CONFIDENCE",
]
