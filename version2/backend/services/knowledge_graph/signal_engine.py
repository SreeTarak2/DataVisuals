"""
Signal Engine - Extracts classification signals from column data
==================================================================

Multi-signal inference: combines column name patterns, data types,
sample values, cardinality, and domain context to classify columns.

Outputs Layer 1 (ColumnRole) and Layer 2 (SemanticCandidate) information.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple

from .models import (
    ColumnProfile,
    SchemaProfile,
    SignalResult,
    SignalType,
    EntityType,
    ColumnRole,
    EvidenceReliability,
    EvidenceSource,
    SemanticCandidate,
)

logger = logging.getLogger(__name__)

_SEM_STRONG = EvidenceReliability.HIGH
_SEM_MEDIUM = EvidenceReliability.MEDIUM
_SEM_LOW = EvidenceReliability.LOW


class SignalExtractionError(Exception):
    pass


class EntitySignalPatterns:
    """
    Column name pattern definitions for the new two-layer architecture.

    Each pattern maps to (ColumnRole, entity_hint, base_confidence, reliability).
    - ColumnRole: universal structural type (never grows)
    - entity_hint: business label hint (None if no hint), used for SemanticCandidate
    - base_confidence: how confident we are in the role match
    - reliability: evidence source reliability weight
    """

    NAME_PATTERNS: Dict[str, Tuple[ColumnRole, Optional[str], float, EvidenceReliability]] = {
        # ── IDENTIFIER (specific patterns first — ordering matters!) ──
        # Each pattern returns the correct hint for its matched entity
        r"^customer_?id": (ColumnRole.IDENTIFIER, "customer", 0.95, _SEM_STRONG),
        r"^user_?id": (ColumnRole.IDENTIFIER, "user", 0.95, _SEM_STRONG),
        r"^client_?id": (ColumnRole.IDENTIFIER, "client", 0.90, _SEM_STRONG),
        r"^review_?id": (ColumnRole.IDENTIFIER, "review", 0.90, _SEM_STRONG),
        r"^(product|item)_?id": (ColumnRole.IDENTIFIER, "product", 0.95, _SEM_STRONG),
        r"^order_?id": (ColumnRole.IDENTIFIER, "order", 0.95, _SEM_STRONG),
        r"^transaction_?id": (ColumnRole.IDENTIFIER, "transaction", 0.95, _SEM_STRONG),
        r"^(order|transaction)_?id": (ColumnRole.IDENTIFIER, "order", 0.95, _SEM_STRONG),
        r"^(employee|staff)_?id": (ColumnRole.IDENTIFIER, "employee", 0.95, _SEM_STRONG),
        r"^patient_?id": (ColumnRole.IDENTIFIER, "patient", 0.95, _SEM_STRONG),
        r"^doctor_?id": (ColumnRole.IDENTIFIER, "doctor", 0.90, _SEM_STRONG),
        r"^physician_?id": (ColumnRole.IDENTIFIER, "physician", 0.85, _SEM_STRONG),
        r"^(patient|doctor|physician)_?id": (ColumnRole.IDENTIFIER, "patient", 0.95, _SEM_STRONG),
        r"^(company|org|organization)_?id": (ColumnRole.IDENTIFIER, "company", 0.95, _SEM_STRONG),
        r"^student_?id": (ColumnRole.IDENTIFIER, "student", 0.90, _SEM_STRONG),
        r"^participant_?id": (ColumnRole.IDENTIFIER, "participant", 0.90, _SEM_STRONG),
        r"^invoice_?id": (ColumnRole.IDENTIFIER, "invoice", 0.90, _SEM_STRONG),
        r"^shipment_?id": (ColumnRole.IDENTIFIER, "shipment", 0.90, _SEM_STRONG),
        r"^account_?id": (ColumnRole.IDENTIFIER, "account", 0.85, _SEM_STRONG),
        r"^merchant_?id": (ColumnRole.IDENTIFIER, "merchant", 0.80, _SEM_MEDIUM),
        r"^txn_?id": (ColumnRole.IDENTIFIER, "transaction", 0.80, _SEM_MEDIUM),
        r"^enrollment_?id": (ColumnRole.IDENTIFIER, "enrollment", 0.90, _SEM_STRONG),
        r"^course_?id": (ColumnRole.IDENTIFIER, "course", 0.85, _SEM_STRONG),
        r"^visit_?id": (ColumnRole.IDENTIFIER, "visit", 0.90, _SEM_STRONG),
        r"^hospital_?id": (ColumnRole.IDENTIFIER, "hospital", 0.85, _SEM_STRONG),
        r"^(job|task)_?id": (ColumnRole.IDENTIFIER, "task", 0.85, _SEM_STRONG),
        r"^project_?id": (ColumnRole.IDENTIFIER, "project", 0.85, _SEM_STRONG),
        r"^ticket_?id": (ColumnRole.IDENTIFIER, "ticket", 0.90, _SEM_STRONG),
        r"^agent_?id": (ColumnRole.IDENTIFIER, "agent", 0.85, _SEM_STRONG),
        r"^dept_?id": (ColumnRole.IDENTIFIER, "department", 0.85, _SEM_STRONG),
        r"^department_?id": (ColumnRole.IDENTIFIER, "department", 0.85, _SEM_STRONG),
        r"^warehouse_?id": (ColumnRole.IDENTIFIER, "warehouse", 0.80, _SEM_MEDIUM),
        r"^supplier_?id": (ColumnRole.IDENTIFIER, "supplier", 0.85, _SEM_STRONG),
        r"^(drug|medication)_?id": (ColumnRole.IDENTIFIER, "drug", 0.85, _SEM_STRONG),
        r"^claim_?id": (ColumnRole.IDENTIFIER, "claim", 0.85, _SEM_STRONG),
        r"^policy_?id": (ColumnRole.IDENTIFIER, "policy", 0.85, _SEM_STRONG),
        r"^appointment_?id": (ColumnRole.IDENTIFIER, "appointment", 0.85, _SEM_STRONG),
        r"^lead_?id": (ColumnRole.IDENTIFIER, "lead", 0.80, _SEM_STRONG),
        r"^provider_?id": (ColumnRole.IDENTIFIER, "provider", 0.80, _SEM_STRONG),
        r"^opportunity_?id": (ColumnRole.IDENTIFIER, "opportunity", 0.80, _SEM_STRONG),
        r"^owner_?id": (ColumnRole.IDENTIFIER, "owner", 0.80, _SEM_STRONG),
        r"^(survey|study)_?id": (ColumnRole.IDENTIFIER, "survey", 0.85, _SEM_STRONG),
        r"^sku$": (ColumnRole.CODE, "product", 0.90, _SEM_STRONG),
        r"^uuid$": (ColumnRole.IDENTIFIER, None, 0.80, _SEM_STRONG),
        r"^code$": (ColumnRole.CODE, None, 0.70, _SEM_MEDIUM),
        # ── INDEX / UNNAMED (before generic ID to prevent false positives on index columns) ──
        r"^unnamed": (ColumnRole.TEXT, None, 0.90, _SEM_STRONG),
        # ── Generic ID (catch-all — after specific patterns) ──
        r"^.+\_id$": (ColumnRole.IDENTIFIER, None, 0.90, _SEM_STRONG),
        r"^id$": (ColumnRole.IDENTIFIER, None, 0.70, _SEM_STRONG),
        # ── NAME (specific patterns first) ──
        r"^customer_?name": (ColumnRole.NAME, "customer", 0.90, _SEM_STRONG),
        r"^user_?name": (ColumnRole.NAME, "user", 0.90, _SEM_STRONG),
        r"^client_?name": (ColumnRole.NAME, "client", 0.85, _SEM_STRONG),
        r"^(product|item)_?name": (ColumnRole.NAME, "product", 0.90, _SEM_STRONG),
        r"^(company|org|organization)_?name": (ColumnRole.NAME, "company", 0.90, _SEM_STRONG),
        r"^(employee|staff)_?name": (ColumnRole.NAME, "employee", 0.90, _SEM_STRONG),
        r"^(patient|doctor)_?name": (ColumnRole.NAME, "patient", 0.90, _SEM_STRONG),
        r"^student_?name": (ColumnRole.NAME, "student", 0.85, _SEM_STRONG),
        r"^participant_?name": (ColumnRole.NAME, "participant", 0.85, _SEM_STRONG),
        r"^(drug|medication)_?name": (ColumnRole.NAME, "drug", 0.90, _SEM_STRONG),
        r"^(survey|study)_?name": (ColumnRole.NAME, "survey", 0.85, _SEM_STRONG),
        r"^(brand|product)_?name": (ColumnRole.NAME, "product", 0.90, _SEM_STRONG),
        # ── Generic name (catch-all — after specific patterns) ──
        r".+_name$": (ColumnRole.NAME, None, 0.85, _SEM_STRONG),
        # ── DATE / TIME ──
        r"_date$": (ColumnRole.DATE, None, 0.95, _SEM_STRONG),
        r"_time$": (ColumnRole.TIMESTAMP, None, 0.90, _SEM_STRONG),
        r"_at$": (ColumnRole.TIMESTAMP, None, 0.85, _SEM_STRONG),
        r"^(created|updated|modified|deleted)_?at": (ColumnRole.TIMESTAMP, None, 0.90, _SEM_STRONG),
        r"^(start|end|expire|due)_?date": (ColumnRole.DATE, None, 0.90, _SEM_STRONG),
        r"^dob$": (ColumnRole.DATE, None, 0.85, _SEM_STRONG),
        # ── AMOUNT / QUANTITY / PERCENTAGE ──
        r"(amount|price|cost|revenue|profit|sales|income)": (
            ColumnRole.AMOUNT,
            None,
            0.95,
            _SEM_STRONG,
        ),
        r"(total|sum|subtotal)": (ColumnRole.AMOUNT, None, 0.90, _SEM_STRONG),
        r"(count|quantity|qty|num|number_of)": (ColumnRole.QUANTITY, None, 0.90, _SEM_STRONG),
        r"(rate|percentage|pct|percent)": (ColumnRole.PERCENTAGE, None, 0.90, _SEM_STRONG),
        r"(balance|discount|tax|tip)": (ColumnRole.AMOUNT, None, 0.85, _SEM_MEDIUM),
        r"(avg|average|mean|median)": (ColumnRole.AMOUNT, None, 0.85, _SEM_MEDIUM),
        # ── LOCATION ──
        r"(region|territory|zone)": (ColumnRole.LOCATION, None, 0.90, _SEM_MEDIUM),
        r"(country|nation|state|province)": (ColumnRole.LOCATION, None, 0.95, _SEM_STRONG),
        r"(city|town|village|address)": (ColumnRole.LOCATION, None, 0.90, _SEM_STRONG),
        r"(postal|zip|pin)": (ColumnRole.LOCATION, None, 0.85, _SEM_MEDIUM),
        r"(lat|latitude|lon|longitude)": (ColumnRole.LOCATION, None, 0.95, _SEM_STRONG),
        # ── STATUS / CATEGORY ──
        r"status": (ColumnRole.STATUS, None, 0.90, _SEM_MEDIUM),
        r"type$": (ColumnRole.CATEGORY, None, 0.80, _SEM_MEDIUM),
        r"category": (ColumnRole.CATEGORY, None, 0.90, _SEM_STRONG),
        r"(class|grade|level|tier|rank)": (ColumnRole.CATEGORY, None, 0.85, _SEM_MEDIUM),
        # ── BOOLEAN ──
        r"^is_": (ColumnRole.BOOLEAN, None, 0.95, _SEM_STRONG),
        r"^has_": (ColumnRole.BOOLEAN, None, 0.95, _SEM_STRONG),
        r"_flag$": (ColumnRole.BOOLEAN, None, 0.90, _SEM_STRONG),
        r"_yn$": (ColumnRole.BOOLEAN, None, 0.85, _SEM_MEDIUM),
        r"^(active|enabled|verified|approved|visible)": (
            ColumnRole.BOOLEAN,
            None,
            0.85,
            _SEM_MEDIUM,
        ),
        # ── CONTACT ──
        r"(email|mail)": (ColumnRole.EMAIL, None, 0.95, _SEM_STRONG),
        r"(phone|mobile|fax|telephone)": (ColumnRole.PHONE, None, 0.95, _SEM_STRONG),
        # ── ORGANIZATION HINTS ──
        r"(company|enterprise|business|vendor|supplier)": (
            ColumnRole.TEXT,
            "company",
            0.70,
            _SEM_MEDIUM,
        ),
        # ── MISCELLANEOUS ──
        r"(department|dept|team|unit)": (ColumnRole.CATEGORY, None, 0.85, _SEM_MEDIUM),
        r"(location|store|warehouse|facility|branch)": (
            ColumnRole.LOCATION,
            None,
            0.85,
            _SEM_MEDIUM,
        ),
        r"(code|icd|sku|isbn|barcode)": (ColumnRole.CODE, None, 0.85, _SEM_MEDIUM),
        # ── URL / LINK ──
        r"(link|url|href|website)": (ColumnRole.URL, None, 0.90, _SEM_STRONG),
    }

    TYPE_ROLE_MAP: Dict[str, Tuple[ColumnRole, float, EvidenceReliability]] = {
        "uuid": (ColumnRole.IDENTIFIER, 0.80, _SEM_STRONG),
        "integer": (ColumnRole.QUANTITY, 0.60, _SEM_MEDIUM),
        "decimal": (ColumnRole.AMOUNT, 0.75, _SEM_MEDIUM),
        "boolean": (ColumnRole.BOOLEAN, 0.90, _SEM_STRONG),
        "date": (ColumnRole.DATE, 0.95, _SEM_STRONG),
        "timestamp": (ColumnRole.TIMESTAMP, 0.95, _SEM_STRONG),
        "string": (ColumnRole.TEXT, 0.50, _SEM_LOW),
    }

    TYPE_PATTERNS: Dict[str, Tuple[List[EntityType], float]] = {
        "uuid": ([EntityType.GENERIC_REFERENCE], 0.80),
        "integer": ([EntityType.METRIC, EntityType.QUANTITY], 0.60),
        "decimal": ([EntityType.METRIC, EntityType.AMOUNT], 0.75),
        "string": ([EntityType.CLASSIFICATION, EntityType.GENERIC_ENTITY], 0.50),
        "boolean": ([EntityType.INDICATOR], 0.90),
        "date": ([EntityType.TIMEDIMENSION], 0.95),
        "timestamp": ([EntityType.TIMEDIMENSION], 0.95),
    }

    VALUE_ROLE_MAP: Dict[str, Tuple[ColumnRole, str, List[str]]] = {
        "status_color": (
            ColumnRole.CATEGORY,
            "status",
            ["red", "green", "blue", "yellow", "purple"],
        ),
        "status_active": (ColumnRole.STATUS, "status", ["active", "inactive", "pending"]),
        # type_simple: use exact match to avoid matching integer ID columns
        "type_simple": (ColumnRole.CATEGORY, "type", ["A", "B", "C", "1", "2", "3"]),
        "code_medical": (ColumnRole.CODE, "code", ["ICD", "CPT", "ICD10"]),
    }

    VALUE_PATTERNS: Dict[str, Tuple[str, List[str], EntityType]] = {
        "status_color": (
            "status",
            ["red", "green", "blue", "yellow", "purple"],
            EntityType.CLASSIFICATION,
        ),
        "status_active": ("status", ["active", "inactive", "pending"], EntityType.STATUS),
        "type_simple": ("type", ["A", "B", "C", "1", "2", "3"], EntityType.CLASSIFICATION),
        "code_medical": ("code", ["ICD", "CPT", "ICD10"], EntityType.CODE),
    }


_ENTITY_HINT_TO_LEGACY_TYPE = {
    "customer": EntityType.CUSTOMER,
    "product": EntityType.PRODUCT,
    "order": EntityType.ORDER,
    "employee": EntityType.EMPLOYEE,
    "patient": EntityType.PATIENT,
    "company": EntityType.COMPANY,
}


def _hint_to_legacy_type(hint: Optional[str]) -> Optional[EntityType]:
    if hint is None:
        return None
    hint_lower = hint.lower()
    for key, etype in _ENTITY_HINT_TO_LEGACY_TYPE.items():
        if key in hint_lower:
            return etype
    return None


class SignalEngine:
    """
    Extracts classification signals from column data.

    Multi-signal approach:
    1. Column name patterns (highest weight)
    2. Data type analysis
    3. Sample value inspection
    4. Cardinality analysis
    5. Domain context (table name, neighbors)
    """

    def __init__(self):
        self.patterns = EntitySignalPatterns()

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Column classification endpoint — produces Layer 1 + Layer 2 output
    # ──────────────────────────────────────────────────────────────────────────

    def classify_column(
        self, column: ColumnProfile, schema: Optional[SchemaProfile] = None
    ) -> Tuple[ColumnRole, List[SemanticCandidate], List[EvidenceSource]]:
        """
        ColumnRole classification + SemanticCandidate extraction.

        Args:
            column: Column profile
            schema: Optional schema context for table-level hints

        Returns:
            (column_role, semantic_candidates, evidence_sources)
        """
        evidence: List[EvidenceSource] = []
        candidates: List[SemanticCandidate] = []
        role_votes: Dict[str, float] = {}
        role_vote_detail: Dict[str, List[float]] = {}

        # Signal 1: Column name pattern
        name_role, name_hint, name_conf, name_rel = self._classify_name(column.name)
        evidence.append(
            EvidenceSource(
                source_type="column_name",
                value=column.name,
                reliability=name_rel,
                confidence=name_conf,
                detail=f"Name pattern → {name_role.value}",
            )
        )
        role_vote_detail.setdefault(name_role.value, []).append(name_conf)

        if name_hint:
            candidates.append(
                SemanticCandidate(label=name_hint, confidence=name_conf, source="column_prefix")
            )

        # Signal 2: Data type
        type_role, type_conf, type_rel = self._classify_type(column)
        evidence.append(
            EvidenceSource(
                source_type="data_type",
                value=column.data_type,
                reliability=type_rel,
                confidence=type_conf,
                detail=f"Data type '{column.data_type}' → {type_role.value}",
            )
        )
        role_vote_detail.setdefault(type_role.value, []).append(type_conf)

        # Signal 3: Sample values
        value_role, value_conf, value_rel, value_detail = self._classify_values(column)
        if value_role:
            evidence.append(
                EvidenceSource(
                    source_type="value_pattern",
                    value=value_detail or "pattern_match",
                    reliability=value_rel,
                    confidence=value_conf,
                    detail=f"Value pattern → {value_role.value}",
                )
            )
            role_vote_detail.setdefault(value_role.value, []).append(value_conf)

        # Signal 4: Cardinality
        card_role, card_conf, card_rel, card_detail = self._classify_cardinality(column)
        evidence.append(
            EvidenceSource(
                source_type="cardinality",
                value=card_detail,
                reliability=card_rel,
                confidence=card_conf,
                detail=f"Cardinality analysis → {card_role.value}",
            )
        )
        role_vote_detail.setdefault(card_role.value, []).append(card_conf)

        # Signal 5: Domain context
        if schema:
            ctx_candidates = self._classify_context(column, schema)
            for cc in ctx_candidates:
                evidence.append(
                    EvidenceSource(
                        source_type="table_name",
                        value=schema.table_name,
                        reliability=EvidenceReliability.MEDIUM,
                        confidence=cc.confidence,
                        detail=f"Table context → entity hint '{cc.label}'",
                    )
                )
                candidates.append(cc)

        # Boost the name signal vote for specific, high-confidence name patterns.
        # When a name pattern explicitly matches (e.g., _id → IDENTIFIER, _name → NAME)
        # with >= 0.80 confidence, count its vote twice to prevent type/cardinality
        # signals from overriding it. This keeps 'drug_name' as NAME even though
        # high cardinality would suggest IDENTIFIER.
        if name_conf >= 0.80 and name_role not in (ColumnRole.TEXT, ColumnRole.UNKNOWN):
            role_vote_detail.setdefault(name_role.value, []).append(name_conf)

        # Conflict resolution: when the name signal has a strong, specific role
        # (like QUANTITY from 'count' pattern, or AMOUNT from 'price' pattern),
        # and cardinality/type suggest IDENTIFIER, penalize the IDENTIFIER votes.
        # This prevents score_range and student_count with 100% distinct values
        # from being misclassified as IDENTIFIER when the name clearly says otherwise.
        if name_conf >= 0.80 and name_role not in (ColumnRole.TEXT, ColumnRole.UNKNOWN, ColumnRole.IDENTIFIER):
            for role_str in list(role_vote_detail.keys()):
                if role_str == ColumnRole.IDENTIFIER.value:
                    # Name signal strongly disagrees with IDENTIFIER — heavily reduce
                    role_vote_detail[role_str] = [c * 0.3 for c in role_vote_detail[role_str]]

        # Aggregate role votes — pick role with highest average confidence
        for role_str, confs in role_vote_detail.items():
            role_votes[role_str] = sum(confs) / len(confs)

        if not role_votes:
            return ColumnRole.UNKNOWN, candidates, evidence

        best_role_str = max(role_votes, key=role_votes.get)
        best_role = ColumnRole(best_role_str)

        return best_role, candidates, evidence

    def _classify_name(
        self, column_name: str
    ) -> Tuple[ColumnRole, Optional[str], float, EvidenceReliability]:
        # Normalize camelCase to snake_case BEFORE space normalization
        # e.g., DeptID → Dept_ID (underscore at lowercase→uppercase boundary), then → dept_id
        # Uses lookahead/lookbehind to avoid breaking on acronyms like "ID" at end
        name_snake = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', column_name)
        name_snake = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', name_snake)
        name_lower = name_snake.lower()
        # Normalize spaces to underscores so that "Student ID" is treated like "student_id"
        name_normalized = name_lower.replace(" ", "_")
        for pattern, (role, hint, conf, rel) in EntitySignalPatterns.NAME_PATTERNS.items():
            if re.search(pattern, name_normalized):
                return role, hint, conf, rel
        return ColumnRole.TEXT, None, 0.30, EvidenceReliability.LOW

    def _classify_type(
        self, column: ColumnProfile
    ) -> Tuple[ColumnRole, float, EvidenceReliability]:
        dt = column.data_type
        if dt in EntitySignalPatterns.TYPE_ROLE_MAP:
            role, conf, rel = EntitySignalPatterns.TYPE_ROLE_MAP[dt]
            if dt == "string" and column.distinct_ratio > 0.9:
                return ColumnRole.IDENTIFIER, 0.75, EvidenceReliability.MEDIUM
            if dt == "string" and column.distinct_ratio < 0.1:
                return ColumnRole.CATEGORY, 0.85, EvidenceReliability.MEDIUM
            return role, conf, rel
        return ColumnRole.UNKNOWN, 0.30, EvidenceReliability.LOW

    def _classify_values(
        self, column: ColumnProfile
    ) -> Tuple[Optional[ColumnRole], float, EvidenceReliability, str]:
        if not column.sample_values:
            return None, 0.0, EvidenceReliability.LOW, ""

        sv = [v.lower() for v in column.sample_values if v]
        if not sv:
            return None, 0.0, EvidenceReliability.LOW, ""

        # Guard: high-cardinality columns (>50% distinct) with numeric data type
        # are likely ID/measure columns — skip value pattern matching for type_simple
        # to prevent '1', '2', '3' in integer ID columns from triggering CATEGORY.
        is_high_cardinality = column.distinct_ratio > 0.5

        for key, (role, _, match_values) in EntitySignalPatterns.VALUE_ROLE_MAP.items():
            if key == "type_simple":
                # type_simple uses exact match (==) and is skipped for high-cardinality columns
                if is_high_cardinality:
                    continue
                if any(val in match_values for val in sv):
                    return role, 0.85, EvidenceReliability.MEDIUM, key
            else:
                # Other patterns keep containment logic (e.g., 'red' in 'dark_red')
                if any(any(mv in val for mv in match_values) for val in sv):
                    return role, 0.85, EvidenceReliability.MEDIUM, key

        bool_vals = {"true", "false", "yes", "no", "y", "n", "1", "0", "active", "inactive"}
        if all(v in bool_vals for v in sv):
            return ColumnRole.BOOLEAN, 0.90, EvidenceReliability.HIGH, "boolean_values"

        code_pat = re.compile(r"^[A-Z]{2,}[0-9]+$|^[0-9]+[A-Z]{2,}$", re.IGNORECASE)
        code_matches = sum(1 for v in sv if code_pat.match(v))
        if code_matches / len(sv) > 0.5:
            return ColumnRole.CODE, 0.80, EvidenceReliability.MEDIUM, "code_pattern"

        return None, 0.40, EvidenceReliability.LOW, ""

    def _classify_cardinality(
        self, column: ColumnProfile
    ) -> Tuple[ColumnRole, float, EvidenceReliability, str]:
        ratio = column.distinct_ratio
        count = column.distinct_count

        if ratio == 1.0 and column.null_ratio == 0.0:
            conf = 0.95 if column.is_primary_key else 0.85
            return ColumnRole.IDENTIFIER, conf, EvidenceReliability.HIGH, "unique"

        if ratio < 0.05:
            return ColumnRole.CATEGORY, 0.85, EvidenceReliability.MEDIUM, "low_cardinality"

        if ratio > 0.95 and count > 100:
            return ColumnRole.IDENTIFIER, 0.70, EvidenceReliability.MEDIUM, "high_cardinality"

        return ColumnRole.TEXT, 0.50, EvidenceReliability.LOW, "medium_cardinality"

    def _classify_context(
        self, column: ColumnProfile, schema: SchemaProfile
    ) -> List[SemanticCandidate]:
        table_lower = schema.table_name.lower()
        candidates: List[SemanticCandidate] = []

        domain_keywords = {
            "customer": ["customer", "client", "user", "member"],
            "product": ["product", "item", "inventory", "sku"],
            "employee": ["employee", "staff", "hr", "personnel"],
            "patient": ["patient", "medical", "health", "clinical"],
            "order": ["order", "transaction", "purchase", "sales"],
        }

        col_lower = column.name.lower()
        for entity_label, keywords in domain_keywords.items():
            if any(kw in table_lower for kw in keywords) and any(
                kw in col_lower for kw in keywords
            ):
                candidates.append(
                    SemanticCandidate(
                        label=entity_label,
                        confidence=0.65,
                        source="table_name",
                    )
                )

        return candidates

    # ──────────────────────────────────────────────────────────────────────────
    # LEGACY: backward-compatible signal extraction (produces SignalResult)
    # ──────────────────────────────────────────────────────────────────────────

    def extract_all_signals(
        self, column: ColumnProfile, schema: Optional[SchemaProfile] = None
    ) -> List[SignalResult]:
        signals = []
        name_signal = self.extract_name_signal(column.name)
        if name_signal:
            signals.append(name_signal)
        type_signal = self.extract_type_signal(column)
        if type_signal:
            signals.append(type_signal)
        if column.sample_values:
            value_signal = self.extract_value_signal(column)
            if value_signal:
                signals.append(value_signal)
        cardinality_signal = self.extract_cardinality_signal(column)
        if cardinality_signal:
            signals.append(cardinality_signal)
        if schema:
            context_signal = self.extract_context_signal(column, schema)
            if context_signal:
                signals.append(context_signal)
        return signals

    def extract_name_signal(self, column_name: str) -> Optional[SignalResult]:
        name_lower = column_name.lower()
        for pattern, (role, hint, base_conf, _) in EntitySignalPatterns.NAME_PATTERNS.items():
            if re.search(pattern, name_lower):
                legacy_types = _hint_to_legacy_type(hint)
                et_list = (
                    [legacy_types]
                    if legacy_types
                    else [
                        EntityType.GENERIC_REFERENCE
                        if role == ColumnRole.IDENTIFIER
                        else EntityType.GENERIC_ENTITY
                    ]
                )
                return SignalResult(
                    signal_type=SignalType.COLUMN_NAME,
                    matched_pattern=pattern,
                    confidence=base_conf,
                    evidence=f"Column name '{column_name}' matches pattern '{pattern}'",
                    raw_match={
                        "column_name": column_name,
                        "entity_types": [e.value for e in et_list],
                    },
                )
        return SignalResult(
            signal_type=SignalType.COLUMN_NAME,
            matched_pattern=None,
            confidence=0.30,
            evidence=f"No name pattern match for '{column_name}'",
            raw_match={"column_name": column_name},
        )

    def extract_type_signal(self, column: ColumnProfile) -> Optional[SignalResult]:
        data_type = column.data_type
        if data_type in EntitySignalPatterns.TYPE_PATTERNS:
            entity_types, base_confidence = EntitySignalPatterns.TYPE_PATTERNS[data_type]
            confidence = base_confidence
            if data_type == "string" and column.distinct_ratio > 0.9:
                confidence = 0.75
                entity_types = [EntityType.GENERIC_REFERENCE]
            if data_type == "string" and column.distinct_ratio < 0.1:
                confidence = 0.85
                entity_types = [EntityType.CLASSIFICATION]
            return SignalResult(
                signal_type=SignalType.DATA_TYPE,
                matched_pattern=data_type,
                confidence=confidence,
                evidence=f"Data type '{data_type}' suggests {entity_types[0].value}",
                raw_match={"data_type": data_type, "distinct_ratio": column.distinct_ratio},
            )
        return SignalResult(
            signal_type=SignalType.DATA_TYPE,
            matched_pattern=data_type,
            confidence=0.30,
            evidence=f"No type pattern for '{data_type}'",
            raw_match={"data_type": data_type},
        )

    def extract_value_signal(self, column: ColumnProfile) -> Optional[SignalResult]:
        if not column.sample_values:
            return None
        sv = [v.lower() for v in column.sample_values if v]
        if not sv:
            return None
        for pattern_key, (
            col_pat,
            match_values,
            entity_type,
        ) in EntitySignalPatterns.VALUE_PATTERNS.items():
            if any(any(mv in val for mv in match_values) for val in sv):
                return SignalResult(
                    signal_type=SignalType.SAMPLE_VALUES,
                    matched_pattern=pattern_key,
                    confidence=0.85,
                    evidence=f"Sample values {sv[:3]} match {pattern_key} pattern -> {entity_type.value}",
                    raw_match={"pattern": pattern_key, "sample": sv[:3]},
                )
        bool_vals = {"true", "false", "yes", "no", "y", "n", "1", "0", "active", "inactive"}
        if all(v in bool_vals for v in sv):
            return SignalResult(
                signal_type=SignalType.SAMPLE_VALUES,
                matched_pattern="boolean_values",
                confidence=0.90,
                evidence=f"All sample values are boolean-like: {sv[:3]}",
                raw_match={"values": sv},
            )
        code_pat = re.compile(r"^[A-Z]{2,}[0-9]+$|^[0-9]+[A-Z]{2,}$", re.IGNORECASE)
        code_matches = sum(1 for v in sv if code_pat.match(v))
        if code_matches / len(sv) > 0.5:
            return SignalResult(
                signal_type=SignalType.SAMPLE_VALUES,
                matched_pattern="code_pattern",
                confidence=0.80,
                evidence="Values match code pattern (alphanumeric)",
                raw_match={"sample": sv[:3]},
            )
        return SignalResult(
            signal_type=SignalType.SAMPLE_VALUES,
            matched_pattern="generic",
            confidence=0.40,
            evidence="No special value patterns detected",
            raw_match={"sample": sv[:3]},
        )

    def extract_cardinality_signal(self, column: ColumnProfile) -> Optional[SignalResult]:
        ratio = column.distinct_ratio
        count = column.distinct_count
        if ratio == 1.0 and column.null_ratio == 0.0:
            confidence = 0.95 if column.is_primary_key else 0.85
            return SignalResult(
                signal_type=SignalType.CARDINALITY,
                matched_pattern="unique",
                confidence=confidence,
                evidence="Unique values (100% distinct) - likely primary key or ID",
                raw_match={"distinct_ratio": ratio, "distinct_count": count},
            )
        if ratio < 0.05:
            return SignalResult(
                signal_type=SignalType.CARDINALITY,
                matched_pattern="low_cardinality",
                confidence=0.85,
                evidence=f"Low cardinality ({ratio:.1%}) - classification field",
                raw_match={"distinct_ratio": ratio, "distinct_count": count},
            )
        if ratio > 0.95 and count > 100:
            return SignalResult(
                signal_type=SignalType.CARDINALITY,
                matched_pattern="high_cardinality",
                confidence=0.70,
                evidence=f"High cardinality ({count} distinct) - possibly reference/entity",
                raw_match={"distinct_ratio": ratio, "distinct_count": count},
            )
        return SignalResult(
            signal_type=SignalType.CARDINALITY,
            matched_pattern="medium_cardinality",
            confidence=0.50,
            evidence=f"Medium cardinality ({ratio:.1%}) - neutral signal",
            raw_match={"distinct_ratio": ratio, "distinct_count": count},
        )

    def extract_context_signal(
        self, column: ColumnProfile, schema: SchemaProfile
    ) -> Optional[SignalResult]:
        table_name = schema.table_name.lower()
        domain_patterns = {
            "order": ["sales", "transaction", "purchase", "order"],
            "customer": ["customer", "client", "user", "member"],
            "product": ["product", "item", "inventory", "sku"],
            "employee": ["employee", "staff", "hr", "personnel"],
            "patient": ["patient", "medical", "health", "clinical"],
            "finance": ["invoice", "payment", "account", "financial"],
        }
        for domain, keywords in domain_patterns.items():
            if any(kw in table_name for kw in keywords):
                col_lower = column.name.lower()
                for kw in keywords:
                    if kw in col_lower and kw != domain:
                        return SignalResult(
                            signal_type=SignalType.DOMAIN_CONTEXT,
                            matched_pattern=f"{domain}_related",
                            confidence=0.75,
                            evidence=f"Table '{schema.table_name}' suggests {domain} domain, column '{column.name}' related",
                            raw_match={"table": schema.table_name, "domain": domain},
                        )
        if self._has_id_name_pair(column, schema.columns):
            if "_id" in column.name.lower():
                return SignalResult(
                    signal_type=SignalType.DOMAIN_CONTEXT,
                    matched_pattern="id_name_pair",
                    confidence=0.80,
                    evidence="Column is ID with corresponding name column - strong entity reference",
                    raw_match={"table": schema.table_name},
                )
        return None

    def _has_id_name_pair(self, column: ColumnProfile, all_columns: List[ColumnProfile]) -> bool:
        col_base = re.sub(r"_id$", "", column.name.lower())
        for col in all_columns:
            col_name_lower = col.name.lower()
            if col_name_base := re.sub(r"_name$", "", col_name_lower):
                if col_base == col_name_base and "_name" in col_name_lower:
                    return True
        return False


signal_engine = SignalEngine()

__all__ = ["SignalEngine", "SignalExtractionError", "signal_engine"]
