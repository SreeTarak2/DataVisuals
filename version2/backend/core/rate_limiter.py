"""
Rate Limiting Configuration for Signal API
================================================

Centralized rate limiting using slowapi to protect against:
- Brute-force attacks on auth endpoints
- LLM endpoint abuse (OpenRouter has its own limits)
- DoS via excessive requests
- Resource exhaustion from file uploads

Usage in routers:
    from core.rate_limiter import limiter

    @router.post("/login")
    @limiter.limit("5/minute")
    async def login(request: Request, ...):
        ...
"""

import os
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ============================================================
# KEY FUNCTION - Identifies the client for rate limiting
# ============================================================


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.

    Priority:
    1. Authenticated user ID (from JWT)
    2. Client IP address

    This ensures:
    - Authenticated users are limited per-user (not per-IP)
    - Unauthenticated requests are limited per-IP
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


# ============================================================
# LIMITER CONFIGURATION
# ============================================================

# Create the limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100/minute"],  # Global default
    storage_uri=os.getenv("REDIS_URL", "memory://"),  # Use Redis if available
    strategy="fixed-window",
)

# ============================================================
# RATE LIMIT PRESETS
# ============================================================


class RateLimits:
    """Centralized rate limit definitions for consistency."""

    # Authentication - strict limits to prevent brute force
    AUTH_LOGIN = "5/minute"
    AUTH_REGISTER = "3/minute"
    AUTH_PASSWORD_RESET = "3/hour"

    # LLM endpoints - protect OpenRouter quotas
    CHAT_MESSAGE = "30/minute"
    CHAT_STREAMING = "20/minute"
    AI_DASHBOARD = "10/minute"
    AI_INSIGHTS = "20/minute"
    CHART_RETRY = "30/minute"  # Higher limit for chart retry operations

    # Dataset operations
    DATASET_UPLOAD = "10/hour"
    DATASET_REPROCESS = "5/hour"
    DATASET_UPDATE = "30/minute"
    DATASET_READ = "60/minute"

    # Chart operations
    CHART_RENDER = "60/minute"
    CHART_RECOMMENDATIONS = "30/minute"

    # Analysis
    ANALYSIS_RUN = "20/minute"

    # Database connections
    DB_TEST = "10/minute"  # test without saving — relaxed
    DB_CONNECT = "5/hour"  # saving a connection is rare
    DB_LIST = "60/minute"  # read operations
    DB_EXTRACT = "5/hour"  # extraction triggers a full Celery pipeline

    # Default for misc endpoints
    DEFAULT = "100/minute"

    # Legacy aliases kept for backward compatibility with older route modules
    CHAT_LIST = CHAT_MESSAGE
    DATASET_LIST = DATASET_READ
    DATASET_GET = DATASET_READ
    DATASET_DELETE = DATASET_READ
    ANALYSIS_CREATE = ANALYSIS_RUN
    DASHBOARD_CREATE = AI_DASHBOARD


# ============================================================
# EXCEPTION HANDLER
# ============================================================


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    Returns a user-friendly JSON response with retry information.
    """
    # Extract retry-after if available
    retry_after = getattr(exc, "retry_after", 60)

    logger.warning(f"Rate limit exceeded for {get_rate_limit_key(request)}: {exc.detail}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": "Too many requests. Please slow down.",
            "retry_after_seconds": retry_after,
            "limit": str(exc.detail) if hasattr(exc, "detail") else "Unknown",
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(exc.detail) if hasattr(exc, "detail") else "Unknown",
        },
    )


# ============================================================
# HELPER DECORATORS
# ============================================================


def limit_auth(func):
    """Apply auth-specific rate limits."""
    return limiter.limit(RateLimits.AUTH_LOGIN)(func)


def limit_chat(func):
    """Apply chat-specific rate limits."""
    return limiter.limit(RateLimits.CHAT_MESSAGE)(func)


def limit_upload(func):
    """Apply upload-specific rate limits."""
    return limiter.limit(RateLimits.DATASET_UPLOAD)(func)
