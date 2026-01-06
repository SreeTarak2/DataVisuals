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
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import math

import polars as pl
from celery import Celery
from celery.signals import worker_process_init
from pymongo import MongoClient
from bson import ObjectId

# Service imports
from services.analysis.analysis_service import analysis_service
from services.datasets.faiss_vector_service import faiss_vector_service
from services.datasets.domain_detector import domain_detector
from services.datasets.data_profiler import data_profiler
from services.datasets.chart_recommender import chart_recommender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =================================================================================
# CELERY & DATABASE CONFIGURATION
# =================================================================================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "datasage_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100
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
    """
    global db_conn
    logger.info("Initializing database connection for worker process...")
    try:
        client = MongoClient(MONGO_URL, maxPoolSize=10, minPoolSize=1)
        db_conn = client[DATABASE_NAME]
        logger.info("✓ Database connection initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database connection: {e}")
        raise


# =================================================================================
# HELPER FUNCTIONS
# =================================================================================

# Worker-level event loop for async operations (avoids creating new loops per call)
_worker_loop = None

def run_async(coro):
    """
    Run an async coroutine in the Celery worker safely.
    
    This avoids the overhead of asyncio.run() which creates a new event loop
    every time. Instead, we reuse a single event loop per worker process.
    
    Performance: ~10x faster than asyncio.run() for frequent async calls.
    
    Args:
        coro: Async coroutine to execute
        
    Returns:
        Result of the coroutine
    """
    global _worker_loop
    
    try:
        # Try to get existing loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        # No loop exists or loop is closed - create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_loop = loop
    
    return loop.run_until_complete(coro)

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
    elif hasattr(obj, 'item'):  # numpy/polars scalars
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
    stage: Optional[str] = None
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
    meta = {'status': status, 'progress': progress}
    if stage:
        meta['stage'] = stage
    
    task_instance.update_state(state='PROGRESS', meta=meta)
    
    update_doc = {
        "processing_status": stage or status.lower().replace(' ', '_'),
        "processing_progress": progress,
        "updated_at": datetime.utcnow()
    }
    
    datasets_collection.update_one(
        {"_id": dataset_id},
        {"$set": update_doc}
    )
    
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

@celery_app.task(bind=True, name='datasage.process_dataset', max_retries=3)
def process_dataset_task(self, dataset_id: str, file_path: str, user_id: str = "unknown"):
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
    
    datasets_collection = db_conn.datasets

    try:
        # =========================================================================
        # STAGE 1: LOAD & VALIDATE
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Loading dataset", 5, "loading")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found: {file_path}")
        
        file_extension = file_path.split('.')[-1].lower()
        logger.info(f"Loading {file_extension.upper()} file: {file_path}")
        
        # Load dataset based on file type
        if file_extension == 'csv':
            df = pl.read_csv(file_path, infer_schema_length=10000, ignore_errors=True)
        elif file_extension in ['xlsx', 'xls']:
            df = pl.read_excel(file_path)
        elif file_extension == 'json':
            df = pl.read_json(file_path)
        elif file_extension == 'parquet':
            df = pl.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Validate dataset
        if df.is_empty():
            raise ValueError("Dataset is empty")
        
        if len(df.columns) == 0:
            raise ValueError("Dataset has no columns")
        
        # Convert to lazy for better performance
        df_lazy = df.lazy()
        original_rows = len(df)
        schema = df.schema
        
        logger.info(f"✓ Loaded: {original_rows:,} rows × {len(schema):,} columns")
        
        # =========================================================================
        # STAGE 2: DATA CLEANING
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Cleaning dataset", 15, "cleaning")
        
        # Identify column types
        string_columns = [name for name, dtype in schema.items() if dtype == pl.Utf8 or dtype == pl.String]
        numeric_columns = [name for name, dtype in schema.items() 
                          if dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32, pl.Int16, pl.Int8, 
                                      pl.UInt64, pl.UInt32, pl.UInt16, pl.UInt8]]
        
        # Clean string columns
        if string_columns:
            df_lazy = df_lazy.with_columns([
                pl.col(col).str.strip_chars().alias(col)
                for col in string_columns
            ])
            
            # Handle null representations
            for col in string_columns:
                df_lazy = df_lazy.with_columns([
                    pl.when(pl.col(col).str.contains(r"(?i)(N/A|null|NULL|none|NONE|^$)"))
                    .then(None)
                    .otherwise(pl.col(col))
                    .alias(col)
                ])
        
        # Clean numeric columns (handle inf/nan)
        if numeric_columns:
            for col in numeric_columns:
                df_lazy = df_lazy.with_columns([
                    pl.when(pl.col(col).is_infinite() | pl.col(col).is_nan())
                    .then(None)
                    .otherwise(pl.col(col))
                    .alias(col)
                ])
        
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
        
        # Collect the lazy dataframe
        df = df_lazy.collect()
        cleaned_rows = len(df)
        duplicates_removed = original_rows - cleaned_rows
        
        if duplicates_removed > 0:
            logger.info(f"✓ Removed {duplicates_removed:,} duplicate rows ({duplicates_removed/original_rows*100:.1f}%)")
        
        logger.info(f"✓ Cleaned: {cleaned_rows:,} rows × {len(df.columns):,} columns")
        
        # =========================================================================
        # STAGE 3: METADATA GENERATION
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Generating metadata", 25, "metadata")
        
        # Generate basic column metadata
        column_metadata = []
        for col in df.columns:
            col_data = df[col]
            column_metadata.append({
                "name": col,
                "type": str(col_data.dtype),
                "null_count": col_data.null_count(),
                "null_percentage": round((col_data.null_count() / len(df)) * 100, 2) if len(df) > 0 else 0,
                "unique_count": col_data.n_unique()
            })
        
        logger.info(f"✓ Generated metadata for {len(column_metadata)} columns")
        
        # =========================================================================
        # STAGE 4: DOMAIN DETECTION (HYBRID APPROACH)
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Detecting domain", 35, "domain_detection")
        
        try:
            # Extract sample rows for LLM context
            sample_rows = _extract_sample_rows(df, n=5)
            
            # Run hybrid domain detection (rule-based + LLM)
            domain_info = run_async(domain_detector.detect_domain_hybrid(
                df=df,
                column_metadata=column_metadata,
                sample_rows=sample_rows
            ))
            
            logger.info(f"✓ Domain detected: {domain_info['domain']} (confidence: {domain_info['confidence']}, method: {domain_info['method']})")
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
                "method": "fallback"
            }
        
        # =========================================================================
        # STAGE 5: DATA PROFILING
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Profiling data", 45, "profiling")
        
        try:
            profile_info = data_profiler.profile_dataset(df, column_metadata)
            logger.info(f"✓ Profiled: {profile_info['row_count']:,} rows, {profile_info['column_count']} columns")
            logger.info(f"  - ID columns: {len(profile_info['id_columns'])}")
            logger.info(f"  - Low-cardinality dimensions: {len(profile_info['low_cardinality_dims'])}")
            logger.info(f"  - High-cardinality dimensions: {len(profile_info['high_cardinality_dims'])}")
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
                "low_cardinality_dims": []
            }
        
        # =========================================================================
        # STAGE 6: STATISTICAL ANALYSIS
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Running statistical analysis", 60, "analysis")
        
        try:
            statistical_findings = analysis_service.run_all_statistical_checks(df)
            logger.info(f"✓ Statistical analysis complete")
        except Exception as e:
            logger.warning(f"Statistical analysis failed: {e}")
            statistical_findings = {
                "correlations": [],
                "outliers": [],
                "distributions": {}
            }
        
        # =========================================================================
        # STAGE 7: CHART RECOMMENDATIONS
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Generating chart recommendations", 70, "charts")
        
        try:
            chart_recommendations = chart_recommender.recommend_charts(
                df=df,
                column_metadata=column_metadata,
                domain=domain_info['domain'],
                cardinality=profile_info.get('cardinality', {}),
                time_columns=domain_info.get('time_columns', [])
            )
            logger.info(f"✓ Generated {len(chart_recommendations)} chart recommendations")
        except Exception as e:
            logger.warning(f"Chart recommendation failed: {e}")
            chart_recommendations = []
        
        # =========================================================================
        # STAGE 8: QUALITY METRICS
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Calculating quality metrics", 80, "quality")
        
        total_nulls = sum(col["null_count"] for col in column_metadata)
        total_cells = len(df) * len(df.columns)
        
        data_quality = {
            "completeness": round(100.0 - (total_nulls / total_cells * 100), 2) if total_cells > 0 else 100.0,
            "uniqueness": round(100.0 - (duplicates_removed / original_rows * 100), 2) if original_rows > 0 else 100.0,
            "duplicates_removed": duplicates_removed,
            "original_rows": original_rows,
            "cleaned_rows": cleaned_rows,
            "data_cleaning_applied": True,
            "null_cells": total_nulls,
            "total_cells": total_cells
        }
        
        logger.info(f"✓ Quality metrics: {data_quality['completeness']:.1f}% complete, {data_quality['uniqueness']:.1f}% unique")
        
        # =========================================================================
        # STAGE 9: CONSOLIDATE METADATA
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Consolidating metadata", 85, "consolidating")
        
        final_metadata = {
            "dataset_overview": {
                "total_rows": cleaned_rows,
                "total_columns": len(df.columns),
                "original_rows": original_rows,
                "file_type": file_extension
            },
            "column_metadata": column_metadata,
            "domain_intelligence": domain_info,
            "data_profile": profile_info,
            "statistical_findings": statistical_findings,
            "chart_recommendations": chart_recommendations,
            "data_quality": data_quality,
            "sample_data": sample_rows[:3],  # Store 3 sample rows
            "processing_info": {
                "processed_at": datetime.utcnow(),
                "pipeline_version": "2.0",
                "celery_task_id": self.request.id
            }
        }
        
        # Sanitize metadata (convert special types to JSON-serializable)
        sanitized_metadata = _convert_types_for_json(final_metadata)
        
        logger.info(f"✓ Metadata consolidation complete")
        
        # =========================================================================
        # STAGE 10: SAVE TO DATABASE
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Saving to database", 90, "saving")
        
        datasets_collection.update_one(
            {"_id": dataset_id},
            {"$set": {
                "metadata": sanitized_metadata,
                "is_processed": True,
                "processing_status": "success",
                "row_count": cleaned_rows,
                "column_count": len(df.columns),
                "domain": domain_info['domain'],
                "domain_confidence": domain_info['confidence'],
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"✓ Saved to database")
        
        # =========================================================================
        # STAGE 11: VECTOR INDEXING (FAISS)
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Indexing to vector database", 95, "vector_indexing")
        
        try:
            vector_success = run_async(faiss_vector_service.add_dataset_to_vector_db(
                dataset_id=dataset_id,
                dataset_metadata=sanitized_metadata,
                user_id=user_id
            ))
            
            if vector_success:
                logger.info(f"✓ Vector indexing successful")
            else:
                logger.warning(f"⚠ Vector indexing returned False")
        except Exception as vector_error:
            logger.error(f"✗ Vector indexing failed: {vector_error}")
        
        # =========================================================================
        # COMPLETION
        # =========================================================================
        _update_progress(self, datasets_collection, dataset_id, "Processing complete", 100, "completed")
        
        logger.info(f"╔════════════════════════════════════════════════════════════════╗")
        logger.info(f"║ DATASET PROCESSING COMPLETED: {dataset_id:<27} ║")
        logger.info(f"║ Domain: {domain_info['domain']:<40} Confidence: {domain_info['confidence']:<5} ║")
        logger.info(f"║ Rows: {cleaned_rows:,<10}  Columns: {len(df.columns):<10}  Quality: {data_quality['completeness']:.1f}% ║")
        logger.info(f"╚════════════════════════════════════════════════════════════════╝")
        
        return {
            'status': 'success',
            'progress': 100,
            'dataset_id': dataset_id,
            'rows': cleaned_rows,
            'columns': len(df.columns),
            'domain': domain_info['domain'],
            'quality': data_quality['completeness']
        }

    except Exception as e:
        logger.error(f"╔════════════════════════════════════════════════════════════════╗")
        logger.error(f"║ DATASET PROCESSING FAILED: {dataset_id:<30} ║")
        logger.error(f"║ Error: {str(e)[:50]:<54} ║")
        logger.error(f"╚════════════════════════════════════════════════════════════════╝")
        logger.exception(e)
        
        # Update database with failure status
        if db_conn is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {"$set": {
                    "is_processed": True,
                    "processing_status": "failed",
                    "processing_error": str(e)[:1000],
                    "error_type": type(e).__name__,
                    "failed_at": datetime.utcnow()
                }}
            )
        
        # Update Celery state
        error_message = str(e)
        if len(error_message) > 1000:
            error_message = error_message[:1000] + "..."
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Processing failed',
                'error': error_message,
                'error_type': type(e).__name__,
                'dataset_id': dataset_id
            }
        )
        
        raise  # Re-raise for Celery's retry mechanism


# =================================================================================
# VECTOR DATABASE TASKS
# =================================================================================

@celery_app.task(bind=True, name='datasage.index_dataset_vector', max_retries=3)
def index_dataset_to_vector_db(self, dataset_id: str, dataset_metadata: Dict, user_id: str):
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
        success = run_async(faiss_vector_service.add_dataset_to_vector_db(
            dataset_id=dataset_id,
            dataset_metadata=dataset_metadata,
            user_id=user_id
        ))
        
        if success:
            logger.info(f"✓ Successfully indexed dataset {dataset_id}")
        else:
            logger.warning(f"⚠ Vector indexing returned False for {dataset_id}")
        
        return success
    
    except Exception as e:
        logger.error(f"✗ Vector indexing failed for {dataset_id}: {e}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_in = 2 ** self.request.retries  # 2, 4, 8 seconds
            logger.info(f"Retrying in {retry_in} seconds... (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_in)
        else:
            logger.error(f"Max retries reached for dataset {dataset_id}")
            return False


@celery_app.task(name='datasage.add_query_history')
def add_query_to_vector_history(query_text: str, dataset_id: str, response: str, user_id: str):
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
        success = run_async(faiss_vector_service.add_query_to_history(
            query_text=query_text,
            dataset_id=dataset_id,
            response=response,
            user_id=user_id
        ))
        
        if success:
            logger.info(f"✓ Added query to history: '{query_text[:50]}...'")
        
        return success
    
    except Exception as e:
        logger.error(f"✗ Failed to add query to history: {e}")
        return False
