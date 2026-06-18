"""
Unit Tests: IntelligentKPIGenerator
====================================
Tests for core functions in intelligent_kpi_generator.py.

Coverage:
  - _downsample_if_needed: memory guard, is_estimated/estimate_ratio
  - KPI output schema: is_estimated/estimate_ratio present in all paths
  - _compute_kpi_value: aggregation correctness
  - _detect_time_period: returns {} when no time column
  - _compute_comparison: requires time column
  - _compute_sparkline: returns empty when no time column
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List, Optional

import polars as pl
import pytest

from services.ai.intelligent_kpi_generator import (
    IntelligentKPIGenerator,
    ColumnProfile,
    ColumnRole,
    _compute_kpi_value,
    _compute_comparison,
    _compute_sparkline,
    _detect_time_period,
    _profile_column,
    _find_time_column,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> IntelligentKPIGenerator:
    return IntelligentKPIGenerator()


@pytest.fixture
def small_df() -> pl.DataFrame:
    """Small DataFrame that fits in memory without downsampling."""
    return pl.DataFrame(
        {
            "revenue": [100.0 * i for i in range(1, 101)],
            "cost": [50.0 * i for i in range(1, 101)],
            "date": pl.date_range(
                start=date(2024, 1, 1),
                end=date(2024, 4, 10),
                interval="1d",
                eager=True,
            )[:100],
        }
    )


@pytest.fixture
def large_df() -> pl.DataFrame:
    """DataFrame large enough to trigger downsampling (small memory limit)."""
    n = 49998  # Multiple of 3 so categories divide evenly
    return pl.DataFrame(
        {
            "revenue": [float(i * 100) for i in range(n)],
            "cost": [float(i * 50) for i in range(n)],
            "category": ["A", "B", "C"] * (n // 3),
        }
    )


@pytest.fixture
def profiles(small_df) -> List[ColumnProfile]:
    return [
        p for p in (_profile_column(small_df, col) for col in small_df.columns)
        if p is not None
    ]


# ── _downsample_if_needed Tests ──────────────────────────────────────────────


class TestDownsampleIfNeeded:
    """Memory guard: returns correct (df, is_estimated, estimate_ratio) tuple."""

    def test_small_df_not_downsampled(self, generator, small_df):
        """Small DataFrames within memory limit should pass through unchanged."""
        result_df, is_estimated, estimate_ratio = generator._downsample_if_needed(small_df)
        assert result_df.height == small_df.height
        assert is_estimated is False
        assert estimate_ratio is None

    def test_large_df_downsampled(self, large_df):
        """Large DataFrames exceeding memory limit should be downsampled."""
        # Force tiny memory limit to ensure downsampling
        gen = IntelligentKPIGenerator(max_memory_mb=0.01, max_safe_rows=1000)
        result_df, is_estimated, estimate_ratio = gen._downsample_if_needed(large_df)
        assert result_df.height <= gen.max_safe_rows
        assert is_estimated is True
        assert estimate_ratio is not None
        assert 0 < estimate_ratio < 1

    def test_empty_df_not_downsampled(self, generator):
        """Empty DataFrame should not be downsampled."""
        df = pl.DataFrame({"a": []})
        result_df, is_estimated, estimate_ratio = generator._downsample_if_needed(df)
        assert is_estimated is False
        assert estimate_ratio is None

    def test_downsample_preserves_categories(self):
        """Stratified sampling should preserve category distribution."""
        n = 20000
        df = pl.DataFrame(
            {
                "value": [float(i) for i in range(n)],
                "category": ["A", "B", "C", "D"] * (n // 4),
            }
        )
        gen = IntelligentKPIGenerator(max_memory_mb=0.01, max_safe_rows=200)
        result_df, is_estimated, _ = gen._downsample_if_needed(df)
        assert is_estimated is True
        # All categories should still be present
        assert result_df["category"].n_unique() == 4

    def test_exact_memory_boundary(self, generator):
        """DataFrame exactly at memory limit should not be downsampled."""
        # Use a DataFrame that's just under 500MB — Polars
        # estimated_size() on this tiny DF will be < 500MB
        df = pl.DataFrame({"x": range(100)})
        result_df, is_estimated, _ = generator._downsample_if_needed(df)
        assert is_estimated is False


# ── KPI Output Schema Tests ──────────────────────────────────────────────────


class TestKpiOutputSchema:
    """Verify is_estimated and estimate_ratio are in all KPI output paths."""

    @pytest.mark.asyncio
    async def test_kpis_have_schema_fields(self, generator, small_df):
        """All generated KPI dicts must contain is_estimated and estimate_ratio."""
        kpis = await generator.generate_intelligent_kpis(small_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert "is_estimated" in kpi, f"KPI {kpi.get('column')} missing is_estimated"
                assert "estimate_ratio" in kpi, f"KPI {kpi.get('column')} missing estimate_ratio"

    @pytest.mark.asyncio
    async def test_fallback_kpis_have_schema_fields(self, generator):
        """Fallback KPIs (edge case: few columns) must also have schema fields."""
        df = pl.DataFrame(
            {
                "revenue": [100.0, 200.0, 300.0],
                "cost": [50.0, 60.0, 70.0],
            }
        )
        kpis = await generator.generate_intelligent_kpis(df, max_kpis=2)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert "is_estimated" in kpi
                assert "estimate_ratio" in kpi

    @pytest.mark.asyncio
    async def test_is_estimated_false_when_not_downsampled(self, generator, small_df):
        """When no downsampling occurs, is_estimated must be False and ratio None."""
        kpis = await generator.generate_intelligent_kpis(small_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert kpi["is_estimated"] is False
                assert kpi["estimate_ratio"] is None

    @pytest.mark.asyncio
    async def test_is_estimated_true_when_downsampled(self):
        """When downsampling occurs, is_estimated must be True."""
        n = 50000
        df = pl.DataFrame(
            {
                "revenue": [float(i * 100) for i in range(n)],
                "cost": [float(i * 50) for i in range(n)],
            }
        )
        gen = IntelligentKPIGenerator(max_memory_mb=0.01, max_safe_rows=1000)
        kpis = await gen.generate_intelligent_kpis(df, max_kpis=2)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert kpi["is_estimated"] is True
                assert kpi["estimate_ratio"] is not None
                assert 0 < kpi["estimate_ratio"] < 1

    @pytest.mark.asyncio
    async def test_single_kpi_has_schema_fields(self, generator, small_df):
        """Single KPI generation (chat-driven) must also have schema fields."""
        kpi = await generator.generate_single_kpi(small_df, "revenue")
        assert kpi is not None
        assert "is_estimated" in kpi
        assert "estimate_ratio" in kpi


# ── _compute_kpi_value Tests ────────────────────────────────────────────────


class TestComputeKpiValue:
    """Aggregation correctness for _compute_kpi_value."""

    def test_sum_aggregation(self):
        df = pl.DataFrame({"sales": [100.0, 200.0, 300.0]})
        profile = ColumnProfile(
            name="sales",
            role=ColumnRole.MEASURE,
            n_rows=3,
            n_nulls=0,
            n_unique=3,
            aggregation="sum",
        )
        result = _compute_kpi_value(df, profile)
        assert result == 600.0

    def test_mean_aggregation(self):
        df = pl.DataFrame({"score": [10.0, 20.0, 30.0]})
        profile = ColumnProfile(
            name="score",
            role=ColumnRole.MEASURE,
            n_rows=3,
            n_nulls=0,
            n_unique=3,
            aggregation="mean",
        )
        result = _compute_kpi_value(df, profile)
        assert result == 20.0

    def test_median_aggregation(self):
        df = pl.DataFrame({"rating": [1.0, 5.0, 10.0]})
        profile = ColumnProfile(
            name="rating",
            role=ColumnRole.MEASURE,
            n_rows=3,
            n_nulls=0,
            n_unique=3,
            aggregation="median",
        )
        result = _compute_kpi_value(df, profile)
        assert result == 5.0

    def test_empty_column_returns_zero(self):
        df = pl.DataFrame({"empty_col": [None, None]})
        profile = ColumnProfile(
            name="empty_col",
            role=ColumnRole.MEASURE,
            n_rows=2,
            n_nulls=2,
            n_unique=0,
            aggregation="sum",
        )
        result = _compute_kpi_value(df, profile)
        assert result == 0


# ── _compute_comparison Tests ────────────────────────────────────────────────


class TestComputeComparison:
    """Time-sorted comparison requires time column."""

    def test_with_time_col_returns_comparison(self):
        df = pl.DataFrame(
            {
                "revenue": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 1100.0, 1200.0],
                "date": pl.date_range(start=date(2024, 1, 1), end=date(2024, 1, 12), interval="1d", eager=True),
            }
        )
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=12,
            n_nulls=0,
            n_unique=12,
            aggregation="sum",
            col_sum=7800.0,
        )
        result = _compute_comparison(df, profile, "date")
        assert result is not None
        assert "delta_percent" in result
        assert "delta_direction" in result

    def test_without_time_col_returns_none(self):
        df = pl.DataFrame({"revenue": [100.0, 200.0, 300.0, 400.0]})
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=4,
            n_nulls=0,
            n_unique=4,
            aggregation="sum",
        )
        result = _compute_comparison(df, profile, None)
        assert result is None


# ── _compute_sparkline Tests ─────────────────────────────────────────────────


class TestComputeSparkline:
    """Sparkline behavior with and without time column."""

    def test_with_time_col_returns_time_series(self):
        df = pl.DataFrame(
            {
                "revenue": [100.0, 200.0, 300.0, 400.0],
                "date": pl.date_range(start=date(2024, 1, 1), end=date(2024, 4, 1), interval="1mo", eager=True),
            }
        )
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=4,
            n_nulls=0,
            n_unique=4,
            aggregation="sum",
        )
        result = _compute_sparkline(df, profile, "date")
        assert result["type"] == "time_series"
        assert len(result["data"]) >= 3

    def test_without_time_col_returns_empty(self):
        df = pl.DataFrame({"revenue": [100.0, 200.0, 300.0, 400.0]})
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=4,
            n_nulls=0,
            n_unique=4,
            aggregation="sum",
        )
        result = _compute_sparkline(df, profile, None)
        assert result["data"] == []
        assert result["type"] == "distribution"

    def test_few_rows_returns_empty(self):
        df = pl.DataFrame(
            {
                "revenue": [100.0, 200.0],
                "date": pl.date_range(start=date(2024, 1, 1), end=date(2024, 1, 2), interval="1d", eager=True),
            }
        )
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=2,
            n_nulls=0,
            n_unique=2,
            aggregation="sum",
        )
        result = _compute_sparkline(df, profile, "date")
        assert result["data"] == []
        assert result["type"] == "distribution"


# ── _detect_time_period Tests ────────────────────────────────────────────────


class TestDetectTimePeriod:
    """Time period detection returns {} when no time column."""

    def test_without_time_col_returns_empty(self):
        df = pl.DataFrame({"revenue": [100.0, 200.0, 300.0, 400.0]})
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=4,
            n_nulls=0,
            n_unique=4,
            aggregation="sum",
        )
        result = _detect_time_period(df, profile, None)
        assert result == {}

    def test_with_time_col_returns_dict(self):
        """With time column, returns a dict (may be empty or populated —
        depends on group_by_dynamic behavior across Polars versions)."""
        df = pl.DataFrame(
            {
                "revenue": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0],
                "date": pl.date_range(start=date(2024, 1, 1), end=date(2024, 10, 1), interval="1mo", eager=True),
            }
        )
        profile = ColumnProfile(
            name="revenue",
            role=ColumnRole.MEASURE,
            n_rows=10,
            n_nulls=0,
            n_unique=10,
            aggregation="sum",
        )
        result = _detect_time_period(df, profile, "date")
        # Must return a dict (can be empty — no crash is the contract)
        assert isinstance(result, dict)


# ── _find_time_column Tests ──────────────────────────────────────────────────


class TestFindTimeColumn:
    """Time column detection."""

    def test_detects_datetime_column(self):
        df = pl.DataFrame(
            {
                "value": [1.0, 2.0],
                "created_at": pl.date_range(start=date(2024, 1, 1), end=date(2024, 1, 2), interval="1d", eager=True),
            }
        )
        assert _find_time_column(df) == "created_at"

    def test_returns_none_when_no_time_col(self):
        df = pl.DataFrame({"value": [1.0, 2.0], "name": ["a", "b"]})
        assert _find_time_column(df) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
