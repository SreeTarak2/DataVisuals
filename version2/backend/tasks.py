# backend/tasks.py

import os
import json
import logging
from datetime import datetime
import math

import polars as pl
from celery import Celery
from celery.signals import worker_process_init
from pymongo import MongoClient

from services.analysis_service import analysis_service

logger = logging.getLogger(__name__)

# =================================================================================
# == CELERY & DATABASE CONFIGURATION
# =================================================================================

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

MONGO_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "datasage_ai")

# Use a global variable to hold the connection for each worker process
db_conn = None

@worker_process_init.connect
def init_worker_db(**kwargs):
    """Creates a new, fork-safe database connection for each worker process."""
    global db_conn
    logger.info("Initializing database connection for worker process...")
    client = MongoClient(MONGO_URL)
    db_conn = client[DATABASE_NAME]
    logger.info("Database connection for worker process initialized.")

# =================================================================================
# == HELPER FUNCTION FOR DATA SERIALIZATION
# =================================================================================

def _convert_types_for_json(obj):
    """Recursively converts special types to JSON-serializable Python native types."""
    if isinstance(obj, dict):
        return {k: _convert_types_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_types_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, pl.Date, pl.Datetime)):
        return obj.isoformat()
    elif hasattr(obj, 'item'):
        return obj.item()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

# =================================================================================
# == THE MAIN BACKGROUND TASK
# =================================================================================

@celery_app.task(bind=True)
def process_dataset_task(self, dataset_id: str, file_path: str):
    """The main background task for processing an uploaded dataset."""
    logger.info(f"Starting processing for dataset_id: {dataset_id}")
    
    # Ensure the worker-specific DB connection is available
    if db_conn is None:
        init_worker_db()
    
    datasets_collection = db_conn.datasets

    try:
        self.update_state(state='PROGRESS', meta={'status': 'Reading file...', 'progress': 10})
        datasets_collection.update_one({"_id": dataset_id}, {"$set": {"processing_status": "reading"}})

        file_extension = file_path.split('.')[-1].lower()
        if file_extension == 'csv':
            df = pl.read_csv(file_path, infer_schema_length=10000)
        elif file_extension in ['xlsx', 'xls']:
            df = pl.read_excel(file_path)
        elif file_extension == 'json':
            df = pl.read_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        self.update_state(state='PROGRESS', meta={'status': 'Generating metadata...', 'progress': 30})

        overview = {"total_rows": len(df), "total_columns": len(df.columns)}
        column_metadata = [{"name": col, "type": str(df[col].dtype), "null_count": df[col].is_null().sum()} for col in df.columns]
        
        self.update_state(state='PROGRESS', meta={'status': 'Running statistical analysis...', 'progress': 60})

        statistical_findings = analysis_service.run_all_statistical_checks(df)
        
        # FIXED: Correct null calculation in Polars
        total_nulls = df.select(pl.all().is_null().sum()).sum_horizontal()[0]
        total_cells = overview['total_rows'] * overview['total_columns']

        # Assemble the final metadata document
        final_metadata = {
            "dataset_overview": overview,
            "column_metadata": column_metadata,
            "statistical_findings": statistical_findings,
            "data_quality": {
                "completeness": 100.0 - (total_nulls / total_cells * 100) if total_cells > 0 else 100.0,
                "uniqueness": 100.0 - (df.is_duplicated().sum() / overview['total_rows'] * 100) if overview['total_rows'] > 0 else 100.0,
            },
            "generated_at": datetime.utcnow()
        }

        sanitized_metadata = _convert_types_for_json(final_metadata)
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving to database...', 'progress': 90})

        datasets_collection.update_one(
            {"_id": dataset_id},
            {"$set": {
                "metadata": sanitized_metadata,
                "is_processed": True,
                "processing_status": "success",
                "row_count": overview["total_rows"],
                "column_count": overview["total_columns"]
            }}
        )
        
        logger.info(f"Successfully processed dataset_id: {dataset_id}")
        return {'status': 'Completed', 'progress': 100, 'rows': overview["total_rows"]}

    except Exception as e:
        logger.error(f"Failed to process dataset_id {dataset_id}: {e}", exc_info=True)
        
        # FIXED: Ensure DB init fallback and safe update (enhances your Bug #2 fix)
        if db_conn is None:
            init_worker_db()  # Re-init if lost in worker fork
        if db_conn:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {"$set": {"is_processed": True, "processing_status": "failed", "processing_error": str(e)}}
            )
        
        self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': str(e)})
        raise e