"""
Category Fixer — Phase 2 proposal-based fuzzy value merging (Fixer #5).

Dirty categorical data ("Shirts", "shirts ", "SHIRTS!") silently inflates
cardinality and breaks aggregations. This fixer is *proposal-based*
(Act-then-Validate): it detects near-duplicate category values and emits a
``pending_critical`` manifest entry — it never mutates silently.

Two proposal modes (both execute through the same value-replace path):

- ``fuzzy`` — targeted mapping of detected variants to a canonical value,
  e.g. ``{"shirts ": "Shirts", "SHIRTS!": "Shirts"}``.
- ``normalize`` — when a single canonical category dominates (>50% of
  rows), the whole column is normalized (lowercase + strip + punctuation
  removal) instead. This avoids risky pairwise fuzzy merges (the
  "Apple"/"Snapple" trap) while still collapsing all case/space variants.

Safety rules baked in:
  * Only low-to-medium cardinality string columns are considered (<100).
  * Fuzzy matching requires ``token_sort_ratio >= 85`` (this naturally
    excludes "Snapple"→"apple" ≈ 83%).
  * Ambiguity guard: the best fuzzy match must beat the second-best by a
    clear margin, or the value is left alone.
  * A single dominant category switches the proposal to global normalize.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import polars as pl
from rapidfuzz import fuzz

MAX_CARDINALITY = 100
MIN_CARDINALITY = 2
SIMILARITY_THRESHOLD = 85  # token_sort_ratio percent
AMBIGUITY_MARGIN = 5.0  # best fuzzy match must beat second-best by this much
DOMINANT_SHARE = 0.5  # above this → propose global normalize instead of fuzzy
MAX_AVG_LENGTH = 40  # skip free-text columns


def _normalize(value: str) -> str:
    """Canonical base form: lowercase, no punctuation, collapsed whitespace."""
    t = value.strip().lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _counts_by_value(df: pl.DataFrame, col: str) -> Dict[str, int]:
    """{unique value: row count} for a column."""
    vc = df[col].drop_nulls().value_counts()
    name = vc.columns[0]
    counts: Dict[str, int] = {}
    for row in vc.to_dicts():
        counts[str(row[name])] = int(row["count"])
    return counts


def _group_by_normalized(counts: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    """Group original values by their normalized base form.

    Returns ``{base: {"members": [...], "canonical": str, "count": int}}``
    where ``canonical`` is the most frequent original member (ties → the
    first alphabetically).
    """
    groups: Dict[str, Dict[str, Any]] = {}
    for value, count in counts.items():
        base = _normalize(value)
        if not base:
            continue
        g = groups.setdefault(base, {"members": [], "canonical": None, "count": 0})
        g["members"].append(value)
        g["count"] += count
    for base, g in groups.items():
        # Canonical = most frequent; ties → the normalized form itself if it
        # exists as a member, else lexicographically first.
        best = max(
            (v for v in g["members"] if _normalize(v) == base),
            key=lambda v: (counts.get(v, 0), -ord(v[:1].lower() or "z")),
        )
        # Prefer an exact normalized member when present; otherwise pick the
        # most frequent member.
        exact = next((v for v in g["members"] if v == base), None)
        g["canonical"] = exact or best
    return groups


def _build_fuzzy_mapping(
    counts: Dict[str, int],
    groups: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    """Variant → canonical for values that fuzzy-match an existing group.

    Only values that are already the *sole* member of their normalized group
    are candidates. Best match must be >= threshold and unambiguous.
    """
    mapping: Dict[str, str] = {}
    bases = list(groups.keys())
    canonical_by_base = {b: groups[b]["canonical"] for b in bases}

    for value, count in counts.items():
        base = _normalize(value)
        if not base or base in groups:
            continue  # already a group member or un-normalizable
        scored = []
        for b in bases:
            if b == base:
                continue
            ratio = fuzz.token_sort_ratio(base, b)
            scored.append((ratio, b))
        scored.sort(reverse=True)
        if not scored:
            continue
        best_ratio, best_base = scored[0]
        if best_ratio < SIMILARITY_THRESHOLD:
            continue
        # Ambiguity guard: the best match must clearly win.
        if len(scored) > 1 and (best_ratio - scored[1][0]) < AMBIGUITY_MARGIN:
            continue
        mapping[value] = canonical_by_base[best_base]
    return mapping


def detect_category_merges(
    df: pl.DataFrame,
    max_cardinality: int = MAX_CARDINALITY,
    similarity: int = SIMILARITY_THRESHOLD,
    dominant_share: float = DOMINANT_SHARE,
) -> List[Dict[str, Any]]:
    """Return merge proposal entries for dirty categorical string columns."""
    proposals: List[Dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        if series.dtype != pl.String:
            continue
        non_null = series.drop_nulls()
        total = non_null.len()
        if total < 3:
            continue
        counts = _counts_by_value(df, col)
        cardinality = len(counts)
        if not (MIN_CARDINALITY <= cardinality <= max_cardinality):
            continue
        avg_len = sum(len(str(v)) for v in counts) / max(cardinality, 1)
        if avg_len > MAX_AVG_LENGTH:
            continue  # free text, not a category

        groups = _group_by_normalized(counts)
        if len(groups) < 2:
            continue

        # ── Dominant category → global normalize proposal ──────────────
        # One canonical covers >50% of rows: normalize the WHOLE column to its
        # canonical base form (lowercase/strip/punctuation) rather than risky
        # pairwise fuzzy merges. Each value maps to its own normalized form, so
        # genuinely distinct categories (e.g. "Snapple") are never collapsed.
        dominant_base, dominant = max(groups.items(), key=lambda kv: kv[1]["count"])
        dominant_share_rows = dominant["count"] / total
        if dominant_share_rows > dominant_share:
            mapping = {
                v: _normalize(v) for v in counts if _normalize(v) != v
            }
            if not mapping:
                continue
            proposals.append(_build_entry(
                col,
                mapping,
                mode="normalize",
                reasoning=(
                    f"'{dominant_base}' covers {dominant_share_rows * 100:.0f}% of "
                    f"the column — normalizing all values (case/space/punctuation) "
                    "to their canonical form instead of risky fuzzy merges."
                ),
            ))
            continue

        # ── Targeted fuzzy mapping ──────────────────────────────────────
        mapping = {}
        for base, g in groups.items():
            if len(g["members"]) > 1:
                for member in g["members"]:
                    if member != g["canonical"]:
                        mapping[member] = g["canonical"]
        mapping.update(_build_fuzzy_mapping(counts, groups))
        if not mapping:
            continue
        proposals.append(_build_entry(
            col,
            mapping,
            mode="fuzzy",
            reasoning=(
                f"Found {len(mapping)} variant(s) of the same category in "
                f"'{col}' — merging them into their canonical value so "
                "aggregations count them together."
            ),
        ))

    return proposals


def _build_entry(
    col: str,
    mapping: Dict[str, str],
    mode: str,
    reasoning: str,
) -> Dict[str, Any]:
    sample_items = list(mapping.items())[:5]
    return {
        "action_type": "merge_values",
        "target_column": col,
        "target_columns": [col],
        "mode": mode,
        "reasoning": reasoning,
        "evidence": {
            "mapping": dict(sample_items),
            "before": [v for v, _ in sample_items],
            "after": [c for _, c in sample_items],
        },
        "mapping": mapping,  # full mapping for execution
        "approved": None,
        "state": "proposed",
        "proposed_at": _now_iso(),
    }


def apply_merge_values(
    df: pl.DataFrame,
    entry: Dict[str, Any],
    warnings: List[str],
) -> pl.DataFrame:
    """Apply a variant → canonical mapping to the target column (execution)."""
    col = entry.get("target_column") or (entry.get("target_columns") or [None])[0]
    if not col or col not in df.columns:
        warnings.append(f"Column '{col}' not found — value merge skipped.")
        return df
    mapping = entry.get("mapping") or (entry.get("evidence") or {}).get("mapping") or {}
    if not mapping:
        warnings.append("No value mapping provided — value merge skipped.")
        return df

    series = df[col]
    if series.dtype != pl.String:
        warnings.append(
            f"Column '{col}' is {series.dtype}, not text — value merge skipped."
        )
        return df

    replaced = series.replace_strict(mapping, default=series)
    return df.with_columns(replaced.alias(col))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


__all__ = [
    "detect_category_merges",
    "apply_merge_values",
    "_normalize",
]
