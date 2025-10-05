import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from typing import Optional, Dict, Any
import magic
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileUploadService:
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)
        
        # Allowed file types and their MIME types
        self.allowed_types = {
            'csv': ['text/csv', 'application/csv'],
            'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            'xls': ['application/vnd.ms-excel'],
            'json': ['application/json']
        }
        
        # Max file size (10MB)
        self.max_size = 10 * 1024 * 1024  # 10MB in bytes
    
    async def validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file"""
        try:
            # Check file size
            content = await file.read()
            file_size = len(content)
            
            if file_size > self.max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {self.max_size // (1024*1024)}MB"
                )
            
            # Reset file pointer
            await file.seek(0)
            
            # Detect file type using python-magic
            try:
                mime_type = magic.from_buffer(content, mime=True)
            except:
                # Fallback to file extension
                mime_type = file.content_type or "application/octet-stream"
            
            # Get file extension
            file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            
            # Validate file type
            if file_ext not in self.allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type not supported. Allowed types: {list(self.allowed_types.keys())}"
                )
            
            if mime_type not in self.allowed_types.get(file_ext, []):
                logger.warning(f"MIME type mismatch: {mime_type} for extension {file_ext}")
            
            return {
                "valid": True,
                "file_size": file_size,
                "mime_type": mime_type,
                "file_extension": file_ext,
                "content": content
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail="File validation failed"
            )
    
    async def save_file(self, file: UploadFile, user_id: str) -> Dict[str, Any]:
        """Save uploaded file to disk"""
        try:
            # Validate file
            validation = await self.validate_file(file)
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_ext = validation["file_extension"]
            filename = f"{file_id}.{file_ext}"
            
            # Create user-specific directory
            user_dir = self.upload_dir / user_id
            user_dir.mkdir(exist_ok=True)
            
            # Save file
            file_path = user_dir / filename
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(validation["content"])
            
            return {
                "file_id": file_id,
                "filename": filename,
                "original_filename": file.filename,
                "file_path": str(file_path),
                "file_size": validation["file_size"],
                "mime_type": validation["mime_type"],
                "file_extension": file_ext
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File save error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save file"
            )
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete uploaded file"""
        try:
            file_obj = Path(file_path)
            if file_obj.exists():
                file_obj.unlink()
                logger.info(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"File deletion error: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                return None
            
            stat = file_obj.stat()
            return {
                "file_path": str(file_obj),
                "file_size": stat.st_size,
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "exists": True
            }
        except Exception as e:
            logger.error(f"File info error: {e}")
            return None

# Create file upload service instance
file_upload_service = FileUploadService()

