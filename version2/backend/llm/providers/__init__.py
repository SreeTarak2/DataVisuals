"""
Provider Router — BYOK Direct Provider Routing
===============================================

Routes LLM calls directly to a user's chosen provider when they have
brought their own API key (BYOK).

Each provider adapter handles the specific API format, auth headers, and
streaming chunk parsing for that provider. The ProviderRouter is the
entry point that dispatches to the correct adapter.

Usage (from LLMRouter):

    from llm.providers import provider_router

    result = await provider_router.call(
        provider="openai",
        api_key="sk-...",
        model="gpt-4o",
        messages=[...],
        temperature=0.7,
        max_tokens=4096,
    )

    # Streaming
    async for chunk in provider_router.call_streaming(
        provider="openai",
        api_key="sk-...",
        model="gpt-4o",
        messages=[...],
    ):
        yield chunk
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

from core.config import settings

logger = logging.getLogger(__name__)


class ProviderRouter:
    """
    Dispatches LLM calls to the correct provider adapter.

    Acts as a simple registry: provider slug → adapter module.
    """

    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def register(self, provider: str, adapter: Any) -> None:
        """Register a provider adapter."""
        self._adapters[provider.lower()] = adapter
        logger.debug("Registered provider adapter: %s", provider)

    def _get_adapter(self, provider: str) -> Any:
        """Get the adapter for a provider, raising if not found."""
        adapter = self._adapters.get(provider.lower())
        if not adapter:
            raise ValueError(
                f"Unsupported provider '{provider}'. "
                f"Registered: {', '.join(sorted(self._adapters.keys()))}"
            )
        return adapter

    # ── Non-streaming call ───────────────────────────────────────────────

    async def call(
        self,
        provider: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        expect_json: bool = False,
        base_url: Optional[str] = None,
    ) -> Any:
        """
        Make a non-streaming LLM call via the specified provider.

        Args:
            provider: Provider slug (``openai``, ``anthropic``, etc.).
            api_key: The user's decrypted API key.
            model: Model ID to use (e.g., ``gpt-4o``, ``claude-sonnet-4``).
            messages: OpenAI-style message list ``[{"role": "user", "content": "..."}]``.
            temperature: Sampling temperature.
            max_tokens: Max tokens to generate.
            expect_json: If True, request JSON response format (where supported).
            base_url: Optional override for the provider's base URL.

        Returns:
            Parsed response (string or dict if expect_json).
        """
        adapter = self._get_adapter(provider)
        return await adapter.call(
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            expect_json=expect_json,
            base_url=base_url,
        )

    # ── Streaming call ───────────────────────────────────────────────────

    async def call_streaming(
        self,
        provider: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: Optional[str] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Make a streaming LLM call via the specified provider.

        Yields dicts with ``type: "token"``, ``type: "done"``, or ``type: "error"``.

        Args:
            provider: Provider slug.
            api_key: The user's decrypted API key.
            model: Model ID.
            messages: OpenAI-style message list.
            temperature: Sampling temperature.
            max_tokens: Max tokens.
            base_url: Optional base URL override.

        Yields:
            Dicts with token/done/error events.
        """
        adapter = self._get_adapter(provider)
        async for chunk in adapter.call_streaming(
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
        ):
            yield chunk

    # ── Health / model test ──────────────────────────────────────────────

    async def test_model(
        self,
        provider: str,
        api_key: str,
        model: str,
    ) -> dict:
        """
        Test a specific model by making a tiny chat completion.

        Used for key validation during setup.

        Returns:
            Dict with ``success``, ``error`` (optional), and ``duration_ms``.
        """
        import time as _time

        adapter = self._get_adapter(provider)
        start = _time.monotonic()
        try:
            await adapter.call(
                api_key=api_key,
                model=model,
                messages=[{"role": "user", "content": "Reply with the word OK."}],
                temperature=0.0,
                max_tokens=10,
            )
            duration_ms = int((_time.monotonic() - start) * 1000)
            return {"success": True, "duration_ms": duration_ms}
        except Exception as exc:
            duration_ms = int((_time.monotonic() - start) * 1000)
            return {"success": False, "error": str(exc), "duration_ms": duration_ms}


# ── Register built-in adapters ───────────────────────────────────────────

from llm.providers import openai_compat, anthropic, google

provider_router = ProviderRouter()
provider_router.register("openai", openai_compat)
provider_router.register("deepseek", openai_compat)
provider_router.register("anthropic", anthropic)
provider_router.register("google", google)
