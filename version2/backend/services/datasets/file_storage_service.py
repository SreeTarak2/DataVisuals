# backend/services/file_storage_service.py

import uuid
import aiofiles
import polars as pl
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging
from datetime import datetime
import magic

from fastapi import HTTPException

logger = logging.getLogger(__name__)

class FileStorageService:
    """
    A comprehensive service for all physical file operations: validation,
    saving, reading, and deletion. This is the single source of truth for file I/O.
    """
    def __init__(self, base_path: str = "uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        (self.base_path / "datasets").mkdir(exist_ok=True)

        self.allowed_extensions = {'csv', 'xlsx', 'xls', 'json'}
        self.max_size_mb = 50  # Increased max size to 50MB
        self.max_size_bytes = self.max_size_mb * 1024 * 1024

    def _validate_file(self, content: bytes, filename: str) -> str:
        """Internal method to validate file content and name."""
        # 1. Check file size
        if len(content) > self.max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {self.max_size_mb}MB."
            )
        
        # 2. Check file extension
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: {', '.join(self.allowed_extensions)}"
            )
        
        # 3. Check MIME type (content-based check) for basic verification
        try:
            mime_type = magic.from_buffer(content, mime=True)
            if 'csv' in file_ext and 'text' not in mime_type and 'csv' not in mime_type:
                 logger.warning(f"Possible MIME mismatch for CSV '{filename}': detected {mime_type}")
            if 'xls' in file_ext and 'excel' not in mime_type and 'spreadsheet' not in mime_type:
                 logger.warning(f"Possible MIME mismatch for Excel '{filename}': detected {mime_type}")
        except Exception as e:
            logger.warning(f"Could not perform MIME type check on '{filename}': {e}")

        return file_ext

    async def save_file(self, file_content: bytes, filename: str, user_id: str) -> Dict[str, Any]:
        """Validates and saves an uploaded file, returning its essential metadata."""
        try:
            file_ext = self._validate_file(file_content, filename)
            
            file_id = str(uuid.uuid4())
            # Use a consistent naming scheme for security (no original filename)
            new_filename = f"{file_id}.{file_ext}"

            user_dir = self.base_path / "datasets" / user_id
            user_dir.mkdir(exist_ok=True)
            file_path = user_dir / new_filename
            
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            logger.info(f"File saved for user {user_id} at {file_path}")

            return {
                "file_id": file_id,
                "file_path": str(file_path),
                "file_size": len(file_content),
                "file_extension": file_ext,
            }
        except HTTPException as e:
            raise e  # Re-raise validation errors to be sent to the user
        except Exception as e:
            logger.error(f"Failed to save file for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Could not save the uploaded file.")

    async def get_paginated_file_data(
        self, file_path: str, limit: int, offset: int
    ) -> Tuple[List[Dict], int]:
        """Reads a file and returns paginated data and total row count using Polars."""
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                logger.error(f"File not found at path: {file_path}")
                return [], 0

            # Polars' lazy scanning is extremely efficient for getting row counts from CSVs.
            if ".csv" in file_path:
                try:
                    total_rows = pl.scan_csv(file_path).select(pl.count()).collect().item()
                    df = pl.read_csv(file_path, skip_rows=offset, n_rows=limit)
                except Exception as e: # Handle empty file or parse error
                    logger.error(f"Polars failed to read CSV {file_path}: {e}")
                    return [], 0
            # For other file types, we might need to read more data to get the count.
            elif ".xlsx" in file_path or ".xls" in file_path:
                # This is less efficient but necessary for Excel files.
                full_df = pl.read_excel(file_path)
                total_rows = len(full_df)
                df = full_df.slice(offset, limit)
            elif ".json" in file_path:
                full_df = pl.read_json(file_path)
                total_rows = len(full_df)
                df = full_df.slice(offset, limit)
            else:
                return [], 0

            return df.to_dicts(), total_rows
        except Exception as e:
            logger.error(f"Error reading file data from {file_path}: {e}")
            return [], 0
            
    async def delete_file(self, file_path: str) -> bool:
        """Permanently deletes a file from the disk."""
        try:
            path_obj = Path(file_path)
            if path_obj.is_file():
                path_obj.unlink()
                logger.info(f"File deleted from disk: {file_path}")
                return True
            logger.warning(f"Attempted to delete non-existent file: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

# Create a singleton instance for easy import and consistent use across the application
file_storage_service = FileStorageService()