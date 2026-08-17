"""
Unit tests for the persona system — audience-aware KPI emphasis.

"Same dataset, different audience → different dashboard." A persona
re-ranks which KPI categories get selected by the gate, so a CEO sees
revenue/risk first while an analyst sees statistics first — all
deterministic, no LLM involved.
"""

from services.ai.kpi_gate import _select_candidates
from services.ai.kpi_types import ColumnProfile, ColumnRole
from services.ai.personas import (
    ANALYST,
    CEO,
    EXPLORER,
    MARKETING,
    OPS,
    get_persona,
    persona_category_priority,
    persona_keys,
)


def _profile(name, category, role=ColumnRole.MEASURE, value=100.0, agg="sum"):
    return ColumnProfile(
        name=name,
        role=role,
        n_rows=1000,
        n_nulls=0,
        n_unique=50,
        col_sum=value if agg == "sum" else None,
        col_mean=value if agg == "mean" else None,
        aggregation=agg,
        business_category=category,
    )


def _profiles():
    return [
        _profile("revenue_total", "revenue", value=1_000_000),
        _profile("error_rate", "rate_metric", role=ColumnRole.RATE, value=0.02, agg="mean"),
        _profile("active_users", "users", value=50_000),
        _profile("cost_total", "cost", value=200_000),
        _profile("volume_total", "volume", value=300_000),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Persona config
# ─────────────────────────────────────────────────────────────────────────────


class TestPersonaConfig:
    def test_default_is_explorer(self):
        assert get_persona(None)["label"] == "Explorer"
        assert get_persona("bogus")["label"] == "Explorer"

    def test_persona_keys(self):
        keys = persona_keys()
        assert {"explorer", "ceo", "analyst", "marketing", "ops"} <= set(keys)

    def test_personas_have_distinct_priorities(self):
        # CEO puts revenue first; analyst puts statistics first.
        assert persona_category_priority(CEO)["revenue"] < persona_category_priority(ANALYST)["revenue"]
        assert persona_category_priority(ANALYST)["rate_metric"] < persona_category_priority(CEO)["rate_metric"]

    def test_every_persona_has_focus_and_style(self):
        for key in persona_keys():
            cfg = get_persona(key)
            assert cfg["focus_instruction"]
            assert cfg["narrative_style"]
            assert cfg["hero_category"]


# ─────────────────────────────────────────────────────────────────────────────
# Persona-aware selection (the gate)
# ─────────────────────────────────────────────────────────────────────────────


class TestPersonaSelection:
    def test_ceo_selects_revenue_first_and_hero(self):
        selected = _select_candidates(_profiles(), max_kpis=3, persona=CEO)
        assert selected[0].business_category == "revenue"
        assert selected[0].importance == "hero"

    def test_analyst_selects_rate_metric_first_and_hero(self):
        selected = _select_candidates(_profiles(), max_kpis=3, persona=ANALYST)
        assert selected[0].business_category == "rate_metric"
        assert selected[0].importance == "hero"

    def test_ops_selects_cost_first(self):
        selected = _select_candidates(_profiles(), max_kpis=3, persona=OPS)
        assert selected[0].business_category == "cost"

    def test_marketing_selects_users_first(self):
        selected = _select_candidates(_profiles(), max_kpis=3, persona=MARKETING)
        assert selected[0].business_category == "users"

    def test_explorer_keeps_base_priority(self):
        selected = _select_candidates(_profiles(), max_kpis=3, persona=EXPLORER)
        assert selected[0].business_category == "revenue"

    def test_no_persona_is_backward_compatible(self):
        # No persona → explorer default (base priority, revenue first).
        selected = _select_candidates(_profiles(), max_kpis=3)
        assert selected[0].business_category == "revenue"

    def test_same_dataset_different_audience_different_dashboard(self):
        # The core principle: the SAME profiles yield different orderings.
        ceo = _select_candidates(_profiles(), max_kpis=3, persona=CEO)
        analyst = _select_candidates(_profiles(), max_kpis=3, persona=ANALYST)
        assert ceo[0].name != analyst[0].name
