from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class _Config:
    orm_mode = True
    extra = "forbid"
    use_enum_values = True


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr

    class Config(_Config):
        pass


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

    class Config(_Config):
        pass


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    class Config(_Config):
        pass


class User(BaseModel):
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


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None

    class Config(_Config):
        pass


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

    class Config(_Config):
        pass


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: User

    class Config(_Config):
        pass


class TokenData(BaseModel):
    email: Optional[str] = None

    class Config(_Config):
        pass


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)

    class Config(_Config):
        pass


__all__ = [
    "UserBase",
    "UserCreate",
    "UserLogin",
    "User",
    "UserUpdate",
    "Token",
    "LoginResponse",
    "TokenData",
    "PasswordChange",
]
