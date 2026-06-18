"""
Dataset Processing Pipeline
============================
Converts a raw dataset file (CSV/XLSX/JSON/Parquet) into an analyzed,
enriched dataset document with domain detection, KPI computation, strategic
advice, chart recommendations, and vector indexing.

This was originally a Celery task (workers/pipeline/dataset.py) but was
converted to a direct async function because the application runs on
Google Cloud Run where Celery/Redis are not available.

Usage:
    from services.pipeline.process import process_dataset
    asyncio.create_task(process_dataset(dataset_id, file_path, user_id))
"""

import logging
import os
from typing import Any
from datetime import datetime

import polars as pl
from pymongo import MongoClient

from core.config import settings
from services.analysis.analysis_service import analysis_service
from services.analysis.insight_interpreter import insight_interpreter
from services.charts.chart_recommender import chart_recommender
from services.datasets.data_profiler import data_profiler
from services.ai.intelligent_kpi_generator import (
    _profile_column,
    _detect_domain_hybrid,
    ColumnProfile as KpiColumnProfile,
    ColumnRole as KpiColumnRole,
)
from services.knowledge_graph.entity_discovery import entity_discovery as kg_entity_discovery
from services.knowledge_graph.models import (
    ColumnProfile as KGColumnProfile,
    SchemaProfile as KGSchemaProfile,
)
from services.datasets.faiss_vector_service import faiss_vector_service
from agents.multi.orchestrator import PipelineOrchestrator
from agents.multi.pipeline import PipelineContext
from services.pipeline.classifier import classify
from services.pipeline.compute import compute_all
from services.pipeline.critic import check_all
from services.pipeline.narrator import narrate
from services.pipeline.planner import plan
from services.pipeline.profiler import profile_dataframe
from services.pipeline.clean import calculate_quality_metrics, clean_dataframe
from services.pipeline.load import coerce_numeric_columns, load_dataset
from services.pipeline.helpers import convert_types_for_json, extract_sample_rows
from services.pipeline.tracker import PipelineTracker

# ── NEW: Unified profiling & intelligence engines ────────────────────────
from services.profiling.engine import profiling_engine
from services.intelligence.engine import intelligence_engine
from services.intelligence.domain_detector_llm import llm_domain_detector

# ── DatasetMemo import ─────────────────────────────────────────────────
from services.intelligence.dataset_memo import DatasetMemo, DatasetMemoCache

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Stage labels for the PipelineTracker (used for the frontend stage display)
STAGE_LABELS = {
    "loading": "Loading Dataset",
    "cleaning": "Cleaning Data",
    "metadata": "Generating Metadata",
    "domain_detection": "Detecting Domain",
    "kpi_pipeline": "Computing KPI Primitives",
    "profiling": "Profiling Data",
    "analysis": "Running Deep Analysis",
    "quis_analysis": "QUIS Subspace Analysis",
    "charts": "Generating Chart Recommendations",
    "quality": "Calculating Quality Metrics",
    "consolidating": "Consolidating Metadata",
    "saving": "Saving Results",
    "artifact_generation": "Pre-computing Artifacts",
    "vector_indexing": "Indexing Vector Database",
}

# Single shared MongoDB client for the pipeline (sync PyMongo — this runs
# in a background task where blocking the event loop is acceptable).
_client: MongoClient | None = None


def _get_db():
    """Get or create a shared sync MongoDB client for the pipeline."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URL, maxPoolSize=5)
    return _client[settings.DATABASE_NAME]


async def process_dataset(dataset_id: str, file_path: str, user_id: str = "unknown") -> dict:
    """
    Process a dataset: load → clean → profile → analyze → index.

    This runs as a background task (via asyncio.create_task), not inside
    a Celery worker. Progress is tracked in MongoDB so the API can poll
    the dataset's ``processing_status`` field directly.

    Args:
        dataset_id: Unique dataset identifier (matches MongoDB _id).
        file_path: Absolute path to the uploaded file.
        user_id: Owner of the dataset.

    Returns:
        dict with processing result summary.
    """
    logger.info("╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║ DATASET PROCESSING STARTED: {dataset_id:<30} ║")
    logger.info("╚════════════════════════════════════════════════════════════════╝")

    db = _get_db()
    datasets_collection = db.uploads
    tracker = PipelineTracker(dataset_id, user_id, db)

    # Shared variables that cross stage boundaries
    df_clean = None
    column_metadata = []
    domain_info = None
    profile_info = None
    sample_rows = []
    pipeline_profile = None
    pipeline_specs = []
    pipeline_compute_results = []
    pipeline_cards = []
    chart_recommendations = []
    data_quality = {}
    sanitized_metadata = {}

    # ── NEW: Unified profiling & intelligence results ──
    unified_profiling = None
    unified_intelligence = None

    try:
        # ── Stage: Loading ────────────────────────────────────────────────────
        async with tracker.stage("loading", STAGE_LABELS["loading"]):
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Dataset file not found: {file_path}")

            df = load_dataset(file_path)

            if df.is_empty():
                raise ValueError("Dataset is empty")

            if len(df.columns) == 0:
                raise ValueError("Dataset has no columns")

            df, coerce_cols = coerce_numeric_columns(df)
            logger.info(f"✓ Numeric coercion: {len(coerce_cols)} columns promoted")

            df_lazy = df.lazy()
            original_rows = len(df)
            schema = df.schema

            logger.info(f"✓ Loaded: {original_rows:,} rows × {len(schema):,} columns")

        # ── Stage: Cleaning ───────────────────────────────────────────────────
        async with tracker.stage("cleaning", STAGE_LABELS["cleaning"]):
            df_clean = clean_dataframe(df_lazy, schema)
            cleaned_rows = len(df_clean)
            duplicates_removed = original_rows - cleaned_rows

            if duplicates_removed > 0:
                logger.info(f"✓ Removed {duplicates_removed:,} duplicate rows")

            parquet_path = None
            try:
                parquet_path = file_path.rsplit(".", 1)[0] + ".parquet"
                df_clean.write_parquet(parquet_path, compression="zstd")
                logger.info(f"✓ Saved Parquet: {parquet_path}")
            except Exception as e:
                logger.warning(f"Parquet save failed: {e}")
                parquet_path = None

        # ── Stage: Metadata (column profiling) ────────────────────────────────
        async with tracker.stage("metadata", STAGE_LABELS["metadata"]):
            for col in df_clean.columns:
                col_data = df_clean[col]
                col_meta = {
                    "name": col,
                    "type": str(col_data.dtype),
                    "null_count": col_data.null_count(),
                    "null_percentage": (
                        round((col_data.null_count() / len(df_clean)) * 100, 2)
                        if len(df_clean) > 0
                        else 0
                    ),
                    "unique_count": col_data.n_unique(),
                }

                if col_data.dtype in pl.NUMERIC_DTYPES:
                    try:
                        col_meta["numeric_summary"] = {
                            "min": float(col_data.min()) if col_data.min() is not None else None,
                            "max": float(col_data.max()) if col_data.max() is not None else None,
                            "mean": (
                                round(float(col_data.mean()), 2)
                                if col_data.mean() is not None
                                else None
                            ),
                        }
                    except Exception:
                        pass
                elif col_data.dtype == pl.Boolean or col_data.n_unique() <= 20:
                    try:
                        col_meta["top_values"] = [
                            {"value": str(v), "count": int((col_data == v).sum())}
                            for v in col_data.drop_nulls().unique().to_list()[:10]
                        ]
                    except Exception:
                        pass
                elif col_data.dtype == pl.Utf8 and col_data.n_unique() < 100:
                    try:
                        vc = df_clean.group_by(col).len().sort("len", descending=True).head(10)
                        col_meta["top_values"] = [
                            {"value": row[col], "count": row["len"]} for row in vc.to_dicts()
                        ]
                    except Exception:
                        pass

                column_metadata.append(col_meta)

            sample_rows = extract_sample_rows(df_clean, n=5)

        # ── Stage: Unified Profiling (NEW — deterministic, no LLM) ──────────
        async with tracker.stage("metadata", STAGE_LABELS["metadata"]):
            try:
                unified_profiling = profiling_engine.run(
                    df_clean,
                    file_type=file_path.split(".")[-1].lower(),
                )
                # Populate file_name and processed_at for the profile page
                try:
                    doc = datasets_collection.find_one({"_id": dataset_id}, {"name": 1})
                    if doc and doc.get("name"):
                        unified_profiling.dataset.file_name = doc["name"]
                except Exception:
                    pass
                unified_profiling.processed_at = datetime.utcnow().isoformat()

                # Run intelligence layer on top of profiling facts
                unified_intelligence = intelligence_engine.run(
                    unified_profiling,
                    df=df_clean,
                )
                logger.info(
                    "✓ Unified profiling: %d columns profiled, %d entities, %d domain candidates",
                    len(unified_profiling.columns),
                    len(unified_intelligence.entities),
                    len(unified_intelligence.domain.candidates),
                )
            except Exception as e:
                logger.warning(f"Unified profiling failed (falling back to legacy): {e}")
                unified_profiling = None
                unified_intelligence = None

        # ── LLM Domain Enrichment (new — runs on top of deterministic pipeline) ─
        if unified_profiling and unified_intelligence:
            try:
                llm_domain_result = await llm_domain_detector.detect(unified_profiling, df_clean)
                if llm_domain_result.llm_verdict:
                    unified_intelligence.domain.llm_verdict = llm_domain_result.llm_verdict
                    # If LLM returned a valid domain candidate, use it as top candidate
                    if llm_domain_result.top_candidate:
                        unified_intelligence.domain.top_candidate = llm_domain_result.top_candidate
                        unified_intelligence.domain.candidates = llm_domain_result.candidates
                        unified_intelligence.domain.method = "llm"
                    logger.info(
                        "✓ LLM domain enrichment: %s (confidence=%.2f)",
                        llm_domain_result.llm_verdict.domain_id,
                        llm_domain_result.llm_verdict.confidence,
                    )
                else:
                    logger.debug(
                        "LLM domain enrichment returned no verdict — using deterministic fallback"
                    )
            except Exception as e:
                logger.warning(f"LLM domain enrichment failed (non-critical): {e}")

        # ── Stage: Domain Detection (legacy — kept for backward compat) ────────
        async with tracker.stage("domain_detection", STAGE_LABELS["domain_detection"]):
            # Initialize the DatasetMemo — this will be populated as the pipeline progresses
            # and consumed by downstream stages (e.g., IntelligentKPIGenerator) to avoid
            # redundant LLM calls for domain re-detection.
            pipeline_memo = DatasetMemo(
                dataset_id=dataset_id,
                user_id=user_id,
                row_count=len(df_clean) if df_clean is not None else 0,
                column_count=len(df_clean.columns) if df_clean is not None else 0,
            )
            try:
                # Use the same LLM-first detection as the KPI generator
                profiles = []
                for col in df_clean.columns:
                    p = _profile_column(df_clean, col)
                    if p is not None:
                        profiles.append(p)

                domain_id, column_mapping = await _detect_domain_hybrid(profiles, df_clean)

                if domain_id:
                    domain_name = domain_id.split("-")[0] if "-" in domain_id else domain_id
                    domain_info = {
                        "domain": domain_name,
                        "domain_id": domain_id,
                        "confidence": 0.85,
                        "matched_patterns": [],
                        "key_metrics": [
                            p.name
                            for p in profiles
                            if p.role in (KpiColumnRole.MEASURE, KpiColumnRole.COUNT)
                        ],
                        "dimensions": [p.name for p in profiles if p.role == KpiColumnRole.DIMENSION],
                        "measures": [
                            p.name
                            for p in profiles
                            if p.role in (KpiColumnRole.MEASURE, KpiColumnRole.COUNT, KpiColumnRole.RATE)
                        ],
                        "time_columns": [p.name for p in profiles if p.role == KpiColumnRole.TIME],
                        "method": "llm_first",
                    }
                    # ── Populate DatasetMemo with domain results ────────────────
                    pipeline_memo.domain_id = domain_id
                    pipeline_memo.domain_name = domain_name
                    pipeline_memo.domain_confidence = 0.85
                    pipeline_memo.domain_method = "llm_first"
                    pipeline_memo.column_mapping = column_mapping
                    DatasetMemoCache.set(dataset_id, pipeline_memo)

                    logger.info(f"✓ Domain: {domain_name} (from template: {domain_id})")
                else:
                    domain_info = {
                        "domain": "general",
                        "domain_id": None,
                        "confidence": 0.5,
                        "matched_patterns": [],
                        "key_metrics": [
                            p.name
                            for p in profiles
                            if p.role in (KpiColumnRole.MEASURE, KpiColumnRole.COUNT)
                        ],
                        "dimensions": [p.name for p in profiles if p.role == KpiColumnRole.DIMENSION],
                        "measures": [
                            p.name
                            for p in profiles
                            if p.role in (KpiColumnRole.MEASURE, KpiColumnRole.COUNT, KpiColumnRole.RATE)
                        ],
                        "time_columns": [p.name for p in profiles if p.role == KpiColumnRole.TIME],
                        "method": "llm_no_match",
                    }
                    # ── Populate DatasetMemo with general domain ─────────────────
                    pipeline_memo.domain_name = "general"
                    pipeline_memo.domain_method = "llm_no_match"
                    DatasetMemoCache.set(dataset_id, pipeline_memo)

                    logger.info("✓ Domain: general (no template matched)")
            except Exception as e:
                logger.warning(f"Domain detection failed: {e}")
                domain_info = {
                    "domain": "general",
                    "confidence": 0.5,
                    "matched_patterns": [],
                    "key_metrics": [],
                    "dimensions": [],
                    "measures": [],
                    "time_columns": [],
                    "method": "fallback",
                }
                # Still populate the memo so downstream can check it.
                # domain_confidence stays 0.0 (default) — this means
                # domain_detected returns False, so KPI generator will
                # still attempt its own domain detection. Correct behavior.
                pipeline_memo.domain_name = "general"
                pipeline_memo.domain_method = "fallback"
                DatasetMemoCache.set(dataset_id, pipeline_memo)

        # ── Stage: KPI Pipeline (profile → classify → plan → compute → narrate) ──
        async with tracker.stage("kpi_pipeline", STAGE_LABELS["kpi_pipeline"]):
            try:
                from agents.multi.chart_agent import ChartAgent as MAChartAgent
                from agents.multi.kpi_agent import KPICAgent as MAKPICAgent
                from agents.multi.profile_agent import ProfileAgent as MAProfileAgent

                profile_agent = MAProfileAgent(
                    tools={
                        "profiler": profile_dataframe,
                        "classifier": classify,
                    }
                )
                kpi_agent = MAKPICAgent()
                chart_agent = MAChartAgent()

                orchestrator = PipelineOrchestrator()
                orchestrator.register_agent("profile", profile_agent)
                orchestrator.register_agent("kpi", kpi_agent)
                orchestrator.register_agent("chart", chart_agent)

                pipeline_ctx = PipelineContext(
                    dataset_id=dataset_id,
                    user_id=user_id,
                    df=df_clean,
                    domain_signal=domain_info.get("domain", "general"),
                    domain_confidence=float(domain_info.get("confidence", 0.5)),
                    source_type="file",
                )
                pipeline_result = await orchestrator.run("kpi", pipeline_ctx)
                pipeline_profile = pipeline_result.get("profile")
                pipeline_specs = pipeline_result.get("specs", [])
                pipeline_compute_results = pipeline_result.get("compute_results", [])
                pipeline_cards = pipeline_result.get("cards", [])
                pipeline_charts = pipeline_result.get("charts", [])
                logger.info(
                    f"✓ Orchestrator: profile={bool(pipeline_profile)}, "
                    f"specs={len(pipeline_specs)}, compute={len(pipeline_compute_results)}, "
                    f"cards={len(pipeline_cards)}, charts={len(pipeline_charts)}"
                )
            except Exception as e:
                logger.warning(f"Multi-agent orchestrator failed: {e}")

            if not pipeline_profile:
                try:
                    pipeline_profile = await profile_dataframe(
                        df_clean,
                        domain_signal=domain_info.get("domain", "general"),
                        domain_confidence=float(domain_info.get("confidence", 0.5)),
                    )
                    pipeline_specs = classify(pipeline_profile)
                    pipeline_specs = await plan(pipeline_profile, pipeline_specs)
                    pipeline_compute_results = await compute_all(pipeline_specs, df_clean)
                    pipeline_compute_results = check_all(pipeline_compute_results)
                    pipeline_cards = await narrate(pipeline_compute_results, pipeline_specs)
                    logger.info(
                        "Fallback: %d results -> %d cards",
                        len(pipeline_compute_results),
                        len(pipeline_cards),
                    )
                except Exception as e:
                    logger.warning(f"Fallback KPI pipeline failed: {e}")

        # ── Stage: Profiling ──────────────────────────────────────────────────
        async with tracker.stage("profiling", STAGE_LABELS["profiling"]):
            try:
                profile_info = data_profiler.profile_dataset(df_clean, column_metadata)
                logger.info(f"✓ Profiled: {profile_info['row_count']:,} rows")
            except Exception as e:
                logger.warning(f"Data profiling failed: {e}")
                profile_info = {
                    "row_count": len(df_clean),
                    "column_count": len(df_clean.columns),
                    "cardinality": {},
                    "patterns": {},
                    "quality_metrics": {},
                    "relationships": {},
                    "id_columns": [],
                    "high_cardinality_dims": [],
                    "low_cardinality_dims": [],
                }

        # ── Stage: Deep Statistical Analysis ──────────────────────────────────
        async with tracker.stage("analysis", STAGE_LABELS["analysis"]):
            try:
                enhanced_results = await analysis_service.run_enhanced_analysis(
                    df_clean, depth="standard"
                )
                logger.info("✓ Enhanced analysis complete")
            except Exception:
                enhanced_results = {
                    "depth": "fallback",
                    "row_count": len(df_clean),
                    "column_count": len(df_clean.columns),
                    "distributions": [],
                    "correlations": [],
                }

        # ── Stage: QUIS Subspace Analysis ─────────────────────────────────────
        async with tracker.stage("quis_analysis", STAGE_LABELS["quis_analysis"]):
            try:
                quis_results = await analysis_service.run_enhanced_quis_sync(
                    df_clean, dataset_id=dataset_id
                )
                logger.info("✓ QUIS complete")
            except Exception:
                quis_results = {
                    "summary": {"total_questions": 0, "significant_insights": 0},
                    "insights": [],
                    "top_insights": [],
                }

            try:
                executive_summary = insight_interpreter.generate_summary(enhanced_results)
            except Exception:
                executive_summary = ""

            try:
                statistical_findings = analysis_service.run_all_statistical_checks(df_clean)
            except Exception:
                statistical_findings = {
                    "correlations": [],
                    "outliers": [],
                    "distributions": {},
                }

            deep_analysis = {
                "enhanced_analysis": enhanced_results,
                "quis_insights": quis_results,
                "executive_summary": executive_summary,
                "analysis_version": "2.0",
            }

        # ── Stage: Chart Recommendations ──────────────────────────────────────
        async with tracker.stage("charts", STAGE_LABELS["charts"]):
            try:
                chart_recommendations = chart_recommender.recommend_charts(
                    df=df_clean,
                    column_metadata=column_metadata,
                    domain=domain_info["domain"],
                    cardinality=profile_info.get("cardinality", {}),
                    time_columns=domain_info.get("time_columns", []),
                )
                logger.info(f"✓ Generated {len(chart_recommendations)} chart recommendations")
            except Exception:
                chart_recommendations = []

        # ── Stage: Quality Metrics ────────────────────────────────────────────
        async with tracker.stage("quality", STAGE_LABELS["quality"]):
            data_quality = calculate_quality_metrics(
                column_metadata, original_rows, duplicates_removed
            )
            logger.info(f"✓ Quality: {data_quality['completeness']:.1f}% complete")

            # Run DataQualityAgent (comprehensive quality monitoring)
            try:
                from services.data_quality import DataQualityAgent

                quality_agent = DataQualityAgent()
                quality_report = await quality_agent.run_quality_check(
                    columns=column_metadata,
                    sample_rows=sample_rows[:5] if sample_rows else None,
                    row_count=cleaned_rows,
                    dataset_id=dataset_id,
                )

                base_metadata = {
                    "dataset_overview": {},
                    "data_quality_agent": {
                        "overall_score": quality_report.overall_score,
                        "issues": quality_report.issues[:50],
                        "completeness": quality_report.completeness,
                        "consistency": quality_report.consistency,
                        "distribution_drift": quality_report.distribution_drift[:10],
                        "schema_changes": quality_report.schema_changes,
                        "passed_checks": quality_report.passed_checks,
                        "failed_checks": quality_report.failed_checks,
                    },
                }
            except Exception as e:
                logger.warning(f"[DataQualityAgent] Failed: {e}")
                base_metadata = {}

        # ── Stage: Consolidating Metadata ─────────────────────────────────────
        async with tracker.stage("consolidating", STAGE_LABELS["consolidating"]):
            # ── Entity Discovery (KG Layer 1 + Layer 2 pipeline) ──
            entity_discovery_report = None
            try:
                kg_profiles = _build_kg_column_profiles(column_metadata, df_clean)
                table_name = os.path.splitext(os.path.basename(file_path))[0]
                entity_discovery_report = kg_entity_discovery.discover(
                    columns=kg_profiles,
                    table_name=table_name,
                )
                logger.info(
                    "✓ Entity discovery: %d entities, %d unknown columns, quality=%.1f, trust=%.1f",
                    entity_discovery_report.entity_count,
                    len(entity_discovery_report.unknown_columns),
                    entity_discovery_report.data_quality_score,
                    entity_discovery_report.trust_score,
                )
            except Exception as e:
                logger.warning(f"Entity discovery failed (non-critical): {e}")
                entity_discovery_report = None

            # ── Populate DatasetMemo with analysis results ────────────────
            # These are all available as local variables at this point
            # (deep_analysis, statistical_findings, data_quality were computed
            #  in the quis_analysis / quality stages above).
            pipeline_memo.deep_analysis = convert_types_for_json(deep_analysis)
            pipeline_memo.statistical_findings = convert_types_for_json(statistical_findings)
            pipeline_memo.data_quality = convert_types_for_json(data_quality)
            DatasetMemoCache.set(dataset_id, pipeline_memo)
            logger.info(
                "✓ DatasetMemo populated with analysis results "
                f"({len(deep_analysis.get('quis_insights', {}).get('top_insights', []))} insights)"
            )

            final_metadata = {
                "dataset_overview": {
                    "total_rows": cleaned_rows,
                    "total_columns": len(df_clean.columns),
                    "original_rows": original_rows,
                    "file_type": file_path.split(".")[-1].lower(),
                },
                "column_metadata": column_metadata,
                "domain_intelligence": domain_info,
                "data_profile": profile_info,
                # ── NEW: Unified deterministic profile ──
                "unified_profile": (
                    _unified_profile_to_dict(unified_profiling) if unified_profiling else None
                ),
                "unified_intelligence": (
                    _unified_intelligence_to_dict(unified_intelligence)
                    if unified_intelligence
                    else None
                ),
                "entity_discovery": (
                    _entity_discovery_to_dict(entity_discovery_report)
                    if entity_discovery_report
                    else None
                ),
                "statistical_findings": statistical_findings,
                "deep_analysis": deep_analysis,
                "chart_recommendations": chart_recommendations,
                "data_quality": data_quality,
                "pipeline_profile": pipeline_profile.model_dump() if pipeline_profile else None,
                "pipeline_specs": [s.model_dump() for s in pipeline_specs],
                "pipeline_compute_results": [r.model_dump() for r in pipeline_compute_results],
                "pipeline_cards": [c.model_dump() for c in pipeline_cards],
                "sample_data": sample_rows[:3],
                "processing_info": {
                    "processed_at": datetime.utcnow(),
                    "pipeline_version": "3.0",
                },
            }

            if base_metadata.get("data_quality_agent"):
                final_metadata["data_quality_agent"] = base_metadata["data_quality_agent"]

            sanitized_metadata = convert_types_for_json(final_metadata)

            # Attach user's analysis intent (set at upload time)
            try:
                doc_for_intent = datasets_collection.find_one(
                    {"_id": dataset_id}, {"analysis_intent": 1}
                )
                if doc_for_intent and doc_for_intent.get("analysis_intent"):
                    sanitized_metadata["analysis_intent"] = doc_for_intent["analysis_intent"]
            except Exception:
                pass

            # Run AnalystAgent (strategic analysis, only if intent provided)
            try:
                analysis_intent = sanitized_metadata.get("analysis_intent")
                if analysis_intent:
                    logger.info(
                        f"[AnalystAgent] Starting strategic analysis with intent='{analysis_intent}'"
                    )
                    from agents.multi import AnalystAgent
                    from agents.multi.registry import MultiAgentToolRegistry

                    MultiAgentToolRegistry.initialize_defaults()
                    tools = MultiAgentToolRegistry.get_tools(["profiler", "rag", "memory"])
                    analyst = AnalystAgent(tools)

                    result = await analyst.run(
                        query=analysis_intent,
                        dataset_id=dataset_id,
                        user_id=user_id,
                        df=df_clean,
                    )

                    raw_profile = result.get("profile")
                    profile_dict = None
                    if raw_profile is not None:
                        profile_dict = (
                            raw_profile.model_dump()
                            if hasattr(raw_profile, "model_dump")
                            else raw_profile
                        )

                    sanitized_metadata["analyst_analysis"] = {
                        "response": result.get("response", ""),
                        "profile": profile_dict,
                        "statistical_findings": result.get("statistical_findings", {}),
                        "kpi_recommendations": result.get("kpi_recommendations", []),
                        "novelty_check": result.get("novelty_check", {}),
                        "analysis_intent": analysis_intent,
                    }
                    logger.info(
                        "[AnalystAgent] Strategic analysis complete — "
                        f"{len(result.get('kpi_recommendations', []))} KPIs recommended, "
                        f"tools used: {result.get('tools_used', [])}"
                    )
                else:
                    logger.debug("[AnalystAgent] No analysis intent — skipping strategic analysis")
            except Exception as e:
                logger.warning(f"[AnalystAgent] Strategic analysis failed: {e}", exc_info=True)
                sanitized_metadata["analyst_analysis"] = {"error": str(e)[:200]}

        # ── Stage: Saving Results ─────────────────────────────────────────────
        async with tracker.stage("saving", STAGE_LABELS["saving"]):
            update_fields = {
                "metadata": sanitized_metadata,
                "is_processed": True,
                "processing_status": "success",
                "row_count": cleaned_rows,
                "column_count": len(df_clean.columns),
                "domain": domain_info["domain"],
                "domain_confidence": domain_info["confidence"],
                "updated_at": datetime.utcnow(),
            }
            if parquet_path:
                update_fields["parquet_path"] = parquet_path
            datasets_collection.update_one({"_id": dataset_id}, {"$set": update_fields})

            try:
                analytics_collection = db.dataset_analytics
                analytics_doc = {
                    "dataset_id": dataset_id,
                    "user_id": user_id,
                    "chart_recommendations": convert_types_for_json(chart_recommendations),
                    "statistical_findings": convert_types_for_json(statistical_findings),
                    "deep_analysis": convert_types_for_json(deep_analysis),
                    "data_profile": convert_types_for_json(profile_info),
                    "domain_intelligence": convert_types_for_json(domain_info),
                    "data_quality": convert_types_for_json(data_quality),
                    "pipeline_compute_results": convert_types_for_json(
                        [r.model_dump() for r in pipeline_compute_results]
                    ),
                    "pipeline_cards": convert_types_for_json(
                        [c.model_dump() for c in pipeline_cards]
                    ),
                    "analyst_analysis": convert_types_for_json(
                        sanitized_metadata.get("analyst_analysis", {})
                    ),
                    "pipeline_profile": convert_types_for_json(
                        pipeline_profile.model_dump() if pipeline_profile else {}
                    ),
                    "computed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "pipeline_version": "3.0",
                }
                analytics_collection.update_one(
                    {"dataset_id": dataset_id, "user_id": user_id},
                    {"$set": analytics_doc},
                    upsert=True,
                )
            except Exception as e:
                logger.warning(f"Failed to save analytics: {e}")

        # ── Stage: Artifact Generation (KPIs, Charts, Dashboard Design) ─────────
        async with tracker.stage("artifact_generation", STAGE_LABELS["artifact_generation"]):
            # KPI pre-computation
            try:
                from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
                from services.cache.dashboard_cache_service import dashboard_cache_service
                from services.datasets.enhanced_dataset_service import enhanced_dataset_service

                try:
                    kpi_df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
                    domain_for_kpi = domain_info.get("domain", "general")
                    intelligent_kpis = await intelligent_kpi_generator.generate_intelligent_kpis(
                        df=kpi_df,
                        domain=domain_for_kpi,
                        max_kpis=6,
                        dataset_metadata=sanitized_metadata,
                        dataset_id=dataset_id,
                    )
                    await dashboard_cache_service.cache_kpis(dataset_id, user_id, intelligent_kpis)
                    # ── Update DatasetMemo with computed KPIs ────────────────
                    pipeline_memo.kpis = intelligent_kpis

                    # ── Extract metric_decomposition edges + root_cause_chains ──
                    # Each KPI card may have metric_decomposition and root_cause_chain
                    # attached by the IntelligentKPIGenerator.
                    metric_decomp_edges = []
                    root_cause_chains = []
                    for kpi in intelligent_kpis:
                        decomp = kpi.get("metric_decomposition")
                        if decomp and decomp.get("has_decomposition"):
                            # Build a metric_graph summary from decomposition edges
                            for comp in decomp.get("components", []):
                                metric_decomp_edges.append({
                                    "source": decomp.get("metric", kpi.get("column", "")),
                                    "target": comp.get("column", ""),
                                    "relationship_type": comp.get("relationship_type", "component"),
                                    "contribution_pct": comp.get("contribution_pct"),
                                    "formula": comp.get("formula", ""),
                                })
                        chain = kpi.get("root_cause_chain")
                        if chain:
                            root_cause_chains.append(chain)

                    if metric_decomp_edges:
                        pipeline_memo.metric_graph = {
                            "edge_count": len(metric_decomp_edges),
                            "edges": metric_decomp_edges,
                        }
                        pipeline_memo.metric_graph_edges = len(metric_decomp_edges)

                    if root_cause_chains:
                        pipeline_memo.root_cause_chains = root_cause_chains

                    DatasetMemoCache.set(dataset_id, pipeline_memo)

                    logger.info(f"✓ Pre-computed {len(intelligent_kpis)} KPIs")
                    if metric_decomp_edges:
                        logger.info(f"  └─ {len(metric_decomp_edges)} metric graph edges extracted")
                    if root_cause_chains:
                        logger.info(f"  └─ {len(root_cause_chains)} root cause chains extracted")
                except Exception as e:
                    logger.warning(f"KPI pre-computation failed: {e}")
            except Exception as e:
                logger.warning(f"KPI pre-computation import/initialization failed: {e}")

            # Chart pre-computation
            try:
                from services.cache.dashboard_cache_service import dashboard_cache_service
                from services.charts.chart_intelligence_service import chart_intelligence_service
                from services.charts.chart_render_service import chart_render_service
                from services.datasets.enhanced_dataset_service import enhanced_dataset_service

                try:
                    chart_df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
                except Exception as e:
                    logger.warning(f"Chart pre-computation data load failed: {e}")
                    chart_df = None

                if chart_df is not None:
                    col_meta = sanitized_metadata.get("column_metadata", [])
                    data_profile_info = sanitized_metadata.get("data_profile", {})
                    domain_intel = sanitized_metadata.get("domain_intelligence", {})
                    deep_analysis_data = sanitized_metadata.get("deep_analysis", {})

                    numeric_cols = chart_df.select(pl.col(pl.NUMERIC_DTYPES)).columns
                    categorical_cols = chart_df.select(pl.col(pl.Utf8, pl.Categorical)).columns

                    precomputed_charts = {}
                    if numeric_cols and categorical_cols:
                        chart_selection = chart_intelligence_service.select_dashboard_charts(
                            df=chart_df,
                            column_metadata=col_meta,
                            domain=domain_intel.get("domain", "general"),
                            domain_confidence=domain_intel.get("confidence", 0.5),
                            statistical_findings=deep_analysis_data.get("enhanced_analysis", {}),
                            data_profile=data_profile_info,
                            context="executive",
                        )
                        for i, chart_spec in enumerate(chart_selection.get("charts", [])[:5]):
                            config = chart_spec.get("config", {})
                            chart_data = await chart_render_service.render_chart(
                                chart_df,
                                {
                                    "chart_type": chart_spec.get("chart_type", "bar"),
                                    "columns": config.get(
                                        "columns",
                                        [categorical_cols[0], numeric_cols[0]],
                                    ),
                                    "aggregation": config.get("aggregation", "sum"),
                                },
                            )
                            precomputed_charts[f"chart_{i}"] = chart_data

                    if precomputed_charts:
                        await dashboard_cache_service.cache_charts(
                            dataset_id, user_id, precomputed_charts
                        )
                        # ── Update DatasetMemo with computed charts ────────────
                        pipeline_memo.charts = list(precomputed_charts.values())
                        pipeline_memo.chart_count = len(precomputed_charts)
                        DatasetMemoCache.set(dataset_id, pipeline_memo)
                        logger.info(f"✓ Pre-computed {len(precomputed_charts)} charts")
                    else:
                        logger.debug("No charts were successfully pre-computed")
            except Exception as e:
                logger.warning(f"Chart pre-computation failed: {e}")

            # Dashboard design
            try:
                from services.ai.ai_designer_service import AIDesignerService

                designer_service = AIDesignerService(sync_db=db)
                await designer_service.design_intelligent_dashboard(
                    dataset_id=dataset_id, user_id=user_id, force_regenerate=True
                )
                datasets_collection.update_one(
                    {"_id": dataset_id},
                    {
                        "$set": {
                            "artifact_status.dashboard_design": "ready",
                            "artifact_status.dashboard_generated_at": datetime.utcnow(),
                        }
                    },
                )
            except Exception as e:
                logger.warning(f"Dashboard design failed: {e}")

        # ── Stage: Vector Indexing ────────────────────────────────────────────
        async with tracker.stage("vector_indexing", STAGE_LABELS["vector_indexing"]):
            try:
                await faiss_vector_service.add_dataset_to_vector_db(
                    dataset_id=dataset_id,
                    dataset_metadata=sanitized_metadata,
                    user_id=user_id,
                )
                logger.info("✓ Vector indexing successful")
            except Exception as e:
                logger.error(f"✗ Vector indexing failed: {e}")

        # ── Mark completed ────────────────────────────────────────────────────
        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "processing_status": "completed",
                    "current_stage_label": "Processing Complete",
                    "processing_progress": 100,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info("╔════════════════════════════════════════════════════════════════╗")
        logger.info(f"║ DATASET PROCESSING COMPLETED: {dataset_id:<27} ║")
        logger.info("╚════════════════════════════════════════════════════════════════╝")

        return {
            "status": "success",
            "progress": 100,
            "dataset_id": dataset_id,
            "rows": cleaned_rows,
            "columns": len(df_clean.columns),
            "domain": domain_info["domain"],
            "quality": data_quality.get("completeness", 0),
        }

    except Exception as e:
        logger.error("╔════════════════════════════════════════════════════════════════╗")
        logger.error(f"║ DATASET PROCESSING FAILED: {dataset_id:<30} ║")
        logger.error(f"║ Error: {str(e)[:50]:<54} ║")
        logger.error("╚════════════════════════════════════════════════════════════════╝")
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
                        "failed_at": datetime.utcnow(),
                    }
                },
            )

        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "error": str(e)[:1000],
        }


# ── Helper: Serialize unified profiling for JSON storage ──────────────────────


def _build_kg_column_profiles(column_metadata: list, df: "pl.DataFrame") -> list:
    """Convert column_metadata dicts to KG ColumnProfile objects for entity discovery."""
    from services.knowledge_graph.models import ColumnProfile as _KGCP

    profiles = []
    total_rows = len(df) if df is not None else 0

    for meta in column_metadata:
        distinct = meta.get("unique_count", 0)
        null_c = meta.get("null_count", 0)
        null_r = (null_c / total_rows) if total_rows > 0 else 0.0
        distinct_r = (distinct / total_rows) if total_rows > 0 else 0.0
        is_unique = distinct_r >= 0.99 and null_r == 0.0

        # Get sample values from the dataframe
        sample_vals: list = []
        if df is not None and meta["name"] in df.columns:
            try:
                vals = df[meta["name"]].drop_nulls().unique().to_list()[:10]
                sample_vals = [str(v) for v in vals if v is not None]
            except Exception:
                pass

        num_summary = meta.get("numeric_summary") or {}

        profiles.append(
            _KGCP(
                name=meta["name"],
                data_type=meta["type"],
                null_ratio=null_r,
                distinct_count=distinct,
                distinct_ratio=distinct_r,
                sample_values=sample_vals[:10],
                is_unique=is_unique,
                is_primary_key=is_unique,
                min_value=num_summary.get("min"),
                max_value=num_summary.get("max"),
                avg_length=None,
            )
        )
    return profiles


def _entity_discovery_to_dict(report: Any) -> dict:
    """Convert DatasetUnderstandingReport to JSON-safe dict."""
    if report is None:
        return None
    try:
        return {
            "table_name": report.table_name,
            "entity_count": report.entity_count,
            "column_count": report.column_count,
            "data_quality_score": report.data_quality_score,
            "trust_score": report.trust_score,
            "entities": [
                {
                    "label": e.label,
                    "columns": e.columns,
                    "identifier_column": e.identifier_column,
                    "role_counts": e.role_counts,
                    "role_confidence": e.role_confidence,
                    "candidate_confidence": e.candidate_confidence,
                    "entity_confidence": e.entity_confidence,
                    "confidence": e.confidence,
                    "validation_notes": e.validation_notes,
                    "is_valid": e.is_valid,
                }
                for e in report.entities
            ],
            "unknown_columns": report.unknown_columns,
            "generated_at": report.generated_at.isoformat()
            if hasattr(report.generated_at, "isoformat")
            else str(report.generated_at),
        }
    except Exception as ex:
        logger.warning(f"Failed to serialize entity discovery report: {ex}")
        return None


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
