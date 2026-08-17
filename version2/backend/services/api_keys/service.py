"""
API Key Service — CRUD, Validation & Model Discovery
=====================================================

Handles the full lifecycle of user-provided API keys:
  - Encrypt at rest (Fernet via services/encryption)
  - Validate keys against provider APIs before storing
  - Discover available models from provider's model list API
  - Provide runtime decryption for LLM routing

All decrypted keys are returned ONLY to the caller (via ``get_decrypted_key``)
and are NEVER exposed through list/get response APIs.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx

from core.config import settings
from db.database import get_database
from db.models.user_api_key import (
    SUPPORTED_PROVIDERS,
    PROVIDER_BASE_URLS,
    PROVIDER_MODEL_LIST_ENDPOINTS,
    UserApiKeyCreate,
    UserApiKeyResponse,
    UserApiKeyUpdate,
)
from services.encryption import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)


class APIKeyServiceError(Exception):
    """Base exception for API key service errors."""
    pass


class KeyValidationError(APIKeyServiceError):
    """Raised when a key fails provider validation."""
    pass


class DuplicateKeyError(APIKeyServiceError):
    """Raised when a key for the same provider already exists for the user."""
    pass


class KeyNotFoundError(APIKeyServiceError):
    """Raised when a requested key is not found."""
    pass


# ── HTTP client for provider API calls ────────────────────────────────────

_provider_http: httpx.AsyncClient | None = None


def _get_http() -> httpx.AsyncClient:
    global _provider_http
    if _provider_http is None:
        _provider_http = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    return _provider_http


# ── Service ───────────────────────────────────────────────────────────────

class APIKeyService:
    """Manages user-provided API key lifecycle."""

    # ── Public: Registration ─────────────────────────────────────────────

    async def register_key(
        self,
        user_id: str,
        data: UserApiKeyCreate,
    ) -> UserApiKeyResponse:
        """
        Validate, encrypt, and store a new API key.

        Args:
            user_id: The authenticated user's ID.
            data: Key creation payload (provider, api_key, label, selected_models).

        Returns:
            UserApiKeyResponse (safe — no decrypted key).

        Raises:
            KeyValidationError: If the key fails validation against the provider.
            DuplicateKeyError: If a key for this provider already exists.
        """
        provider = data.provider.lower()

        if provider not in SUPPORTED_PROVIDERS:
            raise KeyValidationError(
                f"Unsupported provider '{data.provider}'. "
                f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )

        # ── Validate the key against the provider's API ──
        validation = await self._test_key_against_provider(
            provider=provider,
            api_key=data.api_key,
        )
        if not validation.get("valid", False):
            raise KeyValidationError(
                f"API key validation failed for {provider}: "
                f"{validation.get('error', 'unknown error')}"
            )

        # ── Discover available models ──
        available_models = validation.get("models", [])
        logger.info(
            "Key validated for %s — %d models available for user %s",
            provider,
            len(available_models),
            user_id[:8],
        )

        # ── Deduplicate: one active key per provider per user ──
        db = get_database()
        existing = await db.user_api_keys.find_one(
            {"user_id": user_id, "provider": provider, "is_active": True}
        )
        if existing:
            raise DuplicateKeyError(
                f"You already have an active {provider} API key. "
                "Deactivate or delete the existing key first."
            )

        # ── Encrypt and store ──
        encrypted = encrypt_api_key(data.api_key)
        key_id = str(uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        doc = {
            "_id": key_id,
            "user_id": user_id,
            "provider": provider,
            "encrypted_key": encrypted,
            "label": data.label or f"{provider.title()} API Key",
            "base_url": None,
            "selected_models": data.selected_models or available_models,
            "is_active": True,
            "validated": True,
            "last_validated_at": now,
            "created_at": now,
            "updated_at": now,
        }

        await db.user_api_keys.insert_one(doc)

        logger.info(
            "Registered %s API key for user %s (id=%s) — %d models selected",
            provider,
            user_id[:8],
            key_id[:8],
            len(doc["selected_models"]),
        )

        return self._safe_response(doc, key_id)

    # ── Public: Discovery (validate without storing) ─────────────────────

    async def discover_models(
        self,
        provider: str,
        api_key: str,
    ) -> list[str]:
        """
        Validate an API key and return available models, without storing.

        Used during the setup flow before the user commits to saving.

        Args:
            provider: Provider slug (e.g., 'openai', 'anthropic').
            api_key: The raw API key to test.

        Returns:
            List of available model IDs (e.g., ``["gpt-4o", "gpt-4o-mini"]``).

        Raises:
            KeyValidationError: If the key is invalid or the provider is unsupported.
        """
        provider = provider.lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise KeyValidationError(
                f"Unsupported provider '{provider}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )

        validation = await self._test_key_against_provider(
            provider=provider,
            api_key=api_key,
        )
        if not validation.get("valid", False):
            raise KeyValidationError(
                f"Key validation failed for {provider}: "
                f"{validation.get('error', 'unknown error')}"
            )

        return validation.get("models", [])

    # ── Public: Runtime decryption ───────────────────────────────────────

    async def get_decrypted_key(
        self,
        user_id: str,
        provider: str,
    ) -> Optional[dict]:
        """
        Retrieve and decrypt a user's API key for runtime use.

        This is the ONLY path that returns a decrypted key. It is called
        by the LLM router before making a direct provider call.

        Args:
            user_id: The authenticated user's ID.
            provider: Provider slug.

        Returns:
            Dict with ``api_key``, ``provider``, ``selected_models``, ``base_url``,
            or ``None`` if no active key exists.
        """
        db = get_database()
        doc = await db.user_api_keys.find_one(
            {"user_id": user_id, "provider": provider, "is_active": True}
        )
        if not doc:
            return None

        try:
            plain_key = decrypt_api_key(doc["encrypted_key"])
        except Exception as exc:
            logger.error(
                "Failed to decrypt %s key for user %s: %s",
                provider,
                user_id[:8],
                exc,
            )
            return None

        return {
            "api_key": plain_key,
            "provider": provider,
            "selected_models": doc.get("selected_models", []),
            "base_url": doc.get("base_url") or PROVIDER_BASE_URLS.get(provider),
            "key_id": doc["_id"],
        }

    # ── Public: CRUD ─────────────────────────────────────────────────────

    async def list_keys(self, user_id: str) -> list[UserApiKeyResponse]:
        """List all active API keys for a user (decrypted key NEVER exposed)."""
        db = get_database()
        docs = []
        async for doc in db.user_api_keys.find(
            {"user_id": user_id, "is_active": True},
            {"encrypted_key": 0},  # Never expose encrypted blob either
        ).sort("created_at", -1):
            docs.append(self._safe_response(doc, doc["_id"]))
        return docs

    async def get_key(self, user_id: str, key_id: str) -> Optional[UserApiKeyResponse]:
        """Get a single key by ID (decrypted key NEVER exposed)."""
        db = get_database()
        doc = await db.user_api_keys.find_one(
            {"_id": key_id, "user_id": user_id},
            {"encrypted_key": 0},
        )
        if not doc:
            return None
        return self._safe_response(doc, key_id)

    async def update_key(
        self,
        user_id: str,
        key_id: str,
        data: UserApiKeyUpdate,
    ) -> Optional[UserApiKeyResponse]:
        """
        Update an existing API key entry.

        Supports updating label, selected_models, is_active, and api_key.
        If api_key is provided, it will be re-validated and re-encrypted.
        """
        db = get_database()
        doc = await db.user_api_keys.find_one(
            {"_id": key_id, "user_id": user_id}
        )
        if not doc:
            return None

        update = {}
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if data.label is not None:
            update["label"] = data.label
        if data.selected_models is not None:
            update["selected_models"] = data.selected_models
        if data.is_active is not None:
            update["is_active"] = data.is_active

        if data.api_key is not None:
            # Re-validate the new key
            provider = doc["provider"]
            validation = await self._test_key_against_provider(
                provider=provider,
                api_key=data.api_key,
            )
            if not validation.get("valid", False):
                raise KeyValidationError(
                    f"New API key validation failed for {provider}: "
                    f"{validation.get('error', 'unknown error')}"
                )
            update["encrypted_key"] = encrypt_api_key(data.api_key)
            update["validated"] = True
            update["last_validated_at"] = now

            # Update available models
            available = validation.get("models", [])
            if not data.selected_models:
                update["selected_models"] = available

        if not update:
            return await self.get_key(user_id, key_id)

        update["updated_at"] = now
        await db.user_api_keys.update_one(
            {"_id": key_id, "user_id": user_id},
            {"$set": update},
        )

        return await self.get_key(user_id, key_id)

    async def delete_key(self, user_id: str, key_id: str) -> bool:
        """Soft-delete (set is_active=False) or hard-delete an API key."""
        db = get_database()
        result = await db.user_api_keys.delete_one(
            {"_id": key_id, "user_id": user_id}
        )
        if result.deleted_count == 0:
            return False
        logger.info("Deleted API key %s for user %s", key_id[:8], user_id[:8])
        return True

    async def validate_existing_key(
        self,
        user_id: str,
        key_id: str,
    ) -> dict:
        """
        Re-validate a stored key against its provider.

        Updates ``last_validated_at`` and emits a warning log if validation
        fails (but does NOT deactivate the key automatically — that's a
        user decision).
        """
        db = get_database()
        doc = await db.user_api_keys.find_one(
            {"_id": key_id, "user_id": user_id}
        )
        if not doc:
            raise KeyNotFoundError("API key not found.")

        try:
            plain_key = decrypt_api_key(doc["encrypted_key"])
        except Exception as exc:
            raise KeyValidationError(f"Failed to decrypt key: {exc}")

        validation = await self._test_key_against_provider(
            provider=doc["provider"],
            api_key=plain_key,
        )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        is_valid = validation.get("valid", False)

        await db.user_api_keys.update_one(
            {"_id": key_id},
            {
                "$set": {
                    "validated": is_valid,
                    "last_validated_at": now,
                    "updated_at": now,
                }
            },
        )

        if not is_valid:
            logger.warning(
                "API key %s for user %s (%s) failed re-validation: %s",
                key_id[:8],
                user_id[:8],
                doc["provider"],
                validation.get("error", "unknown"),
            )

        return {
            "valid": is_valid,
            "last_validated_at": now.isoformat(),
            "error": validation.get("error"),
            "available_models": validation.get("models", []),
        }

    # ── Internal: Key validation against provider API ────────────────────

    async def _test_key_against_provider(
        self,
        provider: str,
        api_key: str,
    ) -> dict:
        """
        Test an API key by calling the provider's list models endpoint.

        Returns:
            Dict with:
              - ``valid``: bool
              - ``models``: list[str] (available model IDs, empty on failure)
              - ``error``: str | None (human-readable error on failure)
        """
        client = _get_http()

        try:
            if provider == "openai":
                return await self._test_openai(client, api_key)
            elif provider == "anthropic":
                return await self._test_anthropic(client, api_key)
            elif provider == "deepseek":
                return await self._test_deepseek(client, api_key)
            elif provider == "google":
                return await self._test_google(client, api_key)
            else:
                return {"valid": False, "models": [], "error": "Unsupported provider"}
        except httpx.TimeoutException:
            return {
                "valid": False,
                "models": [],
                "error": f"{provider} API timed out. Check your network or try again.",
            }
        except Exception as exc:
            logger.warning("Key validation failed for %s: %s", provider, exc)
            return {"valid": False, "models": [], "error": str(exc)}

    async def _test_openai(self, client: httpx.AsyncClient, api_key: str) -> dict:
        """Validate an OpenAI API key by listing models."""
        resp = await client.get(
            PROVIDER_MODEL_LIST_ENDPOINTS["openai"],
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            all_models = [m["id"] for m in data.get("data", [])]
            # Filter to chat models relevant to our platform
            relevant = [
                m for m in all_models
                if any(kw in m for kw in ("gpt", "o1", "o3", "o4"))
            ]
            return {"valid": True, "models": relevant or all_models, "error": None}
        elif resp.status_code in (401, 403):
            return {"valid": False, "models": [], "error": "Invalid or unauthorized API key"}
        else:
            return {
                "valid": False,
                "models": [],
                "error": f"OpenAI returned HTTP {resp.status_code}: {resp.text[:200]}",
            }

    async def _test_anthropic(self, client: httpx.AsyncClient, api_key: str) -> dict:
        """Validate an Anthropic API key by listing models."""
        resp = await client.get(
            PROVIDER_MODEL_LIST_ENDPOINTS["anthropic"],
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            all_models = [m["id"] for m in data.get("data", [])] if isinstance(data.get("data"), list) else []
            if not all_models and isinstance(data, dict):
                # Some Anthropic versions return model IDs differently
                all_models = [data.get("id")] if data.get("id") else []
            relevant = [m for m in all_models if "claude" in m.lower()]
            return {"valid": True, "models": relevant or all_models, "error": None}
        elif resp.status_code in (401, 403):
            return {"valid": False, "models": [], "error": "Invalid or unauthorized API key"}
        else:
            return {
                "valid": False,
                "models": [],
                "error": f"Anthropic returned HTTP {resp.status_code}: {resp.text[:200]}",
            }

    async def _test_deepseek(self, client: httpx.AsyncClient, api_key: str) -> dict:
        """Validate a DeepSeek API key by listing models (OpenAI-compatible)."""
        resp = await client.get(
            PROVIDER_MODEL_LIST_ENDPOINTS["deepseek"],
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            all_models = [m["id"] for m in data.get("data", [])]
            return {"valid": True, "models": all_models, "error": None}
        elif resp.status_code in (401, 403):
            return {"valid": False, "models": [], "error": "Invalid or unauthorized API key"}
        else:
            return {
                "valid": False,
                "models": [],
                "error": f"DeepSeek returned HTTP {resp.status_code}: {resp.text[:200]}",
            }

    async def _test_google(self, client: httpx.AsyncClient, api_key: str) -> dict:
        """Validate a Google Gemini API key by listing models."""
        resp = await client.get(
            f"{PROVIDER_MODEL_LIST_ENDPOINTS['google']}?key={api_key}",
        )
        if resp.status_code == 200:
            data = resp.json()
            all_models = [m["name"] for m in data.get("models", [])]
            # Strip "models/" prefix from model names (e.g., "models/gemini-2.5-flash" → "gemini-2.5-flash")
            all_models = [m.replace("models/", "", 1) for m in all_models]
            # Filter to Gemini chat models
            relevant = [m for m in all_models if "gemini" in m.lower()]
            return {"valid": True, "models": relevant or all_models, "error": None}
        elif resp.status_code in (401, 403):
            return {"valid": False, "models": [], "error": "Invalid or unauthorized API key"}
        else:
            return {
                "valid": False,
                "models": [],
                "error": f"Google returned HTTP {resp.status_code}: {resp.text[:200]}",
            }

    # ── Internal: Response builder ───────────────────────────────────────

    @staticmethod
    def _safe_response(doc: dict, key_id: str) -> UserApiKeyResponse:
        """Build a safe response (no decrypted key, no encrypted blob)."""
        return UserApiKeyResponse(
            id=key_id,
            provider=doc.get("provider", ""),
            label=doc.get("label", ""),
            selected_models=doc.get("selected_models", []),
            base_url=doc.get("base_url"),
            is_active=doc.get("is_active", True),
            validated=doc.get("validated", False),
            last_validated_at=doc.get("last_validated_at"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    # ── Cleanup ─────────────────────────────────────────────────────────

    async def close(self):
        """Close the shared HTTP client."""
        global _provider_http
        if _provider_http and not _provider_http.is_closed:
            await _provider_http.aclose()
            _provider_http = None


# Singleton
api_key_service = APIKeyService()
