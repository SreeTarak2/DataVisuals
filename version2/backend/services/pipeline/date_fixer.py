"""
Date Fixer — Phase 2 proposal-based type coercion (Fixer #4).

Mixed date formats ("02/01/24" vs "Feb 1, 2024") break time-series analysis,
drill-downs, and date filters. This fixer is *proposal-based* (Act-then-
Validate): it detects string columns that are almost certainly dates and
emits a ``pending_critical`` manifest entry — it never mutates silently.

Because coercing a string to a datetime changes how filters and time-series
queries behave, the proposal triggers the chat guardrail hard-block until
the user reviews it on the Data Briefing (with before/after evidence).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import polars as pl

_MONTH_NAME_RE = re.compile(
    r"(?i)\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b"
)
_SEPARATED_DATE_RE = re.compile(r"^\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}$")
_YEAR4_RE = re.compile(r"\b(19|20)\d{2}\b")


def _looks_date_like(value: str) -> bool:
    """Conservative signal that a string is a date, not just a number/label.

    Requires BOTH a successful dateutil parse AND a structural date signal
    (month name, separated date parts, or a 4-digit year with extra context)
    so bare numbers ("123456"), phone numbers, and years-as-categories are
    never misidentified as dates.
    """
    from dateutil.parser import parse as _du_parse

    t = value.strip()
    if not t:
        return False
    try:
        dt = _du_parse(t, fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return False
    if dt is None:
        return False

    has_separated = bool(_SEPARATED_DATE_RE.match(t))
    has_month = bool(_MONTH_NAME_RE.search(t))
    has_year4 = bool(_YEAR4_RE.search(t))
    has_extra_context = has_year4 and len(re.sub(r"[^a-zA-Z0-9]", "", t)) > 4

    return has_separated or has_month or has_extra_context


def _parse_datetime(value: str) -> datetime | None:
    """dateutil parse with the same conservative date-like gate."""
    if not _looks_date_like(value):
        return None
    from dateutil.parser import parse as _du_parse

    try:
        return _du_parse(value.strip(), fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return None


def detect_date_candidates(
    df: pl.DataFrame,
    sample_size: int = 50,
    threshold: float = 0.9,
) -> List[Dict[str, Any]]:
    """
    Scan string columns for date-like values and return proposal entries.

    Each candidate is a manifest entry::

        {
            "action_type": "type_coercion",
            "target_column": col,
            "target_columns": [col],
            "proposed_type": "Date",
            "reasoning": "...",
            "evidence": {"before": [...], "after": [...]},
            "approved": None,          # pending → chat guardrail blocks
            "state": "proposed",
        }
    """
    proposals: List[Dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        if series.dtype != pl.String:
            continue
        non_null = series.drop_nulls().head(sample_size)
        if non_null.len() < 3:
            continue
        values = [str(v) for v in non_null.to_list()]
        parsed: List[Tuple[str, datetime | None]] = [
            (v, _parse_datetime(v)) for v in values
        ]
        successes = [p for p in parsed if p[1] is not None]
        if not successes:
            continue
        rate = len(successes) / len(values)
        if rate < threshold:
            continue

        before = [s for s, _ in successes[:5]]
        after = [p.isoformat() for _, p in successes[:5]]
        proposals.append(
            {
                "action_type": "type_coercion",
                "target_column": col,
                "target_columns": [col],
                "proposed_type": "Date",
                "reasoning": (
                    f"{rate * 100:.0f}% of sampled values parse as dates — "
                    f"coercing '{col}' to a date enables time-series analysis "
                    "and date filters."
                ),
                "evidence": {"before": before, "after": after},
                "approved": None,
                "state": "proposed",
                "proposed_at": _now_iso(),
            }
        )

    return proposals


def apply_date_coercion(
    df: pl.DataFrame,
    entry: Dict[str, Any],
    warnings: List[str],
) -> pl.DataFrame:
    """
    Coerce the target string column to a datetime (execution path).

    Uses Polars' vectorized auto-detection first; falls back to per-value
    dateutil parsing for anything it could not infer. Unparseable values
    become null — never a crash.
    """
    col = entry.get("target_column") or (entry.get("target_columns") or [None])[0]
    if not col or col not in df.columns:
        warnings.append(f"Column '{col}' not found — date coercion skipped.")
        return df

    series = df[col]
    if isinstance(series.dtype, (pl.Datetime, pl.Date)):
        warnings.append(f"Column '{col}' is already a date type — nothing to do.")
        return df
    if series.dtype != pl.String:
        warnings.append(
            f"Column '{col}' is {series.dtype}, not text — cannot coerce to date."
        )
        return df

    stripped = series.str.strip_chars()
    # Vectorized fast path (auto format inference; failures → null)
    parsed = stripped.str.to_datetime(format=None, strict=False)
    if parsed.null_count() == 0:
        return df.with_columns(parsed.alias(col))

    # Fallback: dateutil per-value for the values Polars could not infer.
    result: List[Any] = []
    for v in stripped.to_list():
        result.append(_parse_datetime(v) if v is not None else None)
    new_col = pl.Series(col, result, dtype=pl.Datetime("us"))
    return df.with_columns(new_col.alias(col))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


__all__ = [
    "detect_date_candidates",
    "apply_date_coercion",
    "_looks_date_like",
    "_parse_datetime",
]
