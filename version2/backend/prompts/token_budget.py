"""
Token budget and context window management for LLM prompts.

This service ensures that prompts never exceed model context windows,
preventing silent truncation and malformed completions from undersized fallbacks.

Strategy: measure → guard → route
- Measure: Know template sizes and model windows at startup
- Guard: Trim context before selection
- Route: Select models that can safely fit the prompt
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional

import tiktoken

logger = logging.getLogger(__name__)

try:
    enc = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    logger.error(f"Failed to initialize tiktoken encoder: {e}")
    enc = None


# ── Model context windows ──────────────────────────────────────────────────────
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # Primary models
    "deepseek_v3": 128_000,
    "gemini_flash_intent": 32_000,
    "gemini_25_flash_lite": 32_000,
    "mistral_small_32_24b": 32_000,
    # Fallbacks
    "stepfun_flash": 8_192,  # small — needs guarding
    "gpt4o_mini": 128_000,
    "claude_3_5_sonnet": 200_000,
    # Add yours here
}

# ── Completion reserves per role ───────────────────────────────────────────────
COMPLETION_RESERVES: dict[str, int] = {
    "sql_generator": 1_500,  # full SQL query + CTE
    "chart_engine": 1_200,  # 7-layer JSON array
    "intent_engine": 600,
    "chat_streaming": 2_000,
    "memory_extraction": 400,
    "chart_explanation": 600,
    "insight_generator": 1_500,
    "narrative_engine": 1_000,
    "belief_update": 300,
}

# ── Context injection limits per role ─────────────────────────────────────────
CONTEXT_MAX_TOKENS: dict[str, int] = {
    "sql_generator": 2_000,
    "chart_engine": 3_000,
    "intent_engine": 1_000,
    "chat_streaming": 2_500,
    "memory_extraction": 800,
    "chart_explanation": 800,
    "insight_generator": 2_000,
    "narrative_engine": 1_500,
    "belief_update": 500,
}


@dataclass
class PromptBudget:
    """Tracks token usage across a prompt."""

    role: str
    template_tokens: int = 0
    context_tokens: int = 0
    completion_reserve: int = 0
    model_limit: int = 32_000

    @property
    def total_input_tokens(self) -> int:
        return self.template_tokens + self.context_tokens

    @property
    def remaining_for_completion(self) -> int:
        return self.model_limit - self.total_input_tokens

    @property
    def is_safe(self) -> bool:
        return self.remaining_for_completion >= self.completion_reserve

    @property
    def overage(self) -> int:
        return max(0, self.completion_reserve - self.remaining_for_completion)

    @property
    def utilization_pct(self) -> float:
        """What % of the context window are we using?"""
        if self.model_limit == 0:
            return 0.0
        return (self.total_input_tokens / self.model_limit) * 100


def count_tokens(text: str) -> int:
    """Count tokens in text using CL100K encoding."""
    if enc is None:
        # Fallback: rough estimate (~4 chars per token)
        return len(text) // 4
    try:
        return len(enc.encode(text))
    except Exception as e:
        logger.warning(f"Token count failed: {e}, using rough estimate")
        return len(text) // 4


def trim_to_token_limit(text: str, max_tokens: int, label: str = "context") -> str:
    """
    Trim text to fit within max_tokens.
    Trims from the END to preserve schema headers and column names at the top.
    """
    if enc is None:
        # Fallback: rough trim
        return text[: max_tokens * 4]

    try:
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text

        trimmed = enc.decode(tokens[:max_tokens])
        dropped = len(tokens) - max_tokens
        logger.warning(
            f"[token_budget] '{label}' trimmed: {len(tokens)} → {max_tokens} tokens "
            f"({dropped} tokens dropped)"
        )
        return trimmed
    except Exception as e:
        logger.error(f"[token_budget] Trim failed for '{label}': {e}")
        return text


def safe_inject_context(
    template: str,
    context: str,
    role: str,
    model: str,
) -> tuple[str, PromptBudget]:
    """
    Trims context to fit within the model's window.
    Returns the (possibly trimmed) context + a PromptBudget for logging.

    Args:
        template: The base prompt without injected context
        context: The context to inject (schema, data, history, etc.)
        role: The role (sql_generator, chart_engine, etc.)
        model: The target model name

    Returns:
        (trimmed_context, budget)
    """
    model_limit = MODEL_CONTEXT_WINDOWS.get(model, 8_192)
    completion_res = COMPLETION_RESERVES.get(role, 1_000)
    context_max = CONTEXT_MAX_TOKENS.get(role, 2_000)

    template_tokens = count_tokens(template)
    available = model_limit - template_tokens - completion_res
    effective_max = min(available, context_max)

    if effective_max <= 0:
        logger.error(
            f"[token_budget] Template alone ({template_tokens} tokens) leaves no room "
            f"for context on model '{model}' (limit={model_limit}). "
            f"Consider switching to a larger model for role '{role}'."
        )
        effective_max = 100  # send minimal context rather than crashing

    trimmed_context = trim_to_token_limit(
        context, effective_max, label=f"{role}/context"
    )

    budget = PromptBudget(
        role=role,
        template_tokens=template_tokens,
        context_tokens=count_tokens(trimmed_context),
        completion_reserve=completion_res,
        model_limit=model_limit,
    )

    if not budget.is_safe:
        logger.warning(
            f"[token_budget] Role '{role}' on model '{model}' is UNSAFE: "
            f"{budget.total_input_tokens} input tokens, only {budget.remaining_for_completion} "
            f"left for completion (need {completion_res}). Overage: {budget.overage} tokens."
        )

    return trimmed_context, budget


def check_prompt_fits_model(
    prompt: str, role: str, model: str, require_safe: bool = True
) -> tuple[bool, str]:
    """
    Check if a prompt fits within a model's context window.

    Args:
        prompt: The full prompt to check
        role: The role (for completion reserves)
        model: The target model
        require_safe: If True, checks against safe threshold; if False, just context window

    Returns:
        (fits, message)
    """
    token_count = count_tokens(prompt)
    model_limit = MODEL_CONTEXT_WINDOWS.get(model, 8_192)
    reserve = COMPLETION_RESERVES.get(role, 1_000) if require_safe else 0

    fits = token_count + reserve <= model_limit
    message = (
        f"{model}: {token_count} tokens"
        f" + {reserve} reserve = {token_count + reserve} / {model_limit}"
    )

    return fits, message
