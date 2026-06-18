"""
Integration Tests: KPICAgent Deduplication
===========================================
Tests for _dedup_kpis_by_slug in kpi_agent.py.

Coverage:
  - Empty inputs → []
  - Cards only → all cards returned
  - Intelligent KPIs only → all returned
  - Overlapping slugs → intelligent KPI wins
  - No overlap → both sets merged
  - Mixed types (dicts, objects with .column attribute)
  - Empty/blank slug handling
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from services.multi_agent.kpi_agent import _dedup_kpis_by_slug


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _card(column: str, title: str = "") -> Dict[str, Any]:
    return {"column": column, "title": title or column, "source": "card"}


def _intelligent_kpi(column: str, title: str = "") -> Dict[str, Any]:
    return {"column": column, "title": title or column, "source": "intelligent"}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestDedupKpisBySlug:
    """_dedup_kpis_by_slug: merge cards + intelligent_kpis by slug."""

    def test_empty_inputs(self):
        """Both empty → empty result."""
        result = _dedup_kpis_by_slug([], [])
        assert result == []

    def test_only_cards(self):
        """Cards only → all cards returned."""
        cards = [_card("revenue"), _card("cost")]
        result = _dedup_kpis_by_slug(cards, [])
        assert len(result) == 2
        assert all(c["source"] == "card" for c in result)

    def test_only_intelligent_kpis(self):
        """Intelligent KPIs only → all returned."""
        kpis = [_intelligent_kpi("revenue"), _intelligent_kpi("cost")]
        result = _dedup_kpis_by_slug([], kpis)
        assert len(result) == 2
        assert all(k["source"] == "intelligent" for k in result)

    def test_no_overlap_merges_both(self):
        """No overlapping columns → both sets are merged."""
        cards = [_card("revenue"), _card("cost")]
        kpis = [_intelligent_kpi("users"), _intelligent_kpi("churn")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 4

    def test_overlap_intelligent_wins(self):
        """When same column appears in both, intelligent KPI wins."""
        cards = [_card("revenue", "Total Revenue")]
        kpis = [_intelligent_kpi("revenue", "MRR")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 1
        assert result[0]["source"] == "intelligent"

    def test_multiple_overlaps(self):
        """Multiple overlapping columns — all intelligent KPIs win."""
        cards = [
            _card("revenue", "Total Revenue"),
            _card("cost", "Total Cost"),
            _card("users", "User Count"),
        ]
        kpis = [
            _intelligent_kpi("revenue", "MRR"),
            _intelligent_kpi("cost", "Cogs"),
        ]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 3  # All 3 columns, but revenue+cost from intelligent
        result_by_col = {r["column"]: r for r in result}
        assert result_by_col["revenue"]["source"] == "intelligent"
        assert result_by_col["cost"]["source"] == "intelligent"
        assert result_by_col["users"]["source"] == "card"

    def test_case_insensitive_dedup(self):
        """Column names are lowercased for dedup."""
        cards = [_card("Revenue")]
        kpis = [_intelligent_kpi("revenue")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 1

    def test_whitespace_stripped(self):
        """Column names have whitespace stripped before matching."""
        cards = [_card("  revenue  ")]
        kpis = [_intelligent_kpi("revenue")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 1

    def test_empty_slug_skipped(self):
        """Items with empty column/title are skipped."""
        cards = [{"column": "", "source": "card"}, _card("valid")]
        kpis = [_intelligent_kpi("also_valid")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 2
        assert all(r["column"] in ("valid", "also_valid") for r in result)

    def test_ordered_intelligent_first(self):
        """Intelligent KPIs should appear before cards in output."""
        cards = [_card("z_metric"), _card("a_metric")]
        kpis = [_intelligent_kpi("m_metric")]
        result = _dedup_kpis_by_slug(cards, kpis)
        # Intelligent KPI should be first
        assert result[0]["source"] == "intelligent"
        # Card should not be lost
        assert result[1]["source"] == "card"

    def test_object_with_column_attr(self):
        """Handle objects with .column attribute (e.g., Pydantic models)."""
        @dataclass
        class MockModel:
            column: str
            source: str = "model"

        cards = [MockModel(column="revenue")]
        kpis = [_intelligent_kpi("revenue")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 1
        assert result[0]["source"] == "intelligent"

    def test_object_without_column_uses_title(self):
        """Handle objects without .column but with .title."""
        @dataclass
        class MockModel:
            title: str
            source: str = "model"

        cards = [MockModel(title="Revenue")]
        kpis = [_intelligent_kpi("revenue")]
        result = _dedup_kpis_by_slug(cards, kpis)
        assert len(result) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
