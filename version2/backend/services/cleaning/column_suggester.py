"""
cleaning/column_suggester.py — AI-Assisted Column Cleaning Suggestions (Stage 1.6)
===================================================================================

Three-tier suggestion system that identifies columns likely needing cleanup:

Tier A (statistics only, no AI, free):
  - Exact-duplicate columns (identical values across all rows) → merge
  - 100%-null columns → flag for removal
  - Single-constant-value columns → flag for removal

Tier B (AI-assisted via Mistral Small 3.2 / OpenRouter):
  - Columns >90% correlated but not identical (possible duplicates)
  - High-null columns below 100% threshold (rare flag vs genuine junk)
  - Columns whose normalized names collided pre-dedup  (same field twice)
  - Batched call per dataset: one LLM call with all candidates

Tier C (escalation — stronger model, rare):
  - User asks "why did you suggest this?"
  - Ambiguous confidence band across multiple candidates

Usage::

    from services.cleaning.column_suggester import suggest_cleaning_actions

    suggestions = await suggest_cleaning_actions(
        df=df,
        profiling_result=profiling_result,
        existing_manifest=manifest,
        user_id=user_id,
    )
    # suggestions is a list of CleaningSuggestion dicts
"""

from __future__ import annotations

import json
import logging
from typing import Any

import polars as pl

from core.config import settings

logger = logging.getLogger(__name__)


# ── Confidence thresholds (from settings / env vars, with hardcoded defaults) ─
CONFIDENCE_AUTO_SURFACE: float = settings.COLUMN_CLEANING_CONFIDENCE_AUTO
CONFIDENCE_SUGGEST: float = settings.COLUMN_CLEANING_CONFIDENCE_SUGGEST
# < 0.50: not surfaced, logged for review

# ── Max candidates per AI batch to avoid blowing context windows ────────────
_MAX_AI_CANDIDATES: int = settings.COLUMN_CLEANING_MAX_CANDIDATES


# ═══════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════


def _build_suggestion(
    action_type: str,
    target_columns: list[str],
    tier: str,
    confidence: float | None = None,
    reasoning: str | None = None,
    **extra,
) -> dict[str, Any]:
    """Build a cleaning suggestion dict matching the manifest schema."""
    entry: dict[str, Any] = {
        "action_type": action_type,
        "target_columns": target_columns,
        "tier": tier,
        "confidence": confidence,
        "reasoning": reasoning,
        "approved": None,
    }
    entry.update(extra)
    return entry


# ═══════════════════════════════════════════════════════════════════════════
# Tier A — Statistics-based detection (no AI)
# ═══════════════════════════════════════════════════════════════════════════


def _detect_exact_duplicates(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Detect columns that are exact duplicates (all values identical).

    Compares columns pairwise.  Uses a cheap hash-based approach:
    hash each column → compare hashes.  Only expands to full comparison
    when hashes match (rare false positive with good hash function).
    """
    suggestions: list[dict[str, Any]] = []
    cols = df.columns
    n = len(cols)

    if n < 2:
        return suggestions

    # ── Compute column hashes for O(n) pre-filter ──────────────────────
    col_hashes: dict[str, int] = {}
    for col in cols:
        try:
            # Use Polars hash + sum for a fast approximate fingerprint
            h = df[col].hash(seed=42).sum()
            col_hashes[col] = h
        except Exception:
            col_hashes[col] = hash(str(df[col].to_list()[:100]))

    # ── Pairwise comparison of columns with matching hashes ────────────
    seen_pairs: set[tuple[str, str]] = set()
    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = cols[i], cols[j]
            pair_key = tuple(sorted([c1, c2]))
            if pair_key in seen_pairs:
                continue
            if col_hashes.get(c1) != col_hashes.get(c2):
                continue
            # Hash collision (or match) — verify with full comparison
            try:
                if df[c1].series_equal(df[c2], null_equal=True):
                    suggestions.append(_build_suggestion(
                        action_type="merge",
                        target_columns=[c1, c2],
                        tier="auto",
                        confidence=0.99,
                        reasoning=f"Column '{c1}' and '{c2}' have identical values across all rows",
                    ))
                    seen_pairs.add(pair_key)
            except Exception:
                continue

    return suggestions


def _detect_null_columns(
    df: pl.DataFrame,
    profiling_result: Any | None,
) -> list[dict[str, Any]]:
    """Detect 100%-null columns and high-null columns.

    Uses profiling results when available (avoids full scan), falls back
    to Polars computation.
    """
    suggestions: list[dict[str, Any]] = []
    n_rows = len(df)

    for col in df.columns:
        # Try profiling results first
        null_pct = None
        if profiling_result:
            profile = profiling_result.column_by_name(col)
            if profile:
                null_pct = profile.quality.null_percentage

        if null_pct is None:
            null_count = df[col].null_count()
            null_pct = (null_count / max(n_rows, 1)) * 100

        if null_pct >= 100.0:
            suggestions.append(_build_suggestion(
                action_type="remove",
                target_columns=[col],
                tier="auto",
                confidence=0.99,
                reasoning=f"Column '{col}' is 100% null — no usable data",
            ))
        elif null_pct >= 99.0:
            suggestions.append(_build_suggestion(
                action_type="remove",
                target_columns=[col],
                tier="suggested",
                confidence=0.85,
                reasoning=f"Column '{col}' is {null_pct:.0f}% null — consider removing",
            ))

    return suggestions


def _detect_constant_columns(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Detect columns with a single constant value (including all-null)."""
    suggestions: list[dict[str, Any]] = []

    for col in df.columns:
        try:
            unique_count = df[col].n_unique()
            if unique_count <= 1:
                null_count = df[col].null_count()
                val = df[col].drop_nulls().head(1).to_list()
                val_str = str(val[0]) if val else "null"
                suggestions.append(_build_suggestion(
                    action_type="remove",
                    target_columns=[col],
                    tier="auto",
                    confidence=0.95,
                    reasoning=(
                        f"Column '{col}' has a single constant value ({val_str}) "
                        f"across all {len(df)} rows"
                    ),
                ))
        except Exception:
            continue

    return suggestions


# ═══════════════════════════════════════════════════════════════════════════
# Tier B Candidate Builder — prepares data for the AI call
# ═══════════════════════════════════════════════════════════════════════════


def _build_tier_b_candidates(
    df: pl.DataFrame,
    profiling_result: Any | None,
    existing_manifest: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Identify candidate columns that may need AI review.

    Candidates include:
    - Columns >90% correlated (numeric columns with high correlation)
    - High-null columns >50% but <100%
    - Columns whose names collided during normalization (from manifest)
    """
    candidates: list[dict[str, Any]] = []
    cols = df.columns
    n = len(cols)

    if n < 2:
        return candidates

    # ── Gather column metadata ─────────────────────────────────────────
    col_info: dict[str, dict[str, Any]] = {}
    for col in cols:
        info: dict[str, Any] = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_pct": 0.0,
            "unique_count": 0,
            "sample_values": [],
        }
        if profiling_result:
            profile = profiling_result.column_by_name(col)
            if profile:
                info["null_pct"] = profile.quality.null_percentage
                info["unique_count"] = profile.cardinality.unique_count
                info["sample_values"] = profile.sample_values[:5]
        else:
            info["null_pct"] = (df[col].null_count() / max(len(df), 1)) * 100
            info["unique_count"] = df[col].n_unique()
            info["sample_values"] = [str(v) for v in df[col].drop_nulls().head(5).to_list()]

        col_info[col] = info

    # ── Check correlations (numeric pairs) ────────────────────────────
    numeric_cols = [c for c in cols if "Int" in str(df[c].dtype) or "Float" in str(df[c].dtype)]
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            c1, c2 = numeric_cols[i], numeric_cols[j]
            # Quick pre-filter: skip exact duplicates (already flagged by Tier A)
            info1, info2 = col_info[c1], col_info[c2]
            if info1["unique_count"] == info2["unique_count"] and info1["unique_count"] < 3:
                continue  # Likely constant/boolean pair — not interesting
            try:
                corr = df[c1].corr(df[c2])
                if corr is not None and abs(corr) > 0.90:
                    candidates.append({
                        "column_1": c1,
                        "column_2": c2,
                        "signal": "high_correlation",
                        "value": round(float(corr), 4),
                        "col_1_info": {
                            "dtype": info1["dtype"],
                            "null_pct": info1["null_pct"],
                            "unique_count": info1["unique_count"],
                            "sample": info1["sample_values"][:3],
                        },
                        "col_2_info": {
                            "dtype": info2["dtype"],
                            "null_pct": info2["null_pct"],
                            "unique_count": info2["unique_count"],
                            "sample": info2["sample_values"][:3],
                        },
                    })
            except Exception:
                continue

    # ── Check high-null columns (50-99%) ──────────────────────────────
    for col in cols:
        info = col_info[col]
        if 50.0 <= info["null_pct"] < 100.0:
            candidates.append({
                "column": col,
                "signal": "high_nulls",
                "null_pct": info["null_pct"],
                "dtype": info["dtype"],
                "unique_count": info["unique_count"],
                "sample": info["sample_values"][:3],
            })

    # ── Check for collision groups from normalization manifest ────────
    if existing_manifest:
        seen_groups: set[str] = set()
        for entry in existing_manifest:
            group = entry.get("collision_group")
            if group and len(group) > 1:
                group_key = ",".join(sorted(group))
                if group_key not in seen_groups:
                    seen_groups.add(group_key)
                    candidates.append({
                        "columns": group,
                        "signal": "name_collision",
                        "note": "These column names collided during normalization — they may be the same field exported twice",
                    })

    return candidates


# ═══════════════════════════════════════════════════════════════════════════
# Tier B — AI-assisted suggestion via OpenRouter
# ═══════════════════════════════════════════════════════════════════════════


def _build_ai_prompt(
    candidates: list[dict[str, Any]],
    column_metadata: list[dict[str, Any]] | None = None,
) -> str:
    """Build the structured prompt for the AI model.

    Sends all Tier B candidates in a single batched call.
    Prompts the model to assess each candidate and return structured JSON.
    """
    prompt_parts = [
        "You are a data cleaning assistant. Review the following columns from a dataset",
        "and determine which ones should be merged or removed.",
        "",
        "For each candidate, respond with:",
        "  - action: \"merge\" | \"remove\" | \"keep\"",
        "  - confidence: float 0.0-1.0",
        "  - reasoning: brief one-sentence explanation",
        "",
        "Return ONLY valid JSON array with no markdown fences:",
        '[{ "action": "...", "confidence": 0.0, "reasoning": "..." }]',
        "",
    ]

    # ── Column metadata context ──────────────────────────────────────
    if column_metadata:
        prompt_parts.append("=== COLUMN METADATA ===")
        # Only include high-level stats to keep prompt small
        for meta in column_metadata[:30]:
            name = meta.get("name", "?")
            dtype = meta.get("type", "?")
            nulls = meta.get("null_percentage", 0)
            unique = meta.get("unique_count", 0)
            prompt_parts.append(f"  {name}: dtype={dtype}, nulls={nulls}%, unique={unique}")
        prompt_parts.append("")

    # ── Candidates ────────────────────────────────────────────────────
    prompt_parts.append("=== CANDIDATES FOR REVIEW ===")
    for i, c in enumerate(candidates):
        signal = c.get("signal", "unknown")
        if signal == "high_correlation":
            prompt_parts.append(
                f"Candidate {i}: Columns '{c['column_1']}' (dtype={c['col_1_info']['dtype']}, "
                f"nulls={c['col_1_info']['null_pct']:.0f}%) and '{c['column_2']}' "
                f"(dtype={c['col_2_info']['dtype']}, nulls={c['col_2_info']['null_pct']:.0f}%) "
                f"are correlated at r={c['value']:.2f}"
            )
            col1_sample = c['col_1_info'].get('sample', [])
            col2_sample = c['col_2_info'].get('sample', [])
            if col1_sample and col2_sample:
                prompt_parts.append(f"  Sample values: '{c['column_1']}'={col1_sample}, '{c['column_2']}'={col2_sample}")
        elif signal == "high_nulls":
            prompt_parts.append(
                f"Candidate {i}: Column '{c['column']}' has {c['null_pct']:.0f}% nulls "
                f"(dtype={c['dtype']}, unique={c['unique_count']})"
            )
            if c.get('sample'):
                prompt_parts.append(f"  Sample values: {c['sample']}")
        elif signal == "name_collision":
            cols = ", ".join(c.get("columns", []))
            prompt_parts.append(
                f"Candidate {i}: These columns collided during normalization: [{cols}]"
            )
            prompt_parts.append(f"  Note: {c.get('note', '')}")

    prompt_parts.append("")
    prompt_parts.append(
        "Respond with a JSON array matching the candidate order above. "
        "Example: [{\"action\": \"keep\", \"confidence\": 0.95, \"reasoning\": \"Columns are distinct metrics\"}]"
    )

    return "\n".join(prompt_parts)


async def _call_ai_for_suggestions(
    candidates: list[dict[str, Any]],
    column_metadata: list[dict[str, Any]] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Call the AI model via OpenRouter and parse structured suggestions.

    Falls back gracefully if the model call fails — returns an empty list
    so the pipeline doesn't break.
    """
    if not candidates:
        return []

    # Truncate to max candidates
    candidates = candidates[:_MAX_AI_CANDIDATES]

    prompt = _build_ai_prompt(candidates, column_metadata)

    try:
        from llm.router import llm_router

        response = await llm_router.call(
            prompt=prompt,
            model_role="column_cleaning_suggestion",
            expect_json=True,
            temperature=0.1,
            max_tokens=1024,
            user_id=user_id,
        )

        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            # Some models wrap in a top-level key
            for key in ("suggestions", "results", "actions", "decisions"):
                if key in response and isinstance(response[key], list):
                    return response[key]
            return [response]
        else:
            logger.warning("[CleaningSuggester] Unexpected AI response type: %s", type(response))
            return []

    except Exception as e:
        logger.warning(
            "[CleaningSuggester] AI suggestion call failed (non-critical): %s",
            e,
        )
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════


async def suggest_cleaning_actions(
    df: pl.DataFrame,
    profiling_result: Any | None = None,
    existing_manifest: list[dict[str, Any]] | None = None,
    column_metadata: list[dict[str, Any]] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Run Stage 1.6 suggestion pipeline and return new manifest entries.

    Args:
        df: Cleaned DataFrame (post-Stage 1.5, with renamed columns).
        profiling_result: RawProfilingResult from the profiling engine.
        existing_manifest: Manifest entries from Stage 1.5 normalization.
        column_metadata: Column metadata list for AI context.
        user_id: Optional user ID for cost tracking.

    Returns:
        List of suggestion dicts to append to the cleaning manifest.
    """
    suggestions: list[dict[str, Any]] = []

    # ── Tier A: Statistics (always runs, free) ─────────────────────────
    try:
        suggestions.extend(_detect_exact_duplicates(df))
        logger.info("[CleaningSuggester] Tier A: %d exact-duplicate suggestions", len(suggestions))
    except Exception as e:
        logger.warning("[CleaningSuggester] Tier A duplicate detection failed: %s", e)

    try:
        suggestions.extend(_detect_null_columns(df, profiling_result))
        logger.info("[CleaningSuggester] Tier A: %d null-column suggestions", len(suggestions))
    except Exception as e:
        logger.warning("[CleaningSuggester] Tier A null detection failed: %s", e)

    try:
        suggestions.extend(_detect_constant_columns(df))
        logger.info("[CleaningSuggester] Tier A: %d constant-column suggestions", len(suggestions))
    except Exception as e:
        logger.warning("[CleaningSuggester] Tier A constant detection failed: %s", e)

    # ── Tier B: AI-assisted (batched, cheap model) ─────────────────────
    candidates = _build_tier_b_candidates(df, profiling_result, existing_manifest)

    if candidates:
        logger.info(
            "[CleaningSuggester] Tier B: %d candidates for AI review",
            len(candidates),
        )

        try:
            ai_results = await _call_ai_for_suggestions(
                candidates=candidates,
                column_metadata=column_metadata,
                user_id=user_id,
            )

            if ai_results:
                # Map AI results back to candidates and apply confidence thresholds
                for i, result in enumerate(ai_results):
                    if i >= len(candidates):
                        break
                    candidate = candidates[i]
                    action = result.get("action", "keep")
                    confidence = result.get("confidence", 0.0)

                    if action == "keep":
                        continue

                    # Apply confidence threshold
                    if confidence < CONFIDENCE_SUGGEST:
                        logger.debug(
                            "[CleaningSuggester] Skipping low-confidence suggestion for %s: %.2f",
                            candidate.get("column", candidate.get("column_1", "?")),
                            confidence,
                        )
                        continue

                    tier = "suggested" if confidence >= CONFIDENCE_AUTO_SURFACE else "suggested"
                    reasoning = result.get("reasoning", "")

                    if action == "merge":
                        col1 = candidate.get("column_1", "")
                        col2 = candidate.get("column_2", "")
                        if col1 and col2:
                            suggestions.append(_build_suggestion(
                                action_type="merge",
                                target_columns=[col1, col2],
                                tier=tier,
                                confidence=round(confidence, 2),
                                reasoning=reasoning or f"Columns '{col1}' and '{col2}' may be duplicates",
                                model_used="mistral_small_32",
                            ))
                    elif action == "remove":
                        col = candidate.get("column", "")
                        if col:
                            suggestions.append(_build_suggestion(
                                action_type="remove",
                                target_columns=[col],
                                tier=tier,
                                confidence=round(confidence, 2),
                                reasoning=reasoning or f"Column '{col}' may be redundant",
                                model_used="mistral_small_32",
                            ))

                logger.info(
                    "[CleaningSuggester] Tier B: %d AI suggestions after thresholding",
                    len(suggestions) - (len(suggestions) - len(ai_results)),
                )
        except Exception as e:
            logger.warning("[CleaningSuggester] Tier B AI call failed (non-critical): %s", e)
    else:
        logger.debug("[CleaningSuggester] No Tier B candidates — skipping AI call")

    # ── De-duplicate suggestions ───────────────────────────────────────
    # Remove suggestions that target the same column pairs
    seen_targets: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for s in suggestions:
        target = tuple(sorted(s.get("target_columns", [])))
        if target not in seen_targets:
            seen_targets.add(target)
            deduped.append(s)

    logger.info(
        "[CleaningSuggester] Total suggestions: %d (%d Tier-B AI) — %d unique after dedup",
        len(suggestions),
        sum(1 for s in suggestions if s["tier"] in ("suggested",) and s.get("model_used")),
        len(deduped),
    )

    return deduped


__all__ = ["suggest_cleaning_actions"]
