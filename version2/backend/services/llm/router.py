import asyncio
import httpx
import json
import logging
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException

from core.config import settings
from core.prompt_templates import CONVERSATIONAL_SYSTEM_PROMPT, COMPLEXITY_HINTS

logger = logging.getLogger(__name__)


# Roles that are always user-facing — must NEVER be queued behind background tasks
INTERACTIVE_ROLES = frozenset(
    {
        "conversational",
        "chat_engine",
        "chat_streaming",
        "narrative_story",
        "sql_generator",
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
            self._semaphore = PriorityLLMSemaphore(
                settings.LLM_MAX_CONCURRENT_CALLS
            )
            
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

        Returns:
            Parsed JSON dict if expect_json=True, otherwise string
        """

        self._ensure_initialized()

        # Use OpenRouter exclusively (Ollama fallback commented out per user request)
        if self.use_openrouter:
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
            try:
                return await self._call_openrouter(
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
                )
            except Exception as e:
                error_str = str(e)
                logger.error(f"OpenRouter call failed for role '{model_role}': {e}")

                status_code = None
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                elif isinstance(e, HTTPException):
                    status_code = e.status_code

                is_auth_error = (
                    status_code in (401, 403)
                    or "401" in error_str
                    or "403" in error_str
                )
                if is_auth_error:
                    self._auth_error_cooldown_until = datetime.utcnow() + timedelta(
                        minutes=5
                    )
                    raise HTTPException(
                        502,
                        "OpenRouter authentication failed (401/403). "
                        "Please verify OPENROUTER_API_KEY in backend/.env.",
                    )

                # Do not retry/fallback for non-rate-limit client errors.
                is_non_rate_client_error = (
                    status_code is not None
                    and 400 <= status_code < 500
                    and status_code != 429
                )
                if is_non_rate_client_error:
                    raise HTTPException(502, f"AI provider unavailable: {str(e)}")

                # Try role-based fallback chain for transient errors.
                fallback_models = self._get_fallback_models(model_role, specific_model)
                for fallback_model_key in fallback_models:
                    fallback_config = self.openrouter_models[fallback_model_key]
                    logger.warning(
                        f"Trying fallback model: {fallback_config['name']}..."
                    )
                    try:
                        return await self._call_openrouter(
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
                        )
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

    def get_model_for_role(
        self, model_role: str, specific_model: str = None
    ) -> Dict[str, Any]:
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
            logger.info(
                f"Using specific model: {model_config['name']} for role '{model_role}'"
            )
            return model_config

        # Otherwise, use role mapping
        model_key = self.role_mapping.get(model_role)
        if not model_key or model_key not in self.openrouter_models:
            # Role not mapped or mapped model unavailable — resolve via "default" role
            model_key = self.role_mapping.get("default", "mistral_small_32")

        model_config = self.openrouter_models.get(
            model_key, self.openrouter_models["mistral_small_32"]
        )
        logger.info(
            f"Auto-selected model: {model_config['name']} for role '{model_role}'"
        )

        return model_config

    def _get_fallback_models(
        self, model_role: str, specific_model: Optional[str] = None
    ) -> List[str]:
        """
        Resolve fallback candidates for a role in priority order.
        """
        current_model_key = specific_model or self.role_mapping.get(
            model_role, "mistral_small_32"
        )
        role_fallbacks = settings.FALLBACKS.get(model_role, [])

        if isinstance(role_fallbacks, str):
            role_fallbacks = [role_fallbacks]

        return [
            model_key
            for model_key in role_fallbacks
            if model_key in self.openrouter_models and model_key != current_model_key
        ]

    # -----------------------------------------------------------
    # CONCURRENCY GATE
    # -----------------------------------------------------------
    async def _acquire_slot(
        self, model_name: str, model_role: str, is_interactive: bool
    ) -> None:
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
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datasage.ai",  # Optional: for ranking on OpenRouter
            "X-Title": "DataSage AI Dashboard",  # Optional: shows in OpenRouter logs
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
        is_interactive = is_conversational or model_role in INTERACTIVE_ROLES
        lane_label = "interactive" if is_interactive else "background"
        logger.debug(f"LLM call routed to [{lane_label}] lane: {model_role}")

        # Retry logic with exponential backoff for rate limiting
        last_error = None

        for attempt in range(max_retries):
            # Acquire a concurrency slot before each HTTP request
            await self._acquire_slot(model_name, model_role, is_interactive)
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
                self._release_slot(is_interactive)
        else:
            # If we exhausted all retries
            if last_error:
                raise last_error

        # Continue with response processing
        data = data if "data" in locals() else None
        if data is None:
            raise HTTPException(
                502, "Failed to get response from OpenRouter after retries"
            )
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning", "")  # legacy string
        reasoning_details = msg.get("reasoning_details", [])  # new structured format

        if reasoning:
            logger.info(
                f"REASONING TRACE ({len(reasoning)} chars): {reasoning[:200]}..."
            )

        if reasoning_details:
            for block in reasoning_details:
                block_type = block.get("type", "unknown")
                if block_type == "reasoning.text":
                    logger.info(
                        f"REASONING BLOCK [text]: {str(block.get('text', ''))[:200]}..."
                    )
                elif block_type == "reasoning.summary":
                    logger.info(
                        f"REASONING BLOCK [summary]: {block.get('summary', '')[:200]}..."
                    )
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
                    logger.warning(
                        "Detected markdown code blocks, attempting to extract JSON..."
                    )
                    content = content.replace("```json", "").replace("```", "").strip()
                    try:
                        parsed = json.loads(content)
                        logger.info("Successfully extracted JSON from markdown!")
                        return parsed
                    except json.JSONDecodeError:
                        pass

                return {"error": "llm_json_parse_failed", "raw": content[:500]}

        return content.strip()

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

        Yields:
            Dict with type 'token' or 'done', and content/full_response
        """
        self._ensure_initialized()
        model_config = self.get_model_for_role(model_role, specific_model)
        selected_model = model_config["model"]
        model_name = model_config["name"]

        system_prompt = self._build_system_prompt(
            model_config,
            expect_json=False,
            is_conversational=is_conversational,
            query_complexity=query_complexity,
            archetype=archetype,
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datasage.ai",
            "X-Title": "DataSage AI Dashboard",
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

        logger.info(
            f"Starting streaming call to OpenRouter with {model_name} (role: {model_role})"
        )

        is_interactive = is_conversational or model_role in INTERACTIVE_ROLES

        full_response = ""

        # Acquire concurrency slot for the entire stream duration
        await self._acquire_slot(model_name, model_role, is_interactive)
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

                # Parse Server-Sent Events (SSE) format
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue  # Skip empty lines and comments

                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str.strip() == "[DONE]":
                            # Stream complete
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

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse streaming chunk: {e}")
                            continue

                # If we exit the loop without [DONE], still yield final response
                if full_response:
                    yield {"type": "done", "full_response": full_response}

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}
        finally:
            self._release_slot(is_interactive)

    def _build_system_prompt(
        self,
        model_config: Dict[str, Any],
        expect_json: bool,
        is_conversational: bool = False,
        query_complexity: str = "moderate",
        archetype: str = "analyst",
    ) -> str:
        """
        Build an optimized system prompt based on model strengths and context.

        Args:
            model_config: Model configuration dict
            expect_json: Whether JSON output is expected
            is_conversational: If True, use structured formatting rules for human-readable responses
            query_complexity: 'simple' | 'moderate' | 'complex' - affects formatting depth
            archetype: 'explorer' | 'analyst' | 'expert' - user sophistication level

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
            complexity_hint = COMPLEXITY_HINTS.get(
                query_complexity, COMPLEXITY_HINTS["moderate"]
            )
            base_prompt += complexity_hint

            # If JSON is expected, add the instruction to the system prompt
            # (the CONVERSATIONAL_SYSTEM_PROMPT now includes its own JSON output format)
            if expect_json:
                base_prompt += (
                    "\n\nOUTPUT FORMAT: Your response MUST be valid JSON with this structure:\n"
                    '{"response_text": "<your markdown analysis>", "chart_config": null | {"type":"...","x":"...","y":"...","aggregation":"...","title":"..."}}\n'
                    "Return ONLY valid JSON — no markdown fences, no explanation outside JSON."
                )

            return base_prompt

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
            logger.info(
                f"Testing {model_key} ({i + 1}/{len(self.openrouter_models)})..."
            )
            results[model_key] = await self.test_model(model_key, test_prompt)

            # Add delay between requests to avoid rate limiting (except after last model)
            if i < len(self.openrouter_models) - 1:
                logger.info(
                    f"Waiting {delay_seconds}s before next test to avoid rate limits..."
                )
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
