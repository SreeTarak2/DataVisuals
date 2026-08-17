"""
intelligence/hierarchy_inference_v2.py — Tiered hierarchy inference (Act-then-Validate)
========================================================================================

Implements the 80/20 ontology contract for hierarchies:

  Pass 1 — DETERMINISTIC (auto-validated, no LLM, no tokens)
    ``hierarchy_detector`` matches curated patterns (geo/category/org/date)
    and verifies cardinality ordering. Every hit becomes a VALIDATED
    assumption with confidence 1.0.

  Pass 2 — LLM PROPOSES, DETERMINISM VERIFIES (the ambiguous tail)
    The LLM proposes hierarchies for the uncovered dimension columns.
    Each proposal is verified DETERMINISTICALLY (cardinality ordering,
    value containment / functional dependency, null discipline, naming
    signal) — the LLM never gets to assert a hierarchy on its own.
      - verification ≥ 0.85  → validated (applied silently)
      - verification 0.5–0.85 → provisional (applied, flagged for review)
      - verification < 0.5    → provisional + low_confidence flag

  Pass 3 — DRIFT (finalize is not permanent)
    Re-verification against fresh data on every regenerate. If a finalized
    hierarchy no longer holds (new values broke the containment/cardinality
    invariant), it reverts to provisional and pings for review.

All hierarchy *mechanics* (drill-down, cross-filter) stay deterministic —
this module only decides WHICH hierarchies exist and how confident we are.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import polars as pl

from services.profiling.models import RawProfilingResult
from services.intelligence.hierarchy_detector import hierarchy_detector
from services.semantic.assumption_store import (
    PROVISIONAL,
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    TYPE_HIERARCHY,
    VALIDATED,
    SemanticAssumption,
    new_assumption,
)

logger = logging.getLogger(__name__)

# ─── Confidence thresholds ───────────────────────────────────────────────────

HIGH_CONFIDENCE = 0.85
MID_CONFIDENCE = 0.50

# Naming tokens that suggest a column participates in a hierarchy.
_HIERARCHY_KEYWORDS = re.compile(
    r"\b(category|subcategory|sub_category|segment|subsegment|sub_segment|"
    r"product|productline|product_line|brand|type|group|tier|channel|"
    r"region|country|state|province|city|territory|division|department|"
    r"team|manager|unit|class|family|subfamily|sub_family|industry|"
    r"vertical|cohort|plan|package|level)\b",
    re.I,
)
_SUB_PREFIX = re.compile(r"^(sub|child|detail)[_ ]", re.I)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic verification
# ─────────────────────────────────────────────────────────────────────────────


def _cardinality_ordering_ok(result: RawProfilingResult, columns: list[str]) -> bool:
    """Parent level must have <= unique values than child (region < country < city)."""
    card_map = result.cardinality_map()
    counts: list[int] = []
    for col in columns:
        info = card_map.get(col)
        if info is None:
            return False
        counts.append(info.unique_count)
    for i in range(len(counts) - 1):
        if counts[i] > counts[i + 1]:
            return False
    return True


def _null_discipline_ok(result: RawProfilingResult, columns: list[str]) -> bool:
    """No hierarchy level may be >50% null (a null-heavy level breaks drill-down)."""
    card_map = result.cardinality_map()
    for col in columns:
        info = card_map.get(col)
        if info is not None and info.null_pct > 50:
            return False
    return True


def _value_containment_ok(df: pl.DataFrame, columns: list[str]) -> Optional[bool]:
    """
    Functional-dependency check: every child value must map to exactly one
    parent value (a valid hierarchy is child → one parent, never child → many).

    Returns None when the check cannot be run (missing columns / no df).
    """
    if df is None or len(columns) < 2:
        return None
    try:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return None
        # For each adjacent (parent, child) pair, the child must map to at most
        # one parent value (child → exactly one parent, never child → many).
        for i in range(len(columns) - 1):
            parent, child = columns[i], columns[i + 1]
            distinct_parents = (
                df.group_by(child)
                .agg(pl.col(parent).n_unique().alias("n_parents"))
                .get_column("n_parents")
                .max()
            )
            if distinct_parents is not None and int(distinct_parents) > 1:
                return False
        return True
    except Exception as exc:  # noqa: BLE001 — verification must never raise
        logger.debug(f"[HierarchyV2] containment check skipped: {exc}")
        return None


def _is_subsequence(short: tuple[str, ...], long: tuple[str, ...]) -> bool:
    """True if ``short`` appears as an ordered subsequence of ``long``."""
    it = iter(long)
    return all(any(c == s for c in it) for s in short)


def _naming_signal(columns: list[str]) -> float:
    """0–1: how strongly the column names suggest a hierarchy chain."""
    if not columns:
        return 0.0
    hits = 0
    for col in columns:
        low = col.lower().replace("_", " ")
        if _HIERARCHY_KEYWORDS.search(low) or _SUB_PREFIX.search(low):
            hits += 1
    return hits / len(columns)


def verify_hierarchy_candidate(
    result: RawProfilingResult,
    df: Optional[pl.DataFrame],
    columns: list[str],
) -> tuple[bool, float, dict[str, Any]]:
    """
    Deterministically verify a hierarchy candidate.

    Returns ``(ok, confidence, evidence)``. The LLM may *propose*; only this
    function decides whether the proposal is structurally sound.

    Checks (strongest first):
      1. All columns exist in the profile.
      2. Value containment — every child maps to exactly one parent.
      3. Cardinality ordering — parent unique count <= child unique count.
      4. Null discipline — no level >50% null.
      5. Naming signal — names carry hierarchy vocabulary (weakest).
    """
    evidence: dict[str, Any] = {}
    if not columns or len(columns) < 2:
        return False, 0.0, {"reason": "need at least 2 columns"}

    card_map = result.cardinality_map()
    missing = [c for c in columns if c not in card_map]
    if missing:
        return False, 0.0, {"reason": f"columns not in profile: {missing}"}

    evidence["unique_counts"] = {c: card_map[c].unique_count for c in columns}
    evidence["null_pcts"] = {c: round(card_map[c].null_pct, 1) for c in columns}

    # 1. Cardinality ordering (cheap, always run)
    card_ok = _cardinality_ordering_ok(result, columns)
    evidence["cardinality_order_ok"] = card_ok
    if card_ok:
        counts = [str(card_map[c].unique_count) for c in columns]
        evidence["cardinality"] = " → ".join(counts)

    # 2. Value containment (strongest — functional dependency)
    contain = _value_containment_ok(df, columns) if df is not None else None
    evidence["containment_ok"] = contain
    if contain is False:
        return False, 0.35, {**evidence, "reason": "child values map to multiple parents"}

    # 3. Null discipline
    null_ok = _null_discipline_ok(result, columns)
    evidence["null_ok"] = null_ok

    # 4. Naming signal (weakest — never decisive alone)
    name_signal = _naming_signal(columns)
    evidence["naming_signal"] = round(name_signal, 2)

    if not card_ok:
        return False, 0.4, {**evidence, "reason": "cardinality ordering violated"}

    # Weighted confidence: containment + ordering dominate; nulls and naming nudge.
    confidence = 0.0
    if contain is True:
        confidence += 0.40
    elif contain is None:
        confidence += 0.20  # no df — partial credit, still usable
    if card_ok:
        confidence += 0.35
    if null_ok:
        confidence += 0.10
    confidence += 0.15 * name_signal
    confidence = max(0.0, min(1.0, round(confidence, 3)))

    return True, confidence, evidence


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — Deterministic (auto-validated)
# ─────────────────────────────────────────────────────────────────────────────


def run_deterministic_pass(
    result: RawProfilingResult,
    df: Optional[pl.DataFrame],
    dataset_id: str,
    workspace_id: str,
    user_id: str = "",
) -> list[SemanticAssumption]:
    """
    Wrap ``hierarchy_detector`` — curated patterns verified by cardinality.

    Every pattern hit becomes a VALIDATED assumption (confidence 1.0,
    source deterministic_pattern). Defensive: if a curated pattern somehow
    fails verification, it is downgraded to provisional instead of trusted.
    """
    assumptions: list[SemanticAssumption] = []
    try:
        detected = hierarchy_detector.detect(result, df)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[HierarchyV2] deterministic pass failed: {exc}")
        return assumptions

    seen: set[tuple[str, ...]] = set()
    for h in detected:
        # The curated detector returns empty-string slots for pattern levels
        # that had no column match (e.g. country→state→city→""). Drop them.
        columns = [c for c in h.columns if c]
        if len(columns) < 2:
            continue
        key = tuple(columns)
        if key in seen:
            continue  # overlapping patterns matched the same chain — keep first
        seen.add(key)
        ok, conf, evidence = verify_hierarchy_candidate(result, df, columns)
        state = VALIDATED if ok else PROVISIONAL
        assumptions.append(
            new_assumption(
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                type=TYPE_HIERARCHY,
                definition={"columns": columns, "hierarchy_type": h.hierarchy_type},
                confidence=1.0 if ok else max(conf, 0.5),
                evidence={**evidence, "verified_by": "deterministic"},
                state=state,
                source=SOURCE_DETERMINISTIC,
                description=h.description or f"Hierarchy: {' → '.join(columns)}",
                user_id=user_id,
            )
        )
    # Keep only MAXIMAL chains: overlapping patterns (geo variants) produce
    # sub-chains like country→city and state→city alongside the full
    # country→state→city. Sub-chains are redundant drill paths — drop any
    # chain that is a subsequence of a longer one.
    assumptions.sort(key=lambda a: len(a.definition["columns"]), reverse=True)
    maximal: list[SemanticAssumption] = []
    for a in assumptions:
        cols = tuple(a.definition["columns"])
        if any(_is_subsequence(cols, tuple(b.definition["columns"])) for b in maximal):
            continue
        maximal.append(a)

    if maximal:
        logger.info(
            "[HierarchyV2] Deterministic pass: %d maximal hierarchies (all validated)",
            len(maximal),
        )
    return maximal


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — LLM proposes, determinism verifies
# ─────────────────────────────────────────────────────────────────────────────


def _candidate_dimension_columns(
    result: RawProfilingResult,
    covered_columns: set[str],
    max_candidates: int = 24,
) -> list[Any]:
    """Dimension-ish columns not already in a hierarchy — the LLM's search space.

    Exclusion rules (all deterministic):
      - already covered by an existing hierarchy
      - ID/entity columns (_id/_key/_uuid suffixes, very high cardinality)
      - date/time dtypes (dates get their own temporal hierarchy)
      - numeric columns (measures aren't hierarchy levels)
      - >50% null, or ultra-low cardinality (1-2 unique = flags, not levels)
    """
    candidates: list[Any] = []
    id_suffix = re.compile(r"(_id|_key|_uuid|_guid)$", re.I)
    flag_prefix = re.compile(r"^(is_|has_|flag_|is|has|flag)", re.I)

    for col in result.columns:
        name = col.name
        if name in covered_columns:
            continue
        if any(t in col.dtype for t in ("Date", "Datetime", "Duration")):
            continue
        if col.stats is not None:  # numeric → measure, not a hierarchy level
            continue
        if id_suffix.search(name) or flag_prefix.search(name):
            continue
        unique = col.cardinality.unique_count
        if unique < 2 or unique > 1000:  # <2 = constant; >1000 = high-card text, not a level
            continue
        if col.cardinality.null_pct > 50:
            continue
        candidates.append(col)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _build_llm_prompt(result: RawProfilingResult, candidates: list[Any]) -> str:
    lines: list[str] = []
    for c in candidates:
        name = c.name
        unique = c.cardinality.unique_count
        nulls = round(c.cardinality.null_pct, 1)
        samples = ", ".join(v[:40] for v in c.sample_values[:3] if v)
        dist = ""
        if c.top_values and unique <= 12:
            pairs = [f"{v.value}({v.count})" for v in c.top_values[:6]]
            dist = f"  distribution: {', '.join(pairs)}"
        lines.append(
            f"- {name}  (unique={unique}, nulls={nulls}%)"
            f"{f'  samples: {samples}' if samples else ''}{dist}"
        )
    return "\n".join(lines)


_LLM_HIERARCHY_PROMPT = """\
You are a data modeling assistant. Your job: propose possible DRILL-DOWN HIERARCHIES between the candidate columns below.

A hierarchy is an ordered chain of columns where each level rolls up to the next, parent → child, e.g.:
  region → country → city
  category → subcategory → product
  department → team → employee
  plan → feature

RULES:
1. Only use column names from the candidate list below (exact names).
2. Each chain must have 2-4 columns, ordered parent (fewer distinct values) → child (more distinct values).
3. Do NOT chain unrelated columns. Only propose chains where the parent genuinely groups the child.
4. A column can appear in at most one chain.
5. Prefer chains with 2-3 columns over speculative 4-column chains.
6. Only propose hierarchies you are reasonably confident about. If nothing fits, return an empty list.

CANDIDATE COLUMNS:
{candidates}

OUTPUT (valid JSON only — no markdown, no commentary):
{{
  "hierarchies": [
    {{"columns": ["region", "country", "city"], "reason": "geo rollup"}}
  ]
}}
"""


async def run_llm_pass(
    result: RawProfilingResult,
    df: Optional[pl.DataFrame],
    dataset_id: str,
    workspace_id: str,
    user_id: str = "",
    llm_caller: Optional[Any] = None,
    covered_columns: Optional[set[str]] = None,
) -> list[SemanticAssumption]:
    """
    LLM proposes hierarchies for uncovered dimensions; each proposal is
    verified deterministically before being accepted at any confidence.

    Never raises — on LLM failure it returns [] so the caller degrades to
    the deterministic pass only (which is always the floor).
    """
    if covered_columns is None:
        covered_columns = set()
    candidates = _candidate_dimension_columns(result, covered_columns)
    if not candidates:
        return []

    prompt = _LLM_HIERARCHY_PROMPT.format(
        candidates=_build_llm_prompt(result, candidates)
    )

    try:
        if llm_caller is None:
            from llm.router import llm_router

            llm_caller = llm_router

        response = await llm_caller.call(
            prompt=prompt,
            model_role="intent_engine",
            expect_json=True,
            temperature=0.1,
            max_tokens=700,
            is_conversational=False,
            user_id=user_id or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[HierarchyV2] LLM pass failed — deterministic only: {exc}")
        return []

    if not isinstance(response, dict):
        return []
    proposals = response.get("hierarchies") or []
    if not isinstance(proposals, list):
        return []

    name_set = {c.name for c in result.columns}
    assumptions: list[SemanticAssumption] = []
    used_columns: set[str] = set(covered_columns)

    for prop in proposals:
        if not isinstance(prop, dict):
            continue
        columns = prop.get("columns") or []
        # Sanitize: existing columns only, 2-5 of them, no reuse.
        columns = [c for c in columns if isinstance(c, str) and c in name_set][:5]
        if len(columns) < 2:
            continue
        if any(c in used_columns for c in columns):
            continue

        ok, conf, evidence = verify_hierarchy_candidate(result, df, columns)
        if not ok:
            logger.info(
                "[HierarchyV2] LLM proposal rejected by verification: %s (%s)",
                columns,
                evidence.get("reason", "failed check"),
            )
            continue

        state = VALIDATED if conf >= HIGH_CONFIDENCE else PROVISIONAL
        if conf < MID_CONFIDENCE:
            evidence["low_confidence"] = True

        used_columns.update(columns)
        reason = prop.get("reason") or ""
        assumptions.append(
            new_assumption(
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                type=TYPE_HIERARCHY,
                definition={"columns": columns, "hierarchy_type": "suggested"},
                confidence=conf,
                evidence={**evidence, "verified_by": "deterministic", "llm_reason": reason},
                state=state,
                source=SOURCE_LLM,
                description=f"Suggested hierarchy: {' → '.join(columns)}",
                user_id=user_id,
            )
        )

    logger.info(
        "[HierarchyV2] LLM pass: %d proposals → %d accepted (%d validated, %d provisional)",
        len(proposals),
        len(assumptions),
        sum(1 for a in assumptions if a.state == VALIDATED),
        sum(1 for a in assumptions if a.state == PROVISIONAL),
    )
    return assumptions


# ─────────────────────────────────────────────────────────────────────────────
# Pass 3 — Drift re-verification
# ─────────────────────────────────────────────────────────────────────────────


def verify_assumption(
    result: RawProfilingResult,
    df: Optional[pl.DataFrame],
    assumption: SemanticAssumption,
) -> tuple[bool, float, dict[str, Any]]:
    """Re-verify a stored assumption against fresh profile/data (drift check)."""
    if assumption.type != TYPE_HIERARCHY:
        return True, assumption.confidence, assumption.evidence
    columns = assumption.definition.get("columns") or []
    return verify_hierarchy_candidate(result, df, columns)


# ─────────────────────────────────────────────────────────────────────────────
# Consumption — effective hierarchies for drill-down / cross-filter
# ─────────────────────────────────────────────────────────────────────────────


def effective_hierarchies(assumptions: list[SemanticAssumption]) -> list[dict[str, Any]]:
    """
    Merge stored assumptions into the ordered hierarchy list consumed by
    drill-down. Validated first (by confidence), then provisional. Rejected
    assumptions are excluded entirely.

    Each entry carries its state so the UI can flag provisional usage.
    """
    usable = [
        a for a in assumptions
        if a.state in (VALIDATED, PROVISIONAL) and a.type == TYPE_HIERARCHY
    ]
    order = {VALIDATED: 0, PROVISIONAL: 1}
    usable.sort(key=lambda a: (order.get(a.state, 2), -a.confidence))

    result: list[dict[str, Any]] = []
    for a in usable:
        result.append(
            {
                "assumption_id": a.assumption_id,
                "columns": a.definition.get("columns", []),
                "hierarchy_type": a.definition.get("hierarchy_type", "suggested"),
                "confidence": a.confidence,
                "state": a.state,
                "source": a.source,
                "evidence": a.evidence,
                "description": a.description,
            }
        )
    return result
