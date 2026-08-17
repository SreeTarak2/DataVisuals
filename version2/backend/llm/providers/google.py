"""
Google Gemini Provider Adapter
==============================

Handles direct API calls to the Google Gemini API.

Key differences from OpenAI:
  - API key passed as query parameter (``?key=...``)
  - Different message format (``contents`` array with ``parts``)
  - Different response format (``candidates[].content.parts[].text``)
  - Different streaming format (SSE with ``text`` field in each chunk)
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


DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _convert_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Convert OpenAI-format messages to Gemini format.

    OpenAI: ``[{"role": "user", "content": "Hello"}]``
    Gemini: ``[{"role": "user", "parts": [{"text": "Hello"}]}]``

    Note: Gemini uses "model" for system role and "user"/"model" for
    conversation turns. We skip system messages here — they're handled
    separately via the ``system_instruction`` field.
    """
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content_text = msg.get("content", "")

        # Map roles: OpenAI "assistant" → Gemini "model"
        gemini_role = "model" if role == "assistant" else "user"

        # Skip system messages — handled separately
        if role == "system":
            continue

        contents.append({
            "role": gemini_role,
            "parts": [{"text": content_text}],
        })

    return contents


def _extract_system_message(messages: list[dict[str, str]]) -> Optional[str]:
    """Extract the system message from the message list, if any."""
    for msg in messages:
        if msg.get("role") == "system":
            return msg.get("content", "")
    return None


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
    Make a non-streaming call to the Google Gemini API.

    Args:
        api_key: Gemini API key.
        model: Model ID (e.g., ``gemini-2.5-flash``, ``gemini-2.5-pro``).
        messages: OpenAI-format message list.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.
        expect_json: If True, adds response_mime_type for JSON.
        base_url: Optional base URL override.

    Returns:
        String content or parsed JSON if expect_json.
    """
    client = _get_client()

    # Gemini doesn't use /v1beta/models for chat — it uses /v1beta/models/{model}:generateContent
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base}/models/{model}:generateContent?key={api_key}"

    system_instruction = _extract_system_message(messages)
    contents = _convert_messages(messages)

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    if expect_json:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Extract text from candidates[].content.parts[].text
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(part.get("text", "") for part in parts)

        if expect_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"error": "json_parse_failed", "raw": content[:500]}
        return (content or "").strip()

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        logger.error("Gemini API error %d: %s", status, detail)
        if status in (400, 401, 403):
            raise ValueError(f"Invalid API key or unauthorized (HTTP {status})")
        elif status == 429:
            raise ValueError(f"Rate limited by Gemini (HTTP {status})")
        raise ValueError(f"Gemini API error {status}: {detail}")


async def call_streaming(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    base_url: Optional[str] = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Make a streaming call to the Google Gemini API.

    Gemini uses SSE: each chunk is a JSON object with ``candidates[].content.parts[].text``.
    The stream ends with a chunk containing ``candidates[].finishReason``.
    """
    client = _get_client()

    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base}/models/{model}:streamGenerateContent?key={api_key}&alt=sse"

    system_instruction = _extract_system_message(messages)
    contents = _convert_messages(messages)

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    full_response = ""

    try:
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code != 200:
                error_text = await resp.aread()
                yield {"type": "error", "content": f"API error {resp.status_code}: {error_text[:200]}"}
                return

            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)

                        # Check for finish reason (stream complete)
                        candidates = data.get("candidates", [])
                        if candidates:
                            finish = candidates[0].get("finishReason")
                            if finish:
                                yield {"type": "done", "full_response": full_response}
                                return

                            # Extract text from parts
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    full_response += text
                                    yield {"type": "token", "content": text}

                    except json.JSONDecodeError:
                        continue

            # Stream ended without finishReason
            if full_response:
                yield {"type": "done", "full_response": full_response}

    except httpx.TimeoutException:
        yield {"type": "error", "content": "Gemini request timed out"}
    except Exception as exc:
        logger.error("Streaming error for Gemini: %s", exc)
        yield {"type": "error", "content": str(exc)}
