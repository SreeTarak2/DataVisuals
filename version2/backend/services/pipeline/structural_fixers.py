"""
Structural Fixers — deterministic, silent, logged (Phase 1 of the 6 fixers).

These fixers are mathematically deterministic: there is only one correct
answer, so they apply silently at ingest time and log to the cleaning
manifest (marked ``approved: True`` / ``state: "applied"`` so the chat
guardrail treats them as settled, not pending).

  - ``shift_header_row``  — CSV/Excel exports often carry 1-3 title rows
    ("Company Name", "Q3 Report") above the real column headers. Detect the
    title rows and promote the first real header row.
  - ``drop_total_rows``   — summary rows at the bottom ("TOTAL", "GRAND
    TOTAL") inflate every aggregate. Drop a row only when it carries a
    TOTAL-like marker AND its numeric values match the column totals.

Both are pure Polars/regex — no LLM, no user validation needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import polars as pl

# ── Header detection ────────────────────────────────────────────────────────

_TITLE_LONG_CELL = 40  # title rows are mostly long prose or blanks
_TITLE_SCORE_MAX = 0.30  # a real header row may still contain a long name or two
_HEADER_SCORE_MIN = 0.70  # fraction of short, non-null, distinct cells required


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _title_score(row: Tuple[Any, ...], ncols: int) -> float:
    """Fraction of cells that look like title prose rather than headers.

    A cell is title-like when it is blank, suspiciously long (>40 chars), or
    carries a digit (years/quarters: "Fiscal Year 2024", "Q3"). Plain short
    prose ("Revenue by Region") deliberately does NOT count — it is
    indistinguishable from a real header, and a false shift corrupts the
    whole dataset. Safety first: only act on clear signals.
    """
    title_cells = 0
    for v in row:
        t = _cell_text(v)
        if not t or len(t) > _TITLE_LONG_CELL or any(ch.isdigit() for ch in t):
            title_cells += 1
    return title_cells / max(ncols, 1)


def _header_score(row: Tuple[Any, ...], ncols: int) -> float:
    """Fraction of cells that are short, non-null, and distinct — header-like."""
    seen = set()
    good = 0
    for v in row:
        t = _cell_text(v).lower()
        if t and len(t) <= _TITLE_LONG_CELL and t not in seen:
            seen.add(t)
            good += 1
    return good / max(ncols, 1)


def _build_unique_headers(row: Tuple[Any, ...], fallback_cols: List[str]) -> List[str]:
    """Column names from a header row — deduped, blanks fall back to existing."""
    new_names: List[str] = []
    seen = set()
    for j, v in enumerate(row):
        base = _cell_text(v) or fallback_cols[j] if j < len(fallback_cols) else _cell_text(v)
        if not base:
            base = f"column_{j}"
        name = base
        k = 1
        while name.lower() in seen:
            k += 1
            name = f"{base}_{k}"
        seen.add(name.lower())
        new_names.append(name)
    return new_names


def shift_header_row(
    df: pl.DataFrame,
    max_title_rows: int = 3,
    min_data_rows: int = 1,
) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
    """
    Promote the first real header row when title rows precede it.

    Returns ``(df, manifest_entries)``. No-op (with an empty manifest) when
    the first row already looks like a clean header or the shift would leave
    too little data.
    """
    if df.height <= min_data_rows or df.width == 0:
        return df, []

    ncols = df.width
    limit = min(max_title_rows, df.height - min_data_rows)
    rows = [df.row(i) for i in range(limit + 1)]

    # Row 0 already looks like a proper header (strong signal AND low
    # title-ness) — nothing to fix.
    if (
        _header_score(rows[0], ncols) >= _HEADER_SCORE_MIN
        and _title_score(rows[0], ncols) < 0.5
    ):
        return df, []

    for i in range(1, limit + 1):
        vals = rows[i]
        if _header_score(vals, ncols) < _HEADER_SCORE_MIN:
            continue
        if _title_score(vals, ncols) > _TITLE_SCORE_MAX:
            continue
        # Every row above the candidate must itself look like a title —
        # otherwise the "header" we found is just one row of a multi-row
        # table and shifting would destroy real data.
        if not all(_title_score(rows[j], ncols) >= 0.5 for j in range(i)):
            continue
        shifted = df.slice(i + 1)
        if shifted.height < min_data_rows:
            return df, []
        new_names = _build_unique_headers(vals, df.columns)
        shifted = shifted.rename(dict(zip(df.columns, new_names)))
        entry = {
            "action_type": "shift_header",
            "from_row": i,
            "target_columns": [],
            "reasoning": (
                f"Detected {i} title row(s) above the column headers — "
                f"promoted row {i + 1} as the header."
            ),
            "approved": True,
            "state": "applied",
            "applied_silently": True,
            "applied_at": _now_iso(),
        }
        return shifted, [entry]

    return df, []


# ── TOTAL row detection ─────────────────────────────────────────────────────

_TOTAL_RE = re.compile(r"(?i)^\s*(grand\s+|sub\s+)?(total|sum|subtotal)\b")


def _is_total_marker(value: Any) -> bool:
    return isinstance(value, str) and bool(_TOTAL_RE.match(value.strip()))


def _numeric_value(value: Any) -> float | None:
    """Best-effort numeric parse of a cell (None → null/blank)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        t = value.strip().replace(",", "").replace("$", "").replace("%", "")
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _matches_column_total(row_value: float | None, column_total: float | None) -> bool:
    """Row value ≈ sum of all *other* rows in the column (the TOTAL invariant).

    With ``S`` = column sum including the candidate row, the candidate is the
    total of the rest iff ``row_value ≈ S - row_value``.
    """
    if row_value is None:
        # Blank numeric cell on a TOTAL row (dash / empty) — accept, not a failure.
        return True
    if column_total is None:
        return True
    other_sum = column_total - row_value
    if abs(other_sum) < 1e-9 and abs(row_value) < 1e-9:
        return True
    return abs(row_value - other_sum) / max(abs(other_sum), 1.0) < 1e-4


def drop_total_rows(
    df: pl.DataFrame,
    scan_last: int = 5,
) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
    """
    Drop trailing summary rows that carry a TOTAL-like marker and whose
    numeric values match the column totals (so real data rows are never
    misidentified). Returns ``(df, manifest_entries)``.
    """
    if df.height < 3:
        return df, []

    numeric_cols = [c for c in df.columns if df[c].dtype.is_numeric()]
    start = max(0, df.height - scan_last)
    drop_indices: List[int] = []

    for idx in range(start, df.height):
        row = df.row(idx)
        if not any(_is_total_marker(v) for v in row):
            continue

        # Every numeric column must satisfy the TOTAL invariant.
        valid = True
        for c in numeric_cols:
            row_val = _numeric_value(row[df.columns.index(c)])
            column_total = df[c].sum()
            col_total_f = float(column_total) if column_total is not None else None
            if not _matches_column_total(row_val, col_total_f):
                valid = False
                break
        if valid:
            drop_indices.append(idx)

    if not drop_indices:
        return df, []

    drop_set = set(drop_indices)
    df = df.filter(~pl.int_range(0, df.height).is_in(list(drop_set)))

    entries = [
        {
            "action_type": "drop_row",
            "target_columns": [],
            "reasoning": (
                f"Removed row {idx + 1}: matched a TOTAL/sum marker and its "
                "numeric values matched the column totals."
            ),
            "row_index": idx,
            "approved": True,
            "state": "applied",
            "applied_silently": True,
            "applied_at": _now_iso(),
        }
        for idx in drop_indices
    ]
    return df, entries


# ── Orchestrator ────────────────────────────────────────────────────────────


def apply_structural_fixers(df: pl.DataFrame) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
    """Run all silent structural fixers and return ``(df, manifest_entries)``."""
    entries: List[Dict[str, Any]] = []
    df, header_entries = shift_header_row(df)
    entries.extend(header_entries)
    df, total_entries = drop_total_rows(df)
    entries.extend(total_entries)
    return df, entries


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


__all__ = [
    "apply_structural_fixers",
    "shift_header_row",
    "drop_total_rows",
]
