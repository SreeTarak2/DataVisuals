# backend/api/auth.py

from fastapi import APIRouter, Depends
from db.schemas import User, UserCreate, UserLogin, LoginResponse
from services.auth_service import auth_service, get_current_user

# Create an APIRouter instance. This is like a "mini-FastAPI" app.
router = APIRouter()

# --- Authentication Endpoints ---

@router.post("/register", response_model=User)
async def register_user(user_data: UserCreate):
    """Handles new user registration."""
    return await auth_service.create_user(user_data)

@router.post("/login", response_model=LoginResponse)
async def login_user(login_data: UserLogin):
    """Handles user login and returns a JWT access token."""
    return await auth_service.login_user(login_data)

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Returns the profile information of the currently authenticated user."""
    return current_user