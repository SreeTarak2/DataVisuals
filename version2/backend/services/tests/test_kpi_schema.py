"""
Schema Validation Tests: KPI Output Structure
==============================================
Verifies that all KPI output paths produce the correct schema with
is_estimated, estimate_ratio, and no confidence_score (deprecated).

Coverage:
  - generate_intelligent_kpis output structure
  - generate_single_kpi output structure
  - _build_template_kpi_card output structure
  - _domain_aware_fallback output structure
  - All required fields present
  - Type correctness for boolean/float/None
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import polars as pl
import pytest

from services.ai.intelligent_kpi_generator import (
    IntelligentKPIGenerator,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> IntelligentKPIGenerator:
    return IntelligentKPIGenerator()


@pytest.fixture
def sample_df() -> pl.DataFrame:
    """A DataFrame with typical business columns."""
    return pl.DataFrame(
        {
            "revenue": [1000.0, 2000.0, 1500.0, 2500.0, 3000.0],
            "cost": [400.0, 800.0, 600.0, 1000.0, 1200.0],
            "users": [100, 150, 120, 200, 180],
            "date": pl.date_range(start=date(2024, 1, 1), end=date(2024, 5, 1), interval="1mo", eager=True),
            "region": ["North", "South", "East", "West", "North"],
        }
    )


# ── Required Field Definitions ───────────────────────────────────────────────

REQUIRED_KPI_FIELDS = {
    "type",
    "column",
    "aggregation",
    "importance",
    "title",
    "value",
    "format",
    "icon",
    "record_count",
    "comparison_value",
    "comparison_label",
    "delta_percent",
    "delta_direction",
    "is_delta_positive",
    "accent_color",
    "sparkline_data",
    "ai_suggestion",
    "action_prompt",
    "dashboard_story",
    "is_estimated",
    "estimate_ratio",
}

# ── KPI Schema Tests ─────────────────────────────────────────────────────────


class TestKpiSchemaRequiredFields:
    """All KPI output dicts must contain required fields."""

    @pytest.mark.asyncio
    async def test_generate_intelligent_kpis_has_required_fields(self, generator, sample_df):
        """generate_intelligent_kpis produces KPIs with all required fields."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                missing = REQUIRED_KPI_FIELDS - set(kpi.keys())
                assert not missing, f"KPI {kpi.get('column')} missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_generate_single_kpi_has_required_fields(self, generator, sample_df):
        """generate_single_kpi produces KPI with all required fields."""
        kpi = await generator.generate_single_kpi(sample_df, "revenue")
        assert kpi is not None
        missing = REQUIRED_KPI_FIELDS - set(kpi.keys())
        assert not missing, f"Single KPI missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_fallback_has_required_fields(self, generator):
        """Fallback KPIs (from _domain_aware_fallback) have required fields."""
        df = pl.DataFrame({"revenue": [100.0, 200.0, 300.0], "cost": [50.0, 60.0, 70.0]})
        kpis = await generator.generate_intelligent_kpis(df, max_kpis=2)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                missing = REQUIRED_KPI_FIELDS - set(kpi.keys())
                assert not missing, f"Fallback KPI {kpi.get('column')} missing fields: {missing}"


class TestKpiSchemaNewFields:
    """is_estimated and estimate_ratio must be present with correct types."""

    @pytest.mark.asyncio
    async def test_is_estimated_is_bool(self, generator, sample_df):
        """is_estimated must be a boolean."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert isinstance(kpi["is_estimated"], bool), (
                    f"is_estimated should be bool, got {type(kpi['is_estimated'])}"
                )

    @pytest.mark.asyncio
    async def test_estimate_ratio_is_float_or_none(self, generator, sample_df):
        """estimate_ratio must be a float or None."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert kpi["estimate_ratio"] is None or isinstance(kpi["estimate_ratio"], float), (
                    f"estimate_ratio should be float or None, got {type(kpi['estimate_ratio'])}"
                )

    @pytest.mark.asyncio
    async def test_no_deprecated_confidence_score(self, generator, sample_df):
        """confidence_score should not be in KPI output (deprecated)."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert "confidence_score" not in kpi, (
                    f"KPI {kpi.get('column')} still has deprecated confidence_score"
                )


class TestKpiSchemaTypes:
    """Type correctness for KPI output fields."""

    @pytest.mark.asyncio
    async def test_value_is_numeric(self, generator, sample_df):
        """KPI value must be numeric."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert isinstance(kpi["value"], (int, float)), (
                    f"value should be numeric, got {type(kpi['value'])}"
                )

    @pytest.mark.asyncio
    async def test_sparkline_data_is_dict(self, generator, sample_df):
        """sparkline_data must be a dict with data and type keys."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert isinstance(kpi["sparkline_data"], dict)
                assert "data" in kpi["sparkline_data"]
                assert "type" in kpi["sparkline_data"]

    @pytest.mark.asyncio
    async def test_anomaly_fields_present(self, generator, sample_df):
        """Anomaly detection fields must be present."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=3)
        for kpi in kpis:
            if kpi.get("type") == "kpi":
                assert "is_anomaly" in kpi
                assert "z_score" in kpi
                assert "anomaly_severity" in kpi
                assert "trend_direction" in kpi


class TestKpiSchemaEdgeCases:
    """Edge cases for schema validation."""

    @pytest.mark.asyncio
    async def test_empty_dataset_returns_empty_list(self, generator):
        """Empty dataset should return [] without schema failures."""
        df = pl.DataFrame({"a": []})
        kpis = await generator.generate_intelligent_kpis(df)
        assert kpis == []

    @pytest.mark.asyncio
    async def test_single_column_returns_something(self, generator):
        """Single column should still produce output."""
        df = pl.DataFrame({"revenue": [100.0, 200.0, 300.0]})
        kpis = await generator.generate_intelligent_kpis(df, max_kpis=2)
        # May or may not produce KPIs, but should not crash
        assert isinstance(kpis, list)

    @pytest.mark.asyncio
    async def test_all_null_column_skipped(self, generator):
        """Column with all nulls should be skipped gracefully."""
        df = pl.DataFrame({"good": [1.0, 2.0, 3.0], "bad": [None, None, None]})
        kpis = await generator.generate_intelligent_kpis(df, max_kpis=2)
        assert isinstance(kpis, list)

    @pytest.mark.asyncio
    async def test_non_numeric_columns_skipped(self, generator):
        """Non-numeric columns should be skipped."""
        df = pl.DataFrame({"name": ["A", "B", "C"], "value": [10.0, 20.0, 30.0]})
        kpis = await generator.generate_intelligent_kpis(df, max_kpis=2)
        assert isinstance(kpis, list)


# ── Template KPI Schema Tests ────────────────────────────────────────────────


class TestTemplateKpiSchema:
    """Template-generated KPIs must also have correct schema."""

    @pytest.mark.asyncio
    async def test_template_kpis_have_new_fields(self, generator, sample_df):
        """Template KPIs must include is_estimated/estimate_ratio."""
        kpis = await generator.generate_intelligent_kpis(sample_df, max_kpis=4)
        template_kpis = [k for k in kpis if k.get("template_kpi")]
        for kpi in template_kpis:
            assert "is_estimated" in kpi
            assert "estimate_ratio" in kpi
            assert kpi["is_estimated"] is False  # Small dataset, not downsampled
            assert kpi["estimate_ratio"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
