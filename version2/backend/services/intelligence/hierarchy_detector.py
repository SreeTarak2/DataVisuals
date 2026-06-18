"""
intelligence/hierarchy_detector.py — Hierarchy detection engine (Layer 3)

Deterministically detects multi-level hierarchies within a single table:
  - Geographic: country → state → city (keyword + cardinality-based)
  - Category: category → subcategory → product
  - Organizational: department → team → employee
  - Temporal: year → quarter → month → day

Uses keyword matching + cardinality ordering (parent has fewer unique values).
No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import polars as pl

from services.profiling.models import RawProfilingResult
from .models import HierarchyInfo

logger = logging.getLogger(__name__)


# ── Hierarchy Definitions ─────────────────────────────────────────────────────

_HIERARCHY_PATTERNS: list[tuple[str, list[str]]] = [
    ("geo", ["country", "state", "city"]),
    ("geo", ["country", "region", "city"]),
    ("geo", ["country", "state", "city", "zip"]),
    ("geo", ["region", "state", "city"]),
    ("category", ["category", "subcategory", "product"]),
    ("category", ["category", "subcategory", "item"]),
    ("category", ["category", "product"]),
    ("category", ["category", "type"]),
    ("org", ["department", "team", "employee"]),
    ("org", ["department", "manager"]),
    ("org", ["division", "department", "team"]),
    ("org", ["region", "territory", "rep"]),
    ("date", ["year", "quarter", "month"]),
    ("date", ["year", "month", "day"]),
    ("date", ["year", "quarter", "month", "day"]),
]


class HierarchyDetector:
    """Detects column hierarchies within a single table."""

    def detect(
        self,
        result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> list[HierarchyInfo]:
        """Detect hierarchies from profiling results.

        Strategy:
          1. For each hierarchy pattern, try to match column names.
          2. Verify cardinality ordering: parent level has FEWER unique
             values than child level (e.g., unique countries < unique states).
          3. Only include if at least 2 levels of the hierarchy match.

        Args:
            result: RawProfilingResult from profiling layer.
            df: Optional DataFrame for cardinality verification.

        Returns:
            List of detected HierarchyInfo objects.
        """
        hierarchies: list[HierarchyInfo] = []

        for h_type, levels in _HIERARCHY_PATTERNS:
            matched = self._match_hierarchy(result, levels)
            if len(matched) >= 2:
                verified = self._verify_cardinality(result, matched, df)
                if verified:
                    hierarchies.append(HierarchyInfo(
                        columns=matched,
                        hierarchy_type=h_type,
                        description=f"Potential hierarchy: {' → '.join(matched)}",
                    ))

        return hierarchies

    def _match_hierarchy(
        self,
        result: RawProfilingResult,
        levels: list[str],
    ) -> list[str]:
        """Match column names against a hierarchy level pattern.

        Returns the actual column names that best match each level.
        """
        column_names = [c.name.lower() for c in result.columns]
        matched: list[str] = []

        for level in levels:
            # Direct match
            if level in column_names:
                actual = next(c.name for c in result.columns if c.name.lower() == level)
                matched.append(actual)
                continue

            # Partial match (e.g., "country_name" matches "country")
            for col_name in column_names:
                if level in col_name and col_name not in [m.lower() for m in matched]:
                    actual = next(c.name for c in result.columns if c.name.lower() == col_name)
                    matched.append(actual)
                    break
            else:
                # No match for this level
                matched.append("")

        return matched

    def _verify_cardinality(
        self,
        result: RawProfilingResult,
        columns: list[str],
        df: Optional[pl.DataFrame] = None,
    ) -> bool:
        """Verify that parent levels have fewer unique values than children.

        In a valid hierarchy:
          unique(country) <= unique(state) <= unique(city)
        """
        card_map = result.cardinality_map()
        unique_counts = []

        for col_name in columns:
            if not col_name:
                unique_counts.append(0)
            elif col_name.lower() in [c.lower() for c in card_map]:
                actual_name = next(c for c in card_map if c.lower() == col_name.lower())
                unique_counts.append(card_map[actual_name].unique_count)
            else:
                unique_counts.append(0)

        if not unique_counts:
            return False

        # Skip empty entries
        valid = [(i, uc) for i, uc in enumerate(unique_counts) if uc > 0]
        if len(valid) < 2:
            return False

        # Check cardinality non-decreasing (parent < child)
        for i in range(len(valid) - 1):
            if valid[i][1] > valid[i + 1][1]:
                return False

        return True


# Singleton
hierarchy_detector = HierarchyDetector()
