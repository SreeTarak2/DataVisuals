"""
pipeline/normalize.py — Column Name Normalization (Stage 1.5)
==============================================================

Deterministically normalises column names from a raw DataFrame into clean,
consistent identifiers.  No AI calls.  No data mutation — only column
renames via ``pl.DataFrame.rename()``.

Mechanical rules (applied in order):
  1. Strip leading/trailing whitespace
  2. Strip parenthetical annotations ``(...)`` / ``[...]``
  3. Transliterate accented Latin via NFKD before special-char replacement
  4. Strip leading/trailing ``[^a-zA-Z0-9_]``
  5. Replace internal special characters with ``_``
  6. Collapse multiple underscores
  7. Lowercase
  8. Prefix ``_`` if starts with digit
  9. Reserved-word suffix check → append ``_col``
 10. Length cap (56 chars, truncate on word boundary)
 11. Empty-result fallback → ``column_{index}``

Semantic rules (single ordered pass after mechanical):
  - Aggregation-prefix strip (``sum_``, ``avg_``, ``count_``, ``total_``)
  - Trailing year/quarter/version strip (``_2024``, ``_q1``, ``_v2``)
  - Draft-label strip (``_copy``, ``_draft``, ``_final``)
  - Year-collision guard: skip strip if result would collide

Dedup pass (final):
  - Case-insensitive collision detection → ``_1``, ``_2`` suffixes
  - ``collision_group`` tracks all names that collided

Usage::

    from services.pipeline.normalize import normalize_column_names

    df_clean, manifest = normalize_column_names(df)
    # df_clean has renamed columns
    # manifest is a list of CleaningEntry dicts for the manifest
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

_RESERVED_WORDS: frozenset[str] = frozenset({
    "select", "order", "group", "table", "user", "limit",
    "where", "from", "join", "left", "right", "inner", "outer",
    "cross", "on", "and", "or", "not", "in", "is", "null",
    "true", "false", "as", "desc", "asc", "having", "by",
    "distinct", "count", "sum", "avg", "min", "max",
    "index", "key", "primary", "foreign", "references",
    "database", "schema", "view", "drop", "alter", "create",
    "delete", "insert", "update", "values", "into",
    "grant", "revoke", "transaction", "commit", "rollback",
    "session", "user", "role", "column", "rows",
    "between", "like", "ilike", "similar", "exists",
    "union", "intersect", "except", "all", "any", "some",
    "case", "when", "then", "else", "end", "cast",
    "window", "partition", "over", "rank", "dense_rank",
    "row_number", "lag", "lead", "first_value", "last_value",
})

_MAX_COLUMN_LENGTH: int = 56

# ── Aggregation prefixes detected for stripping ──────────────────────────
_AGGREGATION_PREFIXES: list[str] = [
    "sum_", "sumof_", "total_", "tot_",
    "avg_", "average_", "avgof_",
    "count_", "countof_", "cnt_",
    "min_", "max_",
    "std_", "stdev_", "var_", "variance_",
    "pct_", "percent_", "percentage_",
]

# ── Trailing labels for stripping ────────────────────────────────────────
_YEAR_PATTERN = re.compile(r"_(19\d{2}|20\d{2})$", re.IGNORECASE)
_QUARTER_PATTERN = re.compile(r"_(q[1-4])$", re.IGNORECASE)
_VERSION_PATTERN = re.compile(r"_v(\d+)$", re.IGNORECASE)
_DRAFT_PATTERN = re.compile(r"_(copy|draft|final|bak|backup|old|new)$", re.IGNORECASE)
_TRAILING_NUMBER = re.compile(r"_(\d+)$")


# ═══════════════════════════════════════════════════════════════════════
# Rule 3 — Accented character transliteration
# ═══════════════════════════════════════════════════════════════════════

def _transliterate_accented(name: str) -> str:
    """Decompose accented Latin characters to ASCII base equivalents.

    ``Región`` → ``Region``, not ``_egi_n``.

    Only non-ASCII characters that NFKD-decompose to ASCII + combining
    diacritics are affected.  ASCII-only strings pay effectively zero cost
    because ``unicodedata.normalize`` is a no-op on ASCII input.
    """
    if name.isascii():
        return name
    decomposed = unicodedata.normalize("NFKD", name)
    # Strip combining diacritics (category Mn/Mc) and keep ASCII base
    return "".join(c for c in decomposed if not unicodedata.combining(c) or c.isascii())


# ═══════════════════════════════════════════════════════════════════════
# Rule 10 — Truncation on word boundary
# ═══════════════════════════════════════════════════════════════════════

def _truncate_on_word_boundary(name: str, max_len: int) -> str:
    """Truncate *name* to *max_len* characters, breaking at a word boundary.

    Prefers to break at ``_`` or at a transition from lower→upper or
    digit→alpha.  If no boundary is found within ``max_len``, truncates
    hard at ``max_len`` and removes trailing ``_``.
    """
    if len(name) <= max_len:
        return name

    # Try to break at the last underscore within the limit
    last_underscore = name.rfind("_", 0, max_len)
    if last_underscore > max_len // 2:  # Only use if it's past the halfway point
        truncated = name[:last_underscore]
    else:
        truncated = name[:max_len].rstrip("_")
    return truncated


# ═══════════════════════════════════════════════════════════════════════
# Main normalization pipeline
# ═══════════════════════════════════════════════════════════════════════

def _apply_mechanical_rules(name: str, index: int) -> tuple[str, list[str]]:
    """Apply rules 1–11 in order and return ``(normalized, applied_steps)``.

    Args:
        name: Original column name.
        index: Column position (used for fallback rule 11).

    Returns:
        (normalized_name, list_of_applied_rule_names)
    """
    applied: list[str] = []
    original = name

    # Rule 1: Strip leading/trailing whitespace
    name = name.strip()
    if name != original:
        applied.append("strip_whitespace")

    # Rule 2: Strip parenthetical annotations (...)[...]
    name = re.sub(r"\s*[\[(][^)\]]*[)\]]\s*", "", name).strip()
    if name != original and "strip_parens" not in applied:
        applied.append("strip_parens")

    # Rule 3: Transliterate accented Latin
    translit = _transliterate_accented(name)
    if translit != name:
        name = translit
        applied.append("transliterate_accents")

    # Rule 4: Strip leading/trailing non-alphanumeric (except underscore)
    name = re.sub(r"^[^a-zA-Z0-9_]+", "", name)
    name = re.sub(r"[^a-zA-Z0-9_]+$", "", name)

    # Rule 5: Replace internal special chars with _
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Rule 6: Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Rule 7: Lowercase
    name = name.lower()

    # Rule 8: Prefix _ if starts with digit
    if name and name[0].isdigit():
        name = "_" + name
        applied.append("prefix_digit")

    # Rule 9: Reserved-word suffix check
    if name in _RESERVED_WORDS:
        name = f"{name}_col"
        applied.append("reserved_word_suffix")

    # Rule 10: Length cap
    if len(name) > _MAX_COLUMN_LENGTH:
        before = name
        name = _truncate_on_word_boundary(name, _MAX_COLUMN_LENGTH)
        if name != before:
            applied.append("truncated")

    # Rule 11: Empty-result fallback
    if not name or re.match(r"^_+$", name):
        name = f"column_{index}"
        applied.append("empty_fallback")

    return name, applied


def _apply_semantic_rules(
    name: str,
    seen_names: set[str],
) -> tuple[str, list[str]]:
    """Apply semantic rules (aggregation-strip, year-strip, draft-strip).

    Args:
        name: Already mechanically-normalized name.
        seen_names: Set of names already committed (for collision guard).

    Returns:
        (refined_name, applied_rules)
    """
    applied: list[str] = []

    # ── Aggregation-prefix strip ──────────────────────────────────────
    for prefix in _AGGREGATION_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            stripped = name[len(prefix):]
            # Collision guard: only apply if the result doesn't collide
            if stripped not in seen_names:
                name = stripped
                applied.append(f"strip_prefix:{prefix.strip('_')}")
                break

    # ── Trailing year strip ───────────────────────────────────────────
    m = _YEAR_PATTERN.search(name)
    if m:
        stripped = _YEAR_PATTERN.sub("", name)
        if stripped and stripped not in seen_names:
            name = stripped
            applied.append("strip_year")
        # If collision, keep the year — it's the distinguishing factor

    # ── Trailing quarter strip ────────────────────────────────────────
    m = _QUARTER_PATTERN.search(name)
    if m:
        stripped = _QUARTER_PATTERN.sub("", name)
        if stripped and stripped not in seen_names:
            name = stripped
            applied.append("strip_quarter")

    # ── Trailing version strip ────────────────────────────────────────
    m = _VERSION_PATTERN.search(name)
    if m:
        stripped = _VERSION_PATTERN.sub("", name)
        if stripped and stripped not in seen_names:
            name = stripped
            applied.append("strip_version")

    # ── Draft-label strip ─────────────────────────────────────────────
    m = _DRAFT_PATTERN.search(name)
    if m:
        stripped = _DRAFT_PATTERN.sub("", name)
        if stripped and stripped not in seen_names:
            name = stripped
            applied.append("strip_draft_label")

    return name, applied


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def apply_mechanical_rules(name: str, index: int = 0) -> tuple[str, list[str]]:
    """Public wrapper around the 11 mechanical normalization rules.

    This is exposed for the API to validate user-provided override names.
    See ``_apply_mechanical_rules`` for the full implementation.

    Args:
        name: Column name to normalize.
        index: Column position index (used for empty-result fallback).

    Returns:
        (normalized_name, list_of_applied_rule_names)
    """
    return _apply_mechanical_rules(name, index)


def normalize_column_names(
    df: pl.DataFrame,
) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    """Normalize all column names in a DataFrame.

    Applies the 11 mechanical rules, 4 semantic rules, and a final dedup
    pass.  Returns the renamed DataFrame and a cleaning manifest.

    The manifest is a list of dicts, each with::

        {
            "original_name": str,
            "normalized_name": str,
            "applied_steps": list[str],
            "collision_group": list[str] | None,
        }

    Args:
        df: Polars DataFrame whose columns will be renamed in place.

    Returns:
        (renamed_df, manifest_entries)
    """
    original_names: list[str] = df.columns
    n = len(original_names)

    # ── Stage A: Apply mechanical rules ───────────────────────────────
    mechanical_results: list[dict[str, Any]] = []
    for i, col in enumerate(original_names):
        norm, steps = _apply_mechanical_rules(col, i)
        mechanical_results.append({
            "original_name": col,
            "normalized_name": norm,
            "applied_steps": steps,
        })

    # ── Stage B: Apply semantic rules (ordered pass) ─────────────────
    semantic_results: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for entry in mechanical_results:
        name = entry["normalized_name"]
        refined, extra_steps = _apply_semantic_rules(name, seen_names)
        # After semantic rules, add to seen set (for year-collision guard)
        seen_names.add(refined)
        entry["normalized_name"] = refined
        entry["applied_steps"] = entry["applied_steps"] + extra_steps
        semantic_results.append(entry)

    # ── Stage C: Dedup (case-insensitive) ─────────────────────────────
    final_names: list[str] = []
    name_count: dict[str, int] = {}
    collision_groups: dict[str, list[str]] = {}

    for entry in semantic_results:
        name = entry["normalized_name"]
        name_lower = name.lower()

        if name_lower not in name_count:
            name_count[name_lower] = 0
            final_names.append(name)
            collision_groups[name_lower] = [name]
        else:
            name_count[name_lower] += 1
            suffix = name_count[name_lower]
            # Try `name_1`, `name_2`, ... but also guard against existing
            deduped = f"{name}_{suffix}"
            # Hard guard: if the deduped name somehow also exists
            while deduped.lower() in name_count and deduped != name:
                suffix += 1
                deduped = f"{name}_{suffix}"
            if deduped.lower() not in name_count:
                name_count[deduped.lower()] = 0
            final_names.append(deduped)
            collision_groups[name_lower].append(deduped)

        entry["normalized_name"] = final_names[-1]
        entry["collision_group"] = (
            collision_groups.get(name_lower) if name_count[name_lower] > 0 else None
        )

    # ── Execute rename ────────────────────────────────────────────────
    rename_map = {
        entry["original_name"]: entry["normalized_name"]
        for entry in semantic_results
    }
    renamed_df = df.rename(rename_map)

    # ── Build manifest entries ────────────────────────────────────────
    manifest = [
        {
            "original_name": e["original_name"],
            "normalized_name": e["normalized_name"],
            "applied_steps": e["applied_steps"],
            "tier": "auto",
            "collision_group": e.get("collision_group"),
        }
        for e in semantic_results
        if e["original_name"] != e["normalized_name"] or e.get("collision_group")
    ]

    # Log summary
    changed = sum(1 for e in semantic_results if e["original_name"] != e["normalized_name"])
    collisions = sum(1 for e in semantic_results if e.get("collision_group"))
    if changed:
        logger.info(
            "[Normalize] %d/%d columns renamed, %d collisions resolved",
            changed,
            n,
            collisions,
        )
    else:
        logger.info("[Normalize] All %d column names already clean — no changes", n)

    return renamed_df, manifest


__all__ = ["normalize_column_names", "apply_mechanical_rules"]
