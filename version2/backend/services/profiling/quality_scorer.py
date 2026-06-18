"""
profiling/quality_scorer.py — Dataset-level quality summary (Layer 1)

Computes:
  - Overall completeness across all columns
  - Columns with data quality issues
  - Potential problems flagged for user review

Pure facts, no interpretation.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import RawColumnProfile, RawProfilingResult

logger = logging.getLogger(__name__)


class QualityScorer:
    """Computes dataset-level quality summary from profiling results."""

    def score(self, result: RawProfilingResult) -> dict[str, Any]:
        """Compute quality summary from profiling results.

        Returns a dict with:
          - overall_completeness: float
          - columns_with_issues: list[str] (columns with quality < 0.9)
          - potential_issues: list[str] (human-readable warnings)
          - duplicate_rows: int (0 — requires full scan, not computed here)
        """
        if not result.columns:
            return {
                "overall_completeness": 0.0,
                "columns_with_issues": [],
                "potential_issues": ["No columns found"],
                "duplicate_rows_estimated": 0,
            }

        scores = [c.quality.quality_score for c in result.columns if c.quality]
        overall = sum(scores) / len(scores) if scores else 0.0

        columns_with_issues = [
            c.name for c in result.columns
            if c.quality.quality_score < 0.9
        ]

        issues: list[str] = []
        for c in result.columns:
            if c.quality.null_percentage > 20:
                issues.append(f"'{c.name}' has {c.quality.null_percentage:.0f}% missing values")
            if c.quality.effective_completeness < 0.8:
                issues.append(f"'{c.name}' has many empty strings ({c.quality.empty_count} empty)")

        return {
            "overall_completeness": round(overall, 4),
            "columns_with_issues": columns_with_issues,
            "potential_issues": issues[:10],
            "duplicate_rows_estimated": 0,
        }


# Singleton
quality_scorer = QualityScorer()
