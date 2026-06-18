"""Error handling and fallback generation for chat streaming.

Provides:
- Safe error messages (no leaking internals)
- Friendly fallback suggestions
- Structured error events
"""
import logging
from typing import Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    RATE_LIMITED = "rate_limited"
    DATASET_ERROR = "dataset_error"
    MODEL_ERROR = "model_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    UNKNOWN = "unknown"


def categorize_error(error_str: str) -> ErrorCategory:
    """Classify error by pattern."""
    lower = error_str.lower()
    if "429" in error_str or "rate" in lower or "throttle" in lower:
        return ErrorCategory.RATE_LIMITED
    if "dataset" in lower or "not found" in lower or "column" in lower:
        return ErrorCategory.DATASET_ERROR
    if "model" in lower or "llm" in lower or "api" in lower:
        return ErrorCategory.MODEL_ERROR
    if "timeout" in lower or "timed out" in lower:
        return ErrorCategory.TIMEOUT
    if "dns" in lower or "connection" in lower or "network" in lower:
        return ErrorCategory.NETWORK_ERROR
    if "unauthorized" in lower or "auth" in lower or "403" in error_str:
        return ErrorCategory.AUTH_ERROR
    return ErrorCategory.UNKNOWN


def create_error_event(category: ErrorCategory, internal_error: str) -> Dict[str, Any]:
    """Create a safe error event for frontend."""
    friendly_messages = {
        ErrorCategory.RATE_LIMITED: (
            "I'm receiving high traffic. Please try again in a few moments."
        ),
        ErrorCategory.DATASET_ERROR: (
            "I couldn't access the dataset. Please check that it exists and try again."
        ),
        ErrorCategory.MODEL_ERROR: (
            "The AI model is temporarily unavailable. Please try again shortly."
        ),
        ErrorCategory.NETWORK_ERROR: (
            "Network connection issue. Please check your internet and try again."
        ),
        ErrorCategory.TIMEOUT: (
            "The request took too long. Please try a simpler question or try again."
        ),
        ErrorCategory.AUTH_ERROR: (
            "Authentication failed. Please log in again."
        ),
        ErrorCategory.UNKNOWN: (
            "Something went wrong. Please try again or contact support."
        ),
    }
    
    message = friendly_messages.get(category, friendly_messages[ErrorCategory.UNKNOWN])
    
    logger.error(f"Chat error ({category.value}): {internal_error}")
    
    return {
        "type": "error",
        "content": message,
        "category": category.value,
        "recoverable": category != ErrorCategory.AUTH_ERROR,
    }


def create_fallback_response(reason: str, query: str = "") -> str:
    """Generate a friendly fallback response."""
    fallback_templates = {
        "rate_limited": "I'm currently at capacity. Please wait a moment and try again.",
        "timeout": f"I couldn't process your question fast enough. Try asking in a simpler way.",
        "model_unavailable": "My AI models are temporarily unavailable. I'll be back soon.",
        "dataset_error": "I'm having trouble accessing your data. Please verify the dataset and try again.",
        "general": "I encountered an unexpected issue. Please try again.",
    }
    
    template = fallback_templates.get(reason, fallback_templates["general"])
    
    if query:
        template += f"\n\nYour question was: *{query[:100]}*"
    
    return template
