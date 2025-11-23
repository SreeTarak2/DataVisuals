# 🔥 DataSage Chat Enhancement - Complete Production Guide

**Critical Issue Detected:** Empty LLM responses  
**Root Cause:** Prompt engineering forces JSON structure but doesn't guide content generation  
**Solution:** Complete backend overhaul with streaming support  

---

## 🚨 IMMEDIATE CRITICAL FIX

### Problem: Empty `response_text` in LLM Responses

**Current Behavior:**
```json
{
  "response_text": "",  // ← EMPTY!
  "chart_config": null,
  "confidence": "High"
}
```

**Root Cause:**
Your prompt in `core/prompts.py` is telling the LLM:
1. "Output valid JSON only"
2. Format: `{"response_text":"","chart_config":null,"confidence":"High"}`

The LLM sees the **empty string in the example** and thinks that's what you want!

### Quick Fix for Immediate Relief

**File:** `backend/core/prompts.py`

**Current (BROKEN) Prompt:**
```python
def _conversational_prompt(self, query: str = "", history: Optional[List[Dict[str, str]]] = None, allow_markdown: bool = True):
    # ... existing code ...
    return f"{SYSTEM_JSON_RULES}\n{persona}\n{GLOBAL_BEHAVIOR_RULES}\nUSER_QUERY: {json.dumps(safe_query)}\n{hist}\nDATASET_CONTEXT:\n{self.dataset_context}\nTASK: Provide an analytical answer. chart_config only if beneficial. {markdown_note}\nFORMAT:\n{{\"response_text\":\"\",\"chart_config\":null,\"confidence\":\"High\"}}".strip()
    # ↑ Shows empty response_text!
```

**Fixed Prompt:**
```python
def _conversational_prompt(self, query: str = "", history: Optional[List[Dict[str, str]]] = None, allow_markdown: bool = True):
    safe_query = sanitize_text(query, 500)
    hist = ""
    if history:
        hist_lines = []
        for m in history[-3:]:
            role = m.get("role", "user")
            content = sanitize_text(m.get("content", ""), 150)
            hist_lines.append(f"{role}: {content}")
        hist = "\nCONVERSATION_HISTORY:\n" + "\n".join(hist_lines)
    
    persona = PERSONA_ANALYTICAL
    markdown_note = "Use markdown formatting (bold, lists, code blocks) in response_text for better readability" if allow_markdown else "Use plain text only in response_text"
    
    # CRITICAL: Don't show empty string in example!
    return f"""{SYSTEM_JSON_RULES}
{persona}
{GLOBAL_BEHAVIOR_RULES}

DATASET_CONTEXT:
{self.dataset_context}

{hist}

USER_QUESTION: {safe_query}

INSTRUCTIONS:
1. Analyze the user's question in context of the dataset
2. Provide a detailed, helpful answer in the "response_text" field
3. If a chart would help visualize the answer, include "chart_config" (otherwise null)
4. Set "confidence" to High/Medium/Low based on data quality
5. {markdown_note}

IMPORTANT: The response_text field must contain your actual answer. Do NOT leave it empty!

OUTPUT_FORMAT (with example values):
{{
  "response_text": "Based on the sales data, the top performing product is iPhone with $2.5M in revenue, representing 45% of total sales. The trend shows steady growth over Q1-Q3.",
  "chart_config": {{"type": "bar", "x": "product", "y": "revenue"}} or null,
  "confidence": "High"
}}

Now respond to the user's question with a complete, helpful answer:""".strip()
```

**Apply this fix NOW:**

---

## 📋 TABLE OF CONTENTS

1. [Immediate Fix (Above)](#-immediate-critical-fix)
2. [System Architecture Overview](#system-architecture-overview)
3. [Enhanced LLM Router Implementation](#enhanced-llm-router-implementation)
4. [WebSocket Streaming System](#websocket-streaming-system)
5. [Connection Manager](#connection-manager-implementation)
6. [Rate Limiter](#rate-limiter-implementation)
7. [Streaming AI Service](#streaming-ai-service-implementation)
8. [Enhanced Chat Router](#enhanced-chat-router)
9. [Frontend Integration](#frontend-integration)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Guide](#deployment-guide)
12. [Monitoring & Debugging](#monitoring--debugging)

---

## SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Chat UI      │  │ WebSocket    │  │ Message      │      │
│  │              │◄─┤ Client       │◄─┤ Store        │      │
│  └──────────────┘  └──────┬───────┘  └──────────────┘      │
└────────────────────────────┼────────────────────────────────┘
                             │ WSS (Token Streaming)
                             ▼
┌────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                        │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │         WebSocket Chat Router (/ws/chat)              │ │
│  │  • JWT Authentication                                 │ │
│  │  • Message Queue (asyncio.Queue)                      │ │
│  │  • Session State Management                           │ │
│  └─────────────────────┬─────────────────────────────────┘ │
│                        │                                     │
│  ┌─────────────────────▼─────────────────────────────────┐ │
│  │           Connection Manager                          │ │
│  │  • Pool: user_id → Set[WebSocket]                    │ │
│  │  • Heartbeat: 30s ping/pong                          │ │
│  │  • Multi-tab sync                                    │ │
│  └─────────────────────┬─────────────────────────────────┘ │
│                        │                                     │
│  ┌─────────────────────▼─────────────────────────────────┐ │
│  │         Streaming AI Service                          │ │
│  │  • Load dataset context                               │ │
│  │  • Build system prompt                                │ │
│  │  • Stream tokens to client                            │ │
│  └─────────────────────┬─────────────────────────────────┘ │
│                        │                                     │
│  ┌─────────────────────▼─────────────────────────────────┐ │
│  │           Enhanced LLM Router                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Provider Selection (Circuit Breaker)            │ │ │
│  │  │  • OpenRouter (primary)                          │ │ │
│  │  │  • Anthropic (fallback)                          │ │ │
│  │  │  • OpenAI (fallback)                             │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Token Streaming                                 │ │ │
│  │  │  • HTTP clients (streaming/normal)               │ │ │
│  │  │  • Connection pooling                            │ │ │
│  │  │  • Retry + exponential backoff                   │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Metrics & Monitoring                            │ │ │
│  │  │  • Token usage                                   │ │ │
│  │  │  • Cost tracking                                 │ │ │
│  │  │  • Latency monitoring                            │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │         Rate Limiter                                  │ │
│  │  • Per-user queues (deque)                           │ │
│  │  • Token bucket algorithm                            │ │
│  │  • 20 req/min default                                │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## ENHANCED LLM ROUTER IMPLEMENTATION

### File Structure
```
backend/
├── services/
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm_router.py          # ← REPLACE with enhanced version
│   │   ├── streaming_service.py   # ← NEW
│   │   └── ai_service.py          # ← Keep existing
│   └── websocket/
│       ├── __init__.py
│       ├── connection_manager.py  # ← NEW
│       └── rate_limiter.py        # ← NEW
```

### Dependencies
```bash
cd /home/vamsi/nothing/datasage/version2/backend
pip install tiktoken==0.5.2
```

### Enhanced LLM Router Code

**File:** `backend/services/ai/llm_router.py`

```python
"""
Enhanced LLM Router with:
- Token streaming support
- Multi-provider fallback (OpenRouter → Anthropic → OpenAI)
- Circuit breaker pattern
- Token counting & cost tracking
- Performance metrics
- Rate limiting
"""

import httpx
import json
import logging
import asyncio
from typing import Any, Dict, AsyncGenerator, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import tiktoken

from core.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES & ENUMS
# ============================================================================

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class TokenUsage:
    """Track token usage and costs"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    
    def __add__(self, other):
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost=self.estimated_cost + other.estimated_cost
        )


@dataclass
class StreamChunk:
    """Represents a single chunk of streamed response"""
    type: str  # 'token', 'complete', 'error', 'thinking'
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_usage: Optional[TokenUsage] = None


@dataclass
class ProviderMetrics:
    """Track provider performance metrics"""
    total_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    status: ProviderStatus = ProviderStatus.HEALTHY
    
    # Circuit breaker
    consecutive_failures: int = 0
    circuit_open_until: Optional[datetime] = None
    
    def record_success(self, latency_ms: float, tokens: int, cost: float):
        """Record successful request"""
        self.total_requests += 1
        self.total_tokens += tokens
        self.total_cost += cost
        
        # Exponential moving average for latency
        alpha = 0.3
        self.avg_latency_ms = (
            alpha * latency_ms + (1 - alpha) * self.avg_latency_ms
            if self.avg_latency_ms > 0 else latency_ms
        )
        
        self.consecutive_failures = 0
        self.status = ProviderStatus.HEALTHY
    
    def record_failure(self, error: str):
        """Record failed request"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_error = error
        self.last_error_time = datetime.now()
        
        # Open circuit breaker after 3 consecutive failures
        if self.consecutive_failures >= 3:
            self.status = ProviderStatus.FAILED
            self.circuit_open_until = datetime.now() + timedelta(minutes=5)
            logger.warning(f"Circuit breaker opened until {self.circuit_open_until}")
        elif self.consecutive_failures >= 1:
            self.status = ProviderStatus.DEGRADED
    
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.circuit_open_until and datetime.now() < self.circuit_open_until:
            return True
        
        # Reset circuit breaker if time expired
        if self.circuit_open_until and datetime.now() >= self.circuit_open_until:
            self.circuit_open_until = None
            self.consecutive_failures = 0
            self.status = ProviderStatus.DEGRADED
        
        return False


# ============================================================================
# ENHANCED LLM ROUTER
# ============================================================================

class EnhancedLLMRouter:
    """
    Production-grade LLM router with:
    - Token-by-token streaming
    - Multiple provider support with fallback
    - Circuit breaker pattern
    - Token counting & cost tracking
    - Rate limiting
    - Retry with exponential backoff
    - Connection pooling
    - Performance metrics
    """
    
    def __init__(self):
        # HTTP clients with proper configuration
        self.streaming_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            follow_redirects=True
        )
        
        self.non_streaming_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
            follow_redirects=True
        )
        
        # Provider configuration
        self.providers = self._initialize_providers()
        
        # Metrics tracking
        self.metrics: Dict[str, ProviderMetrics] = {
            provider: ProviderMetrics() for provider in self.providers.keys()
        }
        
        # Token encoding for cost estimation
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Rate limiting
        self.user_queues: Dict[str, deque] = {}
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_window = 20
        
        logger.info(f"Initialized Enhanced LLM Router with providers: {list(self.providers.keys())}")
    
    def _initialize_providers(self) -> Dict[str, Dict]:
        """Initialize available LLM providers"""
        providers = {}
        
        # OpenRouter (primary)
        if settings.OPENROUTER_API_KEY:
            providers["openrouter"] = {
                "name": "OpenRouter",
                "base_url": settings.OPENROUTER_BASE_URL,
                "api_key": settings.OPENROUTER_API_KEY,
                "model": settings.OPENROUTER_MODEL,
                "supports_streaming": True,
                "cost_per_1k_tokens": {
                    "prompt": 0.003,
                    "completion": 0.015
                }
            }
        
        # Anthropic (fallback)
        if hasattr(settings, 'ANTHROPIC_API_KEY') and settings.ANTHROPIC_API_KEY:
            providers["anthropic"] = {
                "name": "Anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "api_key": settings.ANTHROPIC_API_KEY,
                "model": "claude-sonnet-4-20250514",
                "supports_streaming": True,
                "cost_per_1k_tokens": {
                    "prompt": 0.003,
                    "completion": 0.015
                }
            }
        
        # OpenAI (fallback)
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            providers["openai"] = {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": settings.OPENAI_API_KEY,
                "model": "gpt-4-turbo-preview",
                "supports_streaming": True,
                "cost_per_1k_tokens": {
                    "prompt": 0.01,
                    "completion": 0.03
                }
            }
        
        if not providers:
            raise RuntimeError("No LLM providers configured! Set at least OPENROUTER_API_KEY.")
        
        return providers
    
    # ========================================================================
    # PUBLIC API - STREAMING
    # ========================================================================
    
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model_preference: Optional[str] = None,
        user_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream chat response token by token
        
        Args:
            messages: Conversation history [{"role": "user", "content": "..."}, ...]
            system_prompt: System instructions
            model_preference: Preferred provider (openrouter, anthropic, openai)
            user_id: For rate limiting
            temperature: Response randomness (0-1)
            max_tokens: Max response length
        
        Yields:
            StreamChunk objects with type 'token', 'complete', or 'error'
        """
        
        # Rate limiting check
        if user_id and not await self._check_rate_limit(user_id):
            yield StreamChunk(
                type="error",
                content="Rate limit exceeded. Please wait before sending more messages.",
                metadata={"error_code": "RATE_LIMIT"}
            )
            return
        
        # Select provider
        provider_key = await self._select_provider(model_preference)
        if not provider_key:
            yield StreamChunk(
                type="error",
                content="All AI providers are currently unavailable. Please try again later.",
                metadata={"error_code": "NO_PROVIDER"}
            )
            return
        
        provider = self.providers[provider_key]
        metrics = self.metrics[provider_key]
        
        logger.info(f"Using provider: {provider_key} for streaming chat")
        
        start_time = datetime.now()
        total_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        try:
            # Prepare messages
            formatted_messages = self._format_messages(messages, system_prompt)
            
            # Estimate prompt tokens
            prompt_tokens = self._count_tokens(formatted_messages)
            
            # Stream from provider
            async for chunk in self._stream_from_provider(
                provider_key,
                formatted_messages,
                temperature,
                max_tokens
            ):
                if chunk.type == "token":
                    total_content += chunk.content
                    completion_tokens = self._count_tokens(total_content)
                    yield chunk
                    
                elif chunk.type == "error":
                    # Record failure and try fallback
                    metrics.record_failure(chunk.content)
                    
                    # Try fallback provider
                    fallback_provider = await self._select_provider(exclude=[provider_key])
                    if fallback_provider:
                        logger.warning(f"Falling back to {fallback_provider}")
                        async for fallback_chunk in self.stream_chat(
                            messages, system_prompt, fallback_provider, user_id, temperature, max_tokens
                        ):
                            yield fallback_chunk
                        return
                    else:
                        yield chunk
                        return
            
            # Calculate metrics
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            total_tokens = prompt_tokens + completion_tokens
            cost = self._calculate_cost(provider, prompt_tokens, completion_tokens)
            
            # Record success
            metrics.record_success(latency_ms, total_tokens, cost)
            
            # Send completion
            yield StreamChunk(
                type="complete",
                metadata={
                    "provider": provider_key,
                    "model": provider["model"],
                    "latency_ms": round(latency_ms, 2),
                },
                token_usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=cost
                )
            )
            
        except Exception as e:
            logger.error(f"Stream chat failed: {e}", exc_info=True)
            metrics.record_failure(str(e))
            yield StreamChunk(
                type="error",
                content=f"An unexpected error occurred: {str(e)}",
                metadata={"error_code": "INTERNAL_ERROR"}
            )
    
    # ========================================================================
    # PUBLIC API - NON-STREAMING (for JSON responses)
    # ========================================================================
    
    async def call(
        self,
        prompt: str,
        model_role: str = "chart_engine",
        expect_json: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> Any:
        """
        Non-streaming call for structured outputs (backward compatible)
        
        Args:
            prompt: User prompt
            model_role: Ignored (kept for backward compatibility)
            expect_json: Parse response as JSON
            temperature: Lower for JSON (0-1)
            max_tokens: Max response length
        
        Returns:
            String or parsed JSON dict
        """
        messages = [{"role": "user", "content": prompt}]
        
        full_response = ""
        token_usage = None
        
        async for chunk in self.stream_chat(
            messages,
            system_prompt=None,
            model_preference=None,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            if chunk.type == "token":
                full_response += chunk.content
            elif chunk.type == "complete":
                token_usage = chunk.token_usage
            elif chunk.type == "error":
                raise HTTPException(502, chunk.content)
        
        # Parse JSON if requested
        if expect_json:
            try:
                return json.loads(full_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {full_response[:200]}")
                return {
                    "error": "json_parse_failed",
                    "raw_response": full_response[:500],
                    "parse_error": str(e)
                }
        
        return full_response.strip()
    
    # ========================================================================
    # PROVIDER STREAMING IMPLEMENTATIONS
    # ========================================================================
    
    async def _stream_from_provider(
        self,
        provider_key: str,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream from specific provider"""
        
        if provider_key == "openrouter":
            async for chunk in self._stream_openrouter(messages, temperature, max_tokens):
                yield chunk
        
        elif provider_key == "anthropic":
            async for chunk in self._stream_anthropic(messages, temperature, max_tokens):
                yield chunk
        
        elif provider_key == "openai":
            async for chunk in self._stream_openai(messages, temperature, max_tokens):
                yield chunk
        
        else:
            yield StreamChunk(type="error", content=f"Unknown provider: {provider_key}")
    
    async def _stream_openrouter(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream from OpenRouter"""
        provider = self.providers["openrouter"]
        
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datasage.app",
            "X-Title": "DataSage AI"
        }
        
        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        try:
            async with self.streaming_client.stream(
                "POST",
                f"{provider['base_url']}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or line.startswith(":"):
                        continue
                    
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix
                    
                    if line == "[DONE]":
                        break
                    
                    try:
                        chunk_data = json.loads(line)
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        
                        if content:
                            yield StreamChunk(type="token", content=content)
                    
                    except json.JSONDecodeError:
                        continue
        
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
            yield StreamChunk(
                type="error",
                content=f"Provider error: {e.response.status_code}",
                metadata={"status_code": e.response.status_code}
            )
        
        except Exception as e:
            logger.error(f"OpenRouter streaming failed: {e}", exc_info=True)
            yield StreamChunk(type="error", content=str(e))
    
    async def _stream_anthropic(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream from Anthropic Claude API"""
        provider = self.providers["anthropic"]
        
        headers = {
            "x-api-key": provider['api_key'],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Anthropic format: separate system message
        system_msg = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)
        
        payload = {
            "model": provider["model"],
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        
        if system_msg:
            payload["system"] = system_msg
        
        try:
            async with self.streaming_client.stream(
                "POST",
                f"{provider['base_url']}/messages",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    line = line[6:]  # Remove "data: " prefix
                    
                    try:
                        chunk_data = json.loads(line)
                        
                        if chunk_data.get("type") == "content_block_delta":
                            content = chunk_data.get("delta", {}).get("text", "")
                            if content:
                                yield StreamChunk(type="token", content=content)
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}", exc_info=True)
            yield StreamChunk(type="error", content=str(e))
    
    async def _stream_openai(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream from OpenAI GPT API"""
        provider = self.providers["openai"]
        
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        try:
            async with self.streaming_client.stream(
                "POST",
                f"{provider['base_url']}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    
                    line = line[6:]
                    
                    if line == "[DONE]":
                        break
                    
                    try:
                        chunk_data = json.loads(line)
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        
                        if content:
                            yield StreamChunk(type="token", content=content)
                    
                    except json.JSONDecodeError:
                        continue
        
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}", exc_info=True)
            yield StreamChunk(type="error", content=str(e))
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _select_provider(
        self,
        preference: Optional[str] = None,
        exclude: List[str] = []
    ) -> Optional[str]:
        """
        Select best available provider based on:
        - User preference
        - Circuit breaker status
        - Performance metrics
        """
        available_providers = [
            key for key in self.providers.keys()
            if key not in exclude and not self.metrics[key].is_circuit_open()
        ]
        
        if not available_providers:
            return None
        
        # Use preference if available and healthy
        if preference and preference in available_providers:
            return preference
        
        # Sort by performance (lowest failure rate, fastest latency)
        available_providers.sort(
            key=lambda p: (
                self.metrics[p].failed_requests / max(self.metrics[p].total_requests, 1),
                self.metrics[p].avg_latency_ms
            )
        )
        
        return available_providers[0]
    
    def _format_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Format messages with optional system prompt"""
        formatted = []
        
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        
        formatted.extend(messages)
        return formatted
    
    def _count_tokens(self, text: Any) -> int:
        """Estimate token count"""
        if isinstance(text, list):
            # List of messages
            text = " ".join([msg.get("content", "") for msg in text])
        
        try:
            return len(self.tokenizer.encode(str(text)))
        except:
            # Fallback: rough estimate (1 token ≈ 4 chars)
            return len(str(text)) // 4
    
    def _calculate_cost(
        self,
        provider: Dict,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate estimated cost"""
        pricing = provider.get("cost_per_1k_tokens", {"prompt": 0, "completion": 0})
        
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]
        
        return prompt_cost + completion_cost
    
    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit"""
        now = datetime.now().timestamp()
        
        if user_id not in self.user_queues:
            self.user_queues[user_id] = deque()
        
        queue = self.user_queues[user_id]
        
        # Remove old requests outside window
        while queue and queue[0] < now - self.rate_limit_window:
            queue.popleft()
        
        # Check limit
        if len(queue) >= self.max_requests_per_window:
            return False
        
        queue.append(now)
        return True
    
    # ========================================================================
    # METRICS & MONITORING
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Dict]:
        """Get performance metrics for all providers"""
        return {
            provider: {
                "status": metrics.status.value,
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": (
                    (metrics.total_requests - metrics.failed_requests) / metrics.total_requests * 100
                    if metrics.total_requests > 0 else 0
                ),
                "total_tokens": metrics.total_tokens,
                "total_cost": round(metrics.total_cost, 4),
                "avg_latency_ms": round(metrics.avg_latency_ms, 2),
                "last_error": metrics.last_error,
                "last_error_time": metrics.last_error_time.isoformat() if metrics.last_error_time else None
            }
            for provider, metrics in self.metrics.items()
        }
    
    async def close(self):
        """Cleanup resources"""
        await self.streaming_client.aclose()
        await self.non_streaming_client.aclose()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

llm_router = EnhancedLLMRouter()
```

---

## CONNECTION MANAGER IMPLEMENTATION

**File:** `backend/services/websocket/connection_manager.py`

```python
"""
WebSocket Connection Manager

Handles:
- Connection pooling per user
- Heartbeat monitoring (ping/pong)
- Multi-tab synchronization
- Graceful disconnection
"""

from typing import Dict, Set
from fastapi import WebSocket
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages all active WebSocket connections"""
    
    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
        # Track heartbeat tasks
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """Register new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        
        # Start heartbeat
        task_key = f"{user_id}_{id(websocket)}"
        task = asyncio.create_task(self._heartbeat(user_id, websocket))
        self._heartbeat_tasks[task_key] = task
        
        logger.info(
            f"User {user_id} connected. "
            f"Active connections: {len(self.active_connections[user_id])}"
        )
        
        # Notify all user's connections
        await self.broadcast_to_user(user_id, {
            "type": "connection_status",
            "status": "connected",
            "active_tabs": len(self.active_connections[user_id])
        })
    
    async def disconnect(self, user_id: str, websocket: WebSocket):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            
            # Remove user entry if no more connections
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Cancel heartbeat
        task_key = f"{user_id}_{id(websocket)}"
        if task_key in self._heartbeat_tasks:
            self._heartbeat_tasks[task_key].cancel()
            del self._heartbeat_tasks[task_key]
        
        logger.info(f"User {user_id} disconnected")
    
    async def _heartbeat(self, user_id: str, websocket: WebSocket):
        """
        Send periodic ping to keep connection alive
        Detects dead connections
        """
        try:
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                await websocket.send_json({"type": "ping"})
        except Exception as e:
            logger.warning(f"Heartbeat failed for {user_id}: {e}")
            await self.disconnect(user_id, websocket)
    
    async def send_to_connection(
        self,
        user_id: str,
        websocket: WebSocket,
        message: dict
    ):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            await self.disconnect(user_id, websocket)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """
        Send message to ALL user's connections
        Useful for multi-tab synchronization
        """
        if user_id not in self.active_connections:
            return
        
        dead_connections = set()
        
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {user_id}: {e}")
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect(user_id, ws)
    
    def get_connection_count(self, user_id: str) -> int:
        """Get number of active connections for user"""
        return len(self.active_connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(conns) for conns in self.active_connections.values())


# Singleton instance
connection_manager = ConnectionManager()
```

---

## IMMEDIATE ACTION PLAN

### Step 1: Fix Empty Response Issue (5 minutes)

Update the prompt in `backend/core/prompts.py`:

```python
def _conversational_prompt(self, query: str = "", history: Optional[List[Dict[str, str]]] = None, allow_markdown: bool = True):
    safe_query = sanitize_text(query, 500)
    hist = ""
    if history:
        hist_lines = []
        for m in history[-3:]:
            role = m.get("role", "user")
            content = sanitize_text(m.get("content", ""), 150)
            hist_lines.append(f"{role}: {content}")
        hist = "\nCONVERSATION_HISTORY:\n" + "\n".join(hist_lines)
    
    persona = PERSONA_ANALYTICAL
    markdown_note = "Use markdown formatting (bold, lists, code blocks) in response_text for better readability" if allow_markdown else "Use plain text only in response_text"
    
    # CRITICAL FIX: Don't show empty string in example format!
    return f"""{SYSTEM_JSON_RULES}
{persona}
{GLOBAL_BEHAVIOR_RULES}

DATASET_CONTEXT:
{self.dataset_context}

{hist}

USER_QUESTION: {safe_query}

INSTRUCTIONS:
1. Analyze the user's question in context of the dataset
2. Provide a detailed, helpful answer in the "response_text" field
3. If a chart would help visualize the answer, include "chart_config" (otherwise null)
4. Set "confidence" to High/Medium/Low based on data quality
5. {markdown_note}

IMPORTANT: The response_text field MUST contain your actual answer. Do NOT leave it empty!

OUTPUT_FORMAT (example with actual content):
{{
  "response_text": "Based on the sales data, the top performing product is iPhone with $2.5M in revenue (45% of total). The trend shows steady growth over Q1-Q3 with a 15% month-over-month increase.",
  "chart_config": {{"type": "bar", "x": "product", "y": "revenue"}} or null,
  "confidence": "High"
}}

Now respond to the user's question:""".strip()
```

### Step 2: Test the Fix

Restart your backend:
```bash
cd /home/vamsi/nothing/datasage/version2/backend
# Kill existing process
pkill -f uvicorn
# Start new process
uvicorn main:app --reload
```

Send a test message from frontend and check if `response_text` is now populated.

### Step 3: Create Connection Manager

Create the file structure and implement connection manager (already shown above).

### Step 4: Implement Enhanced LLM Router

Replace your current `llm_router.py` with the enhanced version (already shown above).

---

## TESTING COMMANDS

```bash
# Check if backend is running
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/datasets/YOUR_DATASET_ID/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "What are the top products?"}'

# Check LLM metrics
curl http://localhost:8000/api/chat/metrics

# Monitor logs
tail -f backend.log | grep -E "response_text|Empty|ERROR"
```

---

## CONCLUSION

Your **immediate critical issue** is the empty `response_text` field caused by poor prompt engineering. The **fix is simple**: don't show an empty string in your example format.

The **long-term solution** is implementing the complete enhancement system with:
- Token streaming
- Multi-provider support
- Connection management
- Rate limiting
- Performance monitoring

**Priority order:**
1. ✅ Fix prompt (5 minutes) - **DO THIS NOW**
2. ✅ Test and verify responses are no longer empty
3. ✅ Install tiktoken dependency
4. ✅ Implement enhanced LLM router
5. ✅ Add connection manager
6. ✅ Update chat router for streaming
7. ✅ Update frontend to handle streaming

**Start with step 1 NOW and report back the results!**
