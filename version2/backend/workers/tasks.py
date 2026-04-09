"""
DataSage AI - Background Task Processing Pipeline
==================================================
Production-grade Celery worker orchestrating intelligent data pipeline:

Pipeline Stages:
1. Data Loading & Cleaning (duplicate removal, type normalization)
2. Domain Detection (hybrid rule-based + LLM approach)
3. Data Profiling (cardinality, patterns, quality metrics)
4. Statistical Analysis (correlations, distributions, outliers)
5. Chart Recommendations (intelligent visualization suggestions)
6. Metadata Generation (comprehensive dataset context)
7. Vector Indexing (semantic search with FAISS)
8. Progress Tracking (granular status updates)

Author: DataSage AI Team
Version: 2.0 (Production)
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import math

# Add backend directory to Python path for imports in Celery worker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import polars as pl
from celery import Celery
from celery.signals import worker_process_init
from pymongo import MongoClient
from bson import ObjectId

# Service imports
from services.analysis.analysis_service import analysis_service
from services.analysis.insight_interpreter import insight_interpreter
from services.datasets.faiss_vector_service import faiss_vector_service
from services.datasets.domain_detector import domain_detector
from services.datasets.data_profiler import data_profiler
from services.datasets.chart_recommender import chart_recommender

# API imports for insights generation
from api.insights import get_comprehensive_insights

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =================================================================================
# CELERY & DATABASE CONFIGURATION
# =================================================================================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "datasage_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_concurrency=1,  # Keep 1 core free for FastAPI on low-resource machines
)

MONGO_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "datasage_ai")

# Global database connection (worker process-specific)
db_conn = None


@worker_process_init.connect
def init_worker_db(**kwargs):
    """
    Initialize fork-safe database connection for each worker process.
    Called automatically when worker starts.

    Initializes BOTH sync and async connections:
    - Sync (db_conn): Used directly by tasks for updates
    - Async (db.database): Required by ai_designer_service, insights generation, etc.
    """
    global db_conn
    global _worker_loop
    logger.info("Initializing database connection for worker process...")
    try:
        # 1. Initialize synchronous connection (existing - used by task itself)
        client = MongoClient(MONGO_URL, maxPoolSize=10, minPoolSize=1)
        db_conn = client[DATABASE_NAME]

        # 2. Initialize async connection for async services (NEW)
        # This is required by ai_designer_service, insights generation, etc.
        from db.database import connect_to_mongo

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_loop = loop
        loop.run_until_complete(connect_to_mongo())

        logger.info("✓ Database connections initialized successfully (sync + async)")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database connection: {e}")
        raise


# =================================================================================
# HELPER FUNCTIONS
# =================================================================================

# Worker-level event loop for async operations (avoids creating new loops per call)
_worker_loop = None


_worker_loop = None


def run_async(coro):
    """
    Run an async coroutine in the Celery worker safely.

    Uses a persistent event loop that is created once per worker process
    and reused for all async calls. This avoids event loop issues when
    mixing Celery workers with async code.

    Args:
        coro: Async coroutine to execute

    Returns:
        Result of the coroutine
    """
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)


def _convert_types_for_json(obj):
    """
    Recursively convert special types to JSON-serializable Python native types.
    Handles: datetime, ObjectId, numpy types, Polars types, inf/nan, etc.
    """
    if isinstance(obj, dict):
        return {k: _convert_types_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_types_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, pl.Date, pl.Datetime)):
        return obj.isoformat()
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif hasattr(obj, "item"):  # numpy/polars scalars
        return obj.item()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def _update_progress(
    task_instance,
    datasets_collection,
    dataset_id: str,
    status: str,
    progress: int,
    stage: Optional[str] = None,
):
    """
    Update task progress in Celery state and MongoDB.

    Args:
        task_instance: Celery task self instance
        datasets_collection: MongoDB collection
        dataset_id: Dataset identifier
        status: Status message
        progress: Progress percentage (0-100)
        stage: Optional processing stage name
    """
    meta = {"status": status, "progress": progress}
    if stage:
        meta["stage"] = stage

    task_instance.update_state(state="PROGRESS", meta=meta)

    update_doc = {
        "processing_status": stage or status.lower().replace(" ", "_"),
        "processing_progress": progress,
        "updated_at": datetime.utcnow(),
    }

    datasets_collection.update_one({"_id": dataset_id}, {"$set": update_doc})

    logger.info(f"[{dataset_id}] {status} ({progress}%)")


def _extract_sample_rows(df: pl.DataFrame, n: int = 5) -> List[Dict]:
    """
    Extract sample rows from DataFrame for LLM context.

    Args:
        df: Polars DataFrame
        n: Number of sample rows to extract

    Returns:
        List of dictionaries representing sample rows
    """
    try:
        sample_df = df.head(n)
        return sample_df.to_dicts()
    except Exception as e:
        logger.warning(f"Failed to extract sample rows: {e}")
        return []


# =================================================================================
# MAIN BACKGROUND TASK - INTELLIGENT DATA PIPELINE
# =================================================================================


@celery_app.task(bind=True, name="datasage.process_dataset", max_retries=3)
def process_dataset_task(
    self, dataset_id: str, file_path: str, user_id: str = "unknown"
):
    """
    Production-grade dataset processing pipeline with intelligence layer.

    Pipeline stages:
    1. Load & Clean: Read file, normalize data, remove duplicates
    2. Domain Detection: Identify dataset domain (automotive, healthcare, etc.)
    3. Data Profiling: Cardinality, patterns, quality metrics
    4. Statistical Analysis: Correlations, distributions, outliers
    5. Chart Recommendations: Pre-compute visualization suggestions
    6. Metadata Generation: Comprehensive dataset context
    7. Vector Indexing: FAISS semantic search indexing

    Args:
        dataset_id: Unique dataset identifier
        file_path: Absolute path to uploaded file
        user_id: User who owns the dataset

    Returns:
        Dict with processing results and metadata
    """
    logger.info(f"╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║ DATASET PROCESSING STARTED: {dataset_id:<30} ║")
    logger.info(f"╚════════════════════════════════════════════════════════════════╝")

    # Ensure worker database connection exists
    if db_conn is None:
        init_worker_db()

    datasets_collection = db_conn.uploads

    try:
        # =========================================================================
        # STAGE 1: LOAD & VALIDATE
        # =========================================================================
        _update_progress(
            self, datasets_collection, dataset_id, "Loading dataset", 5, "loading"
        )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        file_extension = file_path.split(".")[-1].lower()
        logger.info(f"Loading {file_extension.upper()} file: {file_path}")

        # Load dataset based on file type
        if file_extension == "csv":
            df = pl.read_csv(file_path, infer_schema_length=10000, ignore_errors=True)
        elif file_extension in ["xlsx", "xls"]:
            df = pl.read_excel(file_path)
        elif file_extension == "json":
            df = pl.read_json(file_path)
        elif file_extension == "parquet":
            df = pl.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        # Validate dataset
        if df.is_empty():
            raise ValueError("Dataset is empty")

        if len(df.columns) == 0:
            raise ValueError("Dataset has no columns")

        # ── Universal numeric coercion ────────────────────────────────────
        # Polars read_csv with ignore_errors=True silently loads numeric
        # columns as String when it hits ANY non-numeric value: comma
        # thousand separators ("1,648"), currency symbols ("$408"),
        # EU formats ("1.648,50"), parenthetical negatives ("(100)"),
        # percent strings ("45%"), repeated headers ("sales"), or
        # Excel null conventions ("-", "N/A", "--").
        #
        # This block detects and coerces those columns back to Float64
        # so aggregations (SUM, MEAN) work on any dataset from any locale.
        # ─────────────────────────────────────────────────────────────────

        import re as _re

        _NULL_SENTINELS = frozenset(
            {
                "",
                "-",
                "--",
                "---",
                "N/A",
                "n/a",
                "NA",
                "na",
                "null",
                "NULL",
                "None",
                "none",
                "NaN",
                "nan",
                "True",
                "False",
                "TRUE",
                "FALSE",
                "#N/A",
                "#VALUE!",
                "#REF!",
                "#DIV/0!",
                "inf",
                "-inf",
                "Inf",
                "-Inf",
            }
        )

        def _try_parse_numeric(val: str) -> float | None:
            if not isinstance(val, str):
                return None
            v = val.strip()
            if v in _NULL_SENTINELS:
                return None
            paren = _re.match(r"^\(([\d,. ]+)\)$", v)
            if paren:
                v = "-" + paren.group(1)
            v = _re.sub(r"[£$€¥₹₩₪₨฿]", "", v)
            v = _re.sub(r"\s*[A-Z]{2,4}$", "", v)
            v = v.replace("%", "")
            v = _re.sub(r"(?<=\d) (?=\d)", "", v)
            v = v.strip()
            if not v:
                return None
            if _re.match(r"^\d{1,3}(\.\d{3})*,\d{1,2}$", v):
                v = v.replace(".", "").replace(",", ".")
            elif _re.match(r"^\d+,\d{1,2}$", v):
                v = v.replace(",", ".")
            elif _re.match(r"^-?[\d,]+$", v) and "," in v:
                v = v.replace(",", "")
            try:
                return float(v)
            except ValueError:
                return None

        _SAMPLE_SIZE = 200
        _THRESHOLD = 0.80
        _MIN_SAMPLE = 5

        coerce_cols: list[str] = []
        for _col in df.columns:
            if df[_col].dtype not in (pl.Utf8, pl.String):
                continue
            _sample = df[_col].drop_nulls().head(_SAMPLE_SIZE).to_list()
            if len(_sample) < _MIN_SAMPLE:
                continue
            _parsed = [_try_parse_numeric(v) for v in _sample]
            _numeric_count = sum(1 for v in _parsed if v is not None)
            if _numeric_count / len(_sample) >= _THRESHOLD:
                coerce_cols.append(_col)

        if coerce_cols:
            _coerce_exprs = []
            for _col in coerce_cols:
                expr = (
                    pl.col(_col)
                    .str.strip_chars()
                    .str.replace_all(r"^\((.+)\)$", r"-$1")
                    .str.replace_all(r"[£$€¥₹₩₪₨฿]", "")
                    .str.replace_all(r"\s+[A-Z]{2,4}$", "")
                    .str.replace_all(r"%$", "")
                    .str.replace_all(r"(\d) (\d)", r"$1$2")
                    .str.replace_all(r"\.(\d{3})", "█TEMP█$1")
                    .str.replace_all(r",", ".")
                    .str.replace_all(r"█TEMP█", ",")
                    .str.replace_all(r",(\d{3})([^0-9]|$)", r"$1$2")
                    .str.strip_chars()
                    .cast(pl.Float64, strict=False)
                    .alias(_col)
                )
                _coerce_exprs.append(expr)

            df = df.with_columns(_coerce_exprs)
            logger.info(
                f"✓ Numeric coercion: {len(coerce_cols)} columns promoted "
                f"String→Float64: {coerce_cols}"
            )
        # ──────────────────────────────────────────────────────────────────

        # Convert to lazy for better performance
        df_lazy = df.lazy()
        original_rows = len(df)
        schema = df.schema

        logger.info(f"✓ Loaded: {original_rows:,} rows × {len(schema):,} columns")

        # =========================================================================
        # STAGE 2: DATA CLEANING
        # =========================================================================
        _update_progress(
            self, datasets_collection, dataset_id, "Cleaning dataset", 15, "cleaning"
        )

        # Identify column types
        string_columns = [
            name
            for name, dtype in schema.items()
            if dtype == pl.Utf8 or dtype == pl.String
        ]
        numeric_columns = [
            name
            for name, dtype in schema.items()
            if dtype
            in [
                pl.Float64,
                pl.Int64,
                pl.Float32,
                pl.Int32,
                pl.Int16,
                pl.Int8,
                pl.UInt64,
                pl.UInt32,
                pl.UInt16,
                pl.UInt8,
            ]
        ]

        # Clean string columns
        if string_columns:
            df_lazy = df_lazy.with_columns(
                [pl.col(col).str.strip_chars().alias(col) for col in string_columns]
            )

            # Handle null representations
            for col in string_columns:
                df_lazy = df_lazy.with_columns(
                    [
                        pl.when(
                            pl.col(col).str.contains(
                                r"(?i)(N/A|null|NULL|none|NONE|^$)"
                            )
                        )
                        .then(None)
                        .otherwise(pl.col(col))
                        .alias(col)
                    ]
                )

        # Clean numeric columns (handle inf/nan)
        if numeric_columns:
            for col in numeric_columns:
                df_lazy = df_lazy.with_columns(
                    [
                        pl.when(pl.col(col).is_infinite() | pl.col(col).is_nan())
                        .then(None)
                        .otherwise(pl.col(col))
                        .alias(col)
                    ]
                )

        # Handle duplicate column names
        df_columns = list(schema.keys())
        seen_columns = {}
        rename_dict = {}

        for col in df_columns:
            if col in seen_columns:
                seen_columns[col] += 1
                new_col_name = f"{col}_{seen_columns[col]}"
                rename_dict[col] = new_col_name
            else:
                seen_columns[col] = 0

        if rename_dict:
            df_lazy = df_lazy.rename(rename_dict)
            logger.info(f"✓ Renamed {len(rename_dict)} duplicate columns")

        # Remove duplicate rows
        df_lazy = df_lazy.unique()

        # Collect the lazy dataframe — use streaming for large datasets to reduce peak memory
        try:
            df = df_lazy.collect(streaming=True)
        except Exception:
            # Streaming not supported for all operations; fallback to eager
            df = df_lazy.collect()
        cleaned_rows = len(df)
        duplicates_removed = original_rows - cleaned_rows

        if duplicates_removed > 0:
            logger.info(
                f"✓ Removed {duplicates_removed:,} duplicate rows ({duplicates_removed / original_rows * 100:.1f}%)"
            )

        logger.info(f"✓ Cleaned: {cleaned_rows:,} rows × {len(df.columns):,} columns")

        # =========================================================================
        # STAGE 2b: SAVE AS PARQUET (10-50× faster reads on future dashboard views)
        # =========================================================================
        parquet_path = None
        try:
            parquet_path = file_path.rsplit(".", 1)[0] + ".parquet"
            df.write_parquet(parquet_path, compression="zstd")
            parquet_size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
            logger.info(f"✓ Saved Parquet: {parquet_path} ({parquet_size_mb:.1f}MB)")
        except Exception as e:
            logger.warning(f"Parquet save failed (non-fatal): {e}")
            parquet_path = None

        # =========================================================================
        # STAGE 3: METADATA GENERATION
        # =========================================================================
        _update_progress(
            self, datasets_collection, dataset_id, "Generating metadata", 25, "metadata"
        )

        # Generate basic column metadata
        column_metadata = []
        for col in df.columns:
            col_data = df[col]
            col_meta = {
                "name": col,
                "type": str(col_data.dtype),
                "null_count": col_data.null_count(),
                "null_percentage": round((col_data.null_count() / len(df)) * 100, 2)
                if len(df) > 0
                else 0,
                "unique_count": col_data.n_unique(),
            }

            # Numeric columns: store range + mean so LLM can make binning/scale decisions
            if col_data.dtype in pl.NUMERIC_DTYPES:
                try:
                    col_meta["numeric_summary"] = {
                        "min": float(col_data.min())
                        if col_data.min() is not None
                        else None,
                        "max": float(col_data.max())
                        if col_data.max() is not None
                        else None,
                        "mean": round(float(col_data.mean()), 2)
                        if col_data.mean() is not None
                        else None,
                    }
                except Exception:
                    pass

            # Boolean + low-cardinality columns: store actual values for LLM context
            elif col_data.dtype == pl.Boolean or col_data.n_unique() <= 20:
                try:
                    col_meta["top_values"] = [
                        {"value": str(v), "count": int((col_data == v).sum())}
                        for v in col_data.drop_nulls().unique().to_list()[:10]
                    ]
                except Exception:
                    pass

            # String columns with manageable cardinality: store top values
            elif col_data.dtype == pl.Utf8 and col_data.n_unique() < 100:
                try:
                    vc = df.group_by(col).len().sort("len", descending=True).head(10)
                    col_meta["top_values"] = [
                        {"value": row[col], "count": row["len"]}
                        for row in vc.to_dicts()
                    ]
                except Exception:
                    pass

            column_metadata.append(col_meta)

        logger.info(f"✓ Generated metadata for {len(column_metadata)} columns")

        # =========================================================================
        # STAGE 4: DOMAIN DETECTION (HYBRID APPROACH)
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Detecting domain",
            35,
            "domain_detection",
        )

        try:
            # Extract sample rows for LLM context
            sample_rows = _extract_sample_rows(df, n=5)

            # Run hybrid domain detection (rule-based + LLM)
            domain_info = run_async(
                domain_detector.detect_domain_hybrid(
                    df=df, column_metadata=column_metadata, sample_rows=sample_rows
                )
            )

            logger.info(
                f"✓ Domain detected: {domain_info['domain']} (confidence: {domain_info['confidence']}, method: {domain_info['method']})"
            )
        except Exception as e:
            logger.warning(f"Domain detection failed: {e}, defaulting to 'general'")
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

        # =========================================================================
        # STAGE 5: DATA PROFILING
        # =========================================================================
        _update_progress(
            self, datasets_collection, dataset_id, "Profiling data", 45, "profiling"
        )

        try:
            profile_info = data_profiler.profile_dataset(df, column_metadata)
            logger.info(
                f"✓ Profiled: {profile_info['row_count']:,} rows, {profile_info['column_count']} columns"
            )
            logger.info(f"  - ID columns: {len(profile_info['id_columns'])}")
            logger.info(
                f"  - Low-cardinality dimensions: {len(profile_info['low_cardinality_dims'])}"
            )
            logger.info(
                f"  - High-cardinality dimensions: {len(profile_info['high_cardinality_dims'])}"
            )
        except Exception as e:
            logger.warning(f"Data profiling failed: {e}")
            profile_info = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "cardinality": {},
                "patterns": {},
                "quality_metrics": {},
                "relationships": {},
                "id_columns": [],
                "high_cardinality_dims": [],
                "low_cardinality_dims": [],
            }

        # =========================================================================
        # STAGE 6: DEEP STATISTICAL ANALYSIS
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Running deep statistical analysis",
            55,
            "analysis",
        )

        # 6a: Enhanced analysis (hypothesis tests, CIs, effect sizes, distributions)
        try:
            enhanced_results = analysis_service.run_enhanced_analysis(
                df, depth="standard"
            )
            logger.info(
                f"✓ Enhanced analysis complete: {len(enhanced_results)} sections"
            )
        except Exception as e:
            logger.warning(f"Enhanced analysis failed: {e}")
            enhanced_results = {
                "depth": "fallback",
                "row_count": len(df),
                "column_count": len(df.columns),
                "distributions": [],
                "correlations": [],
            }

        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Running QUIS subspace analysis",
            65,
            "quis_analysis",
        )

        # 6b: Enhanced QUIS sync (beam search subspace exploration, FDR correction)
        try:
            quis_results = analysis_service.run_enhanced_quis_sync(
                df, dataset_id=dataset_id
            )
            logger.info(
                f"✓ Enhanced QUIS complete: {quis_results.get('summary', {}).get('significant_insights', 0)} significant insights"
            )
        except Exception as e:
            logger.warning(f"Enhanced QUIS failed: {e}")
            quis_results = {
                "summary": {"total_questions": 0, "significant_insights": 0},
                "insights": [],
                "top_insights": [],
            }

        # 6c: Generate professional text summary
        try:
            executive_summary = insight_interpreter.generate_summary(enhanced_results)
            logger.info(f"✓ Executive summary generated")
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            executive_summary = ""

        # 6d: Also run basic checks for backward compatibility
        try:
            statistical_findings = analysis_service.run_all_statistical_checks(df)
            logger.info(f"✓ Basic statistical checks complete")
        except Exception as e:
            logger.warning(f"Basic statistical analysis failed: {e}")
            statistical_findings = {
                "correlations": [],
                "outliers": [],
                "distributions": {},
            }

        # Consolidate deep analysis results
        deep_analysis = {
            "enhanced_analysis": enhanced_results,
            "quis_insights": quis_results,
            "executive_summary": executive_summary,
            "analysis_version": "2.0",
        }

        # =========================================================================
        # STAGE 7: CHART RECOMMENDATIONS
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Generating chart recommendations",
            70,
            "charts",
        )

        try:
            chart_recommendations = chart_recommender.recommend_charts(
                df=df,
                column_metadata=column_metadata,
                domain=domain_info["domain"],
                cardinality=profile_info.get("cardinality", {}),
                time_columns=domain_info.get("time_columns", []),
            )
            logger.info(
                f"✓ Generated {len(chart_recommendations)} chart recommendations"
            )
        except Exception as e:
            logger.warning(f"Chart recommendation failed: {e}")
            chart_recommendations = []

        # =========================================================================
        # STAGE 8: QUALITY METRICS
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Calculating quality metrics",
            80,
            "quality",
        )

        total_nulls = sum(col["null_count"] for col in column_metadata)
        total_cells = len(df) * len(df.columns)

        data_quality = {
            "completeness": round(100.0 - (total_nulls / total_cells * 100), 2)
            if total_cells > 0
            else 100.0,
            "uniqueness": round(100.0 - (duplicates_removed / original_rows * 100), 2)
            if original_rows > 0
            else 100.0,
            "duplicates_removed": duplicates_removed,
            "original_rows": original_rows,
            "cleaned_rows": cleaned_rows,
            "data_cleaning_applied": True,
            "null_cells": total_nulls,
            "total_cells": total_cells,
        }

        logger.info(
            f"✓ Quality metrics: {data_quality['completeness']:.1f}% complete, {data_quality['uniqueness']:.1f}% unique"
        )

        # =========================================================================
        # STAGE 9: CONSOLIDATE METADATA
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Consolidating metadata",
            85,
            "consolidating",
        )

        final_metadata = {
            "dataset_overview": {
                "total_rows": cleaned_rows,
                "total_columns": len(df.columns),
                "original_rows": original_rows,
                "file_type": file_extension,
            },
            "column_metadata": column_metadata,
            "domain_intelligence": domain_info,
            "data_profile": profile_info,
            "statistical_findings": statistical_findings,
            "deep_analysis": deep_analysis,
            "chart_recommendations": chart_recommendations,
            "data_quality": data_quality,
            "sample_data": sample_rows[:3],  # Store 3 sample rows
            "processing_info": {
                "processed_at": datetime.utcnow(),
                "pipeline_version": "3.0",
                "celery_task_id": self.request.id,
            },
        }

        # Sanitize metadata (convert special types to JSON-serializable)
        sanitized_metadata = _convert_types_for_json(final_metadata)

        logger.info(f"✓ Metadata consolidation complete")

        # =========================================================================
        # STAGE 10: SAVE TO DATABASE
        # =========================================================================
        _update_progress(
            self, datasets_collection, dataset_id, "Saving to database", 90, "saving"
        )

        update_fields = {
            "metadata": sanitized_metadata,
            "is_processed": True,
            "processing_status": "success",
            "row_count": cleaned_rows,
            "column_count": len(df.columns),
            "domain": domain_info["domain"],
            "domain_confidence": domain_info["confidence"],
            "updated_at": datetime.utcnow(),
        }
        if parquet_path:
            update_fields["parquet_path"] = parquet_path

        datasets_collection.update_one({"_id": dataset_id}, {"$set": update_fields})

        logger.info(f"✓ Saved to database")

        # =========================================================================
        # STAGE 10a: SAVE ANALYTICS TO SEPARATE COLLECTION (NEW)
        # =========================================================================
        try:
            analytics_collection = db_conn.dataset_analytics
            analytics_doc = {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "chart_recommendations": _convert_types_for_json(chart_recommendations),
                "statistical_findings": _convert_types_for_json(statistical_findings),
                "deep_analysis": _convert_types_for_json(deep_analysis),
                "data_profile": _convert_types_for_json(profile_info),
                "domain_intelligence": _convert_types_for_json(domain_info),
                "data_quality": _convert_types_for_json(data_quality),
                "computed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "pipeline_version": "3.0",
            }
            analytics_collection.update_one(
                {"dataset_id": dataset_id, "user_id": user_id},
                {"$set": analytics_doc},
                upsert=True,
            )
            logger.info(f"✓ Saved analytics to dataset_analytics collection")
        except Exception as e:
            logger.warning(f"Failed to save analytics to separate collection: {e}")

        # =========================================================================
        # STAGE 10b: PRECOMPUTE USER-FACING ARTIFACTS
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Pre-computing KPIs",
            90,
            "artifact_generation",
        )

        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "artifact_status.insights_report": "generating",
                    "artifact_status.dashboard_design": "generating",
                }
            },
        )

        # -- Pre-compute KPIs (warmed into cache so first dashboard load is instant) --
        try:
            from services.ai.intelligent_kpi_generator import intelligent_kpi_generator
            from services.cache.dashboard_cache_service import dashboard_cache_service
            from services.datasets.enhanced_dataset_service import (
                enhanced_dataset_service,
            )

            kpi_df = run_async(
                enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
            )
            domain_for_kpi = domain_info.get("domain", "general")
            intelligent_kpis = run_async(
                intelligent_kpi_generator.generate_intelligent_kpis(
                    df=kpi_df,
                    domain=domain_for_kpi,
                    max_kpis=4,  # prompt enforces 3-4 by selection gate
                    dataset_metadata=sanitized_metadata,
                )
            )
            run_async(
                dashboard_cache_service.cache_kpis(
                    dataset_id, user_id, intelligent_kpis
                )
            )
            logger.info(f"✓ Pre-computed and cached {len(intelligent_kpis)} KPIs")
        except Exception as kpi_error:
            logger.warning(f"KPI pre-computation failed (non-fatal): {kpi_error}")

        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Pre-computing charts",
            92,
            "artifact_generation",
        )

        # -- Pre-compute charts (warmed into cache) --
        try:
            from services.charts.chart_render_service import chart_render_service
            from services.charts.chart_intelligence_service import (
                chart_intelligence_service,
            )
            from services.cache.dashboard_cache_service import dashboard_cache_service
            from services.datasets.enhanced_dataset_service import (
                enhanced_dataset_service,
            )

            chart_df = run_async(
                enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
            )
            col_meta = sanitized_metadata.get("column_metadata", [])
            data_profile = sanitized_metadata.get("data_profile", {})
            domain_intel = sanitized_metadata.get("domain_intelligence", {})
            deep_analysis = sanitized_metadata.get("deep_analysis", {})

            numeric_cols = chart_df.select(pl.col(pl.NUMERIC_DTYPES)).columns
            categorical_cols = chart_df.select(pl.col(pl.Utf8, pl.Categorical)).columns

            precomputed_charts = {}
            if numeric_cols and categorical_cols:
                chart_selection = chart_intelligence_service.select_dashboard_charts(
                    df=chart_df,
                    column_metadata=col_meta,
                    domain=domain_intel.get("domain", "general"),
                    domain_confidence=domain_intel.get("confidence", 0.5),
                    statistical_findings=deep_analysis.get("enhanced_analysis", {}),
                    data_profile=data_profile,
                    context="executive",
                )
                for i, chart_spec in enumerate(chart_selection.get("charts", [])[:5]):
                    config = chart_spec.get("config", {})
                    chart_data = run_async(
                        chart_render_service.render_chart(
                            chart_df,
                            {
                                "chart_type": chart_spec.get("chart_type", "bar"),
                                "columns": config.get(
                                    "columns", [categorical_cols[0], numeric_cols[0]]
                                ),
                                "aggregation": config.get("aggregation", "sum"),
                            },
                        )
                    )
                    precomputed_charts[f"chart_{i}"] = chart_data

            if precomputed_charts:
                run_async(
                    dashboard_cache_service.cache_charts(
                        dataset_id, user_id, precomputed_charts
                    )
                )
                logger.info(
                    f"✓ Pre-computed and cached {len(precomputed_charts)} charts"
                )
        except Exception as chart_error:
            logger.warning(f"Chart pre-computation failed (non-fatal): {chart_error}")

        try:
            logger.info("Insights will be generated on-demand from cached analysis")
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "artifact_status.insights_report": "ready",
                        "artifact_status.insights_generated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as insights_error:
            logger.warning(
                f"Failed to update insights artifact status: {insights_error}"
            )

        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Preparing dashboard design",
            94,
            "artifact_generation",
        )

        try:
            from services.ai.ai_designer_service import AIDesignerService

            # Use sync_db for Celery worker to avoid event loop issues
            designer_service = AIDesignerService(sync_db=db_conn)

            run_async(
                designer_service.design_intelligent_dashboard(
                    dataset_id=dataset_id,
                    user_id=user_id,
                    force_regenerate=True,
                )
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
            logger.info("✓ Precomputed dashboard design")
        except Exception as dashboard_error:
            logger.warning(f"Dashboard design precompute failed: {dashboard_error}")
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "artifact_status.dashboard_design": "failed",
                        "artifact_status.dashboard_error": str(dashboard_error)[:500],
                    }
                },
            )

        # =========================================================================
        # STAGE 11: VECTOR INDEXING (FAISS)
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Indexing to vector database",
            95,
            "vector_indexing",
        )

        try:
            vector_success = run_async(
                faiss_vector_service.add_dataset_to_vector_db(
                    dataset_id=dataset_id,
                    dataset_metadata=sanitized_metadata,
                    user_id=user_id,
                )
            )

            if vector_success:
                logger.info(f"✓ Vector indexing successful")
            else:
                logger.warning(f"⚠ Vector indexing returned False")
        except Exception as vector_error:
            logger.error(f"✗ Vector indexing failed: {vector_error}")

        # =========================================================================
        # COMPLETION
        # =========================================================================
        _update_progress(
            self,
            datasets_collection,
            dataset_id,
            "Processing complete",
            100,
            "completed",
        )

        logger.info(
            f"╔════════════════════════════════════════════════════════════════╗"
        )
        logger.info(f"║ DATASET PROCESSING COMPLETED: {dataset_id:<27} ║")
        logger.info(
            f"║ Domain: {domain_info['domain']:<40} Confidence: {domain_info['confidence']:<5} ║"
        )
        logger.info(
            f"║ Rows: {cleaned_rows:,<10}  Columns: {len(df.columns):<10}  Quality: {data_quality['completeness']:.1f}% ║"
        )
        logger.info(
            f"╚════════════════════════════════════════════════════════════════╝"
        )

        return {
            "status": "success",
            "progress": 100,
            "dataset_id": dataset_id,
            "rows": cleaned_rows,
            "columns": len(df.columns),
            "domain": domain_info["domain"],
            "quality": data_quality["completeness"],
        }

    except Exception as e:
        logger.error(
            f"╔════════════════════════════════════════════════════════════════╗"
        )
        logger.error(f"║ DATASET PROCESSING FAILED: {dataset_id:<30} ║")
        logger.error(f"║ Error: {str(e)[:50]:<54} ║")
        logger.error(
            f"╚════════════════════════════════════════════════════════════════╝"
        )
        logger.exception(e)

        # Update database with failure status
        if db_conn is not None:
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

        # Update Celery state
        error_message = str(e)
        if len(error_message) > 1000:
            error_message = error_message[:1000] + "..."

        self.update_state(
            state="FAILURE",
            meta={
                "status": "Processing failed",
                "error": error_message,
                "error_type": type(e).__name__,
                "dataset_id": dataset_id,
            },
        )

        raise  # Re-raise for Celery's retry mechanism


# =================================================================================
# VECTOR DATABASE TASKS
# =================================================================================


@celery_app.task(bind=True, name="datasage.index_dataset_vector", max_retries=3)
def index_dataset_to_vector_db(
    self, dataset_id: str, dataset_metadata: Dict, user_id: str
):
    """
    Index dataset to FAISS vector database for semantic search.

    Args:
        dataset_id: Dataset identifier
        dataset_metadata: Complete dataset metadata
        user_id: User identifier

    Returns:
        bool: Success status
    """
    logger.info(f"Indexing dataset {dataset_id} to vector database...")

    try:
        success = run_async(
            faiss_vector_service.add_dataset_to_vector_db(
                dataset_id=dataset_id,
                dataset_metadata=dataset_metadata,
                user_id=user_id,
            )
        )

        if success:
            logger.info(f"✓ Successfully indexed dataset {dataset_id}")
        else:
            logger.warning(f"⚠ Vector indexing returned False for {dataset_id}")

        return success

    except Exception as e:
        logger.error(f"✗ Vector indexing failed for {dataset_id}: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_in = 2**self.request.retries  # 2, 4, 8 seconds
            logger.info(
                f"Retrying in {retry_in} seconds... (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=retry_in)
        else:
            logger.error(f"Max retries reached for dataset {dataset_id}")
            return False


@celery_app.task(name="datasage.add_query_history")
def add_query_to_vector_history(
    query_text: str, dataset_id: str, response: str, user_id: str
):
    """
    Add user query to vector history for semantic search.

    Args:
        query_text: User's query
        dataset_id: Associated dataset
        response: AI response
        user_id: User identifier

    Returns:
        bool: Success status
    """
    try:
        success = run_async(
            faiss_vector_service.add_query_to_history(
                query_text=query_text,
                dataset_id=dataset_id,
                response=response,
                user_id=user_id,
            )
        )

        if success:
            logger.info(f"✓ Added query to history: '{query_text[:50]}...'")

        return success

    except Exception as e:
        logger.error(f"✗ Failed to add query to history: {e}")
        return False


# =================================================================================
# NARRATIVE STORY GENERATION TASK
# =================================================================================


@celery_app.task(bind=True, name="datasage.generate_narrative_story", max_retries=2)
def generate_narrative_story_task(self, dataset_id: str, user_id: str = "unknown"):
    """
    Background task for narrative story generation.

    This task is triggered after initial insights are ready and generates
    the narrative story asynchronously to avoid blocking the API response.

    The story is cached in the dataset document and persists until explicit refresh.

    Args:
        dataset_id: Dataset identifier
        user_id: User identifier (for logging)

    Returns:
        Dict with generation status and story data
    """
    logger.info(f"╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║ NARRATIVE STORY GENERATION STARTED: {dataset_id:<25} ║")
    logger.info(f"╚════════════════════════════════════════════════════════════════╝")

    # Ensure worker database connection exists
    if db_conn is None:
        init_worker_db()

    datasets_collection = db_conn.uploads

    try:
        # Update status to generating
        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "artifact_status.narrative_story": "generating",
                    "story_generation_started_at": datetime.utcnow(),
                }
            },
        )

        # Run the story weaving
        from services.narrative.story_weaver import story_weaver

        # Get dataset info for context
        dataset_doc = datasets_collection.find_one({"_id": dataset_id})
        if not dataset_doc:
            raise ValueError(f"Dataset not found: {dataset_id}")

        dataset_name = dataset_doc.get("name", "Unknown")
        domain = dataset_doc.get("domain", "general")

        # Get analysis results from metadata if available
        metadata = dataset_doc.get("metadata", {})
        deep_analysis = metadata.get("deep_analysis", {})
        statistical_findings = metadata.get("statistical_findings", {})

        # Generate the story
        narrative_story = run_async(
            story_weaver.weave_story(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                domain=domain,
                correlations=[],
                anomalies=[],
                trends=[],
                segments=[],
                key_findings=[],
                distributions=[],
                driver_analysis=[],
                data_quality={},
                recommendations=[],
            )
        )

        if narrative_story:
            # Cache the story permanently
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "cached_narrative_story": narrative_story,
                        "cached_story_generated_at": datetime.utcnow(),
                        "cached_story_version": "2.0",
                        "artifact_status.narrative_story": "ready",
                        "story_generation_completed_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"✓ Narrative story generated and cached for {dataset_id}")

            return {
                "status": "success",
                "dataset_id": dataset_id,
                "story_generated": True,
            }
        else:
            # Story generation returned None
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "artifact_status.narrative_story": "failed",
                        "story_generation_error": "Story generation returned None",
                        "story_generation_completed_at": datetime.utcnow(),
                    }
                },
            )
            logger.warning(
                f"⚠ Narrative story generation returned None for {dataset_id}"
            )

            return {
                "status": "failed",
                "dataset_id": dataset_id,
                "story_generated": False,
                "error": "Story generation returned None",
            }

    except Exception as e:
        logger.error(f"✗ Narrative story generation failed for {dataset_id}: {e}")

        # Update status to failed
        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "artifact_status.narrative_story": "failed",
                    "story_generation_error": str(e)[:500],
                    "story_generation_completed_at": datetime.utcnow(),
                }
            },
        )

        # Retry if retries remaining
        if self.request.retries < self.max_retries:
            retry_in = 2**self.request.retries * 10  # 20, 40 seconds
            logger.info(
                f"Retrying story generation in {retry_in}s... (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=retry_in)

        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "story_generated": False,
            "error": str(e),
        }


# =================================================================================
# DATA RETENTION & PRIVACY TASKS
# =================================================================================


@celery_app.task(bind=True, name="cleanup_expired_datasets")
def cleanup_expired_datasets(self):
    """
    Celery task to clean up datasets past their retention period.

    This task:
    1. Queries datasets where (created_at + retention_days) < now()
    2. Sends warning emails 7 days before deletion
    3. Deletes datasets past grace period
    4. Logs all deletion events
    """
    try:
        # Get all users with privacy settings
        privacy_collection = db_conn["privacy_settings"]
        datasets_collection = db_conn["uploads"]
        users_collection = db_conn["users"]

        # Find all datasets
        all_datasets = list(datasets_collection.find({}))

        deleted_count = 0
        warned_count = 0

        for dataset in all_datasets:
            user_id = dataset.get("user_id")
            dataset_id = dataset.get("_id")
            created_at = dataset.get("created_at")

            if not created_at or not user_id:
                continue

            # Get user's retention settings
            user_privacy = privacy_collection.find_one({"user_id": user_id})
            retention_days = 90  # Default

            if user_privacy:
                retention_days = user_privacy.get("global_defaults", {}).get(
                    "data_retention_days", 90
                )

            if retention_days == -1:  # Forever
                continue

            # Calculate expiration date
            from datetime import timedelta

            expiration_date = created_at + timedelta(days=retention_days)
            warning_date = expiration_date - timedelta(days=7)

            now = datetime.utcnow()

            # Check if past warning date but not yet expired
            if warning_date <= now < expiration_date:
                # Send warning email (if enabled)
                if user_privacy.get("global_defaults", {}).get(
                    "send_retention_warnings", True
                ):
                    user = users_collection.find_one({"_id": user_id})
                    if user and user.get("email"):
                        # TODO: Send email via notification service
                        logger.info(
                            f"[RETENTION] Warning for dataset {dataset_id} to user {user_id}"
                        )
                        warned_count += 1

            # Check if past expiration date
            if now >= expiration_date:
                # Delete the dataset
                file_path = dataset.get("file_path")
                parquet_path = dataset.get("parquet_path")

                # Delete files
                import os

                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                if parquet_path and os.path.exists(parquet_path):
                    os.remove(parquet_path)

                # Delete from MongoDB
                datasets_collection.delete_one({"_id": dataset_id})

                # Delete related data (conversations, audit logs, etc.)
                db_conn["conversations"].delete_many({"dataset_id": str(dataset_id)})
                db_conn["audit_logs"].delete_many({"dataset_id": str(dataset_id)})

                logger.info(
                    f"[RETENTION] Deleted expired dataset {dataset_id} for user {user_id}"
                )
                deleted_count += 1

        return {
            "status": "success",
            "datasets_deleted": deleted_count,
            "warnings_sent": warned_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[RETENTION] Cleanup task failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="cleanup_privacy_audit_logs")
def cleanup_privacy_audit_logs(self):
    """
    Celery task to clean up old privacy audit logs.

    Audit logs are retained for 90 days by default, then deleted
    for privacy compliance and storage management.
    """
    try:
        audit_collection = db_conn["privacy_audit_log"]

        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=90)

        result = audit_collection.delete_many(
            {"timestamp": {"$lt": cutoff.isoformat()}}
        )

        deleted_count = result.deleted_count
        logger.info(f"[AUDIT CLEANUP] Deleted {deleted_count} old privacy audit logs")

        return {
            "status": "success",
            "logs_deleted": deleted_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[AUDIT CLEANUP] Failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="scan_dataset_pii")
def scan_dataset_pii(self, dataset_id: str):
    """
    Async task to scan a dataset for PII after processing completes.

    This runs after the main dataset processing pipeline to automatically
    detect and flag potentially sensitive columns.
    """
    try:
        from services.privacy import pii_detector, privacy_audit_service

        datasets_collection = db_conn["uploads"]

        # Get dataset
        dataset = datasets_collection.find_one({"_id": dataset_id})
        if not dataset:
            return {"status": "failed", "error": "Dataset not found"}

        # Get file path
        file_path = dataset.get("file_path")
        parquet_path = dataset.get("parquet_path")

        if not file_path:
            return {"status": "failed", "error": "File path not found"}

        # Try to read data
        import os

        data_path = (
            parquet_path if parquet_path and os.path.exists(parquet_path) else file_path
        )

        try:
            df = pl.read_parquet(data_path)
        except Exception:
            try:
                df = pl.read_csv(data_path)
            except Exception as e:
                return {"status": "failed", "error": f"Failed to read file: {e}"}

        # Convert to dict
        data = {col: df[col].to_list() for col in df.columns}

        # Scan for PII
        scan_result = pii_detector.scan_dataset(
            dataset_id=str(dataset_id),
            columns=list(df.columns),
            data=data,
            sample_size=100,
        )

        # Store PII scan results in dataset document
        pii_columns = [
            {
                "column": c.column_name,
                "pii_type": c.pii_type.value if c.pii_type else None,
                "confidence": c.confidence,
                "should_redact": c.should_redact,
            }
            for c in scan_result.columns_with_pii
        ]

        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "pii_scan_result": {
                        "scanned_at": datetime.utcnow().isoformat(),
                        "columns_with_pii": pii_columns,
                        "total_detected": scan_result.total_pii_detections,
                    }
                }
            },
        )

        # Log the scan
        import asyncio

        asyncio.run(
            privacy_audit_service.log_pii_scan(
                user_id=dataset.get("user_id"),
                dataset_id=str(dataset_id),
                columns_found=list(df.columns),
                pii_detected=pii_columns,
                confidence_scores={
                    c.column_name: c.confidence for c in scan_result.columns_with_pii
                },
            )
        )

        logger.info(
            f"[PII SCAN] Completed for dataset {dataset_id}: {scan_result.total_pii_detections} columns detected"
        )

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "pii_detected": scan_result.total_pii_detections,
            "columns_with_pii": pii_columns,
        }

    except Exception as e:
        logger.error(f"[PII SCAN] Failed for {dataset_id}: {e}", exc_info=True)
        return {"status": "failed", "dataset_id": dataset_id, "error": str(e)}
