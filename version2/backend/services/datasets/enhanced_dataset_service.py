import uuid
import hashlib
from datetime import datetime
import logging
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from bson import ObjectId

from db.database import get_database
from services.datasets.file_storage_service import file_storage_service
from services.datasets.faiss_vector_service import faiss_vector_service
# Note: process_dataset_task imported lazily to avoid circular imports

logger = logging.getLogger(__name__)

class EnhancedDatasetService:
    """
    Manages the lifecycle of dataset metadata records in the database.
    This service does NOT perform file I/O or heavy computation itself;
    it delegates those tasks to file_storage_service and Celery workers.
    """

    def __init__(self):
        """Initialize the enhanced dataset service."""
        pass

    @property
    def db(self):
        """Lazily gets the database connection on first access."""
        db_conn = get_database()
        if db_conn is None:
            raise Exception("Database is not connected. Application startup may have failed.")
        return db_conn

    def _generate_content_hash(self, file_content: bytes) -> str:
        """
        Generate a SHA-256 hash of the file content for duplicate detection.
        
        Args:
            file_content: The raw file content as bytes
            
        Returns:
            str: SHA-256 hash of the content
        """
        return hashlib.sha256(file_content).hexdigest()

    async def _check_duplicate_dataset(self, content_hash: str, user_id: str) -> Optional[Dict]:
        """
        Check if a dataset with the same content hash already exists for the user.
        
        Args:
            content_hash: SHA-256 hash of the file content
            user_id: User ID to check duplicates for
            
        Returns:
            Optional[Dict]: Existing dataset if found, None otherwise
        """
        try:
            existing_dataset = await self.db.datasets.find_one({
                "user_id": user_id,
                "content_hash": content_hash,
                "is_active": True
            })
            
            if existing_dataset:
                existing_dataset["id"] = str(existing_dataset["_id"])
                existing_dataset.pop("_id", None)
                return existing_dataset
            
            return None
        except Exception as e:
            logger.error(f"Error checking for duplicate dataset: {e}")
            return None

    async def upload_dataset(
        self, file: UploadFile, user_id: str, name: str = None, description: str = None
    ) -> JSONResponse:
        """
        Handles the initial upload request with duplicate detection.
        1. Generates content hash for duplicate detection
        2. Checks if identical dataset already exists
        3. If duplicate found, returns existing dataset info
        4. If new, saves file and creates dataset record
        5. Dispatches background task for processing
        """
        try:
            file_content = await file.read()
            content_hash = self._generate_content_hash(file_content)
            existing_dataset = await self._check_duplicate_dataset(content_hash, user_id)
            
            if existing_dataset:
                logger.info(f"Duplicate dataset detected for user {user_id}. Existing dataset: {existing_dataset['id']}")
                return JSONResponse(
                    status_code=409,
                    content={
                        "is_duplicate": True,
                        "existing_dataset": existing_dataset,
                        "message": "Dataset with identical content already exists."
                    }
                )
            
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
                "content_hash": content_hash,
                "upload_date": datetime.utcnow(),
                "is_processed": False,
                "is_active": True,
                "processing_status": "pending",
                "metadata": {}
            }
            
            await self.db.datasets.insert_one(dataset_doc)
            
            # Lazy import to avoid circular dependency
            from tasks import process_dataset_task
            task = process_dataset_task.delay(dataset_id, file_metadata["file_path"])
            
            logger.info(f"New dataset {dataset_id} accepted for processing. Task ID: {task.id}")
            
            return JSONResponse(
                status_code=202,
                content={
                    "is_duplicate": False,
                    "dataset_id": dataset_id,
                    "task_id": task.id,
                    "message": "Dataset upload accepted and is now being processed."
                }
            )
            
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error in upload_dataset orchestration: {e}")
            raise HTTPException(status_code=500, detail="Failed to initiate dataset upload.")

    async def get_user_datasets(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict]:
        """
        Gets all active datasets for a specific user with proper formatting.
        
        Args:
            user_id: User ID to fetch datasets for
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List[Dict]: List of formatted dataset documents
        """
        try:
            cursor = self.db.datasets.find(
                {"user_id": user_id, "is_active": True}
            ).sort("upload_date", -1).skip(skip).limit(limit)
            
            datasets = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)
                doc["name"] = doc.get("name") or doc.get("original_filename", "Unnamed Dataset")
                doc["row_count"] = doc.get("row_count", 0)
                doc["column_count"] = doc.get("column_count", 0)
                doc["created_at"] = doc.get("created_at") or doc.get("upload_date")
                datasets.append(doc)
            
            return datasets
            
        except Exception as e:
            logger.error(f"Error fetching user datasets: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch datasets.")

    async def get_dataset(self, dataset_id: str, user_id: str) -> Dict:
        """
        Gets a single, complete dataset document, including its metadata.
        
        Args:
            dataset_id: Dataset ID (supports both ObjectId and UUID formats)
            user_id: User ID for ownership verification
            
        Returns:
            Dict: Complete dataset document
            
        Raises:
            HTTPException: If dataset not found or access denied
        """
        try:
            try:
                query = {"_id": ObjectId(dataset_id), "user_id": user_id, "is_active": True}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id, "is_active": True}
            
            dataset = await self.db.datasets.find_one(query)
            if not dataset:
                raise HTTPException(status_code=404, detail="Dataset not found.")
            
            dataset["id"] = str(dataset["_id"])
            dataset.pop("_id", None)
            return dataset
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching dataset {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch dataset.")

    async def delete_dataset(self, dataset_id: str, user_id: str) -> bool:
        """
        Permanently deletes a dataset record and its associated file.
        
        Args:
            dataset_id: Dataset ID to delete
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if deletion successful
            
        Raises:
            HTTPException: If dataset not found or deletion fails
        """
        try:
            dataset = await self.get_dataset(dataset_id, user_id)

            if dataset.get("file_path"):
                await file_storage_service.delete_file(dataset["file_path"])

            await self.db.conversations.delete_many({"dataset_id": dataset_id, "user_id": user_id})

            try:
                object_id = ObjectId(dataset_id)
                query = {"_id": object_id, "user_id": user_id}
            except Exception:
                query = {"_id": dataset_id, "user_id": user_id}
            
            result = await self.db.datasets.delete_one(query)
            
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Dataset could not be deleted.")
            
            logger.info(f"Dataset {dataset_id} permanently deleted by user {user_id}.")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting dataset {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete dataset.")

    async def get_dataset_data(self, dataset_id: str, user_id: str, page: int = 1, page_size: int = 100) -> Dict:
        """
        Gets paginated data directly from the dataset's file.
        
        Args:
            dataset_id: Dataset ID to fetch data for
            user_id: User ID for ownership verification
            page: Page number (1-based)
            page_size: Number of records per page
            
        Returns:
            Dict: Paginated data with metadata
        """
        try:
            dataset = await self.get_dataset(dataset_id, user_id)
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
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching dataset data for {dataset_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch dataset data.")

    async def load_dataset_data(self, dataset_id: str, user_id: str):
        """
        Loads the full dataset as a Polars DataFrame for analysis.
        
        Args:
            dataset_id: Dataset ID to load
            user_id: User ID for ownership verification
            
        Returns:
            pl.DataFrame: Polars DataFrame containing the dataset
            
        Raises:
            HTTPException: If dataset not found or loading fails
        """
        import polars as pl
        
        try:
            dataset = await self.get_dataset(dataset_id, user_id)
            file_path = dataset.get("file_path")
            
            if not file_path:
                raise HTTPException(status_code=404, detail="Dataset file not found.")
            
            path = Path(file_path)
            if not path.exists():
                raise HTTPException(status_code=404, detail="Dataset file not found on disk.")
            
            file_ext = path.suffix.lower()
            if file_ext == ".csv":
                return pl.read_csv(file_path, infer_schema_length=10000)
            elif file_ext in [".xlsx", ".xls"]:
                return pl.read_excel(file_path)
            elif file_ext == ".json":
                return pl.read_json(file_path)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to load dataset from {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not load dataset: {str(e)}")

    async def auto_index_dataset_to_vector_db(self, dataset_id: str, user_id: str) -> bool:
        """
        Automatically index a dataset to vector database after processing.
        This is called internally when dataset processing is complete.
        
        Args:
            dataset_id: Dataset ID to index
            user_id: User ID for ownership verification
            
        Returns:
            bool: True if indexing successful, False otherwise
        """
        try:
            dataset_doc = await self.get_dataset(dataset_id, user_id)
            
            if dataset_doc and dataset_doc.get("metadata"):
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

enhanced_dataset_service = EnhancedDatasetService()
