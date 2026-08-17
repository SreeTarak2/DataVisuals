"""
OpenAI-Compatible Provider Adapter
===================================

Handles both OpenAI and DeepSeek API calls since they share the same
Chat Completions API format.

Supported providers:
  - openai (https://api.openai.com/v1)
  - deepseek (https://api.deepseek.com/v1)

Both streaming and non-streaming paths are supported.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Shared HTTP client (lazy)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    return _client


DEFAULT_BASE_URL = "https://api.openai.com/v1"


async def call(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    expect_json: bool = False,
    base_url: Optional[str] = None,
) -> Any:
    """
    Make a non-streaming chat completion call to an OpenAI-compatible API.
    """
    client = _get_client()
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if expect_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "json_parse_failed", "raw": content[:500]}
        return (content or "").strip()

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        logger.error("OpenAI-compat API error %d: %s", status, detail)
        if status in (401, 403):
            raise ValueError(f"Invalid API key or unauthorized access (HTTP {status})")
        elif status == 429:
            raise ValueError(f"Rate limited by provider (HTTP {status})")
        elif status >= 500:
            raise ValueError(f"Provider server error (HTTP {status})")
        raise ValueError(f"API error {status}: {detail}")


async def call_streaming(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    base_url: Optional[str] = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Make a streaming chat completion call to an OpenAI-compatible API.
    """
    client = _get_client()
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    full_response = ""

    try:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                error_text = await resp.aread()
                yield {"type": "error", "content": f"API error {resp.status_code}: {error_text[:200]}"}
                return

            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        yield {"type": "done", "full_response": full_response}
                        return
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_response += content
                                yield {"type": "token", "content": content}
                    except json.JSONDecodeError:
                        continue

            # Stream ended without [DONE] — still yield final response
            if full_response:
                yield {"type": "done", "full_response": full_response}

    except httpx.TimeoutException:
        yield {"type": "error", "content": "Provider request timed out"}
    except Exception as exc:
        logger.error("Streaming error for OpenAI-compat: %s", exc)
        yield {"type": "error", "content": str(exc)}
