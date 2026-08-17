"""
cleaning/mutation_engine.py — Two-Phase Mutation Layer for the Cleaning Manifest
=================================================================================

The manifest was a log dressed up as a control surface: deterministic renames
were applied to the parquet *unconditionally* at pipeline time, AI proposals
(merge/remove) were recorded but never executed, and Approve/Reject in the UI
only flipped flags in MongoDB. This module turns the manifest into a real
execution engine:

    Approve an AI proposal   → execute the Polars op against the active
                               parquet, then refresh every downstream artifact
                               (parquet → re-profile → uploads doc metadata →
                               profile/intelligence collections → RAG chunks →
                               caches) as a background job.
    Reject a deterministic   → invert the rename (rename back), then run the
      rename                   same downstream refresh.
    Reject an AI proposal    → no-op: it was never applied. Just record it.
    Approve a deterministic  → no-op: already applied. Just confirm it.
    override_to              → rename the column to the user-supplied name
                               (validated through mechanical rules).

Trust rules enforced here:

1.  **No silent mutation.** Every decision that changes data runs through
    ``_refresh_downstream`` and leaves a ``mutation_status`` trail on the doc.
2.  **Destructive ops are guarded.** A merge/remove that has already been
    applied cannot be un-applied from the parquet alone (that would require
    re-processing from the original file), so rejecting one raises instead of
    silently lying about the data.
3.  **Renames are invertible.** Rename-backs are guarded against collisions
    with existing column names.
4.  **Concurrent mutations are serialized.** A CAS ``mutation_lock`` on the
    uploads doc prevents two cleaning operations racing on the same parquet.
    The lock is held until the background refresh completes so a second
    mutation can never read a parquet that is mid-rewrite.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from db.database import get_database
from services.pipeline.date_fixer import apply_date_coercion
from services.pipeline.category_fixer import apply_merge_values
from services.pipeline.unpivot_fixer import apply_unpivot

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# State model (backward compatible with the existing manifest)
# ═══════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def is_ai_proposal(entry: dict) -> bool:
    """Proposal entries originate from the AI suggester or deterministic
    detectors and are never executed without user approval."""
    return entry.get("action_type") in (
        "merge",
        "remove",
        "type_coercion",
        "merge_values",
        "unpivot_columns",
    )


def entry_state(entry: dict) -> str:
    """
    Derive the manifest state without requiring a schema migration.

    - ``applied_silently`` — deterministic rename applied at pipeline time,
      not yet reviewed.
    - ``proposed``         — AI proposal, never executed, awaiting review.
    - ``confirmed``        — deterministic rename the user approved (no-op).
    - ``applied``          — an executed mutation (rename override or AI op).
    - ``rejected``         — AI proposal the user rejected (never executed).
    - ``reverted``         — deterministic rename the user rejected; parquet
      was renamed back.
    """
    approved = entry.get("approved")
    if approved is True:
        return "confirmed" if not is_ai_proposal(entry) else "applied"
    if approved is False:
        return "reverted" if not is_ai_proposal(entry) else "rejected"
    if is_ai_proposal(entry):
        return "applied" if entry.get("state") == "applied" else "proposed"
    return "applied_silently"


# ═══════════════════════════════════════════════════════════════════════════
# Pure Polars operations (deterministic, unit-testable)
# ═══════════════════════════════════════════════════════════════════════════

def _find_column(df: pl.DataFrame, name: str) -> str | None:
    """Find the actual column matching *name*, tolerating case drift.

    The manifest's ``normalized_name`` can diverge from the real parquet
    column (legacy datasets, files re-processed on a different path).
    Lookup falls back to a case-insensitive match so the engine stays
    robust instead of silently no-oping.
    """
    if name in df.columns:
        return name
    lower_map = {c.lower(): c for c in df.columns}
    return lower_map.get(name.lower())


def rename_back(df: pl.DataFrame, entry: dict, warnings: list[str]) -> pl.DataFrame:
    """Invert a deterministic rename: normalized → original (collision-guarded)."""
    original = entry.get("original_name")
    normalized = entry.get("normalized_name")
    if not original or not normalized or original == normalized:
        return df
    actual = _find_column(df, normalized)
    if actual is None:
        warnings.append(f"Column '{normalized}' not found — nothing to revert.")
        return df
    if actual.lower() == original.lower():
        return df  # already under the original name
    if _find_column(df, original) is not None:
        warnings.append(
            f"Cannot revert rename of '{normalized}' → '{original}': "
            f"a column named '{original}' already exists."
        )
        return df
    return df.rename({actual: original})


def _reapply_rename(df: pl.DataFrame, entry: dict, warnings: list[str]) -> pl.DataFrame:
    """Re-apply a deterministic rename that was previously reverted.

    The column currently sits under the *original* name; rename it forward
    to the normalized name (collision-guarded)."""
    original = entry.get("original_name")
    normalized = entry.get("normalized_name")
    if not original or not normalized or original == normalized:
        return df
    actual = _find_column(df, original)
    if actual is None:
        warnings.append(f"Column '{original}' not found — cannot re-apply the rename.")
        return df
    if actual.lower() == normalized.lower():
        return df  # already under the normalized name
    if _find_column(df, normalized) is not None:
        warnings.append(
            f"Cannot re-apply rename '{original}' → '{normalized}': "
            f"a column with that name already exists."
        )
        return df
    return df.rename({actual: normalized})


def apply_rename(df: pl.DataFrame, entry: dict, new_name: str, warnings: list[str]) -> pl.DataFrame:
    """Rename the column to a user-supplied override name (collision-guarded)."""
    current = entry.get("normalized_name")
    if not current:
        warnings.append("Rename entry has no normalized_name — skipped.")
        return df
    if new_name == current:
        return df
    actual = _find_column(df, current)
    if actual is None:
        warnings.append(f"Column '{current}' not found — rename skipped.")
        return df
    if actual.lower() == new_name.lower():
        return df  # already under the target name
    if _find_column(df, new_name) is not None:
        warnings.append(
            f"Cannot rename '{current}' → '{new_name}': a column with that name already exists."
        )
        return df
    return df.rename({actual: new_name})


def apply_drop(df: pl.DataFrame, entry: dict, warnings: list[str]) -> pl.DataFrame:
    """Execute an AI 'remove' proposal: drop the target column(s)."""
    targets = entry.get("target_columns") or []
    existing = [c for c in targets if c in df.columns]
    if not existing:
        warnings.append(
            f"No target columns found for removal ({targets or 'none'}) — nothing to drop."
        )
        return df
    return df.drop(existing)


def apply_merge(df: pl.DataFrame, entry: dict, warnings: list[str]) -> pl.DataFrame:
    """Execute an AI 'merge' proposal for exact-duplicate columns: keep first, drop rest."""
    cols = entry.get("target_columns") or []
    if len(cols) < 2:
        warnings.append("Merge suggestion needs at least two columns — skipped.")
        return df
    keep, *drops = cols
    drops = [c for c in drops if c in df.columns and c != keep]
    if not drops:
        warnings.append(f"Duplicate columns for merge already removed — nothing to do.")
        return df
    return df.drop(drops)


def _columns_changed(before: pl.DataFrame, after: pl.DataFrame) -> bool:
    """Detect column renames/drops AND schema changes (e.g. date coercion
    keeps the name but changes the dtype — a mutation that must still
    trigger the downstream refresh cascade)."""
    return before.columns != after.columns or before.schema != after.schema


# ═══════════════════════════════════════════════════════════════════════════
# Decision → execution
# ═══════════════════════════════════════════════════════════════════════════

def execute_mutation(
    df: pl.DataFrame,
    entry: dict,
    approved: bool | None,
    override_to: str | None = None,
    warnings: list[str] | None = None,
) -> tuple[pl.DataFrame, dict]:
    """
    Apply the user's decision to the dataframe and return the updated entry.

    Returns ``(df, updated_entry)``. The entry is a *new* dict — callers must
    write it back into the manifest. ``warnings`` collects non-fatal outcomes
    (collisions, already-applied ops) so the API can surface them honestly.
    """
    warnings = warnings if warnings is not None else []
    updated = dict(entry)
    updated["state"] = entry_state(entry)
    now = _now_iso()

    # ── Structural fixers (drop_row / shift_header) — settled at ingest ──
    # These were applied silently and cannot be undone from the parquet
    # alone (the rows/headers are already gone). Any decision is a no-op
    # with an honest warning — never a silent rename fallback.
    if entry.get("action_type") in ("drop_row", "shift_header"):
        warnings.append(
            "This change was applied automatically during ingest and cannot "
            "be reverted from the parquet alone. Re-process the dataset "
            "from the original file to restore it."
        )
        updated["approved"] = True
        return df, updated

    # ── Reset to pending (approved=None) ─────────────────────────────────
    if approved is None:
        if updated["state"] == "applied":
            # Data already mutated — resetting the flag cannot undo it.
            warnings.append(
                "This change has already been applied to the dataset; resetting "
                "the review flag does not alter the data."
            )
        updated["approved"] = None
        updated["state"] = "proposed" if is_ai_proposal(entry) else "applied_silently"
        return df, updated

    # ── AI proposals (merge / remove) ────────────────────────────────────
    if is_ai_proposal(entry):
        if updated["state"] == "applied":
            if approved:
                warnings.append("This change is already applied — nothing to do.")
            else:
                raise ValueError(
                    "This change has already been applied to the dataset and "
                    "cannot be un-applied from the parquet alone. Re-process "
                    "the dataset from the original file to restore it."
                )
            updated["approved"] = True
            return df, updated

        if approved:
            action_type = entry.get("action_type")
            if action_type == "remove":
                df = apply_drop(df, entry, warnings)
            elif action_type == "type_coercion":
                df = apply_date_coercion(df, entry, warnings)
            elif action_type == "merge_values":
                df = apply_merge_values(df, entry, warnings)
            elif action_type == "unpivot_columns":
                df = apply_unpivot(df, entry, warnings)
            else:
                df = apply_merge(df, entry, warnings)
            updated["approved"] = True
            updated["state"] = "applied"
        else:
            updated["approved"] = False
            updated["state"] = "rejected"
        updated["reviewed_at"] = now
        return df, updated

    # ── Deterministic renames (and overrides) ────────────────────────────
    prev_state = updated["state"]
    if override_to:
        df = apply_rename(df, entry, override_to, warnings)
        updated["normalized_name"] = override_to
        updated["approved"] = True
        updated["state"] = "applied"
    elif approved is False:
        df = rename_back(df, entry, warnings)
        updated["approved"] = False
        updated["state"] = "reverted"
    elif prev_state == "reverted":
        # Re-applying a reverted rename: rename forward original → normalized
        df = _reapply_rename(df, entry, warnings)
        updated["approved"] = True
        updated["state"] = "confirmed"
    else:
        updated["approved"] = True
        updated["state"] = "confirmed"

    updated["reviewed_at"] = now
    return df, updated


# ═══════════════════════════════════════════════════════════════════════════
# Downstream refresh cascade (background task)
# ═══════════════════════════════════════════════════════════════════════════

def _atomic_write_parquet(df: pl.DataFrame, parquet_path: str) -> None:
    """Write parquet atomically (tmp file + os.replace) so a crash never
    leaves a truncated file that downstream readers would happily load."""
    tmp_path = f"{parquet_path}.tmp"
    df.write_parquet(tmp_path, compression="zstd")
    try:
        Path(tmp_path).replace(parquet_path)
    except OSError:
        # replace failed — clean up the tmp file and re-raise
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _load_active_dataframe(doc: dict) -> tuple[pl.DataFrame, str, str]:
    """
    Load the *active* dataframe for mutation.

    Prefers the processed parquet (fast, reflects all pipeline stages);
    falls back to the raw uploaded file only if the parquet is missing.

    Returns ``(df, data_path, file_type)``. Raises ``ValueError`` when no
    file is available.
    """
    parquet_path = doc.get("parquet_path")
    file_path = doc.get("file_path")

    if parquet_path and Path(parquet_path).exists():
        return pl.read_parquet(parquet_path), str(parquet_path), "parquet"

    if file_path and Path(file_path).exists():
        from services.pipeline.load import load_dataset

        df, meta = load_dataset(str(file_path))
        file_type = meta.get("file_type") or Path(file_path).suffix.lstrip(".").lower()
        return df, str(file_path), file_type

    raise ValueError(
        "Dataset file not found on disk — cannot apply the cleaning action. "
        "The dataset may need to be re-uploaded or re-processed."
    )


async def _refresh_downstream(
    dataset_id: str,
    user_id: str,
    workspace_id: str,
    df: pl.DataFrame,
    doc: dict,
    file_type: str,
    data_path: str,
    manifest: list[dict[str, Any]],
) -> None:
    """
    Background cascade after a data mutation:

      1. Atomic parquet rewrite
      2. Deterministic re-profile (no LLM) + rebuild column metadata
      3. Update uploads doc (metadata, counts, domain, manifest)
      4. Refresh dataset_profiles / dataset_intelligence collections
      5. Re-index RAG chunks (MongoDB + FAISS + BM25) from fresh metadata
      6. Invalidate dataframe / insights / dashboard caches
      7. Release the mutation_lock and record mutation_status
    """
    db = get_database()
    mutation_warnings: list[str] = []
    try:
        # ── 1. Atomic parquet write ─────────────────────────────────────
        if data_path.endswith(".parquet"):
            _atomic_write_parquet(df, data_path)
            logger.info("[Mutation] Parquet rewritten for %s", dataset_id[:8])
        else:
            # Fallback path loaded from the raw file — write a parquet
            # alongside it so downstream readers keep using the fast path.
            fallback_parquet = data_path.rsplit(".", 1)[0] + ".parquet"
            _atomic_write_parquet(df, fallback_parquet)
            data_path = fallback_parquet
            logger.info("[Mutation] Parquet created for %s (was raw-only)", dataset_id[:8])

        # ── 2. Deterministic re-profile ─────────────────────────────────
        from services.profiling.engine import profiling_engine
        from services.intelligence.engine import intelligence_engine
        from services.pipeline.clean import calculate_quality_metrics
        from services.pipeline.helpers import convert_types_for_json, extract_sample_rows
        from services.pipeline.process import (
            _build_domain_info,
            _unified_intelligence_to_dict,
            _unified_profile_to_dict,
        )

        profiling = profiling_engine.run(df, file_type=file_type)
        intelligence = intelligence_engine.run(profiling, df=df)
        column_metadata = profiling.column_metadata_list()
        sample_rows = extract_sample_rows(df, n=5)
        data_quality = calculate_quality_metrics(
            column_metadata, len(df), 0, deduplication_applied=False
        )
        domain_info = _build_domain_info(profiling, intelligence)

        metadata = {
            "dataset_overview": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "original_rows": doc.get("metadata", {})
                .get("dataset_overview", {})
                .get("original_rows", len(df)),
                "file_type": file_type,
            },
            "column_metadata": column_metadata,
            "domain_intelligence": domain_info,
            "data_quality": data_quality,
            "sample_data": sample_rows[:3],
            "processing_info": {
                "processed_at": _now_iso(),
                "pipeline_version": "3.1-separated",
                "note": "refresh after cleaning mutation",
            },
        }
        sanitized_metadata = convert_types_for_json(metadata)

        # ── 3. Update uploads doc ───────────────────────────────────────
        await db.uploads.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "metadata": sanitized_metadata,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "domain": domain_info["domain"],
                    "domain_confidence": domain_info["confidence"],
                    "cleaning_manifest": manifest,
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                }
            },
        )

        # ── 4. Refresh profile + intelligence collections ───────────────
        profile_dict = _unified_profile_to_dict(profiling)
        intel_dict = _unified_intelligence_to_dict(intelligence)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if profile_dict:
            await db.dataset_profiles.update_one(
                {"dataset_id": dataset_id},
                {
                    "$set": {
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                        "profile": profile_dict,
                        "pipeline_version": "3.1-separated",
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
        if intel_dict:
            await db.dataset_intelligence.update_one(
                {"dataset_id": dataset_id},
                {
                    "$set": {
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "workspace_id": workspace_id,
                        "intelligence": intel_dict,
                        "pipeline_version": "3.1-separated",
                        "updated_at": now,
                    }
                },
                upsert=True,
            )

        # ── 5. Re-index RAG chunks (delete → rebuild → BM25) ────────────
        try:
            from services.datasets.enhanced_dataset_service import enhanced_dataset_service

            await enhanced_dataset_service.auto_index_dataset_to_vector_db(dataset_id, user_id)
            logger.info("[Mutation] RAG chunks re-indexed for %s", dataset_id[:8])
        except Exception as e:
            mutation_warnings.append(f"RAG index refresh failed: {str(e)[:200]}")
            logger.warning("[Mutation] RAG re-index failed for %s: %s", dataset_id[:8], e)

        # ── 6. Cache invalidation (df cache + insights + dashboards) ────
        try:
            from services.cache.cache_service import cache_service

            await cache_service.invalidate_dataset(dataset_id)
        except Exception as e:
            logger.debug("[Mutation] df cache invalidation skipped: %s", e)
        try:
            from services.cache.insights_cache_service import insights_cache_service

            await insights_cache_service.invalidate(dataset_id, user_id)
        except Exception as e:
            logger.debug("[Mutation] insights cache invalidation skipped: %s", e)
        try:
            from services.cache.dashboard_cache_service import dashboard_cache_service

            await dashboard_cache_service.invalidate_cache(dataset_id, user_id)
        except Exception as e:
            logger.debug("[Mutation] dashboard cache invalidation skipped: %s", e)

        await db.uploads.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "mutation_status": "ok",
                    "mutation_error": None,
                    "mutation_warnings": mutation_warnings,
                    "mutation_finished_at": _now_iso(),
                }
            },
        )
        logger.info("[Mutation] Downstream refresh complete for %s", dataset_id[:8])

    except Exception as e:
        logger.error(
            "[Mutation] Downstream refresh FAILED for %s: %s",
            dataset_id[:8],
            e,
            exc_info=True,
        )
        try:
            await db.uploads.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "mutation_status": "error",
                        "mutation_error": str(e)[:500],
                        "mutation_finished_at": _now_iso(),
                    }
                },
            )
        except Exception:
            pass
    finally:
        try:
            await db.uploads.update_one(
                {"_id": dataset_id}, {"$unset": {"mutation_lock": ""}}
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# Orchestrators (single + bulk)
# ═══════════════════════════════════════════════════════════════════════════

async def _execute_under_lock(
    dataset_id: str,
    user_id: str,
    workspace_id: str,
    actions: list[tuple[int, bool | None, str | None]],
) -> tuple[list[dict[str, Any]], bool, list[str], list[int]]:
    """
    Shared execution path: CAS lock → load → apply each decision → save
    manifest → enqueue the downstream refresh (or release the lock when
    nothing changed).

    ``actions`` is a list of ``(action_index, approved, override_to)``.

    Returns ``(manifest, changed_any, warnings, processed_indices)``.
    """
    db = get_database()
    doc = await db.uploads.find_one({"_id": dataset_id})
    if not doc:
        raise ValueError("Dataset not found")

    status = doc.get("processing_status")
    if status in ("pending", "queued", "running"):
        raise ValueError(
            "Dataset is still processing — cleaning actions are unavailable "
            "until it finishes."
        )

    manifest = doc.get("cleaning_manifest") or []
    if not manifest:
        manifest = doc.get("metadata", {}).get("cleaning_manifest") or []
    if not manifest:
        raise ValueError("No cleaning manifest found for this dataset")

    # Validate indices before acquiring the lock
    indices = [idx for idx, _, _ in actions]
    for idx in indices:
        if not isinstance(idx, int) or not (0 <= idx < len(manifest)):
            raise ValueError(f"action_index {idx} out of range")

    # ── CAS mutation lock ────────────────────────────────────────────────
    lock_result = await db.uploads.update_one(
        {"_id": dataset_id, "mutation_lock": {"$exists": False}},
        {"$set": {"mutation_lock": {"user_id": user_id, "started_at": _now_iso()}}},
    )
    if lock_result.modified_count == 0:
        raise ValueError(
            "Another cleaning operation is already running for this dataset. "
            "Try again shortly."
        )

    warnings: list[str] = []
    changed_any = False
    processed_indices: list[int] = []

    try:
        df, data_path, file_type = _load_active_dataframe(doc)

        for idx, approved, override_to in actions:
            entry = manifest[idx]
            new_df, updated = execute_mutation(df, entry, approved, override_to, warnings)
            manifest[idx] = updated
            if _columns_changed(df, new_df):
                changed_any = True
            df = new_df
            processed_indices.append(idx)

        await db.uploads.update_one(
            {"_id": dataset_id}, {"$set": {"cleaning_manifest": manifest}}
        )

        if changed_any:
            await db.uploads.update_one(
                {"_id": dataset_id},
                {"$set": {"mutation_status": "running", "mutation_error": None}},
            )
            # Lock is released by _refresh_downstream when it finishes.
            asyncio.ensure_future(
                _refresh_downstream(
                    dataset_id,
                    user_id,
                    workspace_id,
                    df,
                    doc,
                    file_type,
                    data_path,
                    manifest,
                )
            )
        else:
            # No data change — nothing to refresh; release the lock now.
            await db.uploads.update_one(
                {"_id": dataset_id},
                {
                    "$set": {"mutation_status": "ok", "mutation_error": None},
                    "$unset": {"mutation_lock": ""},
                },
            )

        return manifest, changed_any, warnings, processed_indices

    except Exception:
        # Release the lock on any failure so the dataset isn't stuck.
        try:
            await db.uploads.update_one(
                {"_id": dataset_id}, {"$unset": {"mutation_lock": ""}}
            )
        except Exception:
            pass
        raise


async def run_single_mutation(
    dataset_id: str,
    user_id: str,
    workspace_id: str,
    action_index: int,
    approved: bool | None,
    override_to: str | None = None,
) -> tuple[list[dict[str, Any]], bool, list[str], str]:
    """
    Approve/reject/reset a single manifest action. Returns
    ``(manifest, changed, warnings, mutation_status)``.

    Raises ``ValueError`` for invalid indices, locked datasets, or
    un-reversible destructive ops.
    """
    # Validate override through mechanical rules before anything else
    if override_to is not None:
        if not isinstance(override_to, str) or not override_to.strip():
            raise ValueError("override_to must be a non-empty string")
        from services.pipeline.normalize import apply_mechanical_rules

        safe_name, _ = apply_mechanical_rules(override_to.strip(), 0)
        override_to = safe_name

    manifest, changed, warnings, _ = await _execute_under_lock(
        dataset_id,
        user_id,
        workspace_id,
        [(action_index, approved, override_to)],
    )
    mutation_status = "running" if changed else "ok"
    return manifest, changed, warnings, mutation_status


async def run_bulk_mutation(
    dataset_id: str,
    user_id: str,
    workspace_id: str,
    indices: list[int] | None,
    approved: bool | None,
) -> tuple[list[dict[str, Any]], bool, list[str], list[int], str]:
    """
    Bulk-approve/reject/reset manifest actions (one lock, one refresh).

    ``indices`` limits the operation; when None, all *pending* entries are
    affected (mirrors the legacy endpoint). Returns
    ``(manifest, changed, warnings, processed_indices, mutation_status)``.
    """
    db = get_database()
    doc = await db.uploads.find_one({"_id": dataset_id})
    if not doc:
        raise ValueError("Dataset not found")

    manifest = doc.get("cleaning_manifest") or []
    if not manifest:
        manifest = doc.get("metadata", {}).get("cleaning_manifest") or []
    if not manifest:
        raise ValueError("No cleaning manifest found for this dataset")

    if indices is None:
        indices = [i for i, a in enumerate(manifest) if a.get("approved") is None]
    else:
        indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(manifest)]

    if not indices:
        return manifest, False, ["No pending cleaning actions to update."], [], "ok"

    actions = [(idx, approved, None) for idx in indices]
    manifest, changed, warnings, processed = await _execute_under_lock(
        dataset_id, user_id, workspace_id, actions
    )
    mutation_status = "running" if changed else "ok"
    return manifest, changed, warnings, processed, mutation_status


__all__ = [
    "run_single_mutation",
    "run_bulk_mutation",
    "entry_state",
    "is_ai_proposal",
    "execute_mutation",
]
