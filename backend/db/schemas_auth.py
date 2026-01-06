"""
Authentication Schemas (Core)
-----------------------------
These schemas define:
- User accounts
- Registration and login requests
- Access tokens
- Token validation payloads
- Profile updates

They are exclusively used by:
- AuthService
- Auth API routes
- JWT handler functions
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ---------------------------------------------------
# Base Config
# ---------------------------------------------------
class _Config:
    orm_mode = True
    extra = "forbid"
    use_enum_values = True


# ---------------------------------------------------
# USER MODELS
# ---------------------------------------------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr

    class Config(_Config):
        pass


class UserCreate(UserBase):
    """
    Used for user.registration
    """
    password: str = Field(..., min_length=6, max_length=128)

    class Config(_Config):
        pass


class UserLogin(BaseModel):
    """
    Used for user.login
    """
    email: EmailStr
    password: str

    class Config(_Config):
        pass


class User(BaseModel):
    """
    Full user model returned to the client.
    """
    id: str
    username: str
    email: EmailStr
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config(_Config):
        pass


# ---------------------------------------------------
# TOKEN SCHEMAS
# ---------------------------------------------------
class Token(BaseModel):
    """
    Used for JWT access tokens.
    """
    access_token: str
    token_type: str
    expires_in: int

    class Config(_Config):
        pass


class LoginResponse(BaseModel):
    """
    Returned after successful login.
    """
    access_token: str
    token_type: str
    expires_in: int
    user: User

    class Config(_Config):
        pass


class TokenData(BaseModel):
    """
    Used to validate JWT payload.
    Optional fields allow token presence only validation.
    """
    email: Optional[str] = None

    class Config(_Config):
        pass


# ---------------------------------------------------
# PROFILE UPDATE & PASSWORD CHANGE
# ---------------------------------------------------
class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)

    class Config(_Config):
        pass


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)

    class Config(_Config):
        pass


# ---------------------------------------------------
# Export
# ---------------------------------------------------
__all__ = [
    "UserBase",
    "UserCreate",
    "UserLogin",
    "User",
    "Token",
    "LoginResponse",
    "TokenData",
    "UserProfileUpdate",
    "PasswordChange",
]
