from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tiktoken
except Exception:  # pragma: no cover - optional dependency fallback
    tiktoken = None


MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gemini_flash_lite": 1_048_576,
    "mistral_small_32": 131_000,
    "deepseek_v32": 164_000,
    "tngtech_deepseek_r1t2_chimera": 163_840,
    "minimax_m25": 196_000,
    "qwen_2.5_72b": 131_000,
    "gemini_flash_lite_intent": 1_000_000,
    "openrouter_free": 32_000,
    "stepfun_flash": 8_192,
}


COMPLETION_RESERVES: dict[str, int] = {
    "sql_generator": 1_500,
    "chart_recommendation": 1_200,
    "chart_engine": 1_200,
    "intent_engine": 600,
    "chat_streaming": 2_000,
    "memory_extraction": 400,
    "insight_generation": 1_500,
    "narrative_insights": 1_500,
    "narrative_story": 1_500,
}


CONTEXT_MAX_TOKENS: dict[str, int] = {
    "sql_generator": 2_000,
    "chart_recommendation": 2_500,
    "chart_engine": 2_500,
    "intent_engine": 1_000,
    "chat_streaming": 2_500,
    "memory_extraction": 800,
    "insight_generation": 3_000,
}


def _get_encoding():
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


_ENCODING = _get_encoding()


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4)


def trim_to_token_limit(text: str, max_tokens: int, label: str = "context") -> str:
    if not text or max_tokens <= 0:
        return ""

    if _ENCODING is not None:
        tokens = _ENCODING.encode(text)
        if len(tokens) <= max_tokens:
            return text
        trimmed = _ENCODING.decode(tokens[:max_tokens])
    else:
        approx_chars = max_tokens * 4
        if len(text) <= approx_chars:
            return text
        trimmed = text[:approx_chars]

    logger.warning(
        f"[token_budget] trimmed {label}: {count_tokens(text)} → {count_tokens(trimmed)} tokens"
    )
    return trimmed


def safe_context_budget(
    role: str,
    model_key: str,
    prompt: str,
    context: Optional[str] = None,
) -> tuple[str, int, int]:
    """
    Trim context to fit inside the chosen model's context window.

    Returns:
        (trimmed_context, prompt_tokens, safe_context_tokens)
    """
    model_limit = MODEL_CONTEXT_WINDOWS.get(model_key, 32_000)
    reserve = COMPLETION_RESERVES.get(role, 1_000)
    prompt_tokens = count_tokens(prompt)
    available_for_context = max(0, model_limit - prompt_tokens - reserve)
    context_budget = min(
        available_for_context,
        CONTEXT_MAX_TOKENS.get(role, available_for_context),
    )
    trimmed_context = trim_to_token_limit(
        context or "", context_budget, f"{role}/context"
    )
    return trimmed_context, prompt_tokens, count_tokens(trimmed_context)