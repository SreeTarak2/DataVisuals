"""
BYOK API Key Management Service
================================

Provides CRUD operations, key validation, and model discovery for
user-provided API keys (Bring Your Own Key).

Key flows:
  - ``register_key``  → validates key against provider → stores encrypted
  - ``list_keys``     → returns safe metadata (never the decrypted key)
  - ``get_key``       → retrieves + decrypts for use at runtime
  - ``delete_key``    → removes stored key
  - ``validate_key``  → tests a key without persisting it
  - ``fetch_models``  → discovers available models from provider's API
"""

from services.api_keys.service import api_key_service

__all__ = [
    "api_key_service",
]
