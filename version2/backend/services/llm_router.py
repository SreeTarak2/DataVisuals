import httpx
import json
import logging
from typing import Any, Dict
from datetime import datetime
from fastapi import HTTPException

from core.config import settings

logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(self):
        self.http = httpx.AsyncClient(timeout=180.0, follow_redirects=True)
        self.model_health_cache = {}
        self.use_openrouter = bool(settings.OPENROUTER_API_KEY)
        
        # Load OpenRouter model configurations
        self.openrouter_models = settings.OPENROUTER_MODELS
        self.role_mapping = settings.OPENROUTER_ROLE_MAPPING

    # -----------------------------------------------------------
    # PUBLIC ENTRY POINT
    # -----------------------------------------------------------
    async def call(
        self, 
        prompt: str, 
        model_role: str, 
        expect_json: bool = False,
        specific_model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
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
            
        Returns:
            Parsed JSON dict if expect_json=True, otherwise string
        """

        # Use OpenRouter exclusively (Ollama fallback commented out per user request)
        if self.use_openrouter:
            try:
                return await self._call_openrouter(
                    prompt, 
                    model_role, 
                    expect_json,
                    specific_model=specific_model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()
                logger.error(f"OpenRouter call failed for role '{model_role}': {e}")
                
                # Get current model and its fallback from FALLBACK_CHAIN
                current_model_key = specific_model or self.role_mapping.get(model_role, "mistral_24b")
                fallback_model_key = settings.FALLBACKS.get(current_model_key)
                
                # Try fallback model from chain if available
                if fallback_model_key and fallback_model_key in self.openrouter_models:
                    fallback_config = self.openrouter_models[fallback_model_key]
                    logger.warning(f"Trying fallback model: {fallback_config['name']}...")
                    try:
                        return await self._call_openrouter(
                            prompt, 
                            model_role,
                            expect_json,
                            specific_model=fallback_model_key,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                    except Exception as fallback_error:
                        logger.error(f"Fallback model also failed: {fallback_error}")
                
                raise HTTPException(502, f"AI provider unavailable: {str(e)}")

        # OpenRouter only mode
        raise HTTPException(500, "OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable.")

    

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
        model_key = self.role_mapping.get(model_role, "default")
        final_model_key = self.role_mapping.get(model_key, "mistral_24b")  # Resolve 'default'
        
        model_config = self.openrouter_models.get(final_model_key, self.openrouter_models["mistral_24b"])
        logger.info(f"Auto-selected model: {model_config['name']} for role '{model_role}'")
        
        return model_config

    # -----------------------------------------------------------
    # OPENROUTER CALL
    # -----------------------------------------------------------
    async def _call_openrouter(
        self, 
        prompt: str, 
        model_role: str, 
        expect_json: bool,
        specific_model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_retries: int = 3,
        retry_delay: float = 6.0  # Increased from 2.0 for OpenRouter free tier
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
        """
        # Get the best model for this task
        model_config = self.get_model_for_role(model_role, specific_model)
        selected_model = model_config["model"]
        model_name = model_config["name"]
        
        # Build system prompt based on model strengths
        system_prompt = self._build_system_prompt(model_config, expect_json)
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datasage.ai",  # Optional: for ranking on OpenRouter
            "X-Title": "DataSage AI Dashboard"       # Optional: shows in OpenRouter logs
        }

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        # Add response format hint for JSON if expected
        # Note: Not all models support this, but it helps when available
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        logger.info(f"Calling OpenRouter with {model_name} (role: {model_role})")
        
        # Retry logic with exponential backoff for rate limiting
        import asyncio
        last_error = None
        
        for attempt in range(max_retries):
            try:
                resp = await self.http.post(settings.OPENROUTER_BASE_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                break  # Success, exit retry loop
                
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limited (429). Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                raise  # Re-raise if not rate limit or last attempt
        else:
            # If we exhausted all retries
            if last_error:
                raise last_error
        
        # Continue with response processing
        data = data if 'data' in locals() else None
        if data is None:
            raise HTTPException(502, "Failed to get response from OpenRouter after retries")
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        
        # Log token usage if available
        usage = data.get("usage", {})
        if usage:
            logger.info(f"Token usage - Prompt: {usage.get('prompt_tokens')}, Completion: {usage.get('completion_tokens')}, Total: {usage.get('total_tokens')}")

        if expect_json:
            try:
                parsed = json.loads(content)
                logger.info(f"Successfully parsed JSON from {model_name}")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse failed from {model_name}. Raw content (first 500 chars): {content[:500]}")
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
        max_tokens: int = 4096
    ):
        """
        Stream tokens from OpenRouter API as an async generator.
        
        Args:
            prompt: User prompt
            model_role: Task role for model selection
            specific_model: Override model selection
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Yields:
            Dict with type 'token' or 'done', and content/full_response
        """
        model_config = self.get_model_for_role(model_role, specific_model)
        selected_model = model_config["model"]
        model_name = model_config["name"]
        
        system_prompt = self._build_system_prompt(model_config, expect_json=False)
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datasage.ai",
            "X-Title": "DataSage AI Dashboard"
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
        
        full_response = ""
        
        try:
            async with self.http.stream(
                "POST",
                settings.OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
                timeout=180.0
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"Streaming failed with status {response.status_code}: {error_text}")
                    yield {"type": "error", "content": f"API error: {response.status_code}"}
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

    

    def _build_system_prompt(self, model_config: Dict[str, Any], expect_json: bool) -> str:
        """
        Build an optimized system prompt based on model strengths.
        
        Args:
            model_config: Model configuration dict
            expect_json: Whether JSON output is expected
            
        Returns:
            Optimized system prompt string
        """
        base_prompt = "You are DataSage AI, an expert data analysis and visualization assistant."
        
        strengths = model_config.get("strengths", [])
        
        # Add specific instructions based on model strengths
        if "structured_output" in strengths or "json_generation" in strengths:
            base_prompt += " You excel at generating well-structured, valid JSON outputs."
        
        if "reasoning" in strengths or "thinking_mode" in strengths:
            base_prompt += " You have advanced reasoning capabilities and can break down complex problems step-by-step."
        
        if "vision" in strengths or "chart_analysis" in strengths:
            base_prompt += " You can analyze charts, images, and visual data with high accuracy."
        
        if "function_calling" in strengths:
            base_prompt += " You can use function calling and tool integration effectively."
        
        # Add JSON-specific instructions if needed
        if expect_json:
            base_prompt += "\n\nIMPORTANT: Return ONLY valid JSON with no markdown formatting, no code blocks (no ```), and no additional text or explanations. The response must be pure JSON that can be parsed directly."
        
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
    async def test_model(self, model_key: str, test_prompt: str = "Hello, please respond with a brief greeting.") -> Dict[str, Any]:
        """
        Test a specific OpenRouter model with a simple prompt.
        
        Args:
            model_key: Model key from OPENROUTER_MODELS (e.g., 'hermes_405b')
            test_prompt: Simple test prompt
            
        Returns:
            Dict with test results including success status, response, and timing
        """
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
                max_tokens=100
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "success": True,
                "model_key": model_key,
                "model_name": model_config["name"],
                "response": response[:200],  # First 200 chars
                "duration_seconds": duration,
                "timestamp": start_time.isoformat()
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
                "timestamp": start_time.isoformat()
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
            logger.info(f"Testing {model_key} ({i+1}/{len(self.openrouter_models)})...")
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
                "failed": total - successful
            },
            "results": results
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
                    "cost": config["cost"]
                }
                for key, config in self.openrouter_models.items()
            },
            "role_mapping": self.role_mapping
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
                timeout=settings.MODEL_HEALTH_CHECK_TIMEOUT
            )
            healthy = resp.status_code == 200
        except Exception:
            healthy = False

        self.model_health_cache[key] = (healthy, now)
        return healthy

llm_router = LLMRouter()
