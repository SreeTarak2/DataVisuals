import os
import uuid
import aiofiles
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FileStorageService:
    def __init__(self, base_path: str = "uploads"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.base_path / "datasets").mkdir(exist_ok=True)
        (self.base_path / "processed").mkdir(exist_ok=True)
        (self.base_path / "temp").mkdir(exist_ok=True)
    
    async def save_file(self, file_content: bytes, filename: str, user_id: str) -> Dict[str, Any]:
        """Save uploaded file and return metadata"""
        try:
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            
            # Create user-specific directory
            user_dir = self.base_path / "datasets" / user_id
            user_dir.mkdir(exist_ok=True)
            
            # Save file
            file_path = user_dir / f"{file_id}_{filename}"
            
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            # Get file info
            file_size = len(file_content)
            
            # Determine if file should be stored in MongoDB or as file
            should_store_in_db = file_size < 10 * 1024 * 1024  # 10MB threshold
            
            metadata = {
                "file_id": file_id,
                "original_filename": filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "upload_date": datetime.utcnow(),
                "user_id": user_id,
                "storage_type": "database" if should_store_in_db else "file",
                "file_extension": Path(filename).suffix.lower()
            }
            
            # If small enough, also store preview data in metadata
            if should_store_in_db:
                preview_data = await self._get_preview_data(file_path)
                metadata.update(preview_data)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise
    
    async def _get_preview_data(self, file_path: Path) -> Dict[str, Any]:
        """Extract preview data from file (first 1000 rows)"""
        try:
            file_extension = file_path.suffix.lower()
            
            if file_extension == '.csv':
                df = pd.read_csv(file_path, nrows=1000)
            elif file_extension in ['.xlsx', '.xls']:
                # Try to read the first sheet
                try:
                    df = pd.read_excel(file_path, nrows=1000, engine='openpyxl')
                except Exception as e:
                    logger.warning(f"Failed to read Excel with openpyxl: {e}")
                    try:
                        df = pd.read_excel(file_path, nrows=1000, engine='xlrd')
                    except Exception as e2:
                        logger.error(f"Failed to read Excel with xlrd: {e2}")
                        return {}
            elif file_extension == '.json':
                df = pd.read_json(file_path)
                if len(df) > 1000:
                    df = df.head(1000)
            else:
                return {}
            
            # Convert to JSON-serializable format
            preview_data = {
                "preview_data": df.to_dict('records'),
                "columns": df.columns.tolist(),
                "data_types": df.dtypes.astype(str).to_dict(),
                "row_count": len(df),
                "column_count": len(df.columns),
                "sample_data": df.head(5).to_dict('records')
            }
            
            return preview_data
            
        except Exception as e:
            logger.error(f"Error extracting preview data: {e}")
            return {}
    
    async def get_file_data(self, file_path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get data from file with optional limit"""
        try:
            file_path = Path(file_path)
            file_extension = file_path.suffix.lower()
            
            if file_extension == '.csv':
                df = pd.read_csv(file_path, nrows=limit)
            elif file_extension in ['.xlsx', '.xls']:
                # Try to read the first sheet
                try:
                    df = pd.read_excel(file_path, nrows=limit, engine='openpyxl')
                except Exception as e:
                    logger.warning(f"Failed to read Excel with openpyxl: {e}")
                    try:
                        df = pd.read_excel(file_path, nrows=limit, engine='xlrd')
                    except Exception as e2:
                        logger.error(f"Failed to read Excel with xlrd: {e2}")
                        raise ValueError(f"Failed to read Excel file: {e2}")
                
                # Handle NaT values in datetime columns
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]':
                        # Replace NaT values with None to avoid utcoffset issues
                        df[col] = df[col].where(pd.notna(df[col]), None)
            elif file_extension == '.json':
                df = pd.read_json(file_path)
                if limit:
                    df = df.head(limit)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error reading file data: {e}")
            raise
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic file information"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            stat = file_path.stat()
            
            return {
                "file_size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            raise
    
    async def delete_file(self, file_id: str, user_id: str, file_extension: str) -> bool:
        """Delete file from storage"""
        try:
            user_dir = self.base_path / "datasets" / user_id
            file_path = user_dir / f"{file_id}{file_extension}"
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"File deleted: {file_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    async def get_file_chunks(self, file_path: str, chunk_size: int = 1000) -> List[List[Dict[str, Any]]]:
        """Get file data in chunks for large files"""
        try:
            file_path = Path(file_path)
            file_extension = file_path.suffix.lower()
            
            chunks = []
            
            if file_extension == '.csv':
                for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                    chunks.append(chunk.to_dict('records'))
            elif file_extension in ['.xlsx', '.xls']:
                # Try to read Excel file
                try:
                    df = pd.read_excel(file_path, engine='openpyxl')
                except Exception as e:
                    logger.warning(f"Failed to read Excel with openpyxl: {e}")
                    try:
                        df = pd.read_excel(file_path, engine='xlrd')
                    except Exception as e2:
                        logger.error(f"Failed to read Excel with xlrd: {e2}")
                        raise ValueError(f"Failed to read Excel file: {e2}")
                
                # Handle NaT values in datetime columns
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]':
                        # Replace NaT values with None to avoid utcoffset issues
                        df[col] = df[col].where(pd.notna(df[col]), None)
                
                for i in range(0, len(df), chunk_size):
                    chunk = df.iloc[i:i + chunk_size]
                    chunks.append(chunk.to_dict('records'))
            elif file_extension == '.json':
                df = pd.read_json(file_path)
                for i in range(0, len(df), chunk_size):
                    chunk = df.iloc[i:i + chunk_size]
                    chunks.append(chunk.to_dict('records'))
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error reading file chunks: {e}")
            raise

# Global instance
file_storage_service = FileStorageService()

