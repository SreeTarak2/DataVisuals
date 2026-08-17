# BYOK (Bring Your Own Key) Implementation Plan

Status: **Planned** — not started

## Goal

Enterprise users bring their own API keys (OpenAI, DeepSeek, Anthropic, Google) instead of routing all traffic through the platform's OpenRouter proxy. Keys encrypted at rest with Fernet. Cost tracked for analytics only — no platform billing for BYOK calls.

---

## Architecture

```
Agent._llm_call(user_id=...)
  → llm_router.call(user_id=...)
      → BYOKLookup(user_id, model_key)
          → if active key exists → ProviderRouter.direct(provider, key, model, prompt)
          → if no key → _call_openrouter(...)  [unchanged]
      → cost_tracker.record_usage(source="byok"|"platform")
```

Three layers added:
1. **Encryption** — Fernet-based key encryption/decryption
2. **Storage** — MongoDB collection `user_api_keys` + CRUD API
3. **Routing** — Provider adapters + LLMRouter integration

---

## Phase 1 — Encryption Service

**File:** `services/encryption.py`

- `encrypt_api_key(plaintext: str) -> str`
- `decrypt_api_key(ciphertext: str) -> str`
- Uses `cryptography.fernet.Fernet` with `DB_ENCRYPTION_KEY`
- Raises error if encryption key is default placeholder in production

**Dependency:** Add `cryptography` to `pyproject.toml`

---

## Phase 2 — BYOK Data Model + API

**Files:**

| File | Purpose |
|------|---------|
| `db/models/user_api_key.py` | Pydantic/Motor document model |
| `services/api_keys/service.py` | Create, read, delete, validate |
| `api/api_keys/routes.py` | REST endpoints |

**Schema** (MongoDB collection: `user_api_keys`):

```json
{
  "user_id": "abc123",
  "provider": "openai",
  "encrypted_key": "<Fernet ciphertext>",
  "label": "My OpenAI key",
  "base_url": null,
  "is_active": true,
  "last_validated_at": null,
  "validated": false,
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/keys` | Add key (validates before storing) |
| GET | `/api/v1/keys` | List user's keys (never return decrypted) |
| DELETE | `/api/v1/keys/{id}` | Remove key |
| POST | `/api/v1/keys/{id}/validate` | Test connectivity |

---

## Phase 3 — Provider Routing Layer

**Files:**

| File | Purpose |
|------|---------|
| `llm/providers/__init__.py` | `ProviderRouter` class with `call()` and `call_streaming()` |
| `llm/providers/openai_compat.py` | OpenAI + DeepSeek (same chat completions format) |
| `llm/providers/anthropic.py` | Anthropic Messages API |
| `llm/providers/google.py` | Google Gemini SDK |

Each adapter handles:
- Different API endpoint URLs
- Different auth header patterns
- Different streaming chunk formats
- Different error response structures

---

## Phase 4 — Router Integration

**File modified:** `llm/router.py`

In `LLMRouter.call()`:

```python
async def call(self, ..., user_id=None, ...):
    byok_key = await self._get_byok_key(user_id, model_key)
    if byok_key:
        return await provider_router.call(
            provider=byok_key["provider"],
            api_key=decrypt(byok_key["encrypted_key"]),
            model=byok_key["model"],
            prompt=prompt,
            ...
        )
    # fall through to OpenRouter path (unchanged)
```

**File modified:** `agents/base_agent.py`

- `_llm_call()` currently lacks `user_id` parameter
- Add `user_id` param and pass it to `llm_router.call()`
- `_reason()` callers already have access to `self.context.user_id`

---

## Phase 5 — Cost Tracking for BYOK

**File modified:** `llm/cost_tracker.py`

- Add `source: str = "platform"` parameter to `record_usage()`
- `source="byok"`: track tokens + call count for analytics only. Skip budget deduction.
- `source="platform"`: existing behavior (deduct from daily budget)

**File modified:** `llm/router.py`

- Pass `source="byok"` to `cost_tracker.record_usage()` when using BYOK key

---

## Phase 6 — Config + Wiring

| File | Change |
|------|--------|
| `core/config.py` | Add `BYOK_ENABLED: bool` env var |
| `main.py` | Register `api/api_keys/routes.py` router |
| `pyproject.toml` | Add `cryptography` dependency |
| `.env.example` | Document `BYOK_ENABLED` and `DB_ENCRYPTION_KEY` |

---

## Pre-deployment Checklist

- [ ] `DB_ENCRYPTION_KEY` set to a real Fernet key in production (not the placeholder)
- [ ] `.env` never committed to git (confirmed already gitignored)
- [ ] Existing OpenRouter path remains functional when BYOK is disabled
- [ ] BYOK keys validated on create (test call to provider)
- [ ] Decrypted keys never appear in logs, error messages, or API responses

---

## Risk: DB_ENCRYPTION_KEY placeholder

Current `.env` has `your-db-encryption-key-change-in-production`. Without a real key, encrypting API keys provides no security.

Generate a real key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set in production `.env`:
```
DB_ENCRYPTION_KEY=<generated key>
```
