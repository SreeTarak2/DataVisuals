"""
Personas — audience-aware dashboard emphasis
=============================================

The "same dataset, different audience → different dashboard" principle
(Lesson: Prompt = f(Intent, Context, Audience, Constraints, Available Info)).

Each persona is a CONFIG — not a prompt rewrite:
  - ``category_priority``  → re-ranks which KPI categories get selected by
    the gate (CEO sees revenue/risk first; analyst sees statistics first).
  - ``hero_category``      → which category wins the hero (lead) card.
  - ``focus_instruction``  → injected into LLM-assisted narrative context.
  - ``narrative_style``    → tone for the insight text.

Applied deterministically at generation time; switching is instant and
reversible.
"""

from __future__ import annotations

from typing import Dict, Optional

EXPLORER = "explorer"
CEO = "ceo"
ANALYST = "analyst"
MARKETING = "marketing"
OPS = "ops"

DEFAULT = EXPLORER

# Category priority maps used by the KPI gate's sort_key (lower = selected
# first). Keys mirror the gate's priority dict; unknown categories fall
# through to the base priority.
_BASE_PRIORITY: Dict[str, int] = {
    "revenue": 0, "volume": 1, "users": 2, "price": 3,
    "rate_metric": 4, "performance": 5, "cost": 6,
    "churn_risk": 7, "duration": 8, "quantity": 9, "neutral": 11,
}

PERSONAS: Dict[str, Dict] = {
    EXPLORER: {
        "label": "Explorer",
        "description": "Neutral default — broad discovery across all key metrics.",
        "category_priority": _BASE_PRIORITY,
        "hero_category": "revenue",
        "focus_instruction": (
            "Broad discovery: surface the most important metrics across the "
            "dataset with balanced emphasis."
        ),
        "narrative_style": "balanced, exploratory",
    },
    CEO: {
        "label": "CEO",
        "description": "Executive view — revenue, growth, profit, and major risks at a glance.",
        "category_priority": {
            "revenue": 0, "volume": 1, "users": 2, "cost": 3, "churn_risk": 4,
            "price": 5, "performance": 6, "rate_metric": 7,
            "quantity": 10, "duration": 10, "neutral": 12,
        },
        "hero_category": "revenue",
        "focus_instruction": (
            "Executive summary: prioritize revenue, growth, profit, and major "
            "risks. Prefer high-level KPIs and decisive, business-readable "
            "narrative."
        ),
        "narrative_style": "executive, decisive, business-focused",
    },
    ANALYST: {
        "label": "Analyst",
        "description": "Statistical depth — distributions, correlations, outliers, and detail.",
        "category_priority": {
            "rate_metric": 0, "performance": 1, "volume": 2, "price": 3,
            "duration": 4, "revenue": 5, "quantity": 6, "users": 7,
            "cost": 8, "neutral": 9, "churn_risk": 11,
        },
        "hero_category": "rate_metric",
        "focus_instruction": (
            "Statistical depth: emphasize distributions, correlations, "
            "outliers, missing-data patterns, and precise figures. Prefer "
            "technical, precise narrative."
        ),
        "narrative_style": "technical, precise, evidence-heavy",
    },
    MARKETING: {
        "label": "Marketing",
        "description": "Acquisition, campaigns, segments, and engagement.",
        "category_priority": {
            "users": 0, "volume": 1, "quantity": 2, "revenue": 3,
            "price": 4, "rate_metric": 5, "performance": 6,
            "cost": 8, "duration": 9, "churn_risk": 10, "neutral": 11,
        },
        "hero_category": "users",
        "focus_instruction": (
            "Marketing focus: prioritize acquisition, campaign performance, "
            "segment behavior, and engagement metrics."
        ),
        "narrative_style": "growth-oriented, segment-aware",
    },
    OPS: {
        "label": "Operations",
        "description": "Efficiency, volume, quality, and bottlenecks.",
        "category_priority": {
            "cost": 0, "volume": 1, "quantity": 2, "duration": 3,
            "performance": 4, "rate_metric": 5, "revenue": 6, "users": 7,
            "price": 8, "churn_risk": 9, "neutral": 11,
        },
        "hero_category": "cost",
        "focus_instruction": (
            "Operations focus: prioritize efficiency, volume, quality, "
            "defect/error rates, and bottlenecks."
        ),
        "narrative_style": "operational, action-oriented",
    },
}


def get_persona(name: Optional[str]) -> Dict:
    """Return the persona config for a name (safe default → explorer)."""
    if not name:
        return PERSONAS[DEFAULT]
    return PERSONAS.get(str(name).lower(), PERSONAS[DEFAULT])


def persona_keys() -> list[str]:
    return list(PERSONAS.keys())


def persona_category_priority(name: Optional[str]) -> Dict[str, int]:
    """Category priority map for a persona (drives KPI selection order)."""
    return get_persona(name)["category_priority"]


def persona_hero_category(name: Optional[str]) -> str:
    return get_persona(name)["hero_category"]


def persona_focus_instruction(name: Optional[str]) -> str:
    return get_persona(name)["focus_instruction"]


def persona_narrative_style(name: Optional[str]) -> str:
    return get_persona(name)["narrative_style"]


__all__ = [
    "EXPLORER",
    "CEO",
    "ANALYST",
    "MARKETING",
    "OPS",
    "DEFAULT",
    "PERSONAS",
    "get_persona",
    "persona_keys",
    "persona_category_priority",
    "persona_hero_category",
    "persona_focus_instruction",
    "persona_narrative_style",
]
