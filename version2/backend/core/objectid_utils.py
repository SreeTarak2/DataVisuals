"""
ObjectId Validation Utilities
==============================

Safe helpers for MongoDB ObjectId conversion across the codebase.

Problems it solves:
- ObjectId("") / ObjectId("invalid") raises bson.errors.InvalidId
- 40+ call sites in the codebase use raw ObjectId() with user-provided strings
- Inconsistent error handling — some wrap in try/except, most don't

Usage:
    from core.objectid_utils import safe_objectid, is_valid_objectid

    # Safe conversion — returns None on invalid
    oid = safe_objectid(dataset_id)
    if oid is None:
        raise HTTPException(400, "Invalid dataset ID")

    # Validation check
    if not is_valid_objectid(dataset_id):
        return {"error": "Invalid ID"}

    # One-liner with default fallback
    oid = safe_objectid(conversation_id) or ObjectId()
"""

import logging
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId

logger = logging.getLogger(__name__)


def is_valid_objectid(id_str: Optional[str]) -> bool:
    """
    Check if a string is a valid MongoDB ObjectId.

    Args:
        id_str: String to validate (can be None)

    Returns:
        True if the string is a valid 24-character hex ObjectId

    Example:
        >>> is_valid_objectid("507f1f77bcf86cd799439011")
        True
        >>> is_valid_objectid("invalid")
        False
        >>> is_valid_objectid(None)
        False
        >>> is_valid_objectid("")
        False
    """
    if not id_str:
        return False
    return ObjectId.is_valid(id_str)


def safe_objectid(id_str: Optional[str]) -> Optional[ObjectId]:
    """
    Safely convert a string to a MongoDB ObjectId.

    Returns None (instead of raising InvalidId) when the string
    is not a valid ObjectId. Never raises.

    Args:
        id_str: String to convert (can be None)

    Returns:
        ObjectId if valid, None otherwise

    Example:
        >>> safe_objectid("507f1f77bcf86cd799439011")
        ObjectId('507f1f77bcf86cd799439011')
        >>> safe_objectid("invalid") is None
        True
        >>> safe_objectid(None) is None
        True
    """
    if not id_str:
        return None
    try:
        if ObjectId.is_valid(id_str):
            return ObjectId(id_str)
        return None
    except (InvalidId, TypeError) as e:
        logger.debug("Invalid ObjectId string '%s': %s", str(id_str or '')[:20], e)
        return None


def require_objectid(id_str: str, field_name: str = "ID") -> ObjectId:
    """
    Convert a string to ObjectId, raising ValueError on failure.

    Use this in route handlers where an invalid ID should produce
    an HTTP 400 response.

    Args:
        id_str: String to convert
        field_name: Human-readable field name for the error message

    Returns:
        ObjectId

    Raises:
        ValueError: If id_str is not a valid ObjectId

    Example:
        try:
            oid = require_objectid(dataset_id, "dataset_id")
        except ValueError as e:
            raise HTTPException(400, str(e))
    """
    oid = safe_objectid(id_str)
    if oid is None:
        raise ValueError(f"Invalid {field_name}: '{id_str}' is not a valid ObjectId")
    return oid
