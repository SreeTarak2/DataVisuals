import asyncio
import httpx
import json
import logging
import re
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException

from core.config import settings
from core.prompt_templates import CONVERSATIONAL_SYSTEM_PROMPT, COMPLEXITY_HINTS
from core.token_budget import count_tokens, MODEL_CONTEXT_WINDOWS, COMPLETION_RESERVES
from prompts.token_budget import (
    safe_inject_context,
    check_prompt_fits_model,
    PromptBudget,
)
from llm.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)


def _strip_json_wrapper(text: str) -> str:
    """
    Defense-in-depth: strip JSON wrappers from LLM responses during streaming.

    Some models ignore the plain-text instruction and wrap their response in
    JSON (e.g. {"response_text": "...", "chart_config": null}). This function
    strips the wrapper and returns just the text content.

    Handles:
    - Standard JSON wrapper from CONVERSATIONAL_SYSTEM_PROMPT format
    - Markdown code fences wrapping JSON
    - Partial/malformed JSON prefixes
    - Non-JSON text (returned as-is)

    Args:
        text: Raw LLM response text

    Returns:
        Clean text with JSON wrapper removed, or original text if no wrapper found
    """
    if not text or not text.strip():
        return text

    cleaned = text.strip()

    # Step 1: Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()

    # Step 2: Try to parse as JSON and extract known text fields
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                # Try fields in priority order (most common first)
                for key in ("response_text", "answer", "response", "text", "content", "message", "output"):
                    val = parsed.get(key)
                    if val and isinstance(val, str) and len(val.strip()) > 5:
                        return val.strip()
                # If only chart_config exists without text, provide fallback
                if parsed.get("chart_config") and not any(
                    isinstance(parsed.get(k), str) and len(parsed.get(k, "").strip()) > 5
                    for k in ("response_text", "answer", "response", "text", "content")
                ):
                    return ""  # Return empty — caller will use fallback text
            # If we get here, parsed as JSON but no text field found
            # Return the raw JSON as-is for frontend extraction
            return text
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON — continue to regex fallback
            pass

        # Step 3: Regex fallback for malformed JSON
        match = re.search(
            r'"(?:response_text|answer|response|text|content|message)"\s*:\s*"((?:[^"\\]|\\.)*)"',
            cleaned,
        )
        if match:
            extracted = match.group(1).replace("\\n", "\n").replace("\\\"", "\"")
            if len(extracted) > 5:
                return extracted.strip()

    # Step 4: Check for partial JSON fragment (e.g., starting mid-key)
    # Pattern: "response_text": "value" or similar
    partial_match = re.match(r'^[a-z_]*"?\s*:\s*"(.+)', cleaned)
    if partial_match:
        extracted = partial_match.group(1).rstrip('"').rstrip(",}")
        # Clean up escaped chars            extracted = extracted.replace("\\n", "\n").replace("\\\"", "\"")
        if len(extracted) > 10:
            return extracted.strip()

    # Not JSON — return as-is
    return text


# Roles that are always user-facing — must NEVER be queued behind background tasks
INTERACTIVE_ROLES = frozenset(
    {
        "conversational",
        "chat_engine",
        "chat_streaming",
        "simple_query",
        "complex_analysis",
        "kpi_suggestion",
        "insight_generation",
        "narrative_insights",
        "narrative_story",
        "sql_generator",
        "chart_recommendation",
        "dashboard_design",
    }
)


class PriorityLLMSemaphore:
    """
    Two-lane semaphore for LLM calls on resource-constrained machines.

    Interactive lane: full capacity for user-facing calls (chat, streaming).
    Background lane: limited slots for Celery workers — never starves interactive.

    On 2 slots (default):
      - Interactive: 2 slots  → user always gets through
      - Background:  1 slot   → Celery tasks share 1 slot
      - Combined:     2 total  → never exceed OpenRouter rate limits
    """

    def __init__(self, max_concurrent: int = 5):
        self._interactive_sem = asyncio.Semaphore(max_concurrent)
        self._background_sem = asyncio.Semaphore(max(1, max_concurrent - 1))
        self._total_sem = asyncio.Semaphore(max_concurrent)

    async def acquire(self, is_interactive: bool) -> None:
        if is_interactive:
            await self._total_sem.acquire()
        else:
            await self._background_sem.acquire()
            await self._total_sem.acquire()

    def release(self, is_interactive: bool) -> None:
        self._total_sem.release()
        if not is_interactive:
            self._background_sem.release()


class LLMRouter:
    def __init__(self):
        self.http = None  # Lazily initialized
        self._semaphore = None  # Lazily initialized
        self._stagger_lock = None  # Lazily initialized

        self.model_health_cache = {}
        self.use_openrouter = bool(settings.OPENROUTER_API_KEY)
        self._auth_error_cooldown_until: Optional[datetime] = None

        # Load OpenRouter model configurations
        self.openrouter_models = settings.OPENROUTER_MODELS
        self.role_mapping = settings.OPENROUTER_ROLE_MAPPING

        self._stagger_delay = settings.LLM_REQUEST_STAGGER_SECONDS  # default 1.0s
        self._last_request_time: float = 0.0  # monotonic timestamp

        logger.info(
            f"LLM Router model mapping loaded ({len(self.role_mapping)} roles). "
            f"OpenRouter enabled: {self.use_openrouter}"
        )

    def _ensure_initialized(self):
        """
        Lazy initialization of loop-bound objects.
        Ensures semaphores, locks, and HTTP clients are bound to the current
        running event loop (critical for Celery workers after fork).
        """
        if self.http is None:
            self.http = httpx.AsyncClient(timeout=180.0, follow_redirects=True)

        if self._semaphore is None:
            self._semaphore = PriorityLLMSemaphore(settings.LLM_MAX_CONCURRENT_CALLS)

        if self._stagger_lock is None:
            self._stagger_lock = asyncio.Lock()

    # -----------------------------------------------------------
    # PUBLIC ENTRY POINT
    # -----------------------------------------------------------
    async def call(
        self,
        prompt: str,
        model_role: str,
        expect_json: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
        specific_model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        is_conversational: bool = False,
        query_complexity: str = "moderate",
        context: Optional[str] = None,
        include_reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
        archetype: str = "analyst",
        is_interactive: Optional[bool] = None,
        user_id: Optional[str] = None,
        instructions_override: Optional[str] = None,
    ) -> Any:
        """
        Main entry point for LLM calls with intelligent model routing.

        Args:
            prompt: The user prompt/query
            model_role: Task role (e.g., 'chart_recommendation', 'kpi_suggestion')
            expect_json: Whether to expect JSON response
            specific_model: Override auto-selection with specific model key (e.g., 'hermes_405b')
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            is_conversational: If True, use structured formatting for responses
            query_complexity: 'simple' | 'moderate' | 'complex' - affects response format
            archetype: 'explorer' | 'analyst' | 'expert' - user sophistication level
            user_id: Optional user ID for cost tracking

        Returns:
            Parsed JSON dict if expect_json=True, otherwise string
        """

        self._ensure_initialized()

        # Use OpenRouter exclusively (Ollama fallback commented out per user request)
        if self.use_openrouter:
            # ── Cost budget check (before making the API call) ──
            if user_id and settings.LLM_COST_TRACKING_ENABLED:
                budget_check = await cost_tracker.check_budget(user_id)
                if not budget_check.get("allowed", True):
                    logger.warning(
                        f"Budget exceeded for user {user_id[:8]}... on role '{model_role}': "
                        f"{budget_check.get('reason', 'unknown')}"
                    )
                    raise HTTPException(
                        429,
                        f"LLM usage limit reached: {budget_check.get('reason', 'Budget exceeded')}. "
                        "Please try again tomorrow or contact support.",
                    )

            # Avoid repeated failing calls when OpenRouter auth is invalid.
            if (
                self._auth_error_cooldown_until
                and datetime.utcnow() < self._auth_error_cooldown_until
            ):
                raise HTTPException(
                    502,
                    "OpenRouter authentication is currently failing (401/403). "
                    "Update OPENROUTER_API_KEY in backend/.env and restart the backend.",
                )
            model_key = specific_model or self.role_mapping.get(model_role, "mistral_small_32")

            try:
                result = await self._call_openrouter(
                    prompt,
                    model_role,
                    expect_json,
                    json_schema=json_schema,
                    specific_model=specific_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    is_conversational=is_conversational,
                    query_complexity=query_complexity,
                    context=context,
                    include_reasoning=include_reasoning,
                    reasoning_effort=reasoning_effort,
                    archetype=archetype,
                    is_interactive=is_interactive,
                    instructions_override=instructions_override,
                )

                # ── Record usage after successful call ──
                await self._record_llm_usage(user_id, model_key, prompt, max_tokens, model_role)
                return result

            except HTTPException:
                raise
            except Exception as e:
                error_str = str(e)
                logger.error(f"OpenRouter call failed for role '{model_role}': {e}")

                status_code = None
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                elif isinstance(e, HTTPException):
                    status_code = e.status_code

                is_auth_error = (
                    status_code in (401, 403) or "401" in error_str or "403" in error_str
                )
                if is_auth_error:
                    self._auth_error_cooldown_until = datetime.utcnow() + timedelta(minutes=5)
                    raise HTTPException(
                        502,
                        "OpenRouter authentication failed (401/403). "
                        "Please verify OPENROUTER_API_KEY in backend/.env.",
                    )

                # Do not retry/fallback for non-rate-limit client errors.
                is_non_rate_client_error = (
                    status_code is not None and 400 <= status_code < 500 and status_code != 429
                )
                if is_non_rate_client_error:
                    raise HTTPException(502, f"AI provider unavailable: {str(e)}")

                # Try role-based fallback chain for transient errors.
                fallback_models = self._get_fallback_models(model_role, specific_model)
                for fallback_model_key in fallback_models:
                    if not self._prompt_fits_model(prompt, fallback_model_key, model_role):
                        continue
                    fallback_config = self.openrouter_models[fallback_model_key]
                    logger.warning(f"Trying fallback model: {fallback_config['name']}...")
                    try:
                        result = await self._call_openrouter(
                            prompt,
                            model_role,
                            expect_json,
                            json_schema=json_schema,
                            specific_model=fallback_model_key,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            is_conversational=is_conversational,
                            query_complexity=query_complexity,
                            context=context,
                            include_reasoning=include_reasoning,
                            reasoning_effort=reasoning_effort,
                            archetype=archetype,
                            is_interactive=is_interactive,
                            instructions_override=instructions_override,
                        )
                        # ── Record usage for the fallback model ──
                        await self._record_llm_usage(user_id, fallback_model_key, prompt, max_tokens, model_role)
                        return result
                    except Exception as fallback_error:
                        logger.error(
                            f"Fallback model {fallback_model_key} failed: {fallback_error}"
                        )

                raise HTTPException(502, f"AI provider unavailable: {str(e)}")

        # OpenRouter only mode
        raise HTTPException(
            500,
            "OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable.",
        )

    def get_model_for_role(self, model_role: str, specific_model: str = None) -> Dict[str, Any]:
        """
        Get the best model configuration for a given role.

        Args:
            model_role: Task role (e.g., 'chart_recommendation')
            specific_model: Optional override with specific model key

        Returns:
            Model configuration dict with 'model', 'name', 'strengths', etc.
        """
        # If specific model requested, use that
        if specific_model and specific_model in self.openrouter_models:
            model_config = self.openrouter_models[specific_model]
            logger.info(f"Using specific model: {model_config['name']} for role '{model_role}'")
            return model_config

        # Otherwise, use role mapping
        model_key = self.role_mapping.get(model_role)
        if not model_key or model_key not in self.openrouter_models:
            # Role not mapped or mapped model unavailable — resolve via "default" role
            model_key = self.role_mapping.get("default", "mistral_small_32")

        model_config = self.openrouter_models.get(
            model_key, self.openrouter_models["mistral_small_32"]
        )
        logger.info(f"Auto-selected model: {model_config['name']} for role '{model_role}'")

        return model_config

    def _get_fallback_models(
        self, model_role: str, specific_model: Optional[str] = None
    ) -> List[str]:
        """
        Resolve fallback candidates for a role in priority order.
        """
        current_model_key = specific_model or self.role_mapping.get(model_role, "mistral_small_32")
        role_fallbacks = settings.FALLBACKS.get(model_role, [])

        if isinstance(role_fallbacks, str):
            role_fallbacks = [role_fallbacks]

        return [
            model_key
            for model_key in role_fallbacks
            if model_key in self.openrouter_models and model_key != current_model_key
        ]

    async def _record_llm_usage(
        self,
        user_id: Optional[str],
        model_key: str,
        prompt: str,
        max_tokens: int,
        model_role: str,
    ) -> None:
        """
        Safely record LLM usage to the cost tracker.

        This is a fire-and-forget helper: it catches all exceptions internally
        so the caller is never disrupted by a cost tracking failure.
        """
        if not user_id or not settings.LLM_COST_TRACKING_ENABLED:
            return
        try:
            input_tokens = count_tokens(prompt)
            # Estimate output as half of max_tokens (conservative for budget)
            output_tokens = max(1, max_tokens // 2)
            await cost_tracker.record_usage(
                user_id=user_id,
                model_key=model_key,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                role=model_role,
            )
        except Exception as e:
            logger.warning(f"[CostTracker] Failed to record usage: {e}")

    def resolve_conversational_role(self, query_complexity: str) -> str:
        """Map query complexity to the conversational model role."""
        return {
            "simple": "simple_query",
            "moderate": "conversational",
            "complex": "complex_analysis",
        }.get(query_complexity, "conversational")

    def _prompt_fits_model(self, prompt: str, model_key: str, model_role: str) -> bool:
        """
        Check if a prompt fits within a model's context window with completion reserve.

        This is the guard in: measure → guard → route.
        Models that can't fit the prompt are skipped to avoid silent truncation.
        """
        model_config = self.openrouter_models.get(model_key, {})
        model_limit = int(
            model_config.get("context_window") or MODEL_CONTEXT_WINDOWS.get(model_key, 32_000)
        )
        reserve = COMPLETION_RESERVES.get(model_role, 1_000)
        prompt_tokens = count_tokens(prompt)
        remaining = model_limit - prompt_tokens
        fits = prompt_tokens + reserve <= model_limit

        if fits:
            logger.debug(
                f"[router] Model '{model_key}' fits role '{model_role}': "
                f"{prompt_tokens} + {reserve} reserve = {prompt_tokens + reserve} / {model_limit}"
            )
        else:
            logger.warning(
                f"[router] Skipping '{model_key}' for '{model_role}': "
                f"prompt {prompt_tokens}T + reserve {reserve}T = {prompt_tokens + reserve}T "
                f"exceeds window {model_limit}T. Remaining: {remaining}T"
            )
        return fits

    # -----------------------------------------------------------
    # CONCURRENCY GATE
    # -----------------------------------------------------------
    async def _acquire_slot(self, model_name: str, model_role: str, is_interactive: bool) -> None:
        """
        Wait for a priority-lane semaphore slot **and** honour the stagger delay.
        Interactive calls (chat, streaming) take from the interactive lane.
        Background calls (dashboard generation) take from the background lane.
        """
        await self._semaphore.acquire(is_interactive)
        async with self._stagger_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._stagger_delay:
                wait = self._stagger_delay - elapsed
                lane = "interactive" if is_interactive else "background"
                logger.debug(
                    f"Stagger [{lane}]: waiting {wait:.2f}s before {model_name} ({model_role})"
                )
                await asyncio.sleep(wait)
            self._last_request_time = time.monotonic()

    def _release_slot(self, is_interactive: bool) -> None:
        """Release a semaphore slot after the HTTP request completes."""
        self._semaphore.release(is_interactive)

    # -----------------------------------------------------------
    # OPENROUTER CALL
    # -----------------------------------------------------------
    async def _call_openrouter(
        self,
        prompt: str,
        model_role: str,
        expect_json: bool,
        json_schema: Optional[Dict[str, Any]] = None,
        specific_model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        max_retries: int = 3,
        retry_delay: float = 6.0,  # Increased from 2.0 for OpenRouter free tier
        is_conversational: bool = False,
        query_complexity: str = "moderate",
        context: Optional[str] = None,
        include_reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
        archetype: str = "analyst",
        is_interactive: Optional[bool] = None,
        instructions_override: Optional[str] = None,
    ) -> Any:
        """
        Call OpenRouter API with intelligent model selection.

        Args:
            prompt: User prompt
            model_role: Task role for model selection
            expect_json: Whether to expect JSON response
            specific_model: Override model selection
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            is_conversational: If True, use structured formatting for responses
            query_complexity: 'simple' | 'moderate' | 'complex' - affects response format
            archetype: 'explorer' | 'analyst' | 'expert' - user sophistication level
        """
        # Get the best model for this task
        model_config = self.get_model_for_role(model_role, specific_model)
        selected_model = model_config["model"]
        model_name = model_config["name"]

        # Build system prompt based on model strengths and conversation mode
        system_prompt = self._build_system_prompt(
            model_config,
            expect_json,
            is_conversational=is_conversational,
            query_complexity=query_complexity,
            archetype=archetype,
            instructions_override=instructions_override,
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://signal.ai",  # Optional: for ranking on OpenRouter
            "X-Title": "Signal Dashboard",  # Optional: shows in OpenRouter logs
        }

        # Build message history with the "Conversation Sandwich" pattern for caching
        # Pattern: [System] -> [User: Context] -> [Assistant: Ready] -> [User: Task]
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            # We add a stable acknowledgement step. This ensures the first ~3-4 messages
            # are identical across different agent calls for the same dataset.
            messages.extend(
                [
                    {"role": "user", "content": f"DATASET CONTEXT:\n{context}"},
                    {
                        "role": "assistant",
                        "content": "I have received the dataset context. I am now ready to perform the specific task you request based on this data.",
                    },
                ]
            )

        # Finally, add the dynamic task prompt
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        # Unified reasoning parameter logic
        reasoning_cfg = model_config.get("reasoning_config", None)
        if reasoning_effort:
            # Caller override — merge into existing config or create new
            reasoning_cfg = {**(reasoning_cfg or {}), "effort": reasoning_effort}

        if include_reasoning and reasoning_cfg is None:
            # Caller explicitly requested reasoning but model has no config — use safe default
            reasoning_cfg = {"effort": "medium", "exclude": False}

        if reasoning_cfg:
            payload["reasoning"] = reasoning_cfg
            logger.info(
                f"Reasoning enabled for {model_name} — "
                f"effort={reasoning_cfg.get('effort', 'N/A')}, "
                f"exclude={reasoning_cfg.get('exclude', False)}"
            )

        # Add response format hint for JSON if expected
        # Note: Not all models support this, but it helps when available
        if expect_json:
            if json_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": json_schema,
                }
            else:
                payload["response_format"] = {"type": "json_object"}

        logger.info(f"Calling OpenRouter with {model_name} (role: {model_role})")

        # Determine priority lane: conversational/chat calls are always interactive.
        # Background dashboard generation tasks use the background lane.
        interactive_call = (
            is_interactive
            if is_interactive is not None
            else (is_conversational or model_role in INTERACTIVE_ROLES)
        )
        lane_label = "interactive" if interactive_call else "background"
        logger.debug(f"LLM call routed to [{lane_label}] lane: {model_role}")

        # Retry logic with exponential backoff for rate limiting
        last_error = None

        for attempt in range(max_retries):
            # Acquire a concurrency slot before each HTTP request
            await self._acquire_slot(model_name, model_role, interactive_call)
            try:
                resp = await self.http.post(
                    settings.OPENROUTER_BASE_URL, headers=headers, json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                break  # Success, exit retry loop

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        wait_time = retry_delay * (2**attempt)  # Exponential backoff
                        logger.warning(
                            f"Rate limited (429). Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                raise  # Re-raise if not rate limit or last attempt
            finally:
                self._release_slot(interactive_call)
        else:
            # If we exhausted all retries
            if last_error:
                raise last_error

        # Continue with response processing
        data = data if "data" in locals() else None
        if data is None:
            raise HTTPException(502, "Failed to get response from OpenRouter after retries")
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning", "")  # legacy string
        reasoning_details = msg.get("reasoning_details", [])  # new structured format

        if reasoning:
            logger.info(f"REASONING TRACE ({len(reasoning)} chars): {reasoning[:200]}...")

        if reasoning_details:
            for block in reasoning_details:
                block_type = block.get("type", "unknown")
                if block_type == "reasoning.text":
                    logger.info(f"REASONING BLOCK [text]: {str(block.get('text', ''))[:200]}...")
                elif block_type == "reasoning.summary":
                    logger.info(f"REASONING BLOCK [summary]: {block.get('summary', '')[:200]}...")
                elif block_type == "reasoning.encrypted":
                    logger.info(f"REASONING BLOCK [encrypted]: <redacted>")

        # Log token usage if available
        usage = data.get("usage", {})
        if usage:
            logger.info(
                f"Token usage - Prompt: {usage.get('prompt_tokens')}, Completion: {usage.get('completion_tokens')}, Total: {usage.get('total_tokens')}"
            )

        if expect_json:
            try:
                parsed = json.loads(content)
                logger.info(f"Successfully parsed JSON from {model_name}")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(
                    f"JSON parse failed from {model_name}. Raw content (first 500 chars): {content[:500]}"
                )
                logger.error(f"JSON error: {str(e)}")

                # Try to extract JSON from markdown code blocks if present
                if "```json" in content or "```" in content:
                    logger.warning("Detected markdown code blocks, attempting to extract JSON...")
                    content = content.replace("```json", "").replace("```", "").strip()
                    try:
                        parsed = json.loads(content)
                        logger.info("Successfully extracted JSON from markdown!")
                        return parsed
                    except json.JSONDecodeError:
                        pass

                return {"error": "llm_json_parse_failed", "raw": content[:500]}

        return (content or "").strip()

    # -----------------------------------------------------------
    # STREAMING OPENROUTER CALL
    # -----------------------------------------------------------
    async def call_streaming(
        self,
        prompt: str,
        model_role: str,
        specific_model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        is_conversational: bool = True,
        query_complexity: str = "moderate",
        archetype: str = "analyst",
        is_interactive: Optional[bool] = None,
        user_id: Optional[str] = None,
        instructions_override: Optional[str] = None,
    ):
        """
        Stream tokens from OpenRouter API as an async generator.

        Args:
            prompt: User prompt
            model_role: Task role for model selection
            specific_model: Override model selection
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            is_conversational: If True, use structured formatting for responses
            query_complexity: 'simple' | 'moderate' | 'complex' - affects response format
            archetype: 'explorer' | 'analyst' | 'expert' - user sophistication level
            user_id: Optional user ID for cost tracking and budget checks

        Yields:
            Dict with type 'token' or 'done', and content/full_response
        """
        self._ensure_initialized()
        model_config = self.get_model_for_role(model_role, specific_model)
        selected_model = model_config["model"]
        model_name = model_config["name"]
        model_key = specific_model or self.role_mapping.get(model_role, "mistral_small_32")

        # ── Budget check before streaming ──
        if user_id and settings.LLM_COST_TRACKING_ENABLED:
            budget_check = await cost_tracker.check_budget(user_id)
            if not budget_check.get("allowed", True):
                logger.warning(
                    f"Budget exceeded for user {user_id[:8]}... on streaming role '{model_role}': "
                    f"{budget_check.get('reason', 'unknown')}"
                )
                yield {
                    "type": "error",
                    "content": f"LLM usage limit reached: {budget_check.get('reason', 'Budget exceeded')}. "
                    "Please try again tomorrow or contact support.",
                }
                return

        system_prompt = self._build_system_prompt(
            model_config,
            expect_json=False,
            is_conversational=is_conversational,
            query_complexity=query_complexity,
            archetype=archetype,
            instructions_override=instructions_override,
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://signal.ai",
            "X-Title": "Signal Dashboard",
        }

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        logger.info(f"Starting streaming call to OpenRouter with {model_name} (role: {model_role})")

        interactive_call = (
            is_interactive
            if is_interactive is not None
            else (is_conversational or model_role in INTERACTIVE_ROLES)
        )

        full_response = ""
        stream_error = None

        # Acquire concurrency slot for the entire stream duration
        await self._acquire_slot(model_name, model_role, interactive_call)
        try:
            async with self.http.stream(
                "POST",
                settings.OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
                timeout=180.0,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(
                        f"Streaming failed with status {response.status_code}: {error_text}"
                    )
                    yield {
                        "type": "error",
                        "content": f"API error: {response.status_code}",
                    }
                    return

                # Estimate input tokens from prompt length
                total_input_tokens = count_tokens(system_prompt + prompt) or 1

                # Parse Server-Sent Events (SSE) format
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue  # Skip empty lines and comments

                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str.strip() == "[DONE]":
                            # Stream complete — strip any JSON wrapper as defense-in-depth
                            cleaned = _strip_json_wrapper(full_response)
                            yield {"type": "done", "full_response": cleaned}
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

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse streaming chunk: {e}")
                            continue

                # If we exit the loop without [DONE], still yield final response
                if full_response:
                    # Strip any JSON wrapper as defense-in-depth
                    cleaned = _strip_json_wrapper(full_response)
                    yield {"type": "done", "full_response": cleaned}

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            stream_error = e
            yield {"type": "error", "content": str(e)}
        finally:
            self._release_slot(interactive_call)
            # ── Record usage after stream completes (even on partial failure) ──
            if user_id and settings.LLM_COST_TRACKING_ENABLED and full_response:
                try:
                    # Use actual token counting for post-hoc estimation
                    input_tokens = count_tokens(system_prompt + prompt) or 1
                    output_tokens = count_tokens(full_response) or 1
                    await cost_tracker.record_usage(
                        user_id=user_id,
                        model_key=model_key,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        role=model_role,
                    )
                except Exception as usage_err:
                    logger.warning(f"[CostTracker] Failed to record streaming usage: {usage_err}")

    def _build_system_prompt(
        self,
        model_config: Dict[str, Any],
        expect_json: bool,
        is_conversational: bool = False,
        query_complexity: str = "moderate",
        archetype: str = "analyst",
        instructions_override: Optional[str] = None,
    ) -> str:
        """
        Build an optimized system prompt based on model strengths and context.

        Args:
            model_config: Model configuration dict
            expect_json: Whether JSON output is expected
            is_conversational: If True, use structured formatting rules for human-readable responses
            query_complexity: 'simple' | 'moderate' | 'complex' - affects formatting depth
            archetype: 'explorer' | 'analyst' | 'expert' - user sophistication level
            instructions_override: Optional instructions block to inject into system prompt
                                  (from InsightReflectionAgent learned improvements)

        Returns:
            Optimized system prompt string
        """
        from core.prompt_templates import ARCHETYPE_INSTRUCTIONS

        # For conversational responses, always use the comprehensive formatting prompt
        # JSON output is handled by the system prompt itself (chart_config generation)
        if is_conversational:
            base_prompt = CONVERSATIONAL_SYSTEM_PROMPT

            # Inject archetype-based response calibration
            archetype_instruction = ARCHETYPE_INSTRUCTIONS.get(
                archetype, ARCHETYPE_INSTRUCTIONS.get("analyst", "")
            )
            base_prompt += archetype_instruction

            # Add complexity-specific guidance
            complexity_hint = COMPLEXITY_HINTS.get(query_complexity, COMPLEXITY_HINTS["moderate"])
            base_prompt += complexity_hint

            if expect_json:
                # Non-streaming: add explicit JSON output instruction
                base_prompt += (
                    "\n\nOUTPUT FORMAT: Your response MUST be valid JSON with this structure:\n"
                    '{"response_text": "<your markdown analysis>", "chart_config": null | {"type":"...","x":"...","y":"...","aggregation":"...","title":"..."}}\n'
                    "Return ONLY valid JSON — no markdown fences, no explanation outside JSON."
                )
            else:
                # Streaming mode: override the embedded JSON instructions with plain text
                # The base CONVERSATIONAL_SYSTEM_PROMPT contains JSON output format sections.
                # This final override instructs the model to output plain text instead.
                # Placed at the end to leverage recency bias — the model sees this last.
                base_prompt += (
                    "\n\n"
                    "══════════════════════════════════════════════════════════\n"
                    "⚠️  STREAMING OUTPUT — OVERRIDE ALL PRIOR FORMAT INSTRUCTIONS\n"
                    "══════════════════════════════════════════════════════════\n\n"
                    "CRITICAL: Do NOT wrap your response in JSON. Write as plain markdown text.\n"
                    "Ignore any previous instructions about JSON output format.\n"
                    "Your response MUST be plain text with markdown formatting only.\n"
                    "No JSON structure. No braces. No quotes wrapping your text.\n"
                    "Just write the analysis directly — clear, direct, with numbers.\n"
                    "Follow all other rules about jargon, confidence, and register.\n"
                )

            # ── Inject learned instructions from ConversationLearner ──
            # These are accumulated from InsightReflectionAgent feedback on
            # previous turns in the same conversation. Only injected for
            # conversational responses where the feedback loop is active.
            if instructions_override:
                base_prompt += f"\n\n{instructions_override}"

            return base_prompt

        # Non-conversational fallback: use the base prompt without modifications
        return CONVERSATIONAL_SYSTEM_PROMPT

    # -----------------------------------------------------------
    # OLLAMA CALL (COMMENTED OUT - USING OPENROUTER ONLY)
    # -----------------------------------------------------------
    # async def _call_ollama(self, prompt: str, model_role: str, expect_json: bool) -> Any:
    #     """
    #     DISABLED: User is using OpenRouter exclusively.
    #     Uncomment this method if you want to enable local Ollama fallback.
    #     """
    #     model_cfg = settings.MODELS.get(model_role)
    #     if not model_cfg:
    #         raise ValueError(f"Unknown model_role: {model_role}")
    #
    #     primary = model_cfg["primary"]
    #     base_url = primary["base_url"].rstrip("/")
    #     model_name = primary["model"]
    #
    #     payload = {"model": model_name, "prompt": prompt, "stream": False}
    #     if expect_json:
    #         payload["format"] = "json"
    #
    #     try:
    #         resp = await self.http.post(f"{base_url}/api/generate", json=payload)
    #         resp.raise_for_status()
    #         result = resp.json()
    #
    #         if expect_json:
    #             try:
    #                 return json.loads(result.get("response", "{}"))
    #             except json.JSONDecodeError:
    #                 return {"error": "llm_json_parse_failed"}
    #
    #         return result.get("response", "").strip()
    #
    #     except Exception as e:
    #         logger.error(f"Ollama call failed: {e}")
    #         if expect_json:
    #             return {"error": "model_unavailable", "details": str(e)}
    #         return f"Model unavailable: {e}"

    # -----------------------------------------------------------
    # MODEL TESTING & UTILITIES
    # -----------------------------------------------------------
    async def test_model(
        self,
        model_key: str,
        test_prompt: str = "Hello, please respond with a brief greeting.",
    ) -> Dict[str, Any]:
        """
        Test a specific OpenRouter model with a simple prompt.

        Args:
            model_key: Model key from OPENROUTER_MODELS (e.g., 'hermes_405b')
            test_prompt: Simple test prompt

        Returns:
            Dict with test results including success status, response, and timing
        """
        self._ensure_initialized()
        if model_key not in self.openrouter_models:
            return {"success": False, "error": f"Unknown model key: {model_key}"}

        model_config = self.openrouter_models[model_key]
        start_time = datetime.now()

        try:
            response = await self._call_openrouter(
                prompt=test_prompt,
                model_role="default",
                expect_json=False,
                specific_model=model_key,
                temperature=0.7,
                max_tokens=100,
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "model_key": model_key,
                "model_name": model_config["name"],
                "response": response[:200],  # First 200 chars
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "success": False,
                "model_key": model_key,
                "model_name": model_config["name"],
                "error": str(e),
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
            }

    async def test_all_models(self, delay_seconds: float = 2.0) -> Dict[str, Any]:
        """
        Test all configured OpenRouter models with rate limit handling.

        Args:
            delay_seconds: Delay between requests to avoid rate limiting (default: 2s)

        Returns:
            Dict with test results for each model
        """
        import asyncio

        results = {}
        test_prompt = "Respond with: 'Model test successful'"

        logger.info("Testing all OpenRouter models (with rate limit protection)...")

        for i, model_key in enumerate(self.openrouter_models.keys()):
            logger.info(f"Testing {model_key} ({i + 1}/{len(self.openrouter_models)})...")
            results[model_key] = await self.test_model(model_key, test_prompt)

            # Add delay between requests to avoid rate limiting (except after last model)
            if i < len(self.openrouter_models) - 1:
                logger.info(f"Waiting {delay_seconds}s before next test to avoid rate limits...")
                await asyncio.sleep(delay_seconds)

        # Summary
        successful = sum(1 for r in results.values() if r.get("success"))
        total = len(results)

        logger.info(f"Model testing complete: {successful}/{total} models successful")

        return {
            "summary": {
                "total_models": total,
                "successful": successful,
                "failed": total - successful,
            },
            "results": results,
        }

    def list_available_models(self) -> Dict[str, Any]:
        """
        List all available OpenRouter models with their configurations.

        Returns:
            Dict with model information
        """
        return {
            "total_models": len(self.openrouter_models),
            "models": {
                key: {
                    "name": config["name"],
                    "model_id": config["model"],
                    "strengths": config["strengths"],
                    "best_for": config["best_for"],
                    "context_window": config["context_window"],
                    "cost": config["cost"],
                }
                for key, config in self.openrouter_models.items()
            },
            "role_mapping": self.role_mapping,
        }

    # -----------------------------------------------------------
    # MODEL HEALTH CHECK (Legacy - for Ollama)
    # -----------------------------------------------------------
    async def check_model_health(self, model_info: Dict[str, str]) -> bool:
        key = f"{model_info['model']}_{model_info['base_url']}"
        now = datetime.now().timestamp()

        # cached health (1 minute)
        if key in self.model_health_cache:
            healthy, ts = self.model_health_cache[key]
            if (now - ts) < 60:
                return healthy

        try:
            resp = await self.http.post(
                f"{model_info['base_url']}/api/generate",
                json={"model": model_info["model"], "prompt": "ping"},
                timeout=settings.MODEL_HEALTH_CHECK_TIMEOUT,
            )
            healthy = resp.status_code == 200
        except Exception:
            healthy = False

        self.model_health_cache[key] = (healthy, now)
        return healthy


llm_router = LLMRouter()
