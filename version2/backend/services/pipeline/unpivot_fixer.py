"""
Unpivot Fixer — Phase 2 proposal-based wide→long transform (Fixer #6).

Financial exports often lay time out as columns ("Jan_Revenue",
"Feb_Revenue", ...). The AI cannot do time-series analysis on that shape —
it reads 12 independent columns instead of a trend. This fixer detects
pivoted time columns and emits a ``pending_critical`` proposal to unpivot
them into a tidy (time, measure) long format.

Safety rules baked in:
  * At least 3 matching columns are required (2 is not a strong signal).
  * All columns in a group must share the same dtype (no mixing numeric
    and text "months").
  * Only month / quarter / year tokens are recognized; a group must be
    consistent in time type (month+year combos are allowed).
  * After unpivoting, rows with a null measure are dropped so missing
    months never skew aggregations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

MIN_GROUP_SIZE = 3

_MONTH_RE = re.compile(
    r"(?i)^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)$"
)
_QUARTER_RE = re.compile(r"(?i)^q[1-4]$")
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")

_TOKEN_SPLIT_RE = re.compile(r"[\s_.\-]+")


def _extract_time_meta(col: str) -> Optional[Tuple[str, str, str]]:
    """Return ``(time_value, measure, time_type)`` if the column carries a
    recognizable time token, else None. Mixed month+quarter is rejected;
    month/quarter may combine with a year (\"Q1 2023\")."""
    tokens = [t for t in _TOKEN_SPLIT_RE.split(col) if t]
    if not tokens:
        return None

    time_vals: List[str] = []
    time_type: Optional[str] = None
    rest: List[str] = []

    for t in tokens:
        m = _MONTH_RE.match(t)
        q = _QUARTER_RE.match(t)
        y = _YEAR_RE.match(t)
        if m:
            tt = "month"
            tv = t[:1].upper() + t[1:3].lower()  # "Jan", "Feb"...
        elif q:
            tt = "quarter"
            tv = t.upper()
        elif y:
            tt = "year"
            tv = t
        else:
            rest.append(t)
            continue

        if time_type is None:
            time_type = tt
        elif tt == "year":
            pass  # year combines with month/quarter
        elif time_type == "year":
            time_type = tt
        elif time_type != tt:
            return None  # month+quarter mix — not a clean pivot
        time_vals.append(tv)

    if not time_vals:
        return None
    return " ".join(time_vals), "_".join(rest) or "value", time_type or "year"


def detect_unpivot_candidates(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """Return unpivot proposal entries for columns pivoted over time."""
    by_measure: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for col in df.columns:
        meta = _extract_time_meta(col)
        if not meta:
            continue
        time_value, measure, time_type = meta
        by_measure.setdefault((measure, time_type), []).append((col, time_value))

    proposals: List[Dict[str, Any]] = []
    for (measure, time_type), members in by_measure.items():
        members.sort()
        if len(members) < MIN_GROUP_SIZE:
            continue
        cols = [c for c, _ in members]

        # All columns must share the same dtype.
        dtypes = {df[c].dtype for c in cols}
        if len(dtypes) != 1:
            continue

        time_col = {"month": "month", "quarter": "quarter", "year": "year"}[time_type]
        value_mapping = {c: tv for c, tv in members}
        sample = cols[:3]
        proposals.append(
            {
                "action_type": "unpivot_columns",
                "target_columns": cols,
                "new_column_names": [time_col, measure],
                "value_mapping": value_mapping,
                "reasoning": (
                    f"Detected {len(cols)} '{measure}' columns by {time_col} "
                    f"(e.g. {', '.join(sample)}) — unpivoting them into "
                    f"'{time_col}' and '{measure}' so time-series analysis works."
                ),
                "evidence": {
                    "mapping": dict(list(value_mapping.items())[:5]),
                    "before": sample,
                    "after": [f"{time_col}={value_mapping[c]}" for c in sample],
                },
                "approved": None,
                "state": "proposed",
                "proposed_at": _now_iso(),
            }
        )

    return proposals


def apply_unpivot(
    df: pl.DataFrame,
    entry: Dict[str, Any],
    warnings: List[str],
) -> pl.DataFrame:
    """Execute a wide→long unpivot on the target time columns."""
    target_cols = entry.get("target_columns") or []
    existing = [c for c in target_cols if c in df.columns]
    if len(existing) < MIN_GROUP_SIZE:
        warnings.append(
            f"Unpivot needs at least {MIN_GROUP_SIZE} matching columns present — skipped."
        )
        return df

    names = entry.get("new_column_names") or ["month", "value"]
    time_col = str(names[0])
    value_col = str(names[1]) if len(names) > 1 else "value"
    value_mapping = entry.get("value_mapping") or {}

    index_cols = [c for c in df.columns if c not in existing]
    melted = df.unpivot(
        on=existing,
        index=index_cols,
        variable_name=time_col,
        value_name=value_col,
    )
    # Map the raw column names back to their time values ("Jan_Revenue" → "Jan").
    melted = melted.with_columns(
        pl.col(time_col).replace_strict(value_mapping, default=pl.col(time_col))
    )
    # Drop rows where the measure is null (a product with no sales in March)
    # so missing months never skew aggregations.
    melted = melted.filter(pl.col(value_col).is_not_null())
    return melted


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


__all__ = [
    "detect_unpivot_candidates",
    "apply_unpivot",
    "_extract_time_meta",
]
