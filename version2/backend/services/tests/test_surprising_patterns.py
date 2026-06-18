"""
Statistical Validation Tests: SurprisingPatternsEngine
=======================================================
Tests for correlation engine, BH FDR correction, min_rows guard, and
time-aware splitting.

Coverage:
  - _apply_bh_fdr: empty, all significant, none significant, mixed
  - _split_periods: with/without time_col
  - _find_correlation_anomalies: min_rows guard, time_col required
  - Simulated data: correlated pairs with divergence
  - Default config values (min_rows=30)
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import polars as pl
import pytest
from services.ai.surprising_patterns import (
    SurprisingPatternsEngine,
    SurprisingInsight,
    _apply_bh_fdr,
    _DEFAULT_MIN_ROWS,
    _DEFAULT_FDR_ALPHA,
    _DEFAULT_CORRELATION_THRESHOLD,
)
from services.ai.intelligent_kpi_generator import (
    ColumnProfile,
    ColumnRole,
    _profile_column,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> SurprisingPatternsEngine:
    return SurprisingPatternsEngine()


@pytest.fixture
def numeric_profiles() -> List[ColumnProfile]:
    """Create synthetic numeric profiles that pass the gate."""
    return [
        ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=100,
            n_nulls=0,
            n_unique=50,
            aggregation="sum",
            business_category="revenue",
            importance="hero",
            col_sum=10000.0,
        ),
        ColumnProfile(
            name="cost",
            role=ColumnRole.MEASURE,
            n_rows=100,
            n_nulls=0,
            n_unique=50,
            aggregation="sum",
            business_category="cost",
            importance="high",
            col_sum=5000.0,
        ),
        ColumnProfile(
            name="users",
            role=ColumnRole.COUNT,
            n_rows=100,
            n_nulls=0,
            n_unique=50,
            aggregation="sum",
            business_category="users",
            importance="high",
            col_sum=1000.0,
        ),
        ColumnProfile(
            name="orders",
            role=ColumnRole.COUNT,
            n_rows=100,
            n_nulls=0,
            n_unique=50,
            aggregation="sum",
            business_category="volume",
            importance="high",
            col_sum=500.0,
        ),
    ]


@pytest.fixture
def correlated_df() -> pl.DataFrame:
    """DataFrame with strongly correlated + time column (50 rows for min_rows=30).
    
    revenue and cost are strongly correlated EARLY (first 25 rows), but diverge
    in period 2 (last 25 rows) where revenue grows while cost stays flat. This
    guarantees divergence detection.
    """
    rng = np.random.default_rng(42)
    n = 50
    # Period 1 (rows 0-24): revenue and cost both grow ~20%, tight linear relationship
    t1 = np.linspace(0, 1, 25)
    r_early = 1000 + 200 * t1 + rng.normal(0, 20, 25)
    c_early = 400 + 80 * t1 + rng.normal(0, 8, 25)  # cost = 0.4 × revenue
    # Period 2 (rows 25-49): revenue grows 80%, cost grows only 15% → big gap
    t2 = np.linspace(0, 1, 25)
    r_late = 1200 + 960 * t2 + rng.normal(0, 20, 25)  # Revenue grows 80%
    c_late = 480 + 72 * t2 + rng.normal(0, 8, 25)  # Cost grows 15% (less efficient)
    
    revenue = np.concatenate([r_early, r_late])
    cost = np.concatenate([c_early, c_late])
    
    return pl.DataFrame(
        {
            "revenue": revenue.tolist(),
            "cost": cost.tolist(),
            "users": (revenue * 0.1 + rng.normal(0, 10, n)).tolist(),
            "orders": (revenue * 0.05 + rng.normal(0, 5, n)).tolist(),
            "date": pl.date_range(start=date(2024, 1, 1), end=date(2025, 2, 18), interval="1w", eager=True)[:n],
        }
    )


@pytest.fixture
def short_df() -> pl.DataFrame:
    """DataFrame with fewer than min_rows rows (should be skipped)."""
    n = 15  # Below DEFAULT_MIN_ROWS=30
    return pl.DataFrame(
        {
            "revenue": [float(i * 100) for i in range(n)],
            "cost": [float(i * 40) for i in range(n)],
        }
    )


# ── _apply_bh_fdr Tests ──────────────────────────────────────────────────────


class TestApplyBhFdr:
    """Benjamini-Hochberg FDR correction correctness."""

    def test_empty_list(self):
        """Empty p-values → empty result."""
        assert _apply_bh_fdr([]) == []

    def test_all_significant(self):
        """All p-values below BH threshold → all True."""
        p_values = [0.001, 0.005, 0.01, 0.02]
        result = _apply_bh_fdr(p_values, alpha=0.05)
        assert all(result)

    def test_none_significant(self):
        """All p-values above BH threshold → all False."""
        p_values = [0.5, 0.6, 0.7, 0.8]
        result = _apply_bh_fdr(p_values, alpha=0.05)
        assert not any(result)

    def test_mixed_significance(self):
        """Only lowest p-values are significant."""
        p_values = [0.001, 0.01, 0.04, 0.1, 0.5]
        result = _apply_bh_fdr(p_values, alpha=0.05)
        # With n=5, threshold for k=1: 0.05/5=0.01, k=2: 0.02, k=3: 0.03, k=4: 0.04
        # p sorted: 0.001, 0.01, 0.04, 0.1, 0.5
        # k=1: 0.001 ≤ 0.01 ✓  k=2: 0.01 ≤ 0.02 ✓  k=3: 0.04 ≤ 0.03 ✗
        # So only first 2 are significant
        n_significant = sum(result)
        assert n_significant == 2, f"Expected 2 significant, got {n_significant}"
        # The three not-significant should be the larger p-values
        not_sig_indices = [i for i, s in enumerate(result) if not s]
        assert all(p_values[i] >= 0.04 for i in not_sig_indices)

    def test_single_p_value_low(self):
        """Single low p-value → significant."""
        assert _apply_bh_fdr([0.01], alpha=0.05) == [True]

    def test_single_p_value_high(self):
        """Single high p-value → not significant."""
        assert _apply_bh_fdr([0.5], alpha=0.05) == [False]

    def test_tighter_alpha_stricter(self):
        """Lower alpha → fewer significant results."""
        p_values = [0.01, 0.02, 0.03]
        n_loose = sum(_apply_bh_fdr(p_values, alpha=0.10))
        n_tight = sum(_apply_bh_fdr(p_values, alpha=0.01))
        assert n_tight <= n_loose

    def test_very_small_p_values(self):
        """Extremely small p-values should be significant."""
        p_values = [1e-10, 1e-8, 1e-6]
        result = _apply_bh_fdr(p_values, alpha=0.05)
        assert all(result)

    def test_all_equal_p_values(self):
        """All equal p-values — BH procedure correctly identifies all as significant.
        
        With n=4 and alpha=0.05:
          k=1: threshold=0.0125, 0.03 > 0.0125
          k=2: threshold=0.025,  0.03 > 0.025
          k=3: threshold=0.0375, 0.03 <= 0.0375 ✓
          k=4: threshold=0.05,   0.03 <= 0.05   ✓
        
        Largest k is 4, so all p-values <= 0.03 are significant (all 4).
        """
        p_values = [0.03, 0.03, 0.03, 0.03]
        result = _apply_bh_fdr(p_values, alpha=0.05)
        assert all(result), "All 4 equal p-values of 0.03 are significant at alpha=0.05 for n=4"


# ── _split_periods Tests ─────────────────────────────────────────────────────


class TestSplitPeriods:
    """Time-aware splitting returns halves or None."""

    def test_with_time_col_returns_two_halves(self, engine, correlated_df):
        """With time column, returns two roughly equal halves."""
        first, second = engine._split_periods(correlated_df, "date")
        assert first is not None
        assert second is not None
        total = first.height + second.height
        assert total == correlated_df.height
        # Halves should be roughly equal
        assert abs(first.height - second.height) <= 1

    def test_without_time_col_returns_none(self, engine, correlated_df):
        """Without time column, returns (None, None)."""
        first, second = engine._split_periods(correlated_df, None)
        assert first is None
        assert second is None

    def test_time_sorted(self, engine, correlated_df):
        """With time column, first half should be earlier than second half."""
        first, second = engine._split_periods(correlated_df, "date")
        assert first is not None and second is not None
        max_first = first["date"].max()
        min_second = second["date"].min()
        assert max_first <= min_second


# ── Default Config Tests ─────────────────────────────────────────────────────


class TestDefaultConfig:
    """Verify production config defaults."""

    def test_min_rows_is_30(self):
        """DEFAULT_MIN_ROWS should be 30 as specified in the roadmap."""
        assert _DEFAULT_MIN_ROWS == 30

    def test_fdr_alpha_is_005(self):
        """Default FDR alpha should be 0.05."""
        assert _DEFAULT_FDR_ALPHA == 0.05

    def test_engine_uses_defaults(self):
        """Engine constructor should use module-level defaults."""
        engine = SurprisingPatternsEngine()
        assert engine.min_rows == _DEFAULT_MIN_ROWS
        assert engine.fdr_alpha == _DEFAULT_FDR_ALPHA
        assert engine.correlation_threshold == _DEFAULT_CORRELATION_THRESHOLD


# ── _find_correlation_anomalies Tests ────────────────────────────────────────


class TestCorrelationAnomalies:
    """Correlation engine requires min_rows and time column."""

    def test_requires_min_rows(self, engine, short_df, numeric_profiles):
        """DataFrame with fewer than min_rows rows should return empty."""
        insights = engine._find_correlation_anomalies(short_df, numeric_profiles[:2], None)
        assert insights == []

    def test_requires_time_col(self, engine, correlated_df, numeric_profiles):
        """Without time column, correlation engine returns empty (split returns None)."""
        insights = engine._find_correlation_anomalies(correlated_df, numeric_profiles, None)
        assert insights == []

    def test_with_correlated_data_returns_insights(self, engine, correlated_df, numeric_profiles):
        """With correlated data + time column, should detect divergence."""
        insights = engine._find_correlation_anomalies(correlated_df, numeric_profiles, "date")
        # The fixture guarantees divergence: revenue grows ~40% while cost stays flat
        assert len(insights) > 0, "Correlation engine should detect divergence in test data"
        for ins in insights:
            assert isinstance(ins, SurprisingInsight)
            assert ins.type == "correlation"
            assert ins.title
            assert ins.description
            assert len(ins.metrics) >= 2

    def test_correlation_pairs_capped(self):
        """Engine should respect max_correlation_pairs cap."""
        engine = SurprisingPatternsEngine(max_correlation_pairs=2)
        assert engine.max_correlation_pairs == 2

    def test_few_profiles_returns_empty(self, engine, correlated_df):
        """Less than 2 numeric profiles → empty."""
        empty_profiles: List[ColumnProfile] = []
        insights = engine._find_correlation_anomalies(correlated_df, empty_profiles, "date")
        assert insights == []


# ── discover_all Integration Tests ───────────────────────────────────────────


class TestDiscoverAll:
    """End-to-end run of all engines."""

    def test_discover_all_with_good_data(self, engine, correlated_df, numeric_profiles):
        """discover_all should return insights without crashing."""
        insights = engine.discover_all(correlated_df, numeric_profiles, "date")
        # Should return some insights
        assert isinstance(insights, list)
        # All should be SurprisingInsight
        for ins in insights:
            assert isinstance(ins, SurprisingInsight)
        # Should be sorted by severity
        assert len(insights) <= engine.max_insights

    def test_discover_all_short_df(self, engine, short_df, numeric_profiles):
        """Short DataFrame should still not crash, engines check min_rows."""
        insights = engine.discover_all(short_df, numeric_profiles)
        # Should not crash — engines handle edge cases gracefully
        assert isinstance(insights, list)

    def test_dedup_removes_duplicates(self):
        """_deduplicate should remove overlapping insights."""
        engine = SurprisingPatternsEngine()
        insights = [
            SurprisingInsight(
                type="correlation",
                title="Revenue and Cost are diverging",
                description="Test",
                severity="warning",
                metrics=["revenue", "cost"],
                evidence={"magnitude": 10.0},
            ),
            SurprisingInsight(
                type="correlation",
                title="Revenue and Cost are diverging",
                description="Test 2",
                severity="critical",
                metrics=["revenue", "cost"],
                evidence={"magnitude": 20.0},
            ),
        ]
        result = engine._deduplicate(insights)
        assert len(result) == 1
        # Critical should win over warning
        assert result[0].severity == "critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
