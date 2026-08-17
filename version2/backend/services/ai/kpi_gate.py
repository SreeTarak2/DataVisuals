"""
KPI Candidate Selection
=======================
KPI gate, hero, and candidate selection with business-rule boosting.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

from .kpi_types import ColumnProfile, ColumnRole

logger = logging.getLogger(__name__)


def _passes_gate(
    profile: ColumnProfile,
    selected_categories: Dict[str, int],
    business_rules: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Six-gate KPI selection with business-rule boosting."""
    is_business_defined = False
    if business_rules:
        prof_name_lower = profile.name.lower()
        for rule in business_rules:
            rule_lower = rule.lower()
            if prof_name_lower in rule_lower:
                is_business_defined = True
                break
            rule_words = set(rule_lower.split())
            prof_words = set(prof_name_lower.replace("_", " ").split())
            if rule_words & prof_words:
                is_business_defined = True
                break

    # Gate 1: Role (relaxed for business-defined)
    if profile.role not in (ColumnRole.MEASURE, ColumnRole.RATE, ColumnRole.COUNT):
        if not is_business_defined:
            return False, f"role={profile.role.value}"

    # Gate 2: Nulls (relaxed for business-defined)
    if profile.null_pct > 40:
        if not is_business_defined:
            return False, f"nulls={profile.null_pct:.0f}%"

    # Gate 3: Value must be non-trivial
    val = profile.primary_value
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return False, "NaN/Inf value"
    if abs(val) < 1e-9 and profile.aggregation == "sum":
        if not is_business_defined:
            return False, "zero sum"

    # Gate 4: Business category
    if profile.business_category == "unknown":
        category = "neutral"
    else:
        category = profile.business_category

    # Gate 5: Non-redundancy (boosted slots for business-defined)
    max_allowed = {"revenue": 2, "cost": 2, "users": 1, "churn_risk": 1}
    max_per = max_allowed.get(category, 1)
    if is_business_defined:
        max_per = max(max_per + 1, 3)
    count = selected_categories.get(category, 0)
    if count >= max_per:
        return False, f"redundant with {category}"
    selected_categories[category] = count + 1

    return True, category


def _select_hero(
    candidates: List[ColumnProfile],
    business_rules: Optional[List[str]] = None,
    persona: Optional[str] = None,
) -> Optional[ColumnProfile]:
    """Hero = the single number the audience asks for first."""
    from services.ai.personas import persona_hero_category

    # 0. Business-defined hero
    if business_rules:
        for c in candidates:
            col_lower = c.name.lower()
            for rule in business_rules:
                if col_lower in rule.lower() or rule.lower() in col_lower:
                    logger.debug(f"[KPI] Business rule selected hero: {c.name}")
                    return c
    # 0b. Persona-preferred category (e.g. rate_metric for the analyst)
    hero_cat = persona_hero_category(persona)
    for c in candidates:
        if c.business_category == hero_cat:
            return c
    # 1. Revenue
    for c in candidates:
        if c.business_category == "revenue":
            return c
    # 2. Count metrics
    for c in candidates:
        if c.role == ColumnRole.COUNT:
            return c
    # 3. RATE metrics
    for c in candidates:
        if c.role == ColumnRole.RATE:
            return c
    # 4. Mean measures
    means = [c for c in candidates
             if c.role == ColumnRole.MEASURE
             and c.aggregation in ("mean", "median")
             and c.col_mean is not None]
    if means:
        return max(means, key=lambda c: abs(c.col_mean or 0))
    # 5. Sum measures
    sums = [c for c in candidates if c.role == ColumnRole.MEASURE and c.col_sum]
    if sums:
        return max(sums, key=lambda c: abs(c.col_sum or 0))
    return candidates[0] if candidates else None


def _select_candidates(
    profiles: List[ColumnProfile],
    max_kpis: int,
    business_rules: Optional[List[str]] = None,
    persona: Optional[str] = None,
) -> List[ColumnProfile]:
    """Apply the gate + business-rule boost, pick hero + 1-3 primaries.

    ``persona`` re-ranks the category priority so the selected KPIs match the
    audience (CEO → revenue/risk first; analyst → statistics first).
    """
    from services.ai.personas import persona_category_priority

    priority = persona_category_priority(persona)
    selected_categories: Dict[str, int] = {}
    passed: List[ColumnProfile] = []

    def sort_key(p: ColumnProfile) -> Tuple[int, float]:
        is_biz = False
        if business_rules:
            col_lower = p.name.lower()
            for rule in business_rules:
                if col_lower in rule.lower() or rule.lower() in col_lower:
                    is_biz = True
                    break
        base_prio = priority.get(p.business_category, 10)
        prio = -1 if is_biz else base_prio
        val = abs(p.primary_value or 0)
        return (prio, -val)

    sorted_profiles = sorted(profiles, key=sort_key)

    for profile in sorted_profiles:
        if len(passed) >= max_kpis:
            break
        if profile.name.startswith("_"):
            logger.debug(f"[KPI] Gate skipped synthetic '{profile.name}'")
            continue
        ok, reason = _passes_gate(profile, selected_categories, business_rules=business_rules)
        if ok:
            passed.append(profile)
        else:
            logger.debug(f"[KPI] Gate rejected '{profile.name}': {reason}")

    hero = _select_hero(passed, business_rules=business_rules, persona=persona)
    for i, p in enumerate(passed):
        p.importance = "hero" if p is hero else ("high" if i <= 2 else "medium")

    if hero and passed[0] is not hero:
        passed.remove(hero)
        passed.insert(0, hero)

    return passed
