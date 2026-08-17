"""
API Key Route Schemas
=====================

Request/response schemas for the BYOK API key management endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from db.models.user_api_key import SUPPORTED_PROVIDERS


class _Config:
    extra = "forbid"
    from_attributes = True


# ── Discovery ─────────────────────────────────────────────────────────────

class KeyDiscoveryRequest(BaseModel):
    """Test an API key and discover available models (no persistence)."""

    provider: str = Field(
        ...,
        description=f"Provider slug. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
    )
    api_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="The API key to test against the provider",
    )

    class Config(_Config):
        pass


class KeyDiscoveryResponse(BaseModel):
    """Result of key validation + model discovery."""

    provider: str
    valid: bool
    available_models: list[str] = Field(default_factory=list)
    error: Optional[str] = None

    class Config(_Config):
        pass


# ── Create ────────────────────────────────────────────────────────────────

class KeyCreateRequest(BaseModel):
    """Register a new API key (validated and encrypted before storage)."""

    provider: str = Field(
        ...,
        description=f"Provider slug. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
    )
    api_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="The API key to store (will be encrypted at rest)",
    )
    label: str = Field(
        default="",
        max_length=128,
        description="Optional human-readable label",
    )
    selected_models: list[str] = Field(
        default_factory=list,
        description="Models to enable. Defaults to all discovered models if empty.",
    )

    class Config(_Config):
        pass


# ── Update ────────────────────────────────────────────────────────────────

class KeyUpdateRequest(BaseModel):
    """Update fields on an existing API key entry."""

    label: Optional[str] = Field(None, max_length=128)
    selected_models: Optional[list[str]] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = Field(
        None,
        min_length=1,
        max_length=512,
        description="New API key (will be re-validated and re-encrypted)",
    )

    class Config(_Config):
        pass


# ── Response ──────────────────────────────────────────────────────────────

class KeyResponse(BaseModel):
    """Safe key response — NEVER includes the decrypted API key."""

    id: str
    provider: str
    label: str
    selected_models: list[str]
    base_url: Optional[str] = None
    is_active: bool
    validated: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config(_Config):
        pass


class KeyListResponse(BaseModel):
    """List of API keys for a user."""

    keys: list[KeyResponse]
    total: int

    class Config(_Config):
        pass


class KeyValidationResponse(BaseModel):
    """Result of re-validating an existing stored key."""

    valid: bool
    last_validated_at: str
    error: Optional[str] = None
    available_models: list[str] = Field(default_factory=list)

    class Config(_Config):
        pass


__all__ = [
    "KeyDiscoveryRequest",
    "KeyDiscoveryResponse",
    "KeyCreateRequest",
    "KeyUpdateRequest",
    "KeyResponse",
    "KeyListResponse",
    "KeyValidationResponse",
]
