"""
User API Key Model
===================

Pydantic model + MongoDB document schema for Bring-Your-Own-Key (BYOK)
user-provided API keys.

Each document stores an encrypted API key for a single provider, along
with the user's model selection and validation state.

MongoDB collection: ``user_api_keys``

Partial index on ``user_id + is_active`` ensures fast lookups for active
keys only. A unique index on ``user_id + provider`` prevents duplicate
key registrations for the same provider.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Config ────────────────────────────────────────────────────────────────

class _Config:
    """Shared Pydantic config for all models in this module."""
    extra = "forbid"
    from_attributes = True


# ── Supported providers ───────────────────────────────────────────────────

SUPPORTED_PROVIDERS = frozenset({
    "openai",
    "anthropic",
    "deepseek",
    "google",
})


# ── Create / Update schemas ───────────────────────────────────────────────

class UserApiKeyCreate(BaseModel):
    """Request schema for storing a new API key."""

    provider: str = Field(
        ...,
        description="Provider slug, e.g. 'openai', 'anthropic', 'deepseek', 'google'",
    )
    api_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="The raw API key provided by the user",
    )
    label: str = Field(
        default="",
        max_length=128,
        description="Optional human-readable label for the key",
    )
    selected_models: list[str] = Field(
        default_factory=list,
        description="Models the user selected from the provider's available list",
    )

    class Config(_Config):
        pass


class UserApiKeyUpdate(BaseModel):
    """Request schema for updating an existing API key entry."""

    label: Optional[str] = Field(None, max_length=128)
    selected_models: Optional[list[str]] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = Field(None, min_length=1, max_length=512)

    class Config(_Config):
        pass


# ── Response schema (safe — decrypted key NEVER included) ─────────────────

class UserApiKeyResponse(BaseModel):
    """Schema returned to the client. The ``api_key`` field is NEVER included."""

    id: str = Field(..., description="MongoDB document ID")
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


# ── MongoDB document structure (for documentation / internal use) ─────────
#
# Actual stored document in the ``user_api_keys`` collection:
#
# .. code-block:: json
#
#     {
#       "_id": "<uuid>",
#       "user_id": "abc123",
#       "provider": "openai",
#       "encrypted_key": "<Fernet ciphertext>",
#       "label": "My OpenAI key",
#       "base_url": null,
#       "selected_models": ["gpt-4o", "gpt-4o-mini"],
#       "is_active": true,
#       "validated": true,
#       "last_validated_at": "2026-07-04T12:00:00Z",
#       "created_at": "2026-07-04T12:00:00Z",
#       "updated_at": "2026-07-04T12:00:00Z"
#     }
#
# Indexes (created in db/database.py):
#
#   - ``{ "user_id": 1, "provider": 1 }``  unique  — one active key per provider per user
#   - ``{ "user_id": 1, "is_active": 1 }``         — fast lookup of user's active keys
#   - ``{ "user_id": 1 }``                          — list user's keys
#


# ── Validation helpers ────────────────────────────────────────────────────

KNOWN_PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
        "o4-mini",
    ],
    "anthropic": [
        "claude-sonnet-4",
        "claude-haiku-3.5",
        "claude-fable-5",
        "claude-opus-5",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ],
    "google": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
    ],
}

# Provider API base URLs for direct connections
PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
}

# Provider model list API endpoints (returns available models for the key)
PROVIDER_MODEL_LIST_ENDPOINTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "deepseek": "https://api.deepseek.com/models",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
}


# ── Export ────────────────────────────────────────────────────────────────

__all__ = [
    "SUPPORTED_PROVIDERS",
    "KNOWN_PROVIDER_MODELS",
    "PROVIDER_BASE_URLS",
    "PROVIDER_MODEL_LIST_ENDPOINTS",
    "UserApiKeyCreate",
    "UserApiKeyUpdate",
    "UserApiKeyResponse",
]
