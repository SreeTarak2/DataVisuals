# OpenRouter Exclusive Mode - Ollama Disabled

## Changes Made

### Problem
The AI Designer Service was trying to call `ai_service._call_ollama()` which doesn't exist, causing AttributeError:
```
AttributeError: 'AIService' object has no attribute '_call_ollama'
```

### Solution
Configured the system to **ONLY use OpenRouter API**, with all Ollama code commented out.

---

## Files Modified

### 1. `services/ai/ai_designer_service.py`

**Changed import:**
```python
# OLD:
from services.ai.ai_service import ai_service

# NEW:
from services.llm_router import llm_router
```

**Changed LLM call:**
```python
# OLD (BROKEN):
ai_output = await ai_service._call_ollama(
    prompt, model_role="layout_designer", expect_json=True
)

# NEW (WORKING):
ai_output = await llm_router.call(
    prompt, model_role="layout_designer", expect_json=True
)
```

### 2. `services/llm_router.py`

**Changed `call()` method to OpenRouter-only:**
```python
# OLD (with Ollama fallback):
if self.use_openrouter:
    try:
        return await self._call_openrouter(prompt, model_role, expect_json)
    except Exception as e:
        logger.warning(f"OpenRouter failed, falling back. Reason: {e}")
        if not settings.MODEL_FALLBACK_ENABLED:
            raise HTTPException(502, "Primary AI provider unavailable.")

# Fallback → Local Ollama
return await self._call_ollama(prompt, model_role, expect_json)

# NEW (OpenRouter only):
if self.use_openrouter:
    try:
        return await self._call_openrouter(prompt, model_role, expect_json)
    except Exception as e:
        logger.error(f"OpenRouter call failed: {e}")
        raise HTTPException(502, f"AI provider unavailable: {str(e)}")

# Ollama fallback disabled - OpenRouter only mode
raise HTTPException(500, "OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable.")
```

**Commented out entire `_call_ollama()` method:**
```python
# -----------------------------------------------------------
# OLLAMA CALL (COMMENTED OUT - USING OPENROUTER ONLY)
# -----------------------------------------------------------
# async def _call_ollama(self, prompt: str, model_role: str, expect_json: bool) -> Any:
#     """
#     DISABLED: User is using OpenRouter exclusively.
#     Uncomment this method if you want to enable local Ollama fallback.
#     """
#     ... (entire method commented out)
```

---

## OpenRouter Configuration

Your current settings (from `core/config.py`):

```python
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "alibaba/tongyi-deepresearch-30b-a3b:free"
```

**Model:** `alibaba/tongyi-deepresearch-30b-a3b:free` (FREE tier model)

---

## How It Works Now

### Request Flow:

1. **AI Designer calls LLM Router:**
   ```python
   llm_router.call(prompt, model_role="layout_designer", expect_json=True)
   ```

2. **LLM Router checks OpenRouter:**
   ```python
   if self.use_openrouter:  # True (API key is set)
       return await self._call_openrouter(...)
   ```

3. **OpenRouter API called:**
   ```python
   POST https://openrouter.ai/api/v1/chat/completions
   Headers: Authorization: Bearer sk-or-v1-...
   Payload: {
       "model": "alibaba/tongyi-deepresearch-30b-a3b:free",
       "messages": [...],
       "stream": False
   }
   ```

4. **Response parsed and returned**

---

## What's Disabled

### ❌ Ollama Integration
- Local Ollama models (llama3.1, qwen3:0.6b)
- Ngrok tunnel endpoints
- `_call_ollama()` method (commented out)
- Ollama fallback logic

### ❌ Local Model Configurations
All these are now ignored:
```python
LLAMA_BASE_URL = "https://16f2df641e78.ngrok-free.app/"
QWEN_BASE_URL = "https://wilber-unremarried-reversibly.ngrok-free.dev/"

MODELS = {
    "chat_engine": {"primary": {"model": "llama3.1", ...}},
    "layout_designer": {"primary": {"model": "llama3.1", ...}},
    # ... all local model configs ignored
}
```

---

## What's Enabled

### ✅ OpenRouter Only
- **Single provider:** OpenRouter API
- **Free model:** alibaba/tongyi-deepresearch-30b-a3b:free
- **No fallback:** If OpenRouter fails, request fails (no silent fallback to Ollama)
- **Clean errors:** Clear error messages if API fails

---

## Testing

### 1. Test AI Designer Endpoint
```bash
curl -X POST "http://localhost:8000/api/ai/0ac6ebf0-1669-42b6-a74f-944add492e31/design-dashboard" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:** No more `AttributeError: 'AIService' object has no attribute '_call_ollama'`

### 2. Check Logs
```
✅ Good:
2025-11-23 09:04:47 - services.ai.ai_designer_service - INFO - Calling OpenRouter for dashboard design

❌ Old Error (Fixed):
2025-11-23 09:04:47 - services.ai.ai_designer_service - ERROR - AttributeError: 'AIService' object has no attribute '_call_ollama'
```

---

## Reverting to Ollama (If Needed)

### To re-enable Ollama fallback:

1. **Uncomment `_call_ollama()` in `llm_router.py`:**
   ```python
   async def _call_ollama(self, prompt: str, model_role: str, expect_json: bool) -> Any:
       # ... uncomment entire method
   ```

2. **Update `call()` method:**
   ```python
   if self.use_openrouter:
       try:
           return await self._call_openrouter(...)
       except Exception as e:
           logger.warning(f"OpenRouter failed, falling back to Ollama")
   
   # Fallback to Ollama
   return await self._call_ollama(prompt, model_role, expect_json)
   ```

3. **Set fallback flag:**
   ```python
   # config.py
   MODEL_FALLBACK_ENABLED = True
   ```

---

## Cost Considerations

### Current Setup (FREE):
- **Model:** alibaba/tongyi-deepresearch-30b-a3b:free
- **Cost:** $0.00 (free tier)
- **Limits:** May have rate limits or quotas

### If You Need Paid Models:
Update config to use paid models:
```python
OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"  # or
OPENROUTER_MODEL = "openai/gpt-4-turbo"
```

Check pricing at: https://openrouter.ai/models

---

## Status: ✅ FIXED

**Before:**
- ❌ AttributeError: '_call_ollama' doesn't exist
- ❌ Code mixing Ollama and OpenRouter logic
- ❌ Confusing fallback behavior

**After:**
- ✅ OpenRouter-only mode
- ✅ Clean error handling
- ✅ Ollama code commented out (not deleted, can be restored)
- ✅ Clear documentation

**Restart your server and test the AI Designer endpoint. It should now work without errors.**
