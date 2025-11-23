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

    # -----------------------------------------------------------
    # PUBLIC ENTRY POINT
    # -----------------------------------------------------------
    async def call(self, prompt: str, model_role: str, expect_json: bool = False) -> Any:
        """
        Always call this method instead of directly calling underlying providers.
        It automatically applies fallback logic.
        """

        # Use OpenRouter exclusively (Ollama fallback commented out per user request)
        if self.use_openrouter:
            try:
                return await self._call_openrouter(prompt, model_role, expect_json)
            except Exception as e:
                logger.error(f"OpenRouter call failed: {e}")
                raise HTTPException(502, f"AI provider unavailable: {str(e)}")

        # Ollama fallback disabled - OpenRouter only mode
        raise HTTPException(500, "OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable.")

    # -----------------------------------------------------------
    # OPENROUTER CALL
    # -----------------------------------------------------------
    async def _call_openrouter(self, prompt: str, model_role: str, expect_json: bool) -> Any:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are DataSage AI, an expert data assistant. When asked for JSON, return ONLY valid JSON with no markdown formatting, no code blocks, and no additional text."
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        
        # Add response format hint for JSON if expected
        if expect_json:
            payload["response_format"] = {"type": "json_object"}

        resp = await self.http.post(settings.OPENROUTER_BASE_URL, headers=headers, json=payload)
        resp.raise_for_status()

        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")

        if expect_json:
            try:
                parsed = json.loads(content)
                logger.info(f"Successfully parsed JSON from OpenRouter")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse failed. Raw content (first 500 chars): {content[:500]}")
                logger.error(f"JSON error: {str(e)}")
                return {"error": "llm_json_parse_failed", "raw": content[:500]}

        return content.strip()

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
    # MODEL HEALTH CHECK
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
