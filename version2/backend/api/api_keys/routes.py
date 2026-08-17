"""
BYOK API Key Management Routes
==============================

REST endpoints for users to manage their own API keys.

Endpoints:
  - POST   /api/v1/keys/discover    — test a key + discover models (no save)
  - POST   /api/v1/keys             — register a new key (validates + encrypts)
  - GET    /api/v1/keys             — list user's active keys
  - GET    /api/v1/keys/{id}        — get a single key's metadata
  - PATCH  /api/v1/keys/{id}        — update key fields or rotate key
  - DELETE /api/v1/keys/{id}        — remove a key
  - POST   /api/v1/keys/{id}/validate  — re-validate an existing key

All endpoints require authentication. Decrypted keys are NEVER returned
in API responses.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.api_keys.schemas import (
    KeyCreateRequest,
    KeyDiscoveryRequest,
    KeyDiscoveryResponse,
    KeyListResponse,
    KeyResponse,
    KeyUpdateRequest,
    KeyValidationResponse,
)
from core.config import settings
from services.api_keys import api_key_service
from services.api_keys.service import (
    APIKeyServiceError,
    DuplicateKeyError,
    KeyNotFoundError,
    KeyValidationError,
)
from services.auth.service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/keys", tags=["8. BYOK API Keys"])


def _check_byok_enabled():
    """Raise 403 if BYOK is disabled via configuration."""
    if not settings.BYOK_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bring Your Own Key (BYOK) is not enabled on this server.",
        )


# ── Discovery ─────────────────────────────────────────────────────────────

@router.post("/discover", response_model=KeyDiscoveryResponse)
async def discover_models(
    payload: KeyDiscoveryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Test an API key against its provider and return available models.

    This endpoint does NOT persist anything. Use it during the setup flow
    to show users which models their key unlocks before they save.
    """
    _check_byok_enabled()

    try:
        models = await api_key_service.discover_models(
            provider=payload.provider,
            api_key=payload.api_key,
        )
        return KeyDiscoveryResponse(
            provider=payload.provider,
            valid=True,
            available_models=models,
        )
    except KeyValidationError as exc:
        return KeyDiscoveryResponse(
            provider=payload.provider,
            valid=False,
            available_models=[],
            error=str(exc),
        )


# ── Create ────────────────────────────────────────────────────────────────

@router.post("", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: KeyCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Register a new API key.

    The key is validated against the provider's API, encrypted with Fernet,
    and stored in the database. The decrypted key is NEVER returned.
    """
    _check_byok_enabled()

    try:
        from db.models.user_api_key import UserApiKeyCreate

        result = await api_key_service.register_key(
            user_id=current_user["id"],
            data=UserApiKeyCreate(
                provider=payload.provider,
                api_key=payload.api_key,
                label=payload.label,
                selected_models=payload.selected_models,
            ),
        )
        return KeyResponse(**result.model_dump())
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except KeyValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except APIKeyServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ── List ──────────────────────────────────────────────────────────────────

@router.get("", response_model=KeyListResponse)
async def list_keys(
    current_user: dict = Depends(get_current_user),
):
    """List all active API keys for the authenticated user."""
    _check_byok_enabled()

    keys = await api_key_service.list_keys(user_id=current_user["id"])
    return KeyListResponse(
        keys=[KeyResponse(**k.model_dump()) for k in keys],
        total=len(keys),
    )


# ── Get ──────────────────────────────────────────────────────────────────

@router.get("/{key_id}", response_model=KeyResponse)
async def get_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single API key's metadata (decrypted key NEVER returned)."""
    _check_byok_enabled()

    key = await api_key_service.get_key(
        user_id=current_user["id"],
        key_id=key_id,
    )
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )
    return KeyResponse(**key.model_dump())


# ── Update ────────────────────────────────────────────────────────────────

@router.patch("/{key_id}", response_model=KeyResponse)
async def update_key(
    key_id: str,
    payload: KeyUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update an existing API key.

    Supports updating label, selected_models, is_active, and api_key
    (key rotation). If ``api_key`` is provided, it will be re-validated
    and re-encrypted.
    """
    _check_byok_enabled()

    try:
        from db.models.user_api_key import UserApiKeyUpdate

        result = await api_key_service.update_key(
            user_id=current_user["id"],
            key_id=key_id,
            data=UserApiKeyUpdate(**payload.model_dump(exclude_unset=True)),
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found.",
            )
        return KeyResponse(**result.model_dump())
    except KeyValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


# ── Delete ────────────────────────────────────────────────────────────────

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete an API key."""
    _check_byok_enabled()

    deleted = await api_key_service.delete_key(
        user_id=current_user["id"],
        key_id=key_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )


# ── Re-validate ──────────────────────────────────────────────────────────

@router.post("/{key_id}/validate", response_model=KeyValidationResponse)
async def validate_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Re-validate an existing stored key against its provider.

    Updates the key's ``validated`` status and ``last_validated_at``
    timestamp. Useful for users to check if their key is still working.
    """
    _check_byok_enabled()

    try:
        result = await api_key_service.validate_existing_key(
            user_id=current_user["id"],
            key_id=key_id,
        )
        return KeyValidationResponse(**result)
    except KeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except APIKeyServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
