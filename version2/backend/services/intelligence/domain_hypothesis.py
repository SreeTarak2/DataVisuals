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
    """

    def match(self, result: RawProfilingResult) -> DomainHypothesisResult:
        """Score all domain templates against profiled columns.

        Returns candidates with scores, NOT a single answer.
        """
        try:
            from services.kpi.patterns import COLUMN_PATTERNS
            from services.kpi.templates import ALL_TEMPLATES
        except ImportError:
            logger.warning("[Domain] kpi package not available — skipping domain matching")
            return DomainHypothesisResult(method="unavailable")

        # Detect column types from column names
        column_names = [c.name for c in result.columns]
        detected_types: set[str] = set()

        for col_name in column_names:
            col_lower = col_name.lower().replace("_", " ").replace("-", " ")
            for col_type, patterns in COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, col_lower, re.IGNORECASE):
                        detected_types.add(col_type)
                        break

        # Score each template
        candidates: list[DomainCandidate] = []
        for template_id, template in ALL_TEMPLATES.items():
            required = set(template.required_columns)
            optional = set(template.optional_columns)

            matched_required = required & detected_types
            matched_optional = optional & detected_types

            if len(matched_required) == len(required):
                # All required columns matched — high score
                score = 50.0 + 10.0 * len(matched_required) + 5.0 * len(matched_optional)
            elif len(matched_required) > 0:
                score = 15.0 * len(matched_required) + 3.0 * len(matched_optional)
            else:
                continue  # No match at all

            # Find the actual column names that matched
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

        if not candidates:
            return DomainHypothesisResult(method="pattern_match")

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        return DomainHypothesisResult(
            candidates=candidates,
            top_candidate=candidates[0],
            method="pattern_match",
        )


# Singleton
domain_hypothesis_engine = DomainHypothesisEngine()
