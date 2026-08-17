"""
intelligence/domain_hypothesis.py — Deterministic domain hypothesis engine (Layer 3)

Treats domains as CANDIDATES with scores, NOT single answers.

Uses pattern-based column type detection + template scoring from
services/kpi/patterns.py and services/kpi/templates.py.

Every domain match produces:
  - A list of candidates, each with a score
  - The number of required and optional columns matched
  - The specific columns that triggered the match

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from services.profiling.models import RawColumnProfile, RawProfilingResult

from .models import (
    DomainCandidate,
    DomainHypothesisResult,
)

logger = logging.getLogger(__name__)


class DomainHypothesisEngine:
    """Deterministic domain matcher that outputs scored candidates.

    Uses existing pattern definitions from services/kpi/patterns.py
    and templates from services/kpi/templates.py.

    Includes an entity-prefix fast-path (Layer 2): if a column matches
    a well-known entity ID pattern (e.g. ``customer_id`` → ``ecommerce-metrics``),
    the corresponding domain gets injected as a high-score candidate before
    pattern matching runs. This costs $0, completes in microseconds, and
    often produces the correct answer without any LLM call.
    """

    # Entity ID suffix pattern — matches primary-key / foreign-key columns
    _ENTITY_ID_RE = re.compile(r"^(.+?)_(id|key|uuid|guid)$", re.I)

    # Entity prefix → domain template mapping
    # High-specificity entities (patient, vehicle, property) map to exactly
    # one domain and are treated as near-certain matches. Generic entities
    # (user, account, transaction) are excluded because they span domains.
    _ENTITY_DOMAIN_MAP: dict[str, str] = {
        # E-commerce / Retail
        "customer": "ecommerce-metrics",
        "order": "ecommerce-metrics",
        "product": "ecommerce-metrics",
        "review": "ecommerce-metrics",
        # SaaS / Technology
        "user": None,  # Too generic — handled by pattern matching instead
        "tenant": "saas-metrics",
        "subscription": "saas-metrics",
        # Finance / Banking
        "transaction": None,  # Too generic — handled by pattern matching
        "account": "finance-metrics",
        "loan": "finance-metrics",
        "invoice": "finance-metrics",
        # Healthcare
        "patient": "healthcare-metrics",
        "provider": "healthcare-metrics",
        "claim": "healthcare-metrics",
        # Real Estate
        "property": "real-estate-metrics",
        "listing": "real-estate-metrics",
        "parcel": "real-estate-metrics",
        # Automotive
        "vehicle": "automotive-metrics",
        "car": "automotive-metrics",
        # HR
        "employee": "hr-metrics",
        "candidate": "hr-metrics",
        # Logistics
        "shipment": "logistics-metrics",
        "carrier": None,  # Too generic
        "warehouse": "logistics-metrics",
        # Education
        "student": "education-metrics",
        "course": "education-metrics",
        "enrollment": "education-metrics",
        # Marketing
        "campaign": "marketing-metrics",
        # Manufacturing
        "batch": "manufacturing-metrics",
        "supplier": "manufacturing-metrics",
    }

    # Mutual-exclusion signal weights (Layer 4).
    #
    # For each domain template, ``"positive"`` entries boost the score when
    # the corresponding column TYPE (detected via COLUMN_PATTERNS) is present.
    # ``"negative"`` entries PENALIZE competing domains for the same signal.
    #
    # This prevents the classic misclassification where ``purchase_amount``
    # matches ``amount`` (in COLUMN_PATTERNS ``revenue``) and pushes
    # ``finance-metrics`` to #1, even though ``customer_id`` is present.
    # Customer_id gives ecommerce +25 and finance -10 → 35-point net separation.
    #
    # Signals are additive — a dataset with ``customer_id`` (+25 ecom, -10 fin)
    # AND ``revenue`` (+15 both) gets (25+15) - (15-10) = 35 net for ecommerce.
    #
    # NOTE: Signal weights operate on detected column TYPES (from COLUMN_PATTERNS),
    # not raw column names. If a column like ``category`` or ``color`` isn't
    # recognized by any pattern in COLUMN_PATTERNS, it won't trigger any weights.
    # Add new patterns to ``services/kpi/patterns.py`` to make them detectable.
    _SIGNAL_WEIGHTS: dict[str, dict[str, dict[str, float]]] = {
        "ecommerce-metrics": {
            "positive": {
                "revenue": 15.0,        # purchase_amount, total_amount
                "customer_id": 25.0,    # customer_id, client_id
                "quantity": 10.0,       # items, quantity
                "date": 5.0,            # date columns
            },
            "negative": {
                # Finance-specific patterns that sometimes leak via
                # "amount" matching COLUMN_PATTERNS revenue
                "stock_price": -30.0,
                "loan_amount": -30.0,
                "interest_rate": -30.0,
            },
        },
        "finance-metrics": {
            "positive": {
                "revenue": 15.0,        # amount, total_amount
                "cost": 15.0,           # expense, payment
                "cash": 20.0,           # cash, balance, bank
                "profit": 20.0,         # profit, margin, earnings
                "date": 5.0,
            },
            "negative": {
                # E-commerce-specific signals — if these appear, it's NOT finance
                "category": -20.0,
                "size": -15.0,
                "color": -10.0,
                "customer_id": -10.0,  # customer_id alone is ambiguous,
                                        # but with category+size+color, it's ecom
            },
        },
        "saas-metrics": {
            "positive": {
                "revenue": 15.0,
                "churn": 25.0,
                "retention": 20.0,
                "acquisition_cost": 20.0,
                "customer_count": 15.0,
                "date": 5.0,
            },
            "negative": {
                "category": -10.0,
                "size": -10.0,
                "color": -5.0,
            },
        },
        "healthcare-metrics": {
            "positive": {
                "patient_id": 30.0,
                "diagnosis": 25.0,
                "length_of_stay": 20.0,
                "readmission": 20.0,
                "date": 5.0,
            },
            "negative": {
                "revenue": -10.0,
                "category": -10.0,
                "customer_id": -10.0,
            },
        },
        "real-estate-metrics": {
            "positive": {
                "property_id": 30.0,
                "bedrooms": 20.0,
                "bathrooms": 20.0,
                "square_feet": 20.0,
                "days_on_market": 15.0,
                "price": 10.0,
            },
            "negative": {
                "patient_id": -10.0,
                "customer_id": -5.0,
            },
        },
        "automotive-metrics": {
            "positive": {
                "mileage": 25.0,
                "engine_size": 20.0,
                "fuel_type": 15.0,
                "transmission": 15.0,
                "horsepower": 20.0,
                "vehicle_model": 20.0,
                "num_owners": 10.0,
                "mpg": 10.0,
            },
            "negative": {
                "patient_id": -10.0,
                "customer_id": -5.0,
                "category": -10.0,
            },
        },
        "hr-metrics": {
            "positive": {
                "employee_id": 30.0,
                "salary": 20.0,
                "performance": 15.0,
                "tenure": 15.0,
                "date": 5.0,
            },
            "negative": {
                "revenue": -10.0,
                "customer_id": -5.0,
            },
        },
        "logistics-metrics": {
            "positive": {
                "shipment_id": 30.0,
                "weight": 20.0,
                "distance": 20.0,
                "delivery_time": 20.0,
                "carrier": 10.0,
                "date": 5.0,
            },
            "negative": {
                "patient_id": -10.0,
                "category": -10.0,
            },
        },
        "education-metrics": {
            "positive": {
                "student_id": 30.0,
                "gpa": 20.0,
                "grade": 20.0,
                "attendance": 15.0,
                "date": 5.0,
            },
            "negative": {
                "revenue": -10.0,
                "customer_id": -5.0,
            },
        },
        "marketing-metrics": {
            "positive": {
                "impressions": 25.0,
                "clicks": 25.0,
                "conversions": 25.0,
                "marketing_spend": 20.0,
                "acquisition_cost": 15.0,
                "date": 5.0,
            },
            "negative": {
                "patient_id": -10.0,
                "employee_id": -10.0,
            },
        },
        "manufacturing-metrics": {
            "positive": {
                "yield": 25.0,
                "cycle_time": 20.0,
                "defect": 20.0,
                "quantity": 10.0,
                "date": 5.0,
            },
            "negative": {
                "patient_id": -10.0,
                "customer_id": -5.0,
            },
        },
    }

    def _detect_entity_domain(self, column_names: list[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Scan columns for entity ID patterns and map the first unambiguous
        entity prefix to a domain template.

        Returns ``(domain_id, entity_prefix, matched_column)`` or
        ``(None, None, None)`` if no entity match is found.

        Scans in order of column list (typically the order they appear in
        the dataset). The first match wins, so more specific entities that
        appear earlier in the schema will be chosen over later generic ones.
        """
        for col_name in column_names:
            m = self._ENTITY_ID_RE.search(col_name)
            if not m:
                continue
            prefix = m.group(1).lower()
            domain_id = self._ENTITY_DOMAIN_MAP.get(prefix)
            if domain_id is not None:
                logger.info(
                    "[Domain] Entity fast-path: column '%s' → prefix='%s' → domain='%s'",
                    col_name, prefix, domain_id,
                )
                return domain_id, prefix, col_name
        return None, None, None

    def match(self, result: RawProfilingResult) -> DomainHypothesisResult:
        """Score all domain templates against profiled columns.

        Returns candidates with scores, NOT a single answer.

        Priority order:
          1. Entity-prefix fast-path (if a strong entity ID column is found)
          2. Pattern-based template scoring (fallback)
        """
        try:
            from services.kpi.patterns import COLUMN_PATTERNS
            from services.kpi.templates import ALL_TEMPLATES
        except ImportError:
            logger.warning("[Domain] kpi package not available — skipping domain matching")
            return DomainHypothesisResult(method="unavailable")

        column_names = [c.name for c in result.columns]

        # ── Step 1: Entity-prefix fast-path ─────────────────────────────
        # If we find a high-specificity entity ID column, inject its domain
        # as a high-score candidate (score=95) that will beat any pattern
        # match. This costs nothing and is often the correct answer.
        entity_domain_id, entity_prefix, entity_col = self._detect_entity_domain(column_names)
        has_entity_match = entity_domain_id is not None

        # ── Step 2: Detect column types from column names ───────────────
        detected_types: set[str] = set()

        for col_name in column_names:
            col_lower = col_name.lower().replace("_", " ").replace("-", " ")
            for col_type, patterns in COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, col_lower, re.IGNORECASE):
                        detected_types.add(col_type)
                        break

        # ── Step 3: Score each template ────────────────────────────────
        #
        # Scoring has two phases:
        #   Phase A — Base score from template column matching (existing)
        #   Phase B — Mutual-exclusion adjustment via SIGNAL_WEIGHTS (Layer 4)
        #
        # Phase B adds positive weights for signals that STRONGLY indicate a
        # specific domain (e.g. ``category`` → ``ecommerce-metrics``) and
        # NEGATIVE weights for the same signals on COMPETING domains
        # (e.g. ``category`` → ``finance-metrics: -20``). This prevents the
        # bug where ``purchase_amount`` matching ``amount`` (in COLUMN_PATTERNS)
        # pushes finance to #1 despite the dataset being clearly e-commerce.
        candidates: list[DomainCandidate] = []
        for template_id, template in ALL_TEMPLATES.items():
            required = set(template.required_columns)
            optional = set(template.optional_columns)

            matched_required = required & detected_types
            matched_optional = optional & detected_types

            # ── Phase A: Base score from template matching ──────────────
            if len(matched_required) == len(required):
                base_score = 50.0 + 10.0 * len(matched_required) + 5.0 * len(matched_optional)
            elif len(matched_required) > 0:
                base_score = 15.0 * len(matched_required) + 3.0 * len(matched_optional)
            else:
                continue

            # ── Phase B: Mutual-exclusion adjustment ────────────────────
            # For each detected column type, apply the per-domain signal
            # weights: positive signals boost this domain, negative signals
            # from competing domains suppress it.
            adjustment = 0.0
            signal_map = self._SIGNAL_WEIGHTS.get(template_id, {})
            pos_signals = signal_map.get("positive", {})
            neg_signals = signal_map.get("negative", {})

            for det_type in detected_types:
                adjustment += pos_signals.get(det_type, 0.0)
                adjustment += neg_signals.get(det_type, 0.0)

            score = base_score + adjustment

            matched_cols = [
                cn for cn in column_names
                if any(
                    re.search(p, cn.lower().replace("_", " ").replace("-", " "), re.I)
                    for col_type in (matched_required | matched_optional)
                    for p in COLUMN_PATTERNS.get(col_type, [])
                )
            ]

            domain_name = template_id.replace("-metrics", "").replace("-", " ").title()

            candidates.append(DomainCandidate(
                domain_id=template_id,
                domain_name=domain_name,
                score=score,
                matched_columns=sorted(set(matched_cols))[:10],
                matched_required=len(matched_required),
                matched_optional=len(matched_optional),
                total_required=len(required),
            ))

        # ── Step 4: Inject entity match as high-score candidate ─────────
        if has_entity_match and entity_domain_id in ALL_TEMPLATES:
            entity_template = ALL_TEMPLATES[entity_domain_id]
            entity_name = entity_domain_id.replace("-metrics", "").replace("-", " ").title()

            # Score of 150 guarantees the entity fast-path always wins
            # over pattern matching (max pattern score is 50+10R+5O which
            # can theoretically exceed 100 for templates with many columns).
            candidates.append(DomainCandidate(
                domain_id=entity_domain_id,
                domain_name=entity_name,
                score=150.0,
                matched_columns=[entity_col],
                matched_required=len(entity_template.required_columns),
                matched_optional=0,
                total_required=len(entity_template.required_columns),
            ))

        if not candidates:
            return DomainHypothesisResult(method="pattern_match")

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        method = "entity_fastpath" if has_entity_match else "pattern_match"

        return DomainHypothesisResult(
            candidates=candidates,
            top_candidate=candidates[0],
            method=method,
        )


# Singleton
domain_hypothesis_engine = DomainHypothesisEngine()
