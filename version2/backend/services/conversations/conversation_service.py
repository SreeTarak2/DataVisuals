"""
Conversation Service
--------------------
Handles all DB operations for conversations:
- create / load existing
- append messages
- fetch list of conversations
- delete a conversation

This file lives inside:
services/sub/conversation_service.py
"""

from typing import Optional, List, Dict
from datetime import datetime
from bson import ObjectId
import logging

from db.database import get_database

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# Load or Create Conversation
# -----------------------------------------------------------

async def load_or_create_conversation(
    conv_id: Optional[str],
    user_id: str,
    dataset_id: str
) -> Dict:
    """
    Loads an existing conversation by ID.
    If not found, creates a new one.
    """
    db = get_database()

    # Try loading existing conversation
    if conv_id:
        try:
            conv = await db.conversations.find_one({
                "_id": ObjectId(conv_id),
                "user_id": user_id
            })
            if conv:
                return conv
        except Exception as e:
            logger.warning(f"Invalid conversation ID '{conv_id}': {e}")

    # Create new conversation
    new_conv = {
        "user_id": user_id,
        "dataset_id": dataset_id,
        "created_at": datetime.utcnow(),
        "messages": []
    }

    result = await db.conversations.insert_one(new_conv)
    new_conv["_id"] = result.inserted_id
    return new_conv


# -----------------------------------------------------------
# Save / Update Conversation
# -----------------------------------------------------------

async def save_conversation(conv_id: ObjectId, messages: List[Dict]) -> None:
    """
    Updates the message history of a conversation.
    """
    db = get_database()
    try:
        await db.conversations.update_one(
            {"_id": conv_id},
            {"$set": {"messages": messages}}
        )
    except Exception as e:
        logger.error(f"Failed to save conversation {conv_id}: {e}")


# -----------------------------------------------------------
# Get All Conversations for User
# -----------------------------------------------------------

async def get_user_conversations(user_id: str) -> List[Dict]:
    """
    Fetches all conversations for a user, sorted by newest first.
    Adds stringified _id and dataset name.
    """
    db = get_database()
    conversations = []

    try:
        conv_list = (
            await db.conversations
            .find({"user_id": user_id})
            .sort("created_at", -1)
            .to_list(length=200)
        )

        for conv in conv_list:
            conv["_id"] = str(conv["_id"])

            # Fetch dataset name
            try:
                dataset = await db.datasets.find_one({
                    "_id": conv.get("dataset_id"),
                    "user_id": user_id
                })
                conv["dataset_name"] = dataset.get("name", "Unknown Dataset") if dataset else "Unknown Dataset"
            except Exception:
                conv["dataset_name"] = "Unknown Dataset"

            conversations.append(conv)

    except Exception as e:
        logger.error(f"Failed to get user conversations: {e}")

    return conversations


# -----------------------------------------------------------
# Get Single Conversation
# -----------------------------------------------------------

async def get_conversation(conversation_id: str, user_id: str) -> Optional[Dict]:
    """
    Fetch a single conversation by ID.
    """
    db = get_database()

    try:
        conv = await db.conversations.find_one({
            "_id": ObjectId(conversation_id),
            "user_id": user_id
        })
        if conv:
            conv["_id"] = str(conv["_id"])

            # attach dataset name
            try:
                dataset = await db.datasets.find_one({
                    "_id": conv.get("dataset_id"),
                    "user_id": user_id
                })
                conv["dataset_name"] = dataset.get("name", "Unknown Dataset") if dataset else "Unknown Dataset"
            except Exception:
                conv["dataset_name"] = "Unknown Dataset"

            return conv

    except Exception as e:
        logger.error(f"Failed to fetch conversation {conversation_id}: {e}")

    return None


# -----------------------------------------------------------
# Delete Conversation
# -----------------------------------------------------------

async def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """
    Delete a conversation from the DB.
    Returns True if deleted successfully.
    """
    db = get_database()

    try:
        result = await db.conversations.delete_one({
            "_id": ObjectId(conversation_id),
            "user_id": user_id
        })
        return result.deleted_count > 0

    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        return False
