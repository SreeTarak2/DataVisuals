"""
Message Tree Service — Conversation Versioning & Branching
============================================================

Production-grade message tree management for AI chat conversations.

Supports:
  - Regenerate: Create a new version of an assistant message (sibling branching)
  - Branch switching: Navigate between parallel conversation branches
  - Version metadata: Track model, latency, temperature per version
  - Active path: Efficient traversal from root to current leaf

Architecture:
  Instead of storing messages as a flat list, we store them as a tree
  using parentId references. Regenerate creates siblings, not overwrites.

  Conversation document structure:
  {
    _id: ObjectId,
    user_id: "...",
    dataset_id: "...",
    active_message_id: "msg_abc",    // leaf of the active branch
    active_branch_id: "branch_main", // which branch is currently active
    messages: [
      {
        id: "msg_abc",
        parent_id: null,             // null for root messages
        version: 1,                  // incremented for sibling regens
        branch_id: "branch_main",    // groups messages in same branch
        role: "user" | "assistant",
        content: "...",
        status: "completed" | "cancelled" | "failed" | "streaming",
        created_at: "...",
        metadata: {
          model: "qwen_2.5_72b",
          latency_ms: 1200,
          temperature: 0.7,
          prompt_version: "v2.1",
          token_count: 512,
          cost_cents: 0.12
        }
      }
    ]
  }
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from db.database import get_database
from services.conversations.conversation_service import (
    load_or_create_conversation,
    save_conversation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _generate_message_id() -> str:
    """Generate a short, unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


def _generate_branch_id() -> str:
    """Generate a unique branch ID."""
    return f"branch_{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    """Current UTC datetime (naive, for MongoDB compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =============================================================================
# Core Tree Operations
# =============================================================================


def build_active_path(messages: List[Dict], active_message_id: Optional[str]) -> List[Dict]:
    """
    Walk the tree from the active message back to root, return ordered path.

    Returns messages from root → leaf based on parent_id chain.
    Returns empty list if active_message_id is None (no path available).
    """
    if not messages or not active_message_id:
        return []

    msg_map = {m["id"]: m for m in messages}
    path = []
    current = active_message_id

    while current and current in msg_map:
        path.append(msg_map[current])
        current = msg_map[current].get("parent_id")

    path.reverse()  # root first
    return path


def build_branch_path(
    messages: List[Dict], branch_id: str
) -> Tuple[List[Dict], Optional[str]]:
    """
    Get the ordered message path for a specific branch.
    Returns (messages_in_branch, leaf_message_id).
    """
    branch_msgs = [m for m in messages if m.get("branch_id") == branch_id]
    if not branch_msgs:
        return [], None

    # O(n) leaf detection: leaf = id not in set of parent_ids
    parent_ids = {m.get("parent_id") for m in branch_msgs}
    leaf_candidates = [m for m in branch_msgs if m["id"] not in parent_ids]
    leaf_id = leaf_candidates[0]["id"] if leaf_candidates else branch_msgs[-1]["id"]

    path = build_active_path(messages, leaf_id)
    return path, leaf_id


def get_versions_for_parent(
    messages: List[Dict], parent_id: str
) -> List[Dict]:
    """Get all assistant messages that share the same parent (sibling versions)."""
    return sorted(
        [
            m
            for m in messages
            if m.get("parent_id") == parent_id and m.get("role") == "assistant"
        ],
        key=lambda m: m.get("version", 1),
    )


# =============================================================================
# Message Creation
# =============================================================================


def create_message(
    role: str,
    content: str,
    parent_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    version: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "completed",
) -> Dict[str, Any]:
    """Create a new message dict with tree metadata."""
    return {
        "id": _generate_message_id(),
        "parent_id": parent_id,
        "version": version,
        "branch_id": branch_id or _generate_branch_id(),
        "role": role,
        "content": content,
        "status": status,
        "created_at": _now(),
        "metadata": metadata or {},
    }


# =============================================================================
# Public API
# =============================================================================


async def get_messages_with_active_branch(
    conv_id: str, user_id: str
) -> Tuple[List[Dict], Optional[str], Optional[str]]:
    """
    Get messages along the active branch path + metadata.

    Returns (active_path, active_message_id, active_branch_id).
    Falls back to all messages if no active branch is set.
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return [], None, None

    messages = conv.get("messages", [])
    active_msg_id = conv.get("active_message_id")
    active_branch_id = conv.get("active_branch_id")

    if active_branch_id:
        path, leaf = build_branch_path(messages, active_branch_id)
        return path, leaf or active_msg_id, active_branch_id

    if active_msg_id:
        path = build_active_path(messages, active_msg_id)
        return path, active_msg_id, None

    # Fallback: return all messages (flat list)
    return messages, None, None


async def regenerate_message(
    conv_id: str,
    message_id: str,
    user_id: str,
    new_content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Regenerate a specific assistant message.

    1. Finds the target message
    2. Creates a new sibling with incremented version
    3. Sets it as the active message
    4. Returns the new message

    Args:
        conv_id: Conversation ID
        message_id: ID of the message to regenerate (must be assistant role)
        user_id: User ID for access control
        new_content: Content for the regenerated version (None = placeholder)
        metadata: LLM metadata for the new version

    Returns:
        The new message dict, or None if regeneration failed
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        logger.warning(f"Conversation {conv_id} not found for regenerate")
        return None

    messages = conv.get("messages", [])
    target = next((m for m in messages if m["id"] == message_id), None)
    if not target:
        logger.warning(f"Message {message_id} not found in conv {conv_id}")
        return None

    if target.get("role") != "assistant":
        logger.warning(f"Can only regenerate assistant messages, got {target.get('role')}")
        return None

    # Count existing siblings to determine next version
    siblings = [
        m
        for m in messages
        if m.get("parent_id") == target.get("parent_id")
        and m.get("role") == "assistant"
    ]
    max_version = max((s.get("version", 1) for s in siblings), default=0)

    new_msg = create_message(
        role="assistant",
        content=new_content or target.get("content", ""),
        parent_id=target.get("parent_id"),
        branch_id=target.get("branch_id"),
        version=max_version + 1,
        metadata=metadata or target.get("metadata", {}),
        status="completed" if new_content else "streaming",
    )

    # Append and update active pointer
    messages.append(new_msg)
    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {
            "$set": {
                "messages": messages,
                "active_message_id": new_msg["id"],
                "active_branch_id": new_msg["branch_id"],
                "updated_at": _now(),
            }
        },
    )

    logger.info(
        f"Regenerated message {message_id} → {new_msg['id']} "
        f"(version {max_version + 1}) in conv {conv_id[:12]}..."
    )
    return new_msg


async def switch_branch(
    conv_id: str, branch_id: str, user_id: str
) -> Tuple[List[Dict], Optional[str]]:
    """
    Switch the active branch of a conversation.

    Returns (new_active_path, leaf_message_id).
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return [], None

    messages = conv.get("messages", [])
    path, leaf_id = build_branch_path(messages, branch_id)

    if leaf_id is None:
        logger.warning(f"Branch {branch_id} not found in conv {conv_id}")
        return messages, None

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {
            "$set": {
                "active_message_id": leaf_id,
                "active_branch_id": branch_id,
                "updated_at": _now(),
            }
        },
    )

    logger.info(f"Switched to branch {branch_id} in conv {conv_id[:12]}...")
    return path, leaf_id


async def get_branches(
    conv_id: str, user_id: str
) -> List[Dict[str, Any]]:
    """
    Get all branches in a conversation with metadata.

    Returns:
        List of {
            branch_id: str,
            version_count: int,
            last_message_preview: str,
            is_active: bool,
            created_at: str
        }
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return []

    messages = conv.get("messages", [])
    active_branch_id = conv.get("active_branch_id")

    # Group messages by branch + build leafs in one pass
    branches: Dict[str, List[Dict]] = {}
    branch_parent_ids: Dict[str, set] = {}
    for m in messages:
        bid = m.get("branch_id", "main")
        if bid not in branches:
            branches[bid] = []
            branch_parent_ids[bid] = set()
        branches[bid].append(m)
        if m.get("parent_id"):
            branch_parent_ids[bid].add(m["parent_id"])

    result = []
    for bid, msgs in branches.items():
        # O(1) leaf detection per branch using pre-built parent set
        leaf_id = None
        for m in msgs:
            if m["id"] not in branch_parent_ids[bid]:
                leaf_id = m["id"]
                break
        if not leaf_id:
            leaf_id = msgs[-1]["id"]

        leaf = next((m for m in msgs if m["id"] == leaf_id), None)

        result.append(
            {
                "branch_id": bid,
                "message_count": len(msgs),
                "version_count": len(
                    [m for m in msgs if m.get("role") == "assistant"]
                ),
                "last_message_preview": (leaf.get("content", "")[:100] + "...")
                if leaf and leaf.get("content")
                else "",
                "last_message_role": leaf.get("role") if leaf else None,
                "is_active": bid == active_branch_id,
                "created_at": min(
                    (m.get("created_at") for m in msgs if m.get("created_at")),
                    default=None,
                ),
            }
        )

    return sorted(result, key=lambda b: b.get("created_at") or "", reverse=True)


async def append_message_to_tree(
    conv_id: str,
    user_id: str,
    role: str,
    content: str,
    parent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Append a new message to the conversation tree.

    If parent_id is provided, the new message is attached to that parent.
    If parent_id is None, it's attached to the current active message.
    The new message becomes the active message.

    Returns the new message dict.
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return None

    messages = conv.get("messages", [])
    active_msg_id = conv.get("active_message_id")

    # Determine parent
    parent = parent_id or active_msg_id
    branch_id = None

    # If parent exists, inherit its branch_id
    if parent:
        parent_msg = next((m for m in messages if m["id"] == parent), None)
        if parent_msg:
            branch_id = parent_msg.get("branch_id")

    new_msg = create_message(
        role=role,
        content=content,
        parent_id=parent,
        branch_id=branch_id,
        metadata=metadata,
        status="completed",
    )

    messages.append(new_msg)

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {
            "$set": {
                "messages": messages,
                "active_message_id": new_msg["id"],
                "active_branch_id": new_msg["branch_id"],
                "updated_at": _now(),
            }
        },
    )

    return new_msg


async def start_streaming_message(
    conv_id: str,
    user_id: str,
    role: str,
    parent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a placeholder message for streaming (status='streaming').
    After streaming completes, call complete_streaming_message().

    Returns the placeholder message.
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return None

    messages = conv.get("messages", [])
    active_msg_id = conv.get("active_message_id")

    parent = parent_id or active_msg_id
    branch_id = None
    if parent:
        parent_msg = next((m for m in messages if m["id"] == parent), None)
        if parent_msg:
            branch_id = parent_msg.get("branch_id")

    placeholder = create_message(
        role=role,
        content="",
        parent_id=parent,
        branch_id=branch_id,
        metadata=metadata,
        status="streaming",
    )

    messages.append(placeholder)

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {
            "$set": {
                "messages": messages,
                "active_message_id": placeholder["id"],
                "active_branch_id": placeholder["branch_id"],
                "updated_at": _now(),
            }
        },
    )

    return placeholder


async def complete_streaming_message(
    conv_id: str,
    user_id: str,
    message_id: str,
    content: str,
    status: str = "completed",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Update a streaming placeholder with completed content.
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return False

    messages = conv.get("messages", [])
    for m in messages:
        if m["id"] == message_id:
            m["content"] = content
            m["status"] = status
            if metadata:
                m["metadata"].update(metadata)
            break
    else:
        return False

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {"$set": {"messages": messages, "updated_at": _now()}},
    )
    return True


# =============================================================================
# Migration Helper: Convert flat messages to tree format
# =============================================================================


async def migrate_flat_to_tree(conv_id: str, user_id: str) -> bool:
    """
    Migrate a conversation from flat message format to tree format.

    Flat format: [{role, content, ...}] - no ids, no parent
    Tree format: [{id, parent_id, role, content, version, branch_id, ...}]

    This is a one-time migration for existing conversations.
    """
    db = get_database()
    conv = await db.conversations.find_one(
        {"_id": ObjectId(conv_id), "user_id": user_id}
    )
    if not conv:
        return False

    messages = conv.get("messages", [])
    if not messages:
        return True  # Nothing to migrate

    # Check if already migrated (has "id" field)
    if messages and "id" in messages[0]:
        logger.info(f"Conversation {conv_id[:12]}... already in tree format")
        return True

    # Convert flat messages to tree
    tree_messages = []
    prev_id = None
    branch_id = _generate_branch_id()

    for i, msg in enumerate(messages):
        msg_id = _generate_message_id()
        tree_msg = {
            "id": msg_id,
            "parent_id": prev_id,
            "version": 1,
            "branch_id": branch_id,
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
            "status": "completed",
            "created_at": msg.get("created_at", _now()),
            "metadata": {
                "chart_config": msg.get("chart_config"),
                "sql": msg.get("sql"),
                "result_table": msg.get("result_table"),
                "confidence": msg.get("confidence", "ai_analysis"),
            },
        }
        # Clean None values from metadata
        tree_msg["metadata"] = {
            k: v for k, v in tree_msg["metadata"].items() if v is not None
        }

        tree_messages.append(tree_msg)
        prev_id = msg_id

    active_id = tree_messages[-1]["id"] if tree_messages else None

    await db.conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {
            "$set": {
                "messages": tree_messages,
                "active_message_id": active_id,
                "active_branch_id": branch_id,
                "updated_at": _now(),
            }
        },
    )

    logger.info(
        f"Migrated conv {conv_id[:12]}... from {len(messages)} flat msgs "
        f"to {len(tree_messages)} tree msgs"
    )
    return True


__all__ = [
    "regenerate_message",
    "switch_branch",
    "get_branches",
    "get_messages_with_active_branch",
    "append_message_to_tree",
    "start_streaming_message",
    "complete_streaming_message",
    "migrate_flat_to_tree",
    "build_active_path",
    "build_branch_path",
    "get_versions_for_parent",
]
