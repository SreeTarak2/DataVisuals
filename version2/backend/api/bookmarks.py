from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from db.database import get_database
from db.schemas import Bookmark, BookmarkCreate, BookmarkUpdate
from services.auth_service import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=Bookmark, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    bookmark: BookmarkCreate,
    current_user: dict = Depends(get_current_user),
):
    """Save an analysis component (chart, insight, config) for future reference."""
    db = get_database()
    doc = bookmark.dict()
    doc["user_id"] = current_user["id"]
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = doc["created_at"]
    
    try:
        result = await db.bookmarks.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        doc["id"] = doc.pop("_id")
        return doc
    except Exception as e:
        logger.error(f"Error creating bookmark: {e}")
        raise HTTPException(status_code=500, detail="Failed to create bookmark")

@router.get("/", response_model=List[Bookmark])
async def get_bookmarks(
    dataset_id: Optional[str] = None,
    item_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all saved bookmarks for the current user, optionally filtered."""
    db = get_database()
    query = {"user_id": current_user["id"]}
    if dataset_id:
        query["dataset_id"] = dataset_id
    if item_type:
        query["item_type"] = item_type
        
    try:
        cursor = db.bookmarks.find(query).sort("created_at", -1)
        bookmarks = []
        async for b in cursor:
            b["id"] = str(b.pop("_id"))
            bookmarks.append(b)
        return bookmarks
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch bookmarks")

@router.put("/{bookmark_id}", response_model=Bookmark)
async def update_bookmark(
    bookmark_id: str,
    bookmark_update: BookmarkUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing bookmark's title, description, or data."""
    db = get_database()
    try:
        obj_id = ObjectId(bookmark_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")
        
    update_data = bookmark_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")
        
    update_data["updated_at"] = datetime.utcnow()
    
    try:
        result = await db.bookmarks.find_one_and_update(
            {"_id": obj_id, "user_id": current_user["id"]},
            {"$set": update_data},
            return_document=True
        )
        if not result:
            raise HTTPException(status_code=404, detail="Bookmark not found")
            
        result["id"] = str(result.pop("_id"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bookmark {bookmark_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update bookmark")

@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a saved bookmark."""
    db = get_database()
    try:
        obj_id = ObjectId(bookmark_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")
        
    try:
        result = await db.bookmarks.delete_one({
            "_id": obj_id,
            "user_id": current_user["id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Bookmark not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bookmark {bookmark_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete bookmark")
