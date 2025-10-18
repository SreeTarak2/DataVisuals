# backend/services/enhanced_dataset_service.py

import uuid
from datetime import datetime
import logging
from typing import List, Dict, Optional

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse

from database import get_database
from models.schemas import DatasetData, DatasetSummary
from services.file_storage_service import file_storage_service
from services.faiss_vector_service import faiss_vector_service
from tasks import process_dataset_task # Import our Celery task

logger = logging.getLogger(__name__)

class EnhancedDatasetService:
    """
    Manages the lifecycle of dataset metadata records in the database.
    This service does NOT perform file I/O or heavy computation itself;
    it delegates those tasks to file_storage_service and Celery workers.
    """

    def __init__(self):
        """
        The __init__ method is good practice, even if empty. It signifies
        that this class is intended to be instantiated.
        """
    @property
    def db(self):
        """Lazily gets the database connection on first access."""
        db_conn = get_database()
        if db_conn is None:
            raise Exception("Database is not connected. Application startup may have failed.")
        return db_conn

    async def upload_dataset(
        self, file: UploadFile, user_id: str, name: str = None, description: str = None
    ) -> JSONResponse:
        """
        Handles the initial upload request.
        1. Saves the file using the file_storage_service.
        2. Creates an initial dataset record in the database.
        3. Dispatches a background task to process the dataset and generate metadata.
        Returns an immediate 'Accepted' response.
        """
        try:
            file_content = await file.read()
            file_metadata = await file_storage_service.save_file(file_content, file.filename, user_id)
            
            dataset_id = str(uuid.uuid4())
            
            dataset_doc = {
                "_id": dataset_id,
                "user_id": user_id,
                "name": name or file.filename.split('.')[0],
                "description": description or "",
                "file_id": file_metadata["file_id"],
                "original_filename": file.filename,
                "file_path": file_metadata["file_path"],
                "file_size": file_metadata["file_size"],
                "file_extension": file_metadata["file_extension"],
                "upload_date": datetime.utcnow(),
                "is_processed": False, # IMPORTANT: Set to False, the worker will update this.
                "is_active": True,
                "processing_status": "pending",
                "metadata": {} # Metadata will be populated by the worker.
            }
            
            await self.db.datasets.insert_one(dataset_doc)
            
            # Dispatch the background task for processing
            task = process_dataset_task.delay(dataset_id, file_metadata["file_path"])
            
            logger.info(f"Dataset {dataset_id} accepted for processing. Task ID: {task.id}")
            
            return JSONResponse(
                status_code=202,
                content={
                    "dataset_id": dataset_id,
                    "task_id": task.id,
                    "message": "Dataset upload accepted and is now being processed."
                }
            )
        except HTTPException as e:
            # Re-raise HTTP exceptions from file validation
            raise e
        except Exception as e:
            logger.error(f"Error in upload_dataset orchestration: {e}")
            raise HTTPException(status_code=500, detail="Failed to initiate dataset upload.")

    async def get_user_datasets(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Gets all active datasets for a specific user."""
        cursor = self.db.datasets.find(
            {"user_id": user_id, "is_active": True}
        ).sort("upload_date", -1).skip(skip).limit(limit)
        
        datasets = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            
            # Ensure we have the basic fields with fallbacks
            if not doc.get("name"):
                doc["name"] = doc.get("original_filename", "Unnamed Dataset")
            if not doc.get("row_count"):
                doc["row_count"] = 0
            if not doc.get("column_count"):
                doc["column_count"] = 0
            if not doc.get("created_at"):
                doc["created_at"] = doc.get("upload_date")
                
            datasets.append(doc)
        return datasets

    async def get_dataset(self, dataset_id: str, user_id: str) -> Dict:
        """Gets a single, complete dataset document, including its metadata."""
        # Handle both ObjectId and UUID formats
        try:
            # Try ObjectId format first
            from bson import ObjectId
            query = {"_id": ObjectId(dataset_id), "user_id": user_id, "is_active": True}
        except Exception:
            # If ObjectId fails, treat as string (UUID format)
            query = {"_id": dataset_id, "user_id": user_id, "is_active": True}
        
        dataset = await self.db.datasets.find_one(query)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        
        dataset["id"] = str(dataset["_id"])
        dataset.pop("_id", None)
        return dataset

    async def delete_dataset(self, dataset_id: str, user_id: str) -> bool:
        """Permanently deletes a dataset record and its associated file."""
        dataset = await self.get_dataset(dataset_id, user_id) # Ensures user owns the dataset

        # Delete the physical file from storage
        if dataset.get("file_path"):
            await file_storage_service.delete_file(dataset["file_path"])

        # Delete related conversations
        await self.db.conversations.delete_many({"dataset_id": dataset_id, "user_id": user_id})

        # Delete the dataset record from MongoDB
        # Convert string ID to ObjectId for MongoDB query
        from bson import ObjectId
        try:
            object_id = ObjectId(dataset_id)
            query = {"_id": object_id, "user_id": user_id}
        except Exception:
            # If ObjectId conversion fails, treat as string (UUID format)
            query = {"_id": dataset_id, "user_id": user_id}
        
        result = await self.db.datasets.delete_one(query)
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Dataset could not be deleted.")
        
        logger.info(f"Dataset {dataset_id} permanently deleted by user {user_id}.")
        return True

    async def get_dataset_data(self, dataset_id: str, user_id: str, page: int = 1, page_size: int = 100) -> Dict:
        """Gets paginated data directly from the dataset's file."""
        dataset = await self.get_dataset(dataset_id, user_id)
        
        # We now always read from the file path via the storage service.
        offset = (page - 1) * page_size
        data, total_rows = await file_storage_service.get_paginated_file_data(
            dataset["file_path"], limit=page_size, offset=offset
        )

        return {
            "data": data,
            "total_rows": total_rows,
            "current_page": page,
            "page_size": page_size,
            "has_more": (page * page_size) < total_rows
        }

    async def load_dataset_data(self, dataset_id: str, user_id: str):
        """Loads the full dataset as a Polars DataFrame for analysis."""
        import polars as pl
        from pathlib import Path
        
        dataset = await self.get_dataset(dataset_id, user_id)
        file_path = dataset.get("file_path")
        
        if not file_path:
            raise HTTPException(status_code=404, detail="Dataset file not found.")
        
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Dataset file not found on disk.")
        
        try:
            file_ext = path.suffix.lower()
            if file_ext == ".csv":
                return pl.read_csv(file_path, infer_schema_length=10000)
            elif file_ext in [".xlsx", ".xls"]:
                return pl.read_excel(file_path)
            elif file_ext == ".json":
                return pl.read_json(file_path)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
        except Exception as e:
            logger.error(f"Failed to load dataset from {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not load dataset: {str(e)}")

    async def auto_index_dataset_to_vector_db(self, dataset_id: str, user_id: str) -> bool:
        """
        Automatically index a dataset to vector database after processing.
        This is called internally when dataset processing is complete.
        """
        try:
            # Get the processed dataset
            dataset_doc = await self.get_dataset(dataset_id, user_id)
            
            if dataset_doc and dataset_doc.get("metadata"):
                # Index to vector database
                success = await faiss_vector_service.add_dataset_to_vector_db(
                    dataset_id=dataset_id,
                    dataset_metadata=dataset_doc["metadata"],
                    user_id=user_id
                )
                
                if success:
                    logger.info(f"Dataset {dataset_id} auto-indexed to vector database")
                    return True
                else:
                    logger.warning(f"Failed to auto-index dataset {dataset_id} to vector database")
                    return False
            else:
                logger.warning(f"Dataset {dataset_id} not ready for vector indexing")
                return False
                
        except Exception as e:
            logger.error(f"Auto-indexing failed for dataset {dataset_id}: {e}")
            return False

# Singleton instance
enhanced_dataset_service = EnhancedDatasetService()
