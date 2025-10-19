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
from services.faiss_vector_service import faiss_vector_service

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
        self.update_state(state='PROGRESS', meta={'status': 'Loading dataset...', 'progress': 10})
        datasets_collection.update_one({"_id": dataset_id}, {"$set": {"processing_status": "reading"}})

        # Load dataset
        file_extension = file_path.split('.')[-1].lower()
        if file_extension == 'csv':
            df = pl.read_csv(file_path, infer_schema_length=10000)
        elif file_extension in ['xlsx', 'xls']:
            df = pl.read_excel(file_path)
        elif file_extension == 'json':
            df = pl.read_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        # Convert to lazy for better performance
        df = df.lazy()
        original_rows = df.select(pl.count()).collect().item()
        schema = df.collect_schema()
        logger.info(f"Original dataset: {original_rows} rows, {len(schema)} columns")

        self.update_state(state='PROGRESS', meta={'status': 'Cleaning dataset...', 'progress': 20})
        
        # Get column names and types first
        string_columns = [name for name, dtype in schema.items() if dtype == pl.Utf8]
        
        # Clean string columns - strip whitespace
        if string_columns:
            df = df.with_columns([
                pl.col(col).str.strip_chars().alias(col)
                for col in string_columns
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
            df = df.rename(rename_dict)
            logger.info(f"Renamed duplicate columns: {rename_dict}")
            # Update schema after renaming
            schema = df.collect_schema()
            string_columns = [name for name, dtype in schema.items() if dtype == pl.Utf8]
            numeric_columns = [name for name, dtype in schema.items() 
                              if dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32, pl.Int16, pl.Int8, pl.UInt64, pl.UInt32, pl.UInt16, pl.UInt8]]
        
        # Clean string columns - handle null representations
        for col in string_columns:
            df = df.with_columns([
                pl.when(pl.col(col).str.contains("N/A|null|NULL|^$"))
                .then(None)
                .otherwise(pl.col(col))
                .alias(col)
            ])
            
            # Standardize casing for specific columns
            if col.lower() in ['batting_hand', 'bowling_skill', 'country']:
                df = df.with_columns([
                    pl.col(col)
                    .str.to_lowercase()
                    .str.replace_all("_", " ")
                    .str.to_titlecase()
                    .alias(col)
                ])
        
        # Clean numeric columns - handle inf/nan values
        numeric_columns = [name for name, dtype in schema.items() 
                          if dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32, pl.Int16, pl.Int8, pl.UInt64, pl.UInt32, pl.UInt16, pl.UInt8]]
        
        for col in numeric_columns:
            df = df.with_columns([
                pl.when(pl.col(col).is_infinite() | pl.col(col).is_nan())
                .then(None)
                .otherwise(pl.col(col))
                .alias(col)
            ])
        
        # Remove duplicate rows
        df = df.unique()
        cleaned_rows = df.select(pl.count()).collect().item()
        duplicates_removed = original_rows - cleaned_rows
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows")

        # Collect the lazy dataframe
        df = df.collect()
        logger.info(f"After cleaning: {cleaned_rows} rows, {len(df.columns)} columns")

        self.update_state(state='PROGRESS', meta={'status': 'Generating metadata...', 'progress': 30})

        # Generate metadata
        overview = {"total_rows": len(df), "total_columns": len(df.columns)}
        column_metadata = [{"name": col, "type": str(df[col].dtype), "null_count": df[col].is_null().sum()} for col in df.columns]
        
        self.update_state(state='PROGRESS', meta={'status': 'Running statistical analysis...', 'progress': 60})

        statistical_findings = analysis_service.run_all_statistical_checks(df)
        
        # Calculate data quality metrics
        total_nulls = df.select(pl.all().is_null().sum()).sum_horizontal()[0]
        total_cells = overview['total_rows'] * overview['total_columns']

        final_metadata = {
            "dataset_overview": overview,
            "column_metadata": column_metadata,
            "statistical_findings": statistical_findings,
            "data_quality": {
                "completeness": 100.0 - (total_nulls / total_cells * 100) if total_cells > 0 else 100.0,
                "uniqueness": 100.0 - (df.is_duplicated().sum() / overview['total_rows'] * 100) if overview['total_rows'] > 0 else 100.0,
                "duplicates_removed": duplicates_removed,
                "original_rows": original_rows,
                "cleaned_rows": cleaned_rows,
                "data_cleaning_applied": True
            },
            "generated_at": datetime.utcnow()
        }

        sanitized_metadata = _convert_types_for_json(final_metadata)
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving to database...', 'progress': 90})

        # Save to database
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
        
        # Index to vector database
        self.update_state(state='PROGRESS', meta={'status': 'Indexing to vector database...', 'progress': 95})
        try:
            import asyncio
            vector_success = asyncio.run(faiss_vector_service.add_dataset_to_vector_db(
                dataset_id=dataset_id,
                dataset_metadata=sanitized_metadata,
                user_id=datasets_collection.find_one({"_id": dataset_id}).get("user_id", "unknown")
            ))
            logger.info(f"Vector indexing result for {dataset_id}: {vector_success}")
        except Exception as vector_error:
            logger.warning(f"Vector indexing failed for {dataset_id}: {vector_error}")
        
        logger.info(f"Successfully processed dataset_id: {dataset_id}")
        return {'status': 'Completed', 'progress': 100, 'rows': overview["total_rows"]}

    except Exception as e:
        logger.error(f"Failed to process dataset_id {dataset_id}: {e}", exc_info=True)
        
        # Update database with failure status
        if db_conn is None:
            init_worker_db()
        if db_conn is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {"$set": {"is_processed": True, "processing_status": "failed", "processing_error": str(e)}}
            )
        
        # Better error handling for Celery
        error_message = str(e)
        if len(error_message) > 1000:
            error_message = error_message[:1000] + "..."
        
        self.update_state(
            state='FAILURE', 
            meta={
                'status': 'Task failed', 
                'error': error_message,
                'error_type': type(e).__name__
            }
        )
        raise e

# =================================================================================
# == VECTOR DATABASE TASKS
# =================================================================================

@celery_app.task(bind=True)
def index_dataset_to_vector_db(self, dataset_id: str, dataset_metadata: dict, user_id: str):
    """Background task to index dataset metadata to vector database."""
    logger.info(f"Starting vector indexing for dataset_id: {dataset_id}")
    
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Indexing to vector database...', 'progress': 10})
        
        # Use asyncio.run to handle the async vector service
        import asyncio
        success = asyncio.run(faiss_vector_service.add_dataset_to_vector_db(
            dataset_id=dataset_id,
            dataset_metadata=dataset_metadata,
            user_id=user_id
        ))
        
        if success:
            self.update_state(state='SUCCESS', meta={'status': 'Vector indexing completed', 'progress': 100})
            logger.info(f"Successfully indexed dataset {dataset_id} to vector database")
            return {'status': 'success', 'dataset_id': dataset_id, 'indexed': True}
        else:
            self.update_state(state='FAILURE', meta={'status': 'Vector indexing failed'})
            return {'status': 'failed', 'dataset_id': dataset_id, 'indexed': False}
            
    except Exception as e:
        logger.error(f"Failed to index dataset {dataset_id} to vector database: {e}")
        self.update_state(state='FAILURE', meta={'status': 'Vector indexing failed', 'error': str(e)})
        return {'status': 'failed', 'dataset_id': dataset_id, 'error': str(e)}

@celery_app.task(bind=True)
def add_query_to_vector_history(self, query: str, dataset_id: str, user_id: str):
    """Background task to add query to vector history."""
    logger.info(f"Adding query to vector history for user: {user_id}")
    
    try:
        import asyncio
        success = asyncio.run(faiss_vector_service.add_query_to_history(
            query=query,
            dataset_id=dataset_id,
            user_id=user_id
        ))
        
        if success:
            logger.info(f"Successfully added query to vector history for user {user_id}")
            return {'status': 'success', 'query_added': True}
        else:
            return {'status': 'failed', 'query_added': False}
            
    except Exception as e:
        logger.error(f"Failed to add query to vector history: {e}")
        return {'status': 'failed', 'error': str(e)}