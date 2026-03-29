# backend/api/auth.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
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
from core.rate_limiter import limiter, RateLimits
from core.config import settings

# Create an APIRouter instance. This is like a "mini-FastAPI" app.
router = APIRouter()

# --- Google OAuth ---


@router.get("/google")
async def google_oauth():
    """Redirects user to Google OAuth consent screen."""
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
    """Handles Google OAuth callback, exchanges code for tokens, and returns JWT."""
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
            )

            redirect_url = f"{settings.FRONTEND_URL}/auth/google/callback?{urlencode({'token': result.access_token, 'type': result.token_type})}"
            return RedirectResponse(url=redirect_url)

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to complete Google OAuth: {str(e)}",
        )


# --- Authentication Endpoints ---


@router.post("/register", response_model=User)
@limiter.limit(RateLimits.AUTH_REGISTER)
async def register_user(request: Request, user_data: UserCreate):
    """Handles new user registration."""
    return await auth_service.create_user(user_data)


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def login_user(request: Request, login_data: UserLogin):
    """Handles user login and returns a JWT access token."""
    return await auth_service.login_user(login_data)


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Returns the profile information of the currently authenticated user."""
    return current_user


@router.post("/change-password")
@limiter.limit(RateLimits.AUTH_LOGIN)
async def change_password(
    request: Request,
    payload: PasswordChange,
    current_user: dict = Depends(get_current_user),
):
    """Changes password for the currently authenticated user."""
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
    """Updates profile information for the currently authenticated user."""
    updated_user = await auth_service.update_user_profile(
        current_user["id"],
        payload.dict(exclude_unset=True)
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated_user.pop("hashed_password", None)
    return updated_user
