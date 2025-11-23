# OpenRouter AI Designer - Invalid Blueprint Debugging

## The Problem

Your logs show:
```
2025-11-23 10:23:27 - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2025-11-23 10:24:01 - WARNING - Invalid AI blueprint. Using fallback pattern.
```

**Translation:**
1. ✅ OpenRouter API call succeeds (HTTP 200)
2. ❌ AI returns invalid/unparseable JSON
3. ⚠️ System falls back to hardcoded template (the "Total Revenue" garbage)

## Root Cause

The free model `alibaba/tongyi-deepresearch-30b-a3b:free` is weak at structured JSON output:

### Common Issues with Weak Models:
1. **Markdown wrapping:** Returns ` ```json {...} ``` ` instead of raw JSON
2. **Incomplete JSON:** Stops mid-response due to token limits
3. **Invalid syntax:** Missing commas, quotes, brackets
4. **Extra text:** Adds explanations before/after JSON
5. **Wrong structure:** Doesn't follow the requested schema

### What Happens:
```python
# LLM returns this:
"""
Here's the dashboard design:
```json
{"dashboard": {"components": [...]}}
```
I chose this layout because...
"""

# Parser tries:
json.loads(content)  # ❌ FAILS (not pure JSON)

# Returns error object:
{"error": "llm_json_parse_failed", "raw": "..."}

# AI Designer checks:
if "components" not in blueprint:  # ❌ TRUE (error object has no components)
    return fallback_pattern  # Uses hardcoded template
```

---

## Fixes Applied

### 1. **Enhanced Logging** 
Track exactly what the LLM is returning:

**File: `ai_designer_service.py`**
```python
# Before:
ai_output = await llm_router.call(...)

# After:
ai_output = await llm_router.call(...)
logger.info(f"AI Designer LLM Response: {json.dumps(ai_output, indent=2)[:500]}")
```

**File: `llm_router.py`**
```python
# Before:
except json.JSONDecodeError:
    return {"error": "llm_json_parse_failed", "raw": content[:500]}

# After:
except json.JSONDecodeError as e:
    logger.error(f"JSON parse failed. Raw content (first 500 chars): {content[:500]}")
    logger.error(f"JSON error: {str(e)}")
    return {"error": "llm_json_parse_failed", "raw": content[:500]}
```

### 2. **Improved Prompts**
Make instructions crystal clear for weak models:

**File: `ai_designer_service.py`**
```python
# OLD PROMPT (vague):
"""
TASK:
Return ONLY valid JSON:
{
  "dashboard": {...}
}
"""

# NEW PROMPT (explicit):
"""
CRITICAL INSTRUCTIONS:
1. Return ONLY raw JSON (no markdown, no code blocks, no explanations)
2. Use the EXACT structure from the example blueprint
3. Replace column names with ACTUAL columns from the dataset
4. Start your response with { and end with }
5. Ensure all JSON is valid (proper quotes, commas, brackets)

REQUIRED JSON FORMAT:
{
  "dashboard": {
      "layout_grid": "repeat(4, 1fr)",
      "components": [...]
  },
  "reasoning": "Brief explanation"
}

RESPOND NOW WITH ONLY THE JSON:
"""
```

### 3. **Response Format Enforcement**
Tell OpenRouter to force JSON output:

**File: `llm_router.py`**
```python
payload = {
    "model": settings.OPENROUTER_MODEL,
    "messages": [...],
    "stream": False,
    "response_format": {"type": "json_object"}  # ← NEW: Forces JSON
}
```

**Note:** Not all models support `response_format`. The free model may ignore this.

### 4. **Better System Message**
Reinforce JSON-only responses:

```python
{
    "role": "system", 
    "content": "You are DataSage AI, an expert data assistant. When asked for JSON, return ONLY valid JSON with no markdown formatting, no code blocks, and no additional text."
}
```

---

## Testing & Debugging

### 1. Restart Server
```bash
# Stop current server (Ctrl+C)
cd /home/vamsi/nothing/datasage/version2/backend
uvicorn main:app --reload
```

### 2. Test AI Designer
```bash
curl -X POST "http://localhost:8000/api/ai/0ac6ebf0-1669-42b6-a74f-944add492e31/design-dashboard" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Check Logs
Look for these new log lines:

**✅ Success:**
```
INFO - Successfully parsed JSON from OpenRouter
INFO - AI Designer LLM Response: {"dashboard": {"components": [...]}}
```

**❌ Failure:**
```
ERROR - JSON parse failed. Raw content (first 500 chars): Here's the design: ```json ...
ERROR - JSON error: Expecting value: line 1 column 1 (char 0)
WARNING - Invalid AI blueprint. Blueprint keys: ['error', 'raw']. Using fallback pattern.
```

The logs will now show **exactly** what the LLM is returning so you can see why it's failing.

---

## Solutions Based on What You See

### If Logs Show Markdown Wrapping:
```
Raw content: ```json\n{"dashboard": ...}\n```
```

**Fix:** Add post-processing to strip markdown:
```python
# In llm_router.py, _call_openrouter():
content = msg.get("content", "").strip()

# Strip markdown code blocks
if content.startswith("```"):
    # Extract JSON between ```json and ```
    import re
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
    if match:
        content = match.group(1)
```

### If Logs Show Incomplete JSON:
```
Raw content: {"dashboard": {"components": [{"type": "kpi", "title":
```

**Cause:** Token limit reached mid-response

**Fix:** Increase max tokens in OpenRouter request:
```python
payload = {
    "model": settings.OPENROUTER_MODEL,
    "messages": [...],
    "max_tokens": 2000,  # ← ADD THIS
    "stream": False
}
```

### If Logs Show Wrong Structure:
```
Raw content: {"layout": {...}, "charts": [...]}
```

**Cause:** Model doesn't follow schema despite instructions

**Fix:** Use a better model (see next section)

---

## Better Model Recommendations

The current model `alibaba/tongyi-deepresearch-30b-a3b:free` is **FREE but WEAK** at structured output.

### Upgrade Options:

#### 1. **Better Free Models:**
```python
# config.py
OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct:free"
# or
OPENROUTER_MODEL = "google/gemini-2.0-flash-exp:free"
```

#### 2. **Cheap But Good Models:**
```python
# ~$0.10-0.20 per 1M tokens
OPENROUTER_MODEL = "anthropic/claude-3-haiku"
# or
OPENROUTER_MODEL = "openai/gpt-3.5-turbo"
```

#### 3. **Best Models (Expensive):**
```python
# ~$3-15 per 1M tokens
OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"
# or
OPENROUTER_MODEL = "openai/gpt-4-turbo"
```

**Check pricing:** https://openrouter.ai/models

---

## Fallback Pattern Issue

Even when falling back, you're getting hardcoded "Total Revenue" KPIs because the fallback uses the e-commerce template:

```python
# ai_designer_service.py line 267
return pattern["blueprint"]  # ← Returns executive_kpi_trend pattern
```

This should use the **Intelligent KPI Generator** I built earlier instead!

### Fix Fallback:
```python
# Instead of:
return pattern["blueprint"]

# Do this:
# Generate intelligent KPIs based on actual data
df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
intelligent_kpis = await intelligent_kpi_generator.generate_intelligent_kpis(df, max_kpis=4)

# Build blueprint with intelligent KPIs
fallback_blueprint = {
    "layout_grid": "repeat(4, 1fr)",
    "components": [
        {
            "type": "kpi",
            "title": kpi["title"],
            "span": 1,
            "config": {"column": kpi["column"], "aggregation": kpi["aggregation"]}
        }
        for kpi in intelligent_kpis
    ]
}
return fallback_blueprint
```

---

## Summary

**Current State:**
- ✅ OpenRouter API working (HTTP 200)
- ❌ LLM returning unparseable JSON
- ⚠️ Falling back to hardcoded e-commerce template

**Fixes Applied:**
1. Enhanced logging to see raw LLM responses
2. Clearer prompts with explicit JSON instructions
3. Response format enforcement
4. Better system messages

**Next Steps:**
1. **Restart server** and test again
2. **Check logs** to see what the LLM actually returns
3. **Based on logs:**
   - If markdown wrapping → Add stripping logic
   - If incomplete → Increase max_tokens
   - If wrong structure → Upgrade model
4. **Fix fallback** to use intelligent KPIs instead of hardcoded ones

**Test it and share the new logs so I can see exactly what the LLM is returning!**
