"""
Grouping Engine — Column → Entity Cluster
============================================

Groups individual column classifications into EntityCluster objects
using prefix matching, abbreviation expansion, and role composition.

No LLM. Deterministic. Domain-agnostic.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from .models import ColumnRole, SemanticCandidate, EntityCluster

logger = logging.getLogger(__name__)


# Static abbreviation dictionary (~20 common pairs)
# Abbreviation expansions are low-confidence — they only contribute
# when other signals (prefix, role) agree.
ABBREVIATIONS: Dict[str, str] = {
    "cust": "customer",
    "pt": "patient",
    "emp": "employee",
    "dept": "department",
    "org": "organization",
    "acct": "account",
    "addr": "address",
    "qty": "quantity",
    "amt": "amount",
    "num": "number",
    "ref": "reference",
    "sub": "subtotal",
    "mgr": "manager",
    "vend": "vendor",
    "supp": "supplier",
    "loc": "location",
    "prod": "product",
    "cat": "category",
    "mfg": "manufacturer",
    "dist": "distributor",
}


class GroupingEngine:
    """
    Groups columns into entity clusters using:
    - Prefix matching (highest weight)
    - Semantic candidates from column name patterns
    - Abbreviation expansion (low weight)
    - Table name as fallback
    - Edit distance for no-prefix cases
    """

    def __init__(self):
        self.abbrev = ABBREVIATIONS

    def group(
        self,
        columns: List[Tuple[str, ColumnRole, List[SemanticCandidate]]],
        table_name: str = "",
    ) -> List[EntityCluster]:
        """
        Group classified columns into entity clusters.

        Args:
            columns: List of (column_name, role, semantic_candidates)
            table_name: Optional table/file name for context

        Returns:
            List of EntityCluster objects
        """
        if not columns:
            return []

        # Phase 1: Collect entity labels from candidates + prefixes
        col_to_labels: Dict[str, List[Tuple[str, float]]] = {}
        for col_name, role, candidates in columns:
            labels: List[Tuple[str, float]] = []

            # Get labels from semantic candidates
            for c in candidates:
                labels.append((c.label, c.confidence))

            # Get labels from column name prefixes
            prefix_labels = self._extract_prefix_labels(col_name)
            for pl, pconf in prefix_labels:
                if not any(pl == l for l, _ in labels):
                    labels.append((pl, pconf))

            # Get labels from abbreviation expansion
            abbrev_labels = self._extract_abbreviation_labels(col_name)
            for al, aconf in abbrev_labels:
                if not any(al == l for l, _ in labels):
                    labels.append((al, aconf))

            col_to_labels[col_name] = labels

        # Phase 2: Cluster columns by shared label
        label_to_cols: Dict[str, List[Tuple[str, ColumnRole, float]]] = defaultdict(list)
        for col_name, role, _ in columns:
            labels = col_to_labels.get(col_name, [])
            if not labels:
                continue
            # Pick the best label for this column
            best_label, best_conf = max(labels, key=lambda x: x[1])
            label_to_cols[best_label].append((col_name, role, best_conf))

        # Phase 3: Build EntityCluster objects
        clusters: List[EntityCluster] = []
        for label, col_entries in label_to_cols.items():
            if len(col_entries) < 1:
                continue

            col_names = [c[0] for c in col_entries]
            col_roles = [c[1] for c in col_entries]
            confs = [c[2] for c in col_entries]

            has_id = any(r == ColumnRole.IDENTIFIER for r in col_roles)

            # Cluster confidence: average of individual confidences,
            # boosted by number of columns and presence of identifier
            avg_conf = sum(confs) / len(confs)
            size_boost = min(0.10, len(col_entries) * 0.03)
            id_boost = 0.10 if has_id else 0.0
            cluster_conf = min(0.99, avg_conf + size_boost + id_boost)

            clusters.append(
                EntityCluster(
                    label=label,
                    columns=col_names,
                    roles=col_roles,
                    confidence=round(cluster_conf, 3),
                    has_identifier=has_id,
                    source="prefix",
                )
            )

        # Phase 4: Table name as fallback — group remaining unlabeled columns
        if table_name:
            table_label = self._table_name_to_label(table_name)
            if table_label and not any(c.label == table_label for c in clusters):
                # Check if any ungrouped columns match the table context
                all_grouped_cols = set()
                for c in clusters:
                    all_grouped_cols.update(c.columns)
                remaining = [(cn, r, _) for cn, r, _ in columns if cn not in all_grouped_cols]
                if remaining:
                    col_names = [c[0] for c in remaining]
                    col_roles = [c[1] for c in remaining]
                    has_id = any(r == ColumnRole.IDENTIFIER for r in col_roles)
                    clusters.append(
                        EntityCluster(
                            label=table_label,
                            columns=col_names,
                            roles=col_roles,
                            confidence=0.50,
                            has_identifier=has_id,
                            source="table_name",
                        )
                    )

        return clusters

    def _extract_prefix_labels(self, column_name: str) -> List[Tuple[str, float]]:
        """
        Extract entity labels from column name prefixes.

        Examples:
            customer_id     → ("customer", 0.72)
            pt_id           → ("pt", 0.60)  [low confidence, needs abbreviation]
            order_date      → ("order", 0.65)
            employee_name   → ("employee", 0.72)
        """
        name = column_name.lower()
        labels: List[Tuple[str, float]] = []

        # Split on underscore, look for common business prefixes
        parts = name.split("_")
        if len(parts) >= 2:
            prefix = parts[0]
            # Common business entity prefixes
            common_prefixes = {
                "customer": 0.72,
                "user": 0.65,
                "product": 0.72,
                "item": 0.65,
                "order": 0.72,
                "transaction": 0.65,
                "employee": 0.72,
                "staff": 0.60,
                "patient": 0.72,
                "doctor": 0.65,
                "physician": 0.60,
                "company": 0.65,
                "vendor": 0.60,
                "supplier": 0.60,
                "invoice": 0.65,
                "payment": 0.60,
                "claim": 0.65,
                "policy": 0.60,
                "student": 0.65,
                "course": 0.60,
                "shipment": 0.72,
                "vehicle": 0.60,
                "sensor": 0.50,
                "device": 0.50,
                "account": 0.65,
                "contact": 0.60,
                "address": 0.60,
                "location": 0.60,
                "department": 0.60,
                "project": 0.55,
                "participant": 0.55,
                "drug": 0.60,
                "survey": 0.50,
                "enrollment": 0.55,
                "visit": 0.55,
                "hospital": 0.55,
                "task": 0.55,
                "ticket": 0.55,
                "agent": 0.55,
                "assignee": 0.60,
                "reviewer": 0.60,
                "warehouse": 0.65,
                "merchant": 0.60,
                "assignee": 0.65,
                "reviewer": 0.65,
            }
            if prefix in common_prefixes:
                labels.append((prefix, common_prefixes[prefix]))

        # Also check for known composite patterns
        # E.g. "part_number" is product; "po_number" is purchase_order
        composite_patterns = {
            r"^po_": ("purchase_order", 0.55),
            r"^so_": ("sales_order", 0.55),
            r"^part_": ("part", 0.55),
        }
        for pattern, (label, conf) in composite_patterns.items():
            if re.match(pattern, name):
                labels.append((label, conf))

        return labels

    def _extract_abbreviation_labels(self, column_name: str) -> List[Tuple[str, float]]:
        """
        Try to expand column name prefix via abbreviation dictionary.

        Examples:
            cust_id   → ("customer", 0.35)
            emp_name  → ("employee", 0.35)
            pt_dob    → ("patient", 0.35)
        """
        name = column_name.lower()
        parts = name.split("_")
        if not parts:
            return []
        prefix = parts[0]
        if prefix in self.abbrev:
            return [(self.abbrev[prefix], 0.35)]
        return []

    def _table_name_to_label(self, table_name: str) -> Optional[str]:
        """
        Extract entity label from table/file name.

        Scans ALL parts of the table name for known entity labels,
        not just the first part. This handles names like:
        - adv_hard_mixed_claims → scans [adv, hard, mixed, claims] → "claim"
        - customers_2024       → [customers, 2024] → "customer"
        - patient_records      → [patient, records] → "patient"
        """
        name = table_name.lower()
        # Remove extension
        name = re.sub(r"\.[a-z]+$", "", name)
        # Remove trailing date/version artifacts
        name = re.sub(r"[_\-\.]?(20\d{2}|q[1-4]|v\d+|export|backup)$", "", name)
        # Split into all parts
        parts = re.split(r"[_\-\.\s]+", name)
        if not parts:
            return None

        # Plural → singular lookup (used for both first-part and any-part matching)
        singular_overrides = {
            "customers": "customer",
            "users": "user",
            "products": "product",
            "items": "item",
            "orders": "order",
            "transactions": "transaction",
            "employees": "employee",
            "staffs": "staff",
            "patients": "patient",
            "doctors": "doctor",
            "companies": "company",
            "vendors": "vendor",
            "invoices": "invoice",
            "payments": "payment",
            "claims": "claim",
            "policies": "policy",
            "students": "student",
            "courses": "course",
            "shipments": "shipment",
            "vehicles": "vehicle",
            "accounts": "account",
            "contacts": "contact",
            "drugs": "drug",
            "participants": "participant",
            "surveys": "survey",
            "appointments": "appointment",
            "leads": "lead",
            "logs": "log",
            "entries": "entry",
            "records": "record",
            "histories": "history",
            "statuses": "status",
            "suppliers": "supplier",
            "warehouses": "warehouse",
            "merchants": "merchant",
            "enrollments": "enrollment",
            "providers": "provider",
            "opportunities": "opportunity",
            "licenses": "license",
            "notifications": "notification",
        }

        # Step 1: Try the LAST meaningful part (most specific — e.g., "claims" in "adv_hard_mixed_claims")
        # Walk backwards through parts to find the best entity label
        for part in reversed(parts):
            if part in singular_overrides:
                return singular_overrides[part]
            if part in self.abbrev:
                return self.abbrev[part]

        # Step 2: Try the FIRST meaningful part (simpler names like "orders_2024")
        first = parts[0]
        if first in singular_overrides:
            return singular_overrides[first]
        if first in self.abbrev:
            return self.abbrev[first]

        # Step 3: Fall back to last part as-is
        return parts[-1]


grouping_engine = GroupingEngine()

__all__ = ["GroupingEngine", "grouping_engine"]
