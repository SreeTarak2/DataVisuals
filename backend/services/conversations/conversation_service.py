"""
Conversation Service
--------------------
Handles all DB operations for conversations:
- create / load existing
- append messages
- fetch list of conversations
- delete a conversation
- ENTERPRISE: Auto-archiving for scale
- ENTERPRISE: Pagination for performance

This file lives inside:
services/conversations/conversation_service.py
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId
import logging

from db.database import get_database

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# Configuration Constants
# -----------------------------------------------------------

# Maximum messages before auto-archiving (prevents MongoDB 16MB limit)
MAX_MESSAGES_PER_CONVERSATION = 500
MESSAGE_PRUNE_THRESHOLD = 400  # Trigger archive at this point
ARCHIVE_KEEP_RECENT = 100      # Keep this many recent messages after archive
DEFAULT_PAGE_SIZE = 50         # Messages per page for pagination


# -----------------------------------------------------------
# Archive Functions (Enterprise Scale)
# -----------------------------------------------------------

async def archive_old_messages(
    conv_id: str,
    keep_recent: int = ARCHIVE_KEEP_RECENT
) -> bool:
    """
    Auto-archive old messages to prevent MongoDB document size crashes.
    
    MongoDB has a 16MB document limit. At ~1KB per message with charts,
    this becomes a problem at scale. This function moves old messages
    to a separate archive collection.
    
    Args:
        conv_id: Conversation ID to archive
        keep_recent: Number of recent messages to keep in active conversation
        
    Returns:
        True if archiving occurred, False otherwise
    """
    db = get_database()
    
    try:
        conv = await db.conversations.find_one({"_id": ObjectId(conv_id)})
        
        if not conv:
            logger.warning(f"Conversation {conv_id} not found for archiving")
            return False
        
        messages = conv.get("messages", [])
        
        if len(messages) <= keep_recent:
            return False
        
        # Split messages: archive old, keep recent
        to_archive = messages[:-keep_recent]
        to_keep = messages[-keep_recent:]
        
        # Create archive document
        archive_doc = {
            "conversation_id": conv_id,
            "user_id": conv.get("user_id"),
            "dataset_id": conv.get("dataset_id"),
            "archived_messages": to_archive,
            "message_count": len(to_archive),
            "archived_at": datetime.utcnow(),
            "archive_batch": await _get_next_archive_batch(conv_id)
        }
        
        # Atomically insert archive and update conversation in a transaction
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                await db.conversation_archives.insert_one(archive_doc, session=session)
                await db.conversations.update_one(
                    {"_id": ObjectId(conv_id)},
                    {
                        "$set": {
                            "messages": to_keep,
                            "updated_at": datetime.utcnow(),
                            "archived_message_count": len(to_archive) + conv.get("archived_message_count", 0)
                        }
                    },
                    session=session
                )
        
        logger.info(
            f"Archived {len(to_archive)} messages from conversation {conv_id}, "
            f"kept {len(to_keep)} recent"
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to archive conversation {conv_id}: {e}")
        return False


async def _get_next_archive_batch(conv_id: str) -> int:
    """Get the next archive batch number atomically using an incremented counter."""
    db = get_database()
    result = await db.conversations.find_one_and_update(
        {"_id": ObjectId(conv_id)},
        {"$inc": {"archive_batch_counter": 1}},
        return_document=True,
        projection={"archive_batch_counter": 1}
    )
    return result.get("archive_batch_counter", 1) if result else 1


async def get_archived_messages(
    conv_id: str,
    user_id: str,
    batch: Optional[int] = None,
    archive_limit: int = 1000
) -> List[Dict]:
    """
    Retrieve archived messages for a conversation.
    
    Args:
        conv_id: Conversation ID
        user_id: User ID for access control
        batch: Specific batch number, or None for all
        
    Returns:
        List of archived messages
    """
    db = get_database()
    
    try:
        query = {
            "conversation_id": conv_id,
            "user_id": user_id
        }
        if batch is not None:
            query["archive_batch"] = batch
        
        archives = await db.conversation_archives.find(
            query,
            sort=[("archive_batch", 1)]
        ).to_list(length=archive_limit)
        
        # Flatten all archived messages
        all_messages = []
        for archive in archives:
            all_messages.extend(archive.get("archived_messages", []))
        
        return all_messages
        
    except Exception as e:
        logger.error(f"Failed to get archived messages: {e}")
        return []


async def auto_archive_if_needed(conv_id: str) -> bool:
    """
    Check if conversation needs archiving and perform it.
    Call this before adding new messages.
    
    Args:
        conv_id: Conversation ID
        
    Returns:
        True if archiving was performed
    """
    db = get_database()
    
    try:
        # Use aggregation to get count without loading all messages
        pipeline = [
            {"$match": {"_id": ObjectId(conv_id)}},
            {"$project": {"message_count": {"$size": {"$ifNull": ["$messages", []]}}}}
        ]
        result = await db.conversations.aggregate(pipeline).to_list(1)
        
        if result and result[0].get("message_count", 0) > MESSAGE_PRUNE_THRESHOLD:
            return await archive_old_messages(conv_id)
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to check archive status: {e}")
        return False


# -----------------------------------------------------------
# Pagination Functions (Enterprise Performance)
# -----------------------------------------------------------

async def get_conversation_page(
    conversation_id: str,
    user_id: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    include_archived: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Load conversation with paginated messages for performance.
    
    Instead of loading all 500+ messages, load only what's needed
    for the current view. Critical for large conversation performance.
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID for access control
        page: Page number (1-indexed)
        page_size: Messages per page
        include_archived: Whether to include archived messages
        
    Returns:
        Dict with paginated messages and metadata
    """
    db = get_database()
    
    try:
        skip = (page - 1) * page_size
        
        # Use aggregation for efficient slicing
        pipeline = [
            {
                "$match": {
                    "_id": ObjectId(conversation_id),
                    "user_id": user_id
                }
            },
            {
                "$project": {
                    "user_id": 1,
                    "dataset_id": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "archived_message_count": {"$ifNull": ["$archived_message_count", 0]},
                    "total_messages": {"$size": {"$ifNull": ["$messages", []]}},
                    "messages": {
                        "$slice": [
                            {"$ifNull": ["$messages", []]},
                            {"$multiply": [-1, {"$add": [skip, page_size]}]},
                            page_size
                        ]
                    }
                }
            }
        ]
        
        result = await db.conversations.aggregate(pipeline).to_list(1)
        
        if not result:
            return None
        
        conv = result[0]
        conv["_id"] = str(conv["_id"])
        
        # Add pagination metadata
        total_active = conv.get("total_messages", 0)
        total_archived = conv.get("archived_message_count", 0)
        total_all = total_active + total_archived
        
        conv["pagination"] = {
            "current_page": page,
            "page_size": page_size,
            "total_active_messages": total_active,
            "total_archived_messages": total_archived,
            "total_all_messages": total_all,
            "total_pages": (total_active + page_size - 1) // page_size,
            "has_more": skip + page_size < total_active,
            "has_archives": total_archived > 0
        }
        
        # Optionally include archived messages
        if include_archived and total_archived > 0:
            archived = await get_archived_messages(conversation_id, user_id)
            conv["archived_messages"] = archived
        
        # Fetch dataset name
        try:
            dataset = await db.datasets.find_one({
                "_id": conv.get("dataset_id"),
                "user_id": user_id
            })
            conv["dataset_name"] = dataset.get("name", "Unknown") if dataset else "Unknown"
        except Exception:
            conv["dataset_name"] = "Unknown"
        
        return conv
        
    except Exception as e:
        logger.error(f"Failed to get conversation page: {e}")
        return None


async def get_message_count(conversation_id: str) -> int:
    """
    Get total message count without loading all messages.
    
    Efficient for checking if archiving is needed.
    """
    db = get_database()
    
    try:
        pipeline = [
            {"$match": {"_id": ObjectId(conversation_id)}},
            {"$project": {"count": {"$size": {"$ifNull": ["$messages", []]}}}}
        ]
        result = await db.conversations.aggregate(pipeline).to_list(1)
        return result[0].get("count", 0) if result else 0
    except Exception:
        return 0


# -----------------------------------------------------------
# Append Message (Enterprise-Safe)
# -----------------------------------------------------------

async def append_message(
    conv_id: str,
    message: Dict[str, Any],
    auto_archive: bool = True
) -> bool:
    """
    Append a message to conversation with auto-archiving.
    
    This is the preferred way to add messages as it prevents
    document size issues at scale.
    
    Args:
        conv_id: Conversation ID
        message: Message dict with role, content, optional chart_config
        auto_archive: Whether to auto-archive if threshold exceeded
        
    Returns:
        True if message was appended successfully
    """
    db = get_database()
    
    try:
        # Check and archive if needed
        if auto_archive:
            await auto_archive_if_needed(conv_id)
        
        # Append the message
        result = await db.conversations.update_one(
            {"_id": ObjectId(conv_id)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"Conversation {conv_id} not found when appending message")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to append message to {conv_id}: {e}")
        return False


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
    
    Security: Verifies that the conversation's dataset_id matches the requested dataset
    to prevent accessing conversations from other datasets.
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
                # SECURITY: Verify dataset ownership - conversation must belong to requested dataset
                conv_dataset_id = conv.get("dataset_id")
                if conv_dataset_id and conv_dataset_id != dataset_id:
                    logger.warning(
                        f"Conversation {conv_id} dataset mismatch: "
                        f"conv has {conv_dataset_id}, requested {dataset_id}. "
                        f"Creating new conversation for security."
                    )
                    # Don't return this conversation - create a new one for the requested dataset
                else:
                    # Check message count and prune if needed
                    messages = conv.get("messages", [])
                    if len(messages) > MESSAGE_PRUNE_THRESHOLD:
                        logger.warning(
                            f"Conversation {conv_id} has {len(messages)} messages, "
                            f"approaching limit. Consider archiving."
                        )
                    return conv
        except Exception as e:
            logger.warning(f"Invalid conversation ID '{conv_id}': {e}")

    # Create new conversation
    new_conv = {
        "user_id": user_id,
        "dataset_id": dataset_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
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
