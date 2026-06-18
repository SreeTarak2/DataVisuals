"""
intelligence/relationship_detector.py — Cross-column relationship engine (Layer 3, NEW)

Detects relationships between columns within a single table:
  - Foreign key candidates (column value overlap analysis)
  - Derived columns (Profit = Revenue - Cost type patterns)
  - Duplicate / near-duplicate columns

For single-table analysis, this focuses on within-table patterns.
Cross-table relationships are a future extension.

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import polars as pl

from services.profiling.models import RawProfilingResult
from .models import RelationshipInfo

logger = logging.getLogger(__name__)


class RelationshipDetector:
    """Detects relationships between columns within a single table."""

    # Patterns that suggest derived columns
    _GROSS_MARGIN = re.compile(r"\b(gross.?(margin|profit)|markup)\b", re.I)
    _NET_PATTERN = re.compile(r"\bnet\b", re.I)
    _PROFIT_PATTERN = re.compile(r"\bprofit\b", re.I)
    _MARGIN_PATTERN = re.compile(r"\bmargin\b", re.I)

    def detect(
        self,
        result: RawProfilingResult,
        df: Optional[pl.DataFrame] = None,
    ) -> list[RelationshipInfo]:
        """Detect relationships between columns.

        For single-table datasets, detects:
          1. Derived column candidates (Profit = Revenue - Cost)
          2. ID-to-name pairs (customer_id + customer_name)
          3. Duplicate columns (identical or near-identical values)

        Args:
            result: RawProfilingResult from profiling layer.
            df: Optional DataFrame for value analysis.

        Returns:
            List of detected RelationshipInfo objects.
        """
        relationships: list[RelationshipInfo] = []
        names_lower = {c.name.lower(): c.name for c in result.columns}

        # ── 1. ID-to-Name pairs ──
        relationships.extend(self._detect_id_name_pairs(result, names_lower))

        # ── 2. Derived column candidates ──
        relationships.extend(self._detect_derived_candidates(result, names_lower))

        # ── 3. Duplicate columns (value overlap) ──
        if df is not None:
            relationships.extend(self._detect_duplicates(result, df))

        return relationships

    def _detect_id_name_pairs(
        self,
        result: RawProfilingResult,
        names_lower: dict[str, str],
    ) -> list[RelationshipInfo]:
        """Detect ID-to-name pairs (e.g., customer_id + customer_name)."""
        relationships: list[RelationshipInfo] = []
        id_suffix = re.compile(r"_id$", re.I)

        for col in result.columns:
            m = id_suffix.search(col.name)
            if not m:
                continue

            # Get base name by removing _id
            base = col.name[:m.start()]
            base_lower = base.lower()

            # Look for matching name column
            name_variants = [
                f"{base}_name",
                f"{base_lower}_name",
                base if "name" in base_lower else None,
            ]

            for variant in name_variants:
                if variant and variant.lower() in names_lower:
                    actual_name = names_lower[variant.lower()]
                    if actual_name != col.name:
                        relationships.append(RelationshipInfo(
                            source_column=col.name,
                            target_column=actual_name,
                            relationship_type="foreign_key",
                            confidence=0.80,
                            description=f"'{col.name}' references '{actual_name}' (ID-to-Name pair)",
                        ))
                    break

        return relationships

    def _detect_derived_candidates(
        self,
        result: RawProfilingResult,
        names_lower: dict[str, str],
    ) -> list[RelationshipInfo]:
        """Detect columns that are likely derived from other columns."""
        relationships: list[RelationshipInfo] = []

        # Check for profit-related columns
        for col in result.columns:
            name_lower = col.name.lower()

            if self._MARGIN_PATTERN.search(name_lower) and col.stats and col.stats.is_bounded_01:
                # Margin = (revenue - cost) / revenue
                rev_col = self._find_column(names_lower, ["revenue", "sales", "income"])
                cost_col = self._find_column(names_lower, ["cost", "cogs", "expense"])
                if rev_col and cost_col:
                    relationships.append(RelationshipInfo(
                        source_column=rev_col,
                        target_column=cost_col,
                        relationship_type="derived",
                        confidence=0.75,
                        description=f"'{col.name}' is likely derived from {rev_col} and {cost_col}: ({rev_col} - {cost_col}) / {rev_col}",
                    ))

            elif self._PROFIT_PATTERN.search(name_lower):
                rev_col = self._find_column(names_lower, ["revenue", "sales", "income"])
                cost_col = self._find_column(names_lower, ["cost", "cogs", "expense"])
                if rev_col and cost_col:
                    relationships.append(RelationshipInfo(
                        source_column=rev_col,
                        target_column=cost_col,
                        relationship_type="derived",
                        confidence=0.70,
                        description=f"'{col.name}' is likely derived: {rev_col} - {cost_col}",
                    ))

        return relationships

    def _detect_duplicates(
        self,
        result: RawProfilingResult,
        df: pl.DataFrame,
    ) -> list[RelationshipInfo]:
        """Detect columns with identical or near-identical values."""
        relationships: list[RelationshipInfo] = []
        numeric_cols = result.numeric_columns()

        # Check for highly correlated numeric columns
        if len(numeric_cols) >= 3:
            try:
                corr_matrix = df.select([c.name for c in numeric_cols]).corr()
                for i, row_name in enumerate(corr_matrix.columns):
                    for j, col_name in enumerate(corr_matrix.columns):
                        if i < j:
                            val = corr_matrix[row_name][j]
                            if val and isinstance(val, float) and val > 0.95:
                                relationships.append(RelationshipInfo(
                                    source_column=row_name,
                                    target_column=col_name,
                                    relationship_type="duplicate",
                                    confidence=round(val, 2),
                                    description=f"'{row_name}' and '{col_name}' are highly correlated (r={val:.2f})",
                                ))
            except Exception:
                pass

        return relationships

    @staticmethod
    def _find_column(names_lower: dict[str, str], keywords: list[str]) -> Optional[str]:
        """Find a column name matching any of the given keywords."""
        for name_actual in names_lower.values():
            name_l = name_actual.lower()
            for kw in keywords:
                if kw in name_l:
                    return name_actual
        return None


# Singleton
relationship_detector = RelationshipDetector()
