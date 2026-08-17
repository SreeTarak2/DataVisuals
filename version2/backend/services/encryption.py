"""
Encryption Service for BYOK API Keys
=====================================

Provides Fernet-based symmetric encryption/decryption for user-provided API
keys. Uses a dedicated DB_ENCRYPTION_KEY (configured in .env) that MUST be
separate from the JWT SECRET_KEY.

Key derivation:
  1. Read DB_ENCRYPTION_KEY from settings (32-byte URL-safe base64 key)
  2. Hash with SHA-256 to get a 32-byte Fernet-compatible key
  3. Encode as URL-safe base64 for Fernet

Security notes:
  - Unlike the legacy db_connection_service, this module does NOT fall back
    to SECRET_KEY. If DB_ENCRYPTION_KEY is missing or is the default
    placeholder, encrypt/decrypt operations raise a clear error.
  - The encryption key should be generated once and kept stable. Rotating it
    requires re-encrypting all stored API keys.
  - API keys in transit (request/response) are handled by the caller — this
    service only handles encryption at rest.

Usage:
    from services.encryption import encrypt_api_key, decrypt_api_key

    ciphertext = encrypt_api_key("sk-proj-xxxxx")
    plaintext  = decrypt_api_key(ciphertext)
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings

logger = logging.getLogger(__name__)

# ── Sentinel value check ──────────────────────────────────────────────────
# We refuse to encrypt with the default placeholder. Production deployments
# MUST generate a real key.
_DEFAULT_KEY_PLACEHOLDERS = frozenset({
    "your-db-encryption-key-change-in-production",
    "",
})

# Cache the derived Fernet instance after first successful creation.
_fernet_cache: Fernet | None = None


def _derive_fernet_key(raw_key_str: str) -> bytes:
    """
    Derive a 32-byte Fernet-compatible key from a raw key string.

    Uses SHA-256 to produce a uniformly-distributed 32-byte digest, then
    URL-safe base64 encodes it for Fernet. This allows users to provide a
    key in any format (hex, base64, plain text) while ensuring Fernet's
    strict 32-byte URL-safe base64 requirement is always met.

    Args:
        raw_key_str: The raw encryption key string from settings.

    Returns:
        bytes: A 44-character URL-safe base64-encoded Fernet key.

    Raises:
        ValueError: If the derived key is unsuitable (should never happen
                    with SHA-256, but guards against future changes).
    """
    digest = hashlib.sha256(raw_key_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    """
    Create (or return cached) Fernet cipher from the configured DB_ENCRYPTION_KEY.

    The Fernet instance is cached after first successful creation because the
    encryption key doesn't change during a process lifetime. This avoids
    recomputing the SHA-256 key derivation on every encrypt/decrypt call.

    Returns:
        Fernet: Initialised Fernet cipher instance.

    Raises:
        ValueError: If DB_ENCRYPTION_KEY is missing, empty, or set to the
                    default placeholder value.
    """
    global _fernet_cache

    if _fernet_cache is not None:
        return _fernet_cache

    raw_key = settings.DB_ENCRYPTION_KEY

    if raw_key in _DEFAULT_KEY_PLACEHOLDERS:
        raise ValueError(
            "DB_ENCRYPTION_KEY is not set or is still the default placeholder. "
            "This key is required for BYOK API key encryption. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    if not raw_key or len(raw_key) < 16:
        raise ValueError(
            f"DB_ENCRYPTION_KEY must be at least 16 characters (got {len(raw_key) if raw_key else 0}). "
            "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    fernet_key = _derive_fernet_key(raw_key)
    _fernet_cache = Fernet(fernet_key)
    return _fernet_cache


# ── Public API ────────────────────────────────────────────────────────────


def encrypt_api_key(plaintext: str) -> str:
    """
    Encrypt an API key string for storage.

    Args:
        plaintext: The raw API key to encrypt (e.g., ``"sk-proj-xxxxx"``).

    Returns:
        str: Fernet-encrypted ciphertext token (URL-safe base64).

    Raises:
        ValueError: If ``plaintext`` is empty or DB_ENCRYPTION_KEY is invalid.
        RuntimeError: If encryption fails unexpectedly.
    """
    if not plaintext:
        raise ValueError("Cannot encrypt an empty API key.")

    try:
        cipher = _get_fernet()
        encrypted: bytes = cipher.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")
    except ValueError:
        raise  # Re-raise configuration errors as-is
    except Exception as exc:
        logger.error("API key encryption failed: %s", exc)
        raise RuntimeError("Failed to encrypt API key. Check DB_ENCRYPTION_KEY configuration.") from exc


def decrypt_api_key(ciphertext: str) -> str:
    """
    Decrypt a previously encrypted API key.

    Args:
        ciphertext: The encrypted token (URL-safe base64 string) as returned
                    by :func:`encrypt_api_key`.

    Returns:
        str: The original plaintext API key.

    Raises:
        ValueError: If ``ciphertext`` is empty, malformed, or the encryption
                    key has changed since encryption.
        RuntimeError: If decryption fails unexpectedly.
    """
    if not ciphertext:
        raise ValueError("Cannot decrypt an empty ciphertext.")

    try:
        cipher = _get_fernet()
        decrypted: bytes = cipher.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt API key. The ciphertext may be corrupted or "
            "DB_ENCRYPTION_KEY may have changed since encryption."
        )
    except ValueError:
        raise  # Re-raise configuration errors as-is
    except Exception as exc:
        logger.error("API key decryption failed: %s", exc)
        raise RuntimeError("Failed to decrypt API key.") from exc


def test_encryption_key() -> dict:
    """
    Verify that the configured DB_ENCRYPTION_KEY works correctly.

    Encrypts and decrypts a test string, returning the result. Useful for
    startup health checks and diagnostics.

    Returns:
        dict: ``{"valid": True}`` on success, or ``{"valid": False, "error": <msg>}``.
    """
    try:
        test_value = "test-key-verification"
        encrypted = encrypt_api_key(test_value)
        decrypted = decrypt_api_key(encrypted)
        if decrypted != test_value:
            return {"valid": False, "error": "Encrypt/decrypt round-trip failed: output mismatch"}
        return {"valid": True}
    except (ValueError, RuntimeError) as exc:
        return {"valid": False, "error": str(exc)}
