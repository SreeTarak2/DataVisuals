from fastapi import APIRouter, Depends, Request, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
import httpx
from db.schemas import (
    User,
    UserCreate,
    UserUpdate,
    UserLogin,
    LoginResponse,
    PasswordChange,
)
from services.auth_service import auth_service, get_current_user
from services.notifications.hub import notification_hub
from core.rate_limiter import limiter, RateLimits
from core.config import settings


# ── Cookie helpers (HttpOnly JWT cookie + HttpOnly refresh cookie) ───────
# The access token cookie is sent on every API request; the refresh token
# cookie is path-scoped to /api/auth so it is only ever sent to auth
# endpoints (least privilege — the value never reaches other routes).

def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the HttpOnly JWT access-token cookie on the response."""
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN or None,
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear the HttpOnly JWT cookie (used on logout)."""
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=0,  # Expire immediately
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN or None,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the HttpOnly refresh-token cookie (long-lived, rotation-managed)."""
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN or None,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the HttpOnly refresh-token cookie (used on logout)."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value="",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=0,  # Expire immediately
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN or None,
    )

router = APIRouter()


@router.get("/google")
async def google_oauth():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    return RedirectResponse(url=f"{google_auth_url}?{urlencode(params)}")


@router.get("/google/callback")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def google_callback(request: Request, code: str):
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code not provided",
        )

    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=data)
            token_response.raise_for_status()
            tokens = token_response.json()

            access_token = tokens.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to obtain access token from Google",
                )

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()

            result = await auth_service.google_oauth_user(
                email=userinfo.get("email"),
                name=userinfo.get("name"),
                google_id=userinfo.get("id"),
                picture=userinfo.get("picture"),
                device_name=(
                    request.headers.get("X-Device-Name") or "Web browser"
                ),
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )

            # Set HttpOnly cookies AND pass token in URL (frontend callback reads it)
            redirect_url = (
                f"{settings.FRONTEND_URL}/auth/google/callback"
                f"?{urlencode({'token': result.access_token, 'type': result.token_type})}"
            )
            redirect = RedirectResponse(url=redirect_url)
            _set_auth_cookie(redirect, result.access_token)
            _set_refresh_cookie(redirect, result.refresh_token)
            return redirect

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete Google OAuth: {str(e)}",
        )


@router.post("/register", response_model=User)
@limiter.limit(RateLimits.AUTH_REGISTER)
async def register_user(request: Request, user_data: UserCreate):
    return await auth_service.create_user(user_data)


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def login_user(request: Request, login_data: UserLogin, response: Response):
    """
    Authenticate user and return JWT in both:
    - JSON response body (backward compatible with existing clients)
    - HttpOnly cookies (access token + refresh token)
    """
    result = await auth_service.login_user(
        login_data,
        device_name=request.headers.get("X-Device-Name") or "Web browser",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    _set_auth_cookie(response, result.access_token)
    _set_refresh_cookie(response, result.refresh_token)
    return result


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def change_password(
    request: Request,
    payload: PasswordChange,
    current_user: dict = Depends(get_current_user),
):
    await auth_service.change_password(
        current_user["id"],
        payload.old_password,
        payload.new_password,
    )
    return {"message": "Password changed successfully"}


@router.put("/profile", response_model=User)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def update_profile(
    request: Request,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    updated_user = await auth_service.update_user_profile(
        current_user["id"], payload.dict(exclude_unset=True)
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user.pop("hashed_password", None)
    return updated_user

@router.post("/logout")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def logout_user(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """
    Log out the current device: revoke this session server-side (so its
    access token dies instantly via the denylist), clear both cookies, and
    push ``session_revoked`` so any live WebSocket on this account closes.
    """
    jti = current_user.get("jti")
    if jti:
        await auth_service.revoke_session_by_jti(jti, current_user["id"])
    _clear_auth_cookie(response)
    _clear_refresh_cookie(response)
    # Force any open sockets (other devices/tabs) to drop their session state
    notification_hub.schedule_push(
        current_user["id"], {"type": "session_revoked"}
    )
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def logout_all(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """
    Log out every device except this one: revoke all other active sessions.
    The current device keeps its session (access token stays valid); other
    devices are denied on their next request/refresh.
    """
    count = await auth_service.revoke_all_other_sessions(
        current_user["id"], current_user.get("jti")
    )
    return {"message": "Logged out everywhere else", "revoked": count}


@router.post("/refresh")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def refresh_session(
    request: Request,
    response: Response,
):
    """
    Rotate the refresh token and mint a fresh access token.

    The refresh token is read from its HttpOnly cookie (path-scoped to
    /api/auth). Rotation: every call issues a new refresh token and marks
    the old one as used; presenting a used token revokes the session.
    """
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    access_token, new_refresh_token = await auth_service.refresh_session(
        refresh_token, ip=request.client.host if request.client else None
    )
    _set_auth_cookie(response, access_token)
    _set_refresh_cookie(response, new_refresh_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/sessions")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def list_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List active sessions (devices) for the current user, newest first."""
    sessions = await auth_service.list_sessions(current_user["id"])
    current_jti = current_user.get("jti")
    for s in sessions:
        s["is_current"] = s.get("jti") == current_jti
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def revoke_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Revoke a specific session (device) — cannot revoke the current one."""
    session = await auth_service.get_session_by_jti(session_id)
    if not session or session.get("user_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session.get("jti") == current_user.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke the current session — use logout instead",
        )
    await auth_service.revoke_session_by_jti(session_id, current_user["id"])
    return {"message": "Session revoked", "session_id": session_id}


# Token refresh endpoint for WebSocket connections
@router.post("/refresh-token")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def refresh_token(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Refreshes the user's access token.
    This is used by WebSocket connections to get a fresh token when needed.
    """
    # In a real implementation, you would generate a new token here
    # For now, we'll just return the current user's token
    return {"token": current_user.get("token")}




