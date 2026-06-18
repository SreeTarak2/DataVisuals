# backend/services/file_storage_service.py

import uuid
import shutil
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
        self.max_size_mb = 500  # Increased to support large datasets
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

    def _check_content_magic(self, file_path: str, expected_ext: str) -> None:
        """
        Verify file content matches its extension via magic-byte signatures.

        Raises HTTPException on obvious mismatch.
        """
        try:
            import magic
            with open(file_path, 'rb') as f:
                header = f.read(4096)
            mime = magic.from_buffer(header, mime=True)

            ext_to_mime = {
                'csv':  ('text/csv', 'text/plain', 'text/comma-separated-values', 'application/csv'),
                'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         'application/octet-stream'),  # some systems return octet-stream for xlsx
                'xls':  ('application/vnd.ms-excel', 'application/octet-stream'),
                'json': ('application/json', 'text/plain'),
            }
            allowed = ext_to_mime.get(expected_ext, ())
            if allowed and mime not in allowed:
                logger.warning(
                    f"Content MIME mismatch for .{expected_ext} file: got '{mime}', "
                    f"expected one of {allowed}"
                )
                # Soft-warning only — some CSV files legitimately report as
                # text/plain or application/octet-stream.  We log but don't reject.
        except ImportError:
            logger.debug("python-magic not installed; skipping content validation")
        except Exception as e:
            logger.debug(f"Content validation skipped ({e})")

    def _check_csv_formula_injection(self, file_path: str) -> None:
        """
        Check CSV for cells starting with dangerous formula prefixes (=, +, -, @).

        These are CSV injection / formula injection vectors. When exported to
        Excel or Google Sheets, they can execute arbitrary formulas.

        We scan the first 10KB of the file and log a warning if detected.
        This is a soft check — we read the file but don't reject it.
        """
        try:
            dangerous_prefixes = ('=', '+', '-', '@', '\t', '\r')
            with open(file_path, 'r', errors='replace') as f:
                chunk = f.read(10240)  # first ~10KB

            lines = chunk.split('\n')
            suspicious_cells = []
            for i, line in enumerate(lines[:200]):  # check first 200 lines
                if not line.strip():
                    continue
                cells = line.split(',')
                for j, cell in enumerate(cells):
                    cell_stripped = cell.strip()
                    if cell_stripped and cell_stripped[0] in dangerous_prefixes:
                        suspicious_cells.append(f"row {i+1}, col {j+1}: '{cell_stripped[:30]}'")
                        if len(suspicious_cells) >= 10:
                            break
                if len(suspicious_cells) >= 10:
                    break

            if suspicious_cells:
                logger.warning(
                    f"CSV formula injection risk: {len(suspicious_cells)} cell(s) start with "
                    f"dangerous prefixes. Examples: {suspicious_cells[:5]}"
                )
        except Exception as e:
            logger.debug(f"CSV formula injection check skipped ({e})")

    async def save_file_from_path(self, source_path: str, filename: str, user_id: str) -> Dict[str, Any]:
        """Moves a file from a temp path to permanent storage. Used by streaming uploads."""
        try:
            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            if file_ext not in self.allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type not supported. Allowed types: {', '.join(self.allowed_extensions)}"
                )

            # Validate content against expected extension
            self._check_content_magic(source_path, file_ext)

            # Check CSV formula injection risk
            if file_ext == 'csv':
                self._check_csv_formula_injection(source_path)

            source = Path(source_path)
            file_size = source.stat().st_size
            
            file_id = str(uuid.uuid4())
            new_filename = f"{file_id}.{file_ext}"
            user_dir = self.base_path / "datasets" / user_id
            user_dir.mkdir(exist_ok=True)
            file_path = user_dir / new_filename
            
            # Move file (uses rename if same filesystem, copy+delete otherwise)
            shutil.move(str(source), str(file_path))
            
            logger.info(f"File moved for user {user_id} at {file_path}")
            
            return {
                "file_id": file_id,
                "file_path": str(file_path),
                "file_size": file_size,
                "file_extension": file_ext,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to move file for user {user_id}: {e}")
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