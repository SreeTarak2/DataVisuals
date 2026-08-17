"""
Comparison-Period Resolver
==========================

The "which baseline?" decision, made explicit. The KPI engine used to pick a
comparison purely from the dataset's date range — the user's question never
influenced it. This module resolves the comparison in three ways:

1. EXPLICIT  — the question names a comparison ("vs last year", "month over
   month", "vs the 3-month average"). Extract it and honor it.
2. DEFAULT   — no explicit comparison → data-driven default by date range
   (mirrors ``pipeline/classifier._pick_comparison``: ≥2y of data → year-over-
   year, ≥14d → prior period, else none).
3. CLARIFY   — multi-year data + no explicit comparison → the choice
   (YoY vs MoM) materially changes the answer; the caller should surface it.

Deterministic first — the LLM is never asked to "pick a comparison". Only the
*resolution* of the user's words is extracted here, then computed exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import polars as pl

# Comparison keys (kept as plain strings to avoid importing the pipeline enum
# into the AI layer; values match ComparisonType for prior_period/prior_year).
PRIOR_YEAR = "prior_year"
PRIOR_PERIOD = "prior_period"
ROLLING_BASELINE = "rolling_baseline"
NONE = "none"

_LABELS = {
    PRIOR_YEAR: "vs same period last year",
    PRIOR_PERIOD: "vs previous period",
    ROLLING_BASELINE: "vs 3-period average",
    NONE: "no comparison",
}

# Explicit comparison phrases, ordered most-specific-first (first match wins).
_EXPLICIT_RULES: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(
            r"\b(year[-\s]?over[-\s]?year|yoy|year[-\s]?on[-\s]?year|"
            r"vs\.?\s+(last|previous|prior)\s+year|"
            r"compared?\s+to\s+(last|previous|prior)\s+year)\b",
            re.IGNORECASE,
        ),
        PRIOR_YEAR,
        _LABELS[PRIOR_YEAR],
    ),
    (
        re.compile(
            r"\b(month[-\s]?over[-\s]?month|mom|"
            r"vs\.?\s+(last|previous|prior)\s+month|"
            r"compared?\s+to\s+(last|previous|prior)\s+month)\b",
            re.IGNORECASE,
        ),
        PRIOR_PERIOD,
        _LABELS[PRIOR_PERIOD],
    ),
    (
        re.compile(
            r"\b(week[-\s]?over[-\s]?week|wow|"
            r"vs\.?\s+(last|previous|prior)\s+week)\b",
            re.IGNORECASE,
        ),
        PRIOR_PERIOD,
        "vs previous week",
    ),
    (
        re.compile(
            r"\b((3|three)[-\s]?month\s+(rolling\s+)?(average|baseline|mean)|"
            r"rolling\s+(average|baseline|mean)|"
            r"trailing\s+(3[-\s]?month|average)|"
            r"vs\.?\s+(the\s+)?(average|baseline))\b",
            re.IGNORECASE,
        ),
        ROLLING_BASELINE,
        _LABELS[ROLLING_BASELINE],
    ),
    # Specific year: "vs 2024", "compared to 2024"
    (
        re.compile(r"\bvs\.?\s+(20\d{2})\b", re.IGNORECASE),
        PRIOR_YEAR,
        "vs same period in the specified year",
    ),
]


@dataclass
class ComparisonResolution:
    """The resolved comparison for a question."""

    comparison: str  # PRIOR_YEAR | PRIOR_PERIOD | ROLLING_BASELINE | NONE
    source: str      # "explicit" | "default"
    needs_clarification: bool
    label: str
    matched_phrase: Optional[str] = None


def _default_comparison(date_range_days: Optional[int]) -> str:
    """Data-driven default — mirrors pipeline/classifier._pick_comparison."""
    if date_range_days is None or date_range_days < 14:
        return NONE
    if date_range_days >= 730:
        return PRIOR_YEAR
    return PRIOR_PERIOD


def resolve_comparison_period(
    question: Optional[str],
    date_range_days: Optional[int] = None,
) -> ComparisonResolution:
    """
    Resolve which comparison a question asks for.

    Args:
        question: The user's raw question (may be empty).
        date_range_days: Days spanned by the dataset's time column, used for
            the data-driven default and the clarification flag.

    Returns:
        ComparisonResolution — the resolved comparison, its source, and
        whether the caller should surface the choice (multi-year data with no
        explicit comparison).
    """
    q = (question or "").strip()
    if q:
        for pattern, comparison, label in _EXPLICIT_RULES:
            m = pattern.search(q)
            if m:
                return ComparisonResolution(
                    comparison=comparison,
                    source="explicit",
                    needs_clarification=False,
                    label=label,
                    matched_phrase=m.group(0),
                )

    comparison = _default_comparison(date_range_days)
    # Multi-year data + no explicit comparison → YoY vs MoM changes the answer.
    needs_clarification = comparison != NONE and (date_range_days or 0) >= 730
    return ComparisonResolution(
        comparison=comparison,
        source="default",
        needs_clarification=needs_clarification,
        label=_LABELS.get(comparison, comparison),
    )


def comparison_label(comparison: Optional[str]) -> str:
    """Human label for a comparison key (safe for None/unknown)."""
    if not comparison:
        return _LABELS[NONE]
    return _LABELS.get(comparison, comparison)


def date_range_days_from_df(df: Optional[pl.DataFrame]) -> Optional[int]:
    """Best-effort day span of the first date/datetime column in a DataFrame."""
    if df is None:
        return None
    try:
        for col in df.columns:
            if df[col].dtype in (pl.Date, pl.Datetime):
                mn, mx = df[col].min(), df[col].max()
                if mn is not None and mx is not None:
                    return (mx - mn).days
                return None
    except Exception:
        return None
    return None


def resolve_comparison_for_df(
    question: Optional[str],
    df: Optional[pl.DataFrame],
) -> ComparisonResolution:
    """
    Resolve the comparison for a question given the actual data.

    Uses the dataset's date span for the data-driven default and the
    clarification flag (callers that have the raw DataFrame — agents,
    KPI generation — use this instead of passing date_range_days by hand).
    """
    return resolve_comparison_period(question, date_range_days_from_df(df))


__all__ = [
    "PRIOR_YEAR",
    "PRIOR_PERIOD",
    "ROLLING_BASELINE",
    "NONE",
    "ComparisonResolution",
    "resolve_comparison_period",
    "comparison_label",
    "date_range_days_from_df",
    "resolve_comparison_for_df",
]
