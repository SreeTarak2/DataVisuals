"""
Dataset Processing Pipeline — Tier 1 (Lean Upload)
====================================================

Converts a raw dataset file (CSV/XLSX/JSON/Parquet) into an analyzed,
enriched dataset document.

**Design: Only what's essential for upload.**

Tier 1 stages run on every upload and complete in <5 seconds:
  1. Load + Clean      — Polars I/O, deduplication, Parquet cache
  2. Unified Profiling — Deterministic stats + semantic roles (no LLM)
  3. Domain Enrichment — 1 lightweight LLM call for domain context
  4. Save + Vector     — MongoDB write + FAISS indexing

**Everything else is deferred to on-demand (Tier 2 / Tier 3).**
See ``services/pipeline/on_demand.py`` for lazy computation wrappers.

This runs as a background task (via ``asyncio.create_task``).
Progress is tracked in MongoDB so the API can poll the dataset's
``processing_status`` field directly.

Originally this pipeline pre-computed KPIs, charts, QUIS subspace
analysis, dashboard design, deep reasoning, entity discovery, and more
ALL at upload time — before the user had asked a single question. That
approach wasted compute and delayed dataset availability.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import polars as pl
from pymongo import MongoClient

from core.config import settings
from db.tenant_guard import (
    TenantIsolationError,
    assert_doc_workspace,
    resolve_workspace_id,
)
from services.profiling.engine import profiling_engine
from services.intelligence.engine import intelligence_engine
from services.intelligence.domain_detector_llm import llm_domain_detector
from services.datasets.faiss_vector_service import faiss_vector_service
from services.pipeline.clean import calculate_quality_metrics, clean_dataframe
from services.pipeline.load import coerce_numeric_columns, load_dataset
from services.pipeline.helpers import convert_types_for_json, extract_sample_rows
from services.pipeline.normalize import normalize_column_names
from services.pipeline.structural_fixers import apply_structural_fixers
from services.pipeline.tracker import PipelineTracker
from services.cleaning.column_suggester import suggest_cleaning_actions
from services.intelligence.dataset_memo import DatasetMemo, DatasetMemoCache
from services.storage.s3_service import s3_storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ── Progress map for the frontend polling endpoint ──────────────────────────
# Only Tier 1 stages. The progress bar reaches 100% in seconds.
_PROGRESS_MAP: dict[str, int] = {
    "loading": 5,
    "cleaning": 15,
    "normalizing": 25,
    "profiling": 50,
    "column_suggestions": 55,
    "domain_detection": 75,
    "saving": 85,
    "vector_indexing": 95,
    "completed": 100,
}

# Stage 3 (metadata scan) was removed — column_metadata is derived from
# RawProfilingResult.column_metadata_list() after Stage 4 instead,
# eliminating one full column scan per pipeline run.

# ── Sync MongoDB client (shared across stages) ──────────────────────────────
_client: MongoClient | None = None


def _get_db():
    """Get or create a shared sync MongoDB client for the pipeline."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URL, maxPoolSize=5)
    return _client[settings.DATABASE_NAME]


# ═══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE — Tier 1
# ═══════════════════════════════════════════════════════════════════════════


async def _resolve_effective_workspace_id(workspace_id: str | None, user_id: str) -> str:
    """
    Resolve the workspace this pipeline should tag writes with.

    Uses the explicit ``workspace_id`` when provided; otherwise resolves the
    user's personal workspace (the canonical tag the backfill migration wrote
    on legacy documents). Falls back to ``user_id`` only if resolution fails.
    """
    try:
        from services.workspace import workspace_service

        return await workspace_service.resolve_effective_workspace_id(workspace_id, user_id)
    except Exception as e:
        logger.warning(
            "[TenantGuard] Workspace resolution failed for %s — falling back to user_id: %s",
            user_id[:8],
            e,
        )
        return resolve_workspace_id(None, user_id)


async def process_dataset(
    dataset_id: str,
    file_path: str,
    user_id: str = "unknown",
    workspace_id: str | None = None,
) -> dict:
    """
    Process a dataset: load → clean → metadata → profile → save → index.

    Runs as a background task. Only Tier 1 stages — completes in <5 seconds.

    Idempotency guarantees:
    - If status is already ``"completed"``, returns early (no-op).
    - Uses a compare-and-swap (``pending → running``) so a concurrent call
      for the same dataset_id races and only one proceeds.

    Tenant isolation:
    - Resolves the effective workspace from ``workspace_id`` (falling back to
      the user's personal workspace id for legacy callers).
    - Refuses to process a dataset document that belongs to another workspace.
    - Every MongoDB write this pipeline performs is tenant-tagged with
      ``workspace_id`` so split collections stay workspace-scoped.

    Args:
        dataset_id: MongoDB _id of the dataset.
        file_path:  Absolute path to the uploaded file.
        user_id:    Owner of the dataset.
        workspace_id: The tenant (workspace) this dataset belongs to.
                      Defaults to ``user_id`` (personal workspace) when omitted.

    Returns:
        dict with processing result summary.
    """
    wid = await _resolve_effective_workspace_id(workspace_id, user_id)

    async def _notify(status: str, body: str = "", error: str = ""):
        """Fire-and-forget job notification for this dataset."""
        try:
            from services.notifications.service import (
                CTA_OPEN_DASHBOARD,
                CTA_RETRY_PROCESSING,
                TYPE_DATASET_FAILED,
                TYPE_DATASET_READY,
                create_notification,
            )

            notif_type = TYPE_DATASET_READY if status == "completed" else TYPE_DATASET_FAILED
            if status == "completed":
                title = f"✅ Dataset ready: {_dataset_display_name}"
                body = body or (
                    f"Your dataset \"{_dataset_display_name}\" has finished processing "
                    "and is ready to explore."
                )
                cta = {"text": "Open dashboard", "action": CTA_OPEN_DASHBOARD}
            else:
                title = f"⚠️ Processing failed: {_dataset_display_name}"
                body = body or (
                    f"We couldn't finish processing \"{_dataset_display_name}\". "
                    f"{error or 'Please retry or re-upload the file.'}"
                )
                cta = {"text": "Retry", "action": CTA_RETRY_PROCESSING}

            await create_notification(
                user_id=user_id,
                workspace_id=wid,
                notif_type=notif_type,
                title=title[:200],
                body=body[:500],
                cta=cta,
                dataset_id=dataset_id,
                dataset_name=_dataset_display_name,
            )

            # Terminal progress event so open clients drop this job from the
            # processing indicator instantly (fire-and-forget).
            try:
                from services.notifications.hub import notification_hub

                notification_hub.schedule_push(
                    user_id,
                    {
                        "type": "processing_update",
                        "dataset_id": str(dataset_id),
                        "status": status,
                        "progress": 100 if status == "completed" else 0,
                        "stage_label": (
                            "Completed" if status == "completed" else "Failed"
                        ),
                    },
                )
            except Exception as push_exc:
                logger.debug(
                    f"[Notifications] Processing push failed for {dataset_id[:8]}: {push_exc}"
                )
        except Exception as e:
            logger.warning(f"[Notifications] Job notification failed for {dataset_id[:8]}: {e}")

    logger.info("╔══════════════════════════════════════════════════════╗")
    logger.info(f"║ TIER 1 STARTED: {dataset_id:<35} ║")
    logger.info("╚══════════════════════════════════════════════════════╝")

    db = _get_db()
    datasets_collection = db.uploads

    # ── Idempotency guard (compare-and-swap) ────────────────────────────
    # Atomically claim the dataset for processing: only the first caller
    # that successfully transitions "pending"/"queued"/"failed" → "running"
    # proceeds.
    existing = datasets_collection.find_one(
        {"_id": dataset_id},
        {
            "processing_status": 1,
            "workspace_id": 1,
            "user_id": 1,
            "size_limit_mb": 1,
            "name": 1,
            "original_filename": 1,
        },
    )
    if existing is None:
        logger.error(
            "[Idempotency] Dataset %s not found in DB — cannot process",
            dataset_id[:8],
        )
        return {"status": "failed", "dataset_id": dataset_id, "error": "dataset document not found"}

    # Name used in job notifications (falls back to the uploaded filename)
    _dataset_display_name = (
        existing.get("name")
        or existing.get("original_filename")
        or "your dataset"
    )

    # ── Tenant guard ──────────────────────────────────────────────────
    # Refuse to process a dataset that belongs to another workspace, even if
    # a caller supplies a dataset_id directly (defense in depth).
    try:
        assert_doc_workspace(existing, wid, user_id)
    except TenantIsolationError as e:
        logger.error(
            "[TenantGuard] Refusing to process dataset %s: %s",
            dataset_id[:8],
            e,
        )
        return {"status": "failed", "dataset_id": dataset_id, "error": str(e)}

    current_status = existing.get("processing_status", "")
    if current_status == "completed":
        logger.info(
            "[Idempotency] Dataset %s already processed (status=completed) — skipping",
            dataset_id[:8],
        )
        # Re-read full metadata for the return value
        completed_doc = datasets_collection.find_one({"_id": dataset_id})
        if completed_doc:
            meta = completed_doc.get("metadata", {})
            return {
                "status": "success",
                "progress": 100,
                "dataset_id": dataset_id,
                "rows": completed_doc.get("row_count", 0),
                "columns": completed_doc.get("column_count", 0),
                "domain": completed_doc.get("domain", "general"),
                "quality": meta.get("data_quality", {}).get("completeness", 0),
            }
        return {"status": "success", "dataset_id": dataset_id, "note": "already processed"}

    # Atomically claim ownership: eligible statuses include "pending" (first run),
    # "queued", and "failed" (retry/reprocess). If the reprocess endpoint resets
    # status to "pending", those are covered too.
    claim_result = datasets_collection.update_one(
        {
            "_id": dataset_id,
            "processing_status": {"$in": ["pending", "queued", "failed"]},
        },
        {
            "$set": {
                "processing_status": "running",
                "processing_started_at": datetime.now(timezone.utc)
                .replace(tzinfo=None)
                .isoformat(),
            }
        },
    )
    if claim_result.modified_count == 0:
        # Someone else is already processing — return early without error
        logger.info(
            "[Idempotency] Dataset %s is already being processed by another task — won't compete",
            dataset_id[:8],
        )
        return {
            "status": "success",
            "dataset_id": dataset_id,
            "note": "already being processed (concurrent call)",
        }

    tracker = PipelineTracker(
        dataset_id,
        user_id,
        db,
        progress_map=_PROGRESS_MAP,
        workspace_id=wid,
    )

    # Shared variables — set by closure in _run_pipeline_stages()
    df_clean: pl.DataFrame | None = None
    column_metadata: list[dict] = []
    unified_profiling = None
    unified_intelligence = None
    sanitized_metadata: dict = {}
    sample_rows: list[dict] = []
    parquet_path: str | None = None
    s3_parquet_key: str | None = None
    original_rows = 0
    duplicates_removed = 0
    load_metadata: dict = {}
    null_sentinel_audit: dict[str, dict[str, int]] = {}
    coercion_audit: dict[str, dict[str, Any]] = {}
    cleaning_manifest: list[dict[str, Any]] = []

    async def _run_pipeline_stages() -> dict:
        """Execute all Tier 1 pipeline stages.

        Extracted as an inner coroutine so that ``asyncio.wait_for`` can
        enforce a hard timeout on the entire processing body. All shared
        variables are captured by closure from the outer scope.
        """
        # Allow Python to rebind closure variables
        nonlocal df_clean, column_metadata, unified_profiling
        nonlocal unified_intelligence, sanitized_metadata, sample_rows
        nonlocal parquet_path, s3_parquet_key, original_rows, duplicates_removed, load_metadata
        nonlocal null_sentinel_audit, coercion_audit, cleaning_manifest

        # ── Stage 1: Load ────────────────────────────────────────────────
        async with tracker.stage("loading", "Loading Dataset"):
            # Memory pressure guard: reject files that exceed the max size.
            # CSV→Polars can expand 5-10× in memory, so we check file size
            # before any Polars I/O to prevent OOM.
            #
            # The effective limit is min(tier limit, pipeline ceiling) and is
            # stored on the dataset doc at upload time (``size_limit_mb``) so
            # this background task doesn't need to re-resolve the user's tier.
            # Legacy docs without the field fall back to the server ceiling.
            stored_limit_mb = existing.get("size_limit_mb")
            limit_mb = stored_limit_mb or settings.PIPELINE_MAX_FILE_SIZE_MB
            max_size_bytes = limit_mb * 1024 * 1024
            try:
                file_size = os.path.getsize(file_path)
            except FileNotFoundError:
                raise FileNotFoundError(f"Dataset file not found: {file_path}")
            except PermissionError:
                raise PermissionError(f"Permission denied reading dataset: {file_path}")

            size_mb = file_size / (1024 * 1024)

            if file_size > max_size_bytes:
                raise ValueError(
                    f"File size {size_mb:.1f}MB exceeds pipeline limit of "
                    f"{limit_mb}MB.  Large files cause memory pressure "
                    f"(CSV→Polars can expand 5-10×). "
                    f"Split the file or increase "
                    f"PIPELINE_MAX_FILE_SIZE_MB in environment config."
                )

            logger.info(
                "  File size: %.1f MB (limit: %d MB)",
                size_mb,
                limit_mb,
            )

            df, load_metadata = load_dataset(file_path)

            if df.is_empty():
                raise ValueError("Dataset is empty")
            if len(df.columns) == 0:
                raise ValueError("Dataset has no columns")

            # ── Structural fixers (silent, deterministic, logged) ──────
            # Title-row detection + TOTAL-row removal run before coercion
            # so every downstream read (parquet, DuckDB, chat) sees clean
            # data. Entries are marked applied/settled in the manifest.
            # A fixer failure must never fail the upload — fall back to the
            # un-fixed dataframe and continue.
            structural_entries = []
            try:
                df, structural_entries = apply_structural_fixers(df)
                if structural_entries:
                    logger.info(
                        "  Structural fixers applied: %d (header/total-row)",
                        len(structural_entries),
                    )
            except Exception as e:
                logger.warning("  Structural fixers skipped (%s) — continuing", e)

            df, coerce_cols, coercion_audit = coerce_numeric_columns(
                df,
                track_failures=True,
            )

            original_rows = len(df)
            schema = df.schema

            logger.info(f"  Loaded: {original_rows:,} rows × {len(schema):,} cols")

            # ── Immediate Parquet conversion ─────────────────────────
            # DuckDB reads Parquet 5-10x faster than CSV. Converting at
            # load time makes all downstream reads (SQL, DuckDB executor,
            # sample cache) use the fast Parquet path.
            #
            # The parquet_path is saved to MongoDB immediately so the
            # DuckDB executor can use it even while the pipeline is still
            # running (e.g., for the first AI chat query).
            parquet_path = file_path.rsplit(".", 1)[0] + ".parquet"
            try:
                df.write_parquet(parquet_path, compression="zstd")
                logger.info(f"  Parquet saved: {parquet_path}")

                # Upload to S3 if enabled
                # NOTE: S3 upload runs in a thread executor to avoid
                # blocking the asyncio event loop.  s3fs.S3FileSystem.put()
                # is a synchronous network call that would otherwise hang
                # the entire pipeline while waiting on network I/O.
                if settings.S3_ENABLED:
                    try:
                        s3_parquet_key = s3_storage.generate_parquet_key(
                            user_id, Path(parquet_path).stem
                        )
                        loop = asyncio.get_running_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                s3_storage.upload_file,
                                parquet_path,
                                s3_parquet_key,
                            ),
                            timeout=30.0,
                        )
                        logger.info("  Parquet uploaded to S3: %s", s3_parquet_key)
                    except asyncio.TimeoutError:
                        logger.warning("  S3 upload timed out after 30s — continuing without S3")
                        s3_parquet_key = None
                    except Exception as s3_err:
                        logger.warning("  S3 upload failed: %s", s3_err)
                        s3_parquet_key = None

                # Save parquet_path to MongoDB immediately (before
                # pipeline completes) so DuckDB executor can use it.
                datasets_collection.update_one(
                    {"_id": dataset_id},
                    {"$set": {"parquet_path": parquet_path}},
                )
                logger.info("  Parquet path saved to MongoDB immediately")
            except Exception as e:
                logger.warning(f"  Parquet conversion failed: {e}")
                parquet_path = None
                s3_parquet_key = None

            df_lazy = df.lazy()

        # ── Stage 2: Clean ───────────────────────────────────────────────
        async with tracker.stage("cleaning", "Cleaning Data"):
            df_clean, null_sentinel_audit = clean_dataframe(
                df_lazy,
                schema,
                deduplicate=False,
                track_sentinels=True,
            )
            cleaned_rows = len(df_clean)
            duplicates_removed = 0  # Dedup is opt-in (not applied by default)
            logger.info("  Deduplication skipped (opt-in — use UI toggle to enable)")

        # ── Stage 3: Column Name Normalization (deterministic, no LLM) ────
        async with tracker.stage("normalizing", "Normalizing Column Names"):
            df_clean, normalized_entries = normalize_column_names(df_clean)
            # Structural fixer entries (applied silently at ingest) come
            # first, then the reviewable rename entries.
            cleaning_manifest = (structural_entries or []) + (normalized_entries or [])
            if cleaning_manifest:
                logger.info(
                    "  Manifest: %d structural + %d normalized entries",
                    len(structural_entries or []),
                    len(normalized_entries or []),
                )
                # Overwrite parquet with renamed columns
                if parquet_path:
                    try:
                        df_clean.write_parquet(parquet_path, compression="zstd")
                        logger.info("  Updated Parquet with normalized column names")
                    except Exception as e:
                        logger.warning(f"  Parquet update after normalization failed: {e}")

        # ── Stage 5: Unified Profiling (deterministic, no LLM) ──────────
        async with tracker.stage("profiling", "Profiling Data"):
            try:
                unified_profiling = profiling_engine.run(
                    df_clean,
                    file_type=file_path.split(".")[-1].lower(),
                )
                # Try to attach filename from the dataset doc
                try:
                    doc = datasets_collection.find_one({"_id": dataset_id}, {"name": 1})
                    if doc and doc.get("name"):
                        unified_profiling.dataset.file_name = doc["name"]
                except Exception:
                    pass
                unified_profiling.processed_at = (
                    datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                )

                # Intelligence layer on top of profiling facts
                unified_intelligence = intelligence_engine.run(unified_profiling, df=df_clean)

                logger.info(
                    "  Unified: %d cols, %d entities, %d domain candidates",
                    len(unified_profiling.columns),
                    len(unified_intelligence.entities),
                    len(unified_intelligence.domain.candidates),
                )

                # ── Semantic assumptions: deterministic pass (act-first) ──
                # Every deterministic hierarchy becomes a VALIDATED ontology
                # assumption, persisted for drill-down/cross-filter consumption.
                # No LLM, no tokens — just the curated pattern + cardinality
                # verification already computed above. LLM proposals are
                # deferred to the on-demand regenerate endpoint (Tier 1 stays
                # <5s).
                try:
                    from services.intelligence.hierarchy_inference_v2 import (
                        run_deterministic_pass,
                    )
                    from services.semantic.assumption_store import assumption_store

                    det_assumptions = run_deterministic_pass(
                        unified_profiling,
                        df_clean,
                        dataset_id,
                        wid,
                        user_id=user_id,
                    )
                    for _a in det_assumptions:
                        await assumption_store.upsert(_a)
                    if det_assumptions:
                        logger.info(
                            "  Assumptions: %d deterministic hierarchies persisted",
                            len(det_assumptions),
                        )
                except Exception as _aexc:
                    logger.debug("  Assumption store write skipped (non-critical): %s", _aexc)
            except Exception as e:
                logger.warning(f"  Unified profiling failed: {e}")
                unified_profiling = None
                unified_intelligence = None

            # ── Derive column_metadata from profiling (replaces Stage 3) ─
            if unified_profiling:
                try:
                    column_metadata = unified_profiling.column_metadata_list()
                    logger.info(
                        "  Metadata derived from profile: %d columns",
                        len(column_metadata),
                    )
                except Exception as e:
                    logger.warning(f"  Metadata derivation failed: {e}")
                    column_metadata = []
            else:
                # Fallback: minimal metadata from DataFrame directly
                logger.warning("  Profiling failed — building fallback metadata from DataFrame")
                column_metadata = []
                for col in df_clean.columns:
                    col_data = df_clean[col]
                    column_metadata.append(
                        {
                            "name": col,
                            "type": str(col_data.dtype),
                            "null_count": col_data.null_count(),
                            "null_percentage": round(col_data.null_count() / len(df_clean) * 100, 2)
                            if len(df_clean) > 0
                            else 0,
                            "unique_count": col_data.n_unique(),
                        }
                    )

            # Extract sample rows (available from df_clean regardless of profiling)
            sample_rows = extract_sample_rows(df_clean, n=5)

        # ── Stage 6: AI-Assisted Column Suggestions (Stage 1.6) ─────────
        async with tracker.stage("column_suggestions", "Analyzing Column Quality"):
            try:
                ai_suggestions = await suggest_cleaning_actions(
                    df=df_clean,
                    profiling_result=unified_profiling,
                    existing_manifest=cleaning_manifest,
                    column_metadata=column_metadata,
                    user_id=user_id,
                )
                if ai_suggestions:
                    cleaning_manifest = (cleaning_manifest or []) + ai_suggestions
                    logger.info(
                        "  AI suggestions: %d added to cleaning manifest",
                        len(ai_suggestions),
                    )
            except Exception as e:
                logger.warning(
                    "  AI column suggestions skipped (non-critical): %s", e
                )

        # ── Stage 7: Domain Enrichment (1 lightweight LLM call) ─────────
        async with tracker.stage("domain_detection", "Detecting Domain"):
            # Build domain_info from unified profiling results
            domain_info = _build_domain_info(unified_profiling, unified_intelligence)

            # Initialize DatasetMemo for downstream use
            pipeline_memo = DatasetMemo(
                dataset_id=dataset_id,
                user_id=user_id,
                row_count=len(df_clean) if df_clean is not None else 0,
                column_count=len(df_clean.columns) if df_clean is not None else 0,
                domain_name=domain_info.get("domain", "general"),
                domain_confidence=domain_info.get("confidence", 0.5),
                domain_method=domain_info.get("method", "deterministic"),
            )
            DatasetMemoCache.set(dataset_id, pipeline_memo)

            # Optional LLM enrichment (runs only if deterministic was successful)
            if unified_profiling and unified_intelligence:
                try:
                    llm_result = await llm_domain_detector.detect(unified_profiling, df_clean)
                    if llm_result.llm_verdict:
                        unified_intelligence.domain.llm_verdict = llm_result.llm_verdict
                        if llm_result.top_candidate:
                            unified_intelligence.domain.top_candidate = llm_result.top_candidate
                            unified_intelligence.domain.candidates = llm_result.candidates
                            unified_intelligence.domain.method = "llm"
                        logger.info(
                            "  LLM domain: %s (confidence=%.2f)",
                            llm_result.llm_verdict.domain_id,
                            llm_result.llm_verdict.confidence,
                        )

                        # ── Rebuild domain_info with LLM-enriched result ──
                        # The initial _build_domain_info() call at the top of
                        # this stage used the DETERMINISTIC domain. Now that
                        # the LLM verdict has replaced top_candidate, we must
                        # rebuild domain_info so it reflects the LLM's more
                        # accurate classification instead of the deterministic
                        # pattern match (which was wrong for this dataset).
                        domain_info = _build_domain_info(unified_profiling, unified_intelligence)
                        pipeline_memo = DatasetMemo(
                            dataset_id=dataset_id,
                            user_id=user_id,
                            row_count=len(df_clean) if df_clean is not None else 0,
                            column_count=len(df_clean.columns) if df_clean is not None else 0,
                            domain_name=domain_info.get("domain", "general"),
                            domain_confidence=domain_info.get("confidence", 0.5),
                            domain_method=domain_info.get("method", "llm"),
                        )
                        DatasetMemoCache.set(dataset_id, pipeline_memo)

                        logger.info(
                            "  Domain corrected after LLM enrichment: "
                            "%s (confidence=%.2f)",
                            domain_info["domain"],
                            domain_info["confidence"],
                        )
                except Exception as e:
                    logger.debug(f"  LLM domain enrichment skipped: {e}")

            # Data quality snapshot (deterministic, no LLM)
            # Add encoding/delimiter to data_quality for audit trail
            # Attach coercion audit to load_metadata
            if coercion_audit:
                load_metadata["coercion_audit"] = coercion_audit

            encoding_info = {
                "detected_encoding": load_metadata.get("detected_encoding", "utf-8"),
                "detected_encoding_confidence": load_metadata.get(
                    "detected_encoding_confidence", 0.0
                ),
                "detected_delimiter": load_metadata.get("detected_delimiter", ","),
            }

            data_quality = calculate_quality_metrics(
                column_metadata,
                original_rows,
                duplicates_removed,
                deduplication_applied=False,
            )
            # Attach null sentinel audit trail (which sentinel strings were
            # found in which string columns, and how many times each appeared)
            if null_sentinel_audit:
                total_sentinel_cells = sum(sum(c.values()) for c in null_sentinel_audit.values())
                data_quality["null_sentinel_audit"] = null_sentinel_audit
                data_quality["null_sentinel_cells"] = total_sentinel_cells

            data_quality.update(encoding_info)
            logger.info(f"  Quality: {data_quality.get('completeness', 0):.1f}%")

        # ── Stage 6: Save to MongoDB (split document model) ───────────────
        #
        # "unified_profile" and "unified_intelligence" are large and will grow
        # when histograms and distributions are added. Storing them in the
        # uploads document risks the 16MB BSON limit. We store them in
        # separate collections keyed by dataset_id.
        #
        # Legacy datasets (pipeline_version < 3.1) have them embedded in
        # metadata — readers fall back gracefully.
        async with tracker.stage("saving", "Saving Results"):
            # ── Serialize profile + intelligence for separate storage ─────
            profile_dict = (
                _unified_profile_to_dict(unified_profiling) if unified_profiling else None
            )
            intelligence_dict = (
                _unified_intelligence_to_dict(unified_intelligence)
                if unified_intelligence
                else None
            )

            # ── Build lightweight uploads doc (no profile/intelligence) ───
            final_metadata: dict[str, Any] = {
                "dataset_overview": {
                    "total_rows": cleaned_rows,
                    "total_columns": len(df_clean.columns),
                    "original_rows": original_rows,
                    "file_type": file_path.split(".")[-1].lower(),
                },
                "column_metadata": column_metadata,
                "domain_intelligence": domain_info,
                "data_quality": data_quality,
                "sample_data": sample_rows[:3],
                "processing_info": {
                    "processed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    "pipeline_version": "3.1-separated",
                    "note": "Tier 1 — profile and intelligence stored in separate collections.",
                },
            }

            sanitized_metadata = convert_types_for_json(final_metadata)

            # ── Pre-write size check ─────────────────────────────────────
            import json as _json

            doc_size_bytes = len(_json.dumps(sanitized_metadata, default=str))
            doc_size_mb = doc_size_bytes / (1024 * 1024)
            if doc_size_mb > 10:
                logger.warning(
                    f"[SIZE] Uploads doc for {dataset_id[:8]} is {doc_size_mb:.1f}MB — "
                    f"approaching 16MB BSON limit. Consider moving more fields out."
                )
            elif doc_size_mb > 5:
                logger.info(f"[SIZE] Uploads doc for {dataset_id[:8]} is {doc_size_mb:.1f}MB")

            update_fields: dict[str, Any] = {
                "metadata": sanitized_metadata,
                "workspace_id": wid,  # tenant tag — enforced at the DB layer
                "is_processed": True,
                "processing_status": "saving",
                "row_count": cleaned_rows,
                "column_count": len(df_clean.columns),
                "domain": domain_info["domain"],
                "domain_confidence": domain_info["confidence"],
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
            if parquet_path:
                update_fields["parquet_path"] = parquet_path
            if s3_parquet_key:
                update_fields["s3_parquet_key"] = s3_parquet_key
            if cleaning_manifest:
                update_fields["cleaning_manifest"] = cleaning_manifest

            datasets_collection.update_one({"_id": dataset_id}, {"$set": update_fields})

            # ── Write unified_profile to separate collection ─────────────
            if profile_dict:
                try:
                    profile_doc = {
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "workspace_id": wid,
                        "profile": profile_dict,
                        "pipeline_version": "3.1-separated",
                        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    }
                    db.dataset_profiles.update_one(
                        {"dataset_id": dataset_id},
                        {"$set": profile_doc},
                        upsert=True,
                    )
                    logger.info("  Profile → dataset_profiles: OK")
                except Exception as e:
                    logger.error(f"  Profile write failed: {e}")

            # ── Write unified_intelligence to separate collection ────────
            if intelligence_dict:
                try:
                    intel_doc = {
                        "dataset_id": dataset_id,
                        "user_id": user_id,
                        "workspace_id": wid,
                        "intelligence": intelligence_dict,
                        "pipeline_version": "3.1-separated",
                        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    }
                    db.dataset_intelligence.update_one(
                        {"dataset_id": dataset_id},
                        {"$set": intel_doc},
                        upsert=True,
                    )
                    logger.info("  Intelligence → dataset_intelligence: OK")
                except Exception as e:
                    logger.error(f"  Intelligence write failed: {e}")

            logger.info("  Saved to MongoDB")

        # ── Stage 8: Vector Indexing ─────────────────────────────────────
        async with tracker.stage("vector_indexing", "Indexing Vector Database"):
            try:
                await faiss_vector_service.add_dataset_to_vector_db(
                    dataset_id=dataset_id,
                    dataset_metadata=sanitized_metadata,
                    user_id=user_id,
                    workspace_id=wid,
                )
                logger.info("  Vector index: OK")
            except Exception as e:
                logger.error(f"  Vector index failed: {e}")

        # ── Mark completed ──────────────────────────────────────────────
        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "processing_status": "completed",
                    "current_stage_label": "Ready",
                    "processing_progress": 100,
                    "artifact_status.dashboard_design": "ready",
                    "artifact_status.insights_report": "ready",
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                }
            },
        )

        logger.info("╔══════════════════════════════════════════════════════╗")
        logger.info(f"║ TIER 1 COMPLETED: {dataset_id:<33} ║")
        logger.info("╚══════════════════════════════════════════════════════╝")

        # Job notification — user may have closed the browser mid-processing
        try:
            await _notify("completed")
        except Exception:
            pass

        logger.info(
            "[PERF] Tier 1 pipeline complete (%s): %d rows × %d cols → %s%s",
            dataset_id[:8],
            cleaned_rows,
            len(df_clean.columns),
            domain_info["domain"],
            " (LLM enriched)"
            if unified_intelligence and unified_intelligence.domain.method == "llm"
            else "",
        )

        # ── Progressive Learning: check user preferences ────────────────
        # If the user has a cross-dataset preference profile with high
        # confidence, fire background pre-computation for their preferred
        # KPIs and charts so they don't have to wait on first access.
        # The caller's workspace_id is threaded through so preference
        # signals stay scoped to the correct tenant.
        try:
            from services.learning.preference_learner import preference_learner as _learner

            _pref_summary = await _learner.get_user_summary(
                user_id=user_id,
                workspace_id=wid,
            )
            if _pref_summary.overall_confidence > 0.4:
                logger.info(
                    "[Learning] User has %.2f-confidence profile across %d datasets — "
                    "pre-computing preferred items for %s",
                    _pref_summary.overall_confidence,
                    _pref_summary.profile_count,
                    dataset_id[:8],
                )
                # Kick off background pre-computation of KPIs for this dataset
                from services.pipeline.on_demand import ensure_kpis as _ensure_kpis

                asyncio.create_task(_ensure_kpis(dataset_id, user_id))
        except Exception as e:
            logger.debug("[Learning] Preference-guided pre-computation skipped: %s", e)

        return {
            "status": "success",
            "progress": 100,
            "dataset_id": dataset_id,
            "rows": cleaned_rows,
            "columns": len(df_clean.columns),
            "domain": domain_info["domain"],
            "quality": data_quality.get("completeness", 0),
        }

    # ── Execute stages with a size-aware hard timeout ────────────────────
    # Small files keep the fast fail-fast PIPELINE_TIMEOUT; large files get
    # proportional headroom (file_size_mb * PIPELINE_TIMEOUT_PER_MB, capped at
    # PIPELINE_TIMEOUT_MAX). Without this, a >300MB CSV would be killed by the
    # fixed 120s default mid-pipeline even though it's processing fine.
    try:
        try:
            _size_bytes = os.path.getsize(file_path)
        except OSError:
            _size_bytes = 0
        _size_mb = _size_bytes / (1024 * 1024)
        timeout_sec = max(
            settings.PIPELINE_TIMEOUT,
            min(
                int(_size_mb * settings.PIPELINE_TIMEOUT_PER_MB),
                settings.PIPELINE_TIMEOUT_MAX,
            ),
        )
        logger.info(
            "  Timeout budget: %ds (file %.1f MB)",
            timeout_sec,
            _size_mb,
        )
        result = await asyncio.wait_for(
            _run_pipeline_stages(),
            timeout=timeout_sec,
        )
        return result
    except asyncio.TimeoutError:
        logger.error("╔══════════════════════════════════════════════════════╗")
        logger.error(f"║ TIER 1 TIMEOUT: {dataset_id:<35} ║")
        logger.error(f"║ Exceeded {timeout_sec}s hard limit{'':>22} ║")
        logger.error("╚══════════════════════════════════════════════════════╝")

        if db is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "is_processed": True,
                        "processing_status": "failed",
                        "processing_error": f"Pipeline timed out after {timeout_sec}s",
                        "error_type": "TimeoutError",
                        "failed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    }
                },
            )

        # Job notification for the timeout failure
        try:
            await _notify("failed", error=f"The pipeline timed out after {timeout_sec}s.")
        except Exception:
            pass

        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "error": f"Pipeline timed out after {timeout_sec}s",
        }

    except Exception as e:
        logger.error("╔══════════════════════════════════════════════════════╗")
        logger.error(f"║ TIER 1 FAILED: {dataset_id:<36} ║")
        logger.error(f"║ {str(e)[:50]:<50} ║")
        logger.error("╚══════════════════════════════════════════════════════╝")
        logger.exception(e)

        if db is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "is_processed": True,
                        "processing_status": "failed",
                        "processing_error": str(e)[:1000],
                        "error_type": type(e).__name__,
                        "failed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    }
                },
            )

        # Job notification for the failure
        try:
            await _notify("failed", error=str(e)[:300])
        except Exception:
            pass

        return {"status": "failed", "dataset_id": dataset_id, "error": str(e)[:1000]}


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def _build_domain_info(unified_profiling: Any, unified_intelligence: Any) -> dict[str, Any]:
    """
    Build the ``domain_info`` dict from unified profiling + intelligence results.

    If unified data is available, we extract domain candidates, key metrics,
    dimensions, and time columns from the deterministic pipeline.
    If not, we return a sensible default ("general").
    """
    if not unified_profiling or not unified_intelligence:
        return {
            "domain": "general",
            "domain_id": None,
            "confidence": 0.5,
            "method": "fallback_deterministic",
            "key_metrics": [],
            "dimensions": [],
            "measures": [],
            "time_columns": [],
        }

    # Extract domain from unified intelligence
    top = unified_intelligence.domain.top_candidate
    domain_name = "general"
    domain_id = None
    confidence = 0.5

    if top:
        domain_name = top.domain_name or "general"
        domain_id = top.domain_id
        confidence = top.score or 0.5
    elif unified_intelligence.domain.candidates:
        best = unified_intelligence.domain.candidates[0]
        domain_name = best.domain_name or "general"
        domain_id = best.domain_id
        confidence = best.score or 0.5

    # Extract column roles from intelligence
    key_metrics: list[str] = []
    dimensions: list[str] = []
    measures: list[str] = []
    time_columns: list[str] = []

    for col in unified_intelligence.columns:
        role = (
            str(col.semantic_role)
            if hasattr(col.semantic_role, "value")
            else str(col.semantic_role)
        )
        name = col.name

        if role in ("MEASURE", "COUNT", "RATE", "METRIC"):
            key_metrics.append(name)
            measures.append(name)
        elif role == "DIMENSION":
            dimensions.append(name)
        elif role == "TIME":
            time_columns.append(name)
            dimensions.append(name)
        elif role == "GEO":
            dimensions.append(name)

    return {
        "domain": domain_name,
        "domain_id": domain_id,
        "confidence": confidence,
        "method": unified_intelligence.domain.method,
        "key_metrics": key_metrics,
        "dimensions": dimensions,
        "measures": measures,
        "time_columns": time_columns,
    }


# ── Serialization helpers (same as before, kept for backward compat) ──────


def _unified_profile_to_dict(profiling: Any) -> dict:
    """Convert RawProfilingResult to a JSON-safe dict."""
    if profiling is None:
        return {}
    try:
        return {
            "dataset": profiling.dataset.model_dump()
            if hasattr(profiling.dataset, "model_dump")
            else {},
            "processed_at": profiling.processed_at,
            "columns": [
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "cardinality": {
                        "unique_count": c.cardinality.unique_count,
                        "total_count": c.cardinality.total_count,
                        "null_count": c.cardinality.null_count,
                        "cardinality_ratio": c.cardinality.cardinality_ratio,
                        "cardinality_level": c.cardinality.cardinality_level,
                    },
                    "stats": {
                        "min": c.stats.col_min if c.stats else None,
                        "max": c.stats.col_max if c.stats else None,
                        "mean": c.stats.col_mean if c.stats else None,
                        "median": c.stats.col_median if c.stats else None,
                        "std": c.stats.col_std if c.stats else None,
                        "p25": c.stats.col_p25 if c.stats else None,
                        "p75": c.stats.col_p75 if c.stats else None,
                        "p90": c.stats.col_p90 if c.stats else None,
                        "skewness": c.stats.skewness if c.stats else None,
                        "cv": c.stats.cv if c.stats else None,
                    }
                    if c.stats
                    else None,
                    "patterns": [p.model_dump() for p in c.patterns],
                    "quality": {
                        "null_percentage": c.quality.null_percentage,
                        "completeness": c.quality.completeness,
                        "quality_score": c.quality.quality_score,
                    },
                    "sample_values": c.sample_values[:5],
                    "top_values": [{"value": v.value, "count": v.count} for v in c.top_values[:10]],
                }
                for c in profiling.columns
            ],
        }
    except Exception as e:
        logger.warning(f"Failed to serialize unified profile: {e}")
        return {}


def _unified_intelligence_to_dict(intel: Any) -> dict:
    """Convert UnifiedIntelligenceResult to a JSON-safe dict."""
    if intel is None:
        return {}
    try:
        return {
            "columns": [
                {
                    "name": c.name,
                    "semantic_role": c.semantic_role.value
                    if hasattr(c.semantic_role, "value")
                    else str(c.semantic_role),
                    "behavioral_role": c.behavioral_role.value
                    if hasattr(c.behavioral_role, "value")
                    else str(c.behavioral_role),
                    "business_category": c.business_category.value
                    if hasattr(c.business_category, "value")
                    else str(c.business_category),
                    "polarity": c.polarity,
                    "classification_confidence": c.classification_confidence,
                    "needs_review": c.needs_review,
                    "geo_role": c.geo_role,
                    "aggregation_suitability": {
                        "sum_allowed": c.aggregation_suitability.sum_allowed,
                        "avg_allowed": c.aggregation_suitability.avg_allowed,
                        "min_allowed": c.aggregation_suitability.min_allowed,
                        "max_allowed": c.aggregation_suitability.max_allowed,
                        "count_allowed": c.aggregation_suitability.count_allowed,
                        "count_distinct_allowed": c.aggregation_suitability.count_distinct_allowed,
                        "median_allowed": c.aggregation_suitability.median_allowed,
                        "additive_type": c.aggregation_suitability.additive_type.value
                        if hasattr(c.aggregation_suitability.additive_type, "value")
                        else str(c.aggregation_suitability.additive_type),
                        "recommended_aggregation": c.aggregation_suitability.recommended_aggregation,
                        "aggregation_rationale": c.aggregation_suitability.aggregation_rationale,
                    },
                    "entity_info": {
                        "entity_type": c.entity_info.entity_type,
                        "unique_count": c.entity_info.unique_count,
                        "avg_records_per_entity": c.entity_info.avg_records_per_entity,
                        "confidence": c.entity_info.confidence,
                    }
                    if c.entity_info
                    else None,
                }
                for c in intel.columns
            ],
            "entities": [
                {
                    "entity_column": e.entity_column,
                    "entity_type": e.entity_type,
                    "unique_count": e.unique_count,
                    "avg_records_per_entity": e.avg_records_per_entity,
                    "confidence": e.confidence,
                }
                for e in intel.entities
            ],
            "geo": {
                "latitude": intel.geo.latitude,
                "longitude": intel.geo.longitude,
                "country": intel.geo.country,
                "state": intel.geo.state,
                "city": intel.geo.city,
                "has_geo": intel.geo.has_geo,
                "lat_lng_pair": intel.geo.lat_lng_pair,
            },
            "hierarchies": [
                {
                    "columns": h.columns,
                    "hierarchy_type": h.hierarchy_type,
                    "description": h.description,
                }
                for h in intel.hierarchies
            ],
            "temporal": {
                "date_column": intel.temporal.date_column,
                "date_range_days": intel.temporal.date_range_days,
                "grain": intel.temporal.grain,
                "has_date_hierarchy": intel.temporal.has_date_hierarchy,
            },
            "domain": {
                "method": intel.domain.method,
                "top_candidate": {
                    "domain_id": intel.domain.top_candidate.domain_id,
                    "domain_name": intel.domain.top_candidate.domain_name,
                    "score": intel.domain.top_candidate.score,
                    "matched_columns": intel.domain.top_candidate.matched_columns,
                }
                if intel.domain.top_candidate
                else None,
                "candidates": [
                    {
                        "domain_id": c.domain_id,
                        "domain_name": c.domain_name,
                        "score": c.score,
                    }
                    for c in intel.domain.candidates
                ],
                "llm_verdict": {
                    "domain": intel.domain.llm_verdict.domain,
                    "domain_id": intel.domain.llm_verdict.domain_id,
                    "confidence": intel.domain.llm_verdict.confidence,
                    "reasoning": intel.domain.llm_verdict.reasoning,
                    "column_mapping": intel.domain.llm_verdict.column_mapping,
                }
                if intel.domain.llm_verdict
                else None,
            },
            "columns_needing_review": intel.columns_needing_review(),
        }
    except Exception as e:
        logger.warning(f"Failed to serialize unified intelligence: {e}")
        return {}
