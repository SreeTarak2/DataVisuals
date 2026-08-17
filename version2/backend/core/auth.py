"""
HTTP Cookie & CSRF Authentication
==================================
Provides:
  1. get_token_from_request — Extracts JWT from HttpOnly cookie or Authorization header
  2. CSRFProtectionMiddleware — Requires custom header on state-changing requests

Usage (token extraction — used by services/auth/service.py):
    from core.auth import get_token_from_request

    @router.get("/protected")
    async def protected(token: str = Depends(get_token_from_request)):
        ...

Usage (CSRF — registered in main.py):
    app.add_middleware(CSRFProtectionMiddleware)

Transition strategy:
    - Phase 1: Accept tokens from both cookies AND Authorization header
    - Phase 2 (future): Drop Authorization header support once all clients migrate
"""

import logging
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Auth Token Extraction
# ═══════════════════════════════════════════════════════════════════════════════

async def get_token_from_request(request: Request) -> str:
    """
    Extract a Bearer JWT token from the request.

    Resolution order:
      1. ``access_token`` HttpOnly cookie (primary — Phase 1+)
      2. ``Authorization: Bearer <token>`` header (fallback — backward compat)

    Returns the raw token string.

    Raises ``401 Unauthorized`` if neither source provides a valid token.
    """
    # 1. Try HttpOnly cookie (new in Phase 1 — set by /auth/login, /auth/google/callback)
    cookie = request.cookies.get("access_token")
    if cookie:
        scheme, param = get_authorization_scheme_param(cookie)
        if scheme.lower() == "bearer":
            return param

    # 2. Try Authorization header (legacy — maintained for backward compat)
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, param = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer":
            return param

    # 3. No token found
    logger.debug("No Bearer token found in cookie or Authorization header")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  CSRF Protection Middleware
# ═══════════════════════════════════════════════════════════════════════════════
#
# How it works:
#   SPAs that use JSON APIs are inherently protected against classic form-based
#   CSRF because browsers enforce CORS on XMLHttpRequest/fetch — a malicious
#   <form> cannot read the response of a cross-origin XHR.
#
#   This middleware adds defense-in-depth:
#     1. Auth cookie uses SameSite=Lax (prevents cross-site POSTs from external
#        <form> submissions in most cases).
#     2. State-changing requests (POST/PUT/PATCH/DELETE) must include a custom
#        header ``X-CSRF-Protection: 1`` that plain HTML <form> elements cannot
#        set. The frontend axios interceptor adds this header to all requests.
#
#   The combination of SameSite=Lax + custom-header check covers all practical
#   CSRF vectors for an SPA with a JSON API.
# ═══════════════════════════════════════════════════════════════════════════════

class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that requires ``X-CSRF-Protection: 1`` on state-changing requests.

    Safe methods (GET, HEAD, OPTIONS, TRACE) are exempt.

    **Exempt paths:** Auth and health endpoints must be reachable without CSRF
    protection — they are the entry points where a session is established.

    **Gating:** Controlled by ``settings.CSRF_ENABLED``. Phase 1 deploys with
    CSRF disabled (``false``) so existing Bearer-header clients continue to work.
    Set ``CSRF_ENABLED=true`` once the frontend sends the custom header (Phase 2).
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
    REQUIRED_HEADER = "X-CSRF-Protection"
    REQUIRED_VALUE = "1"

    # Paths that are exempt from CSRF checking.
    # Auth endpoints must be reachable without a session (chicken-and-egg).
    # Health endpoint is public.
    EXEMPT_PATHS = frozenset({
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/google",
        "/api/auth/google/callback",
        "/health",
    })

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        from core.config import settings
        self._enabled = settings.CSRF_ENABLED
        if self._enabled:
            logger.info("CSRF protection is ENABLED")
        else:
            logger.info("CSRF protection is DISABLED (set CSRF_ENABLED=true in production)")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip entire check if disabled
        if not self._enabled:
            return await call_next(request)

        # Exempt safe methods and pre-configured paths
        if request.method in self.SAFE_METHODS or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Enforce CSRF header on state-changing requests
        header_value = request.headers.get(self.REQUIRED_HEADER)
        if header_value != self.REQUIRED_VALUE:
            logger.warning(
                "CSRF check failed: %s %s (header=%r)",
                request.method,
                request.url.path,
                header_value,
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": (
                        "CSRF protection: missing required request header. "
                        "Ensure your client sends X-CSRF-Protection: 1 "
                        "on state-changing requests."
                    ),
                },
            )
        return await call_next(request)
