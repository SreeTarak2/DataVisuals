"""
Anthropic Claude Provider Adapter
==================================

Handles direct API calls to the Anthropic Messages API.

Different from OpenAI:
  - Auth via ``x-api-key`` header (not Bearer token)
  - Requires ``anthropic-version`` header
  - Different message format (``content`` is a list of blocks)
  - Different streaming format (SSE with ``event: content_block_delta``)
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    return _client


DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


def _convert_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Convert OpenAI-format messages to Anthropic format.

    Anthropic expects:
      ``{"role": "user", "content": [{"type": "text", "text": "..."}]}``
    """
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        content_text = msg.get("content", "")
        converted.append({
            "role": role,
            "content": [{"type": "text", "text": content_text}],
        })
    return converted


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
    Make a non-streaming call to the Anthropic Messages API.

    Note: Anthropic does not support native JSON mode like OpenAI, so
    ``expect_json`` is handled via system prompt instruction.
    """
    client = _get_client()
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": _convert_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if expect_json:
        payload["system"] = "You must respond with valid JSON only. No markdown, no explanation."

    try:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Anthropic response: content is a list of blocks
        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        if expect_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "json_parse_failed", "raw": content[:500]}
        return (content or "").strip()

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        logger.error("Anthropic API error %d: %s", status, detail)
        if status in (401, 403):
            raise ValueError(f"Invalid API key or unauthorized access (HTTP {status})")
        elif status == 429:
            raise ValueError(f"Rate limited by Anthropic (HTTP {status})")
        raise ValueError(f"Anthropic API error {status}: {detail}")


async def call_streaming(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    base_url: Optional[str] = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Make a streaming call to the Anthropic Messages API.

    Anthropic uses SSE events:
      - ``event: content_block_delta`` → delta.text
      - ``event: message_delta`` → stop_reason
      - ``event: message_stop`` → complete
    """
    client = _get_client()
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": _convert_messages(messages),
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

            current_event = ""

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue

                if line.startswith("event: "):
                    current_event = line[7:]
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)

                        if current_event == "content_block_delta":
                            delta = data.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                full_response += text
                                yield {"type": "token", "content": text}

                        elif current_event == "message_stop":
                            yield {"type": "done", "full_response": full_response}
                            return

                        elif current_event == "error":
                            error_msg = data.get("error", {}).get("message", "Unknown error")
                            yield {"type": "error", "content": error_msg}
                            return

                    except json.JSONDecodeError:
                        continue

            # Stream ended without message_stop
            if full_response:
                yield {"type": "done", "full_response": full_response}

    except httpx.TimeoutException:
        yield {"type": "error", "content": "Anthropic request timed out"}
    except Exception as exc:
        logger.error("Streaming error for Anthropic: %s", exc)
        yield {"type": "error", "content": str(exc)}
