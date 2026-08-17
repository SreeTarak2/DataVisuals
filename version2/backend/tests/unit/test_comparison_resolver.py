"""
Unit tests for the comparison-period resolver + period-over-period KPI
comparison (the "which baseline?" decision made explicit).

Covers:
1. EXPLICIT — the question names a comparison and it is honored.
2. DEFAULT  — no explicit comparison → data-driven default by date range.
3. CLARIFY  — multi-year data + no explicit comparison → flag it.
4. COMPUTE  — _compute_comparison produces correct deltas for prior_period,
   prior_year, rolling_baseline, and keeps the first-half fallback.
"""

import polars as pl
from datetime import date

from services.ai.comparison_resolver import (
    PRIOR_PERIOD,
    PRIOR_YEAR,
    ROLLING_BASELINE,
    comparison_label,
    date_range_days_from_df,
    resolve_comparison_for_df,
    resolve_comparison_period,
)
from services.ai.kpi_compute import _compute_comparison
from services.ai.kpi_types import ColumnProfile, ColumnRole


# ─────────────────────────────────────────────────────────────────────────────
# Resolver — explicit extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestExplicitExtraction:
    def test_yoy_phrase(self):
        r = resolve_comparison_period("why did sales drop vs last year?")
        assert r.comparison == PRIOR_YEAR
        assert r.source == "explicit"
        assert r.needs_clarification is False
        assert "last year" in r.label

    def test_mom_phrase(self):
        r = resolve_comparison_period("is revenue declining month over month?")
        assert r.comparison == PRIOR_PERIOD
        assert r.source == "explicit"

    def test_rolling_phrase(self):
        r = resolve_comparison_period("how are July sales vs the 3-month average?")
        assert r.comparison == ROLLING_BASELINE
        assert r.source == "explicit"

    def test_specific_year(self):
        r = resolve_comparison_period("compare July 2025 vs 2024")
        assert r.comparison == PRIOR_YEAR
        assert r.source == "explicit"

    def test_matches_case_insensitively(self):
        r = resolve_comparison_period("YOY change in premium product sales")
        assert r.comparison == PRIOR_YEAR

    def test_ignores_comparison_words_that_are_not_periods(self):
        # "compare" alone (segment comparison) must NOT become a period baseline.
        r = resolve_comparison_period("compare revenue by region")
        assert r.source == "default"


# ─────────────────────────────────────────────────────────────────────────────
# Resolver — data-driven default + clarification flag
# ─────────────────────────────────────────────────────────────────────────────


class TestDefaultAndClarification:
    def test_multiyear_defaults_to_yoy_and_asks(self):
        r = resolve_comparison_period("why did sales drop?", date_range_days=800)
        assert r.comparison == PRIOR_YEAR
        assert r.source == "default"
        assert r.needs_clarification is True  # YoY vs MoM changes the answer

    def test_short_range_defaults_to_prior_period(self):
        r = resolve_comparison_period("why did sales drop?", date_range_days=200)
        assert r.comparison == PRIOR_PERIOD
        assert r.source == "default"
        assert r.needs_clarification is False

    def test_very_short_range_no_comparison(self):
        r = resolve_comparison_period("why did sales drop?", date_range_days=5)
        assert r.comparison == "none"
        assert r.source == "default"

    def test_empty_question_defaults(self):
        r = resolve_comparison_period(None, date_range_days=400)
        assert r.source == "default"
        assert r.comparison == PRIOR_PERIOD

    def test_labels(self):
        assert comparison_label(PRIOR_YEAR) == "vs same period last year"
        assert comparison_label(PRIOR_PERIOD) == "vs previous period"
        assert comparison_label(None) == "no comparison"


# ─────────────────────────────────────────────────────────────────────────────
# Resolver — df-aware (date range extracted from the actual data)
# ─────────────────────────────────────────────────────────────────────────────


class TestDfAwareResolution:
    def test_date_range_from_df(self):
        df = _monthly_df([100] * 13, 2024, 1)  # Jan 2024 → Jan 2025 ≈ 365 days
        days = date_range_days_from_df(df)
        assert days is not None
        assert 364 <= days <= 367

    def test_resolve_for_df_defaults_to_yoy_on_multiyear(self):
        df = _monthly_df(list(range(1, 37)), 2024, 1)  # 3 years of months
        r = resolve_comparison_for_df("why did sales drop?", df)
        assert r.comparison == PRIOR_YEAR
        assert r.source == "default"
        assert r.needs_clarification is True

    def test_resolve_for_df_explicit_wins(self):
        df = _monthly_df([100] * 6)
        r = resolve_comparison_for_df("why did sales drop month over month?", df)
        assert r.comparison == PRIOR_PERIOD
        assert r.source == "explicit"
        assert r.needs_clarification is False

    def test_resolve_for_df_without_date_column(self):
        df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        r = resolve_comparison_for_df("why did sales drop?", df)
        assert r.source == "default"
        assert r.comparison == "none"

    def test_resolve_for_df_none_df(self):
        r = resolve_comparison_for_df(None, None)
        assert r.source == "default"


# ─────────────────────────────────────────────────────────────────────────────
# Compute — period-over-period deltas (deterministic, polars)
# ─────────────────────────────────────────────────────────────────────────────


def _monthly_df(values, start_year=2024, start_month=1):
    rows = []
    y, m = start_year, start_month
    for v in values:
        rows.append((date(y, m, 1), v))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return pl.DataFrame({"date": [r[0] for r in rows], "revenue": [r[1] for r in rows]})


def _profile(polarity="higher_is_better"):
    return ColumnProfile(
        name="revenue", aggregation="sum", role=ColumnRole.MEASURE,
        importance="medium", business_category="general", polarity=polarity,
        col_p75=None, col_median=None, n_nulls=0, n_rows=24, n_unique=24,
    )


class TestPeriodComparisonCompute:
    def test_prior_period_delta(self):
        # Jan=100, Feb=110, Mar=90, Apr=80 → last (80) vs prev (90) = -11.1%
        df = _monthly_df([100, 110, 90, 80])
        comp = _compute_comparison(df, _profile(), "date", PRIOR_PERIOD)
        assert comp is not None
        assert comp["delta_percent"] == -11.1
        assert comp["comparison_label"] == "vs previous period"
        assert comp["comparison_value"] == 90.0
        assert comp["delta_direction"] == "down"

    def test_prior_year_delta(self):
        # Jan24..Feb25 values 1..14 → last (Feb25=14) vs Feb24=2 → +600%
        df = _monthly_df(list(range(1, 15)), 2024, 1)
        comp = _compute_comparison(df, _profile(), "date", PRIOR_YEAR)
        assert comp is not None
        assert comp["delta_percent"] == 600.0
        assert comp["comparison_label"] == "vs same period last year"

    def test_prior_year_missing_same_month_returns_none(self):
        # Only 6 months of data — no same-month-last-year exists.
        df = _monthly_df([100, 110, 120, 90, 80, 85])
        comp = _compute_comparison(df, _profile(), "date", PRIOR_YEAR)
        assert comp is None

    def test_rolling_baseline_delta(self):
        # Last 3 months avg = 100, current = 130 → +30%
        df = _monthly_df([100, 100, 100, 130])
        comp = _compute_comparison(df, _profile(), "date", ROLLING_BASELINE)
        assert comp is not None
        assert comp["delta_percent"] == 30.0
        assert comp["comparison_label"] == "vs 3-period average"

    def test_default_first_half_fallback(self):
        # Backward compatible: no comparison key → first-half vs second-half.
        df = _monthly_df([100] * 6 + [50] * 6)  # 12 months: 600 vs 300 → -50%
        comp = _compute_comparison(df, _profile(), "date", None)
        assert comp is not None
        assert comp["delta_percent"] == -50.0
        assert comp["comparison_label"] == "vs first half (time-sorted)"

    def test_polarity_drives_is_good(self):
        df = _monthly_df([100, 110, 90, 80])  # down → bad for higher_is_better
        comp = _compute_comparison(df, _profile(), "date", PRIOR_PERIOD)
        assert comp["is_good"] is False
        # Down is GOOD for lower_is_better (e.g. costs)
        comp2 = _compute_comparison(df, _profile("lower_is_better"), "date", PRIOR_PERIOD)
        assert comp2["is_good"] is True

    def test_not_enough_periods_returns_none(self):
        df = _monthly_df([100])  # single month
        comp = _compute_comparison(df, _profile(), "date", PRIOR_PERIOD)
        assert comp is None
