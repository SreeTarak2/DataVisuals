# Token Budgeting & Model Routing Implementation

## Overview

This implementation prevents silent truncation and malformed JSON outputs by ensuring prompts never exceed the model's context window. It uses a three-phase strategy: **measure → guard → route**.

---

## Architecture

### Phase 1: MEASURE (Startup)

At app startup, `init_token_budgets()` runs and measures the baseline size of every prompt template **without any injected context**. This lets you see the mandatory cost before any business logic runs.

```python
# services/prompts/measure_templates.py
init_token_budgets()   # Logs baselines like:
# [template_baseline] sql_generator:    1,847 tokens (+1500 reserve = 3,347 min window) ✅ OK
# [template_baseline] chart_engine:     2,103 tokens (+1200 reserve = 3,303 min window) ✅ OK
```

**Output:**
- `TEMPLATE_BASELINES` dict: template size + completion reserve per role
- Warnings if any template is already too large for fallback models
- Helps identify which prompts are the bloat culprits

### Phase 2: GUARD (Before Model Selection)

When constructing a prompt, trim its context to fit within the model's window **before** selecting which model to use.

```python
# services/prompts/token_budget.py
safe_context, budget = safe_inject_context(
    template=prompt_template,
    context=large_schema_or_history,
    role="sql_generator",
    model="deepseek_v3",
)

# budget tells you:
# - template_tokens: 1847
# - context_tokens: 1203 (after trimming if needed)
# - total_input_tokens: 3050
# - remaining_for_completion: 124950
# - is_safe: True
```

If context doesn't fit, it's trimmed from the **end** (preserving schema headers at the top) and a warning is logged.

### Phase 3: ROUTE (Model Selection)

When building the full prompt, select a model that can safely fit it. The router skips models that would produce truncated completions.

```python
# services/llm/router.py
def _prompt_fits_model(self, prompt: str, model_key: str, model_role: str) -> bool:
    # Checks: prompt_tokens + completion_reserve <= model_limit
    # Logs why a model is skipped if unsafe
    # Returns bool
```

In fallback flow:
```python
for fallback_model_key in fallback_models:
    if not self._prompt_fits_model(prompt, fallback_model_key, model_role):
        logger.warning(f"Skipping '{fallback_model_key}' — prompt too large")
        continue  # Try next fallback
    # Safe to use this model
    return await self._call_openrouter(prompt, model=fallback_model_key)
```

---

## Core Concepts

### 1. Token Budgets by Role

Each role has two budgets:

- **Completion Reserve**: minimum tokens needed for a valid output
  - SQL generation: 1500 (full query + CTEs)
  - Chart engine: 1200 (JSON array)
  - Chat streaming: 2000 (multi-turn response)

- **Context Max**: maximum tokens we'll inject for a role
  - SQL: 2000 (schema + stats)
  - Chart: 3000 (dataset context + examples)

```python
# services/prompts/token_budget.py
COMPLETION_RESERVES = {
    "sql_generator": 1_500,
    "chart_engine": 1_200,
    "chart_explanation": 600,
    "insight_generator": 1_500,
    "chat_streaming": 2_000,
}

CONTEXT_MAX_TOKENS = {
    "sql_generator": 2_000,
    "chart_engine": 3_000,
    "insight_generator": 2_000,
    "chat_streaming": 2_500,
}
```

### 2. Model Context Windows

```python
MODEL_CONTEXT_WINDOWS = {
    "deepseek_v3": 128_000,           # Primary for heavy prompts
    "gemini_flash_intent": 32_000,
    "mistral_small_32_24b": 32_000,
    "stepfun_flash": 8_192,           # Small fallback — needs guarding
    "gpt4o_mini": 128_000,
    "claude_3_5_sonnet": 200_000,
}
```

### 3. PromptBudget Class

Tracks token usage across a prompt and provides safety checks:

```python
@dataclass
class PromptBudget:
    role: str
    template_tokens: int
    context_tokens: int
    completion_reserve: int
    model_limit: int

    @property
    def is_safe(self) -> bool:
        # remaining >= completion_reserve?
        return self.remaining_for_completion >= self.completion_reserve

    @property
    def utilization_pct(self) -> float:
        # What % of window are we using?
        return (self.total_input_tokens / self.model_limit) * 100
```

---

## Usage Patterns

### Pattern 1: Simple Check

```python
from services.prompts.token_budget import check_prompt_fits_model

fits, message = check_prompt_fits_model(
    prompt=full_prompt,
    role="sql_generator",
    model="stepfun_flash",
    require_safe=True,
)

if not fits:
    logger.warning(f"Unsafe prompt: {message}")
```

### Pattern 2: Context Trimming Before Selection

```python
from services.prompts.token_budget import safe_inject_context
from services.prompts.prompt_templates import PromptRegistry

# Get empty template to measure it
template = PromptRegistry.get_sql_generation_prompt(
    column_schema="", sample_data="", data_stats="",
    user_query=query, allowed_columns=cols,
    include_context=False,
)

# Trim context before selecting model
safe_context, budget = safe_inject_context(
    template=template,
    context=raw_schema_and_data,
    role="sql_generator",
    model="deepseek_v3",
)

# If safe_context was trimmed, you'll see warnings in logs
# budget.is_safe tells you if we're good for fallbacks too
```

### Pattern 3: Schema Scoping

Reduce schema size by sending only relevant columns:

```python
from services.prompts.schema_scoper import scope_schema_to_query

# Only include columns mentioned in the user's query
scoped_schema = scope_schema_to_query(
    schema_text=full_schema,
    user_query=user_question,
    top_k=15,  # Max 15 columns
)
# Estimated ~40-50% reduction for wide datasets
```

---

## Integration Points

### 1. App Startup

In `main.py`:
```python
from services.prompts.measure_templates import init_token_budgets

@app.on_event("startup")
async def startup_event():
    # ... existing setup ...
    init_token_budgets()  # Measure templates, log warnings
```

### 2. LLM Router

Router already does fallback filtering via `_prompt_fits_model()`, which now has enhanced logging:

```python
# In router.py fallback chain
for fallback_model in fallback_chain:
    if not self._prompt_fits_model(prompt, fallback_model, role):
        # Skips this model — logs why
        continue
    # Safe to use
    return await call_llm(prompt, model=fallback_model)
```

### 3. Query Executor (SQL Generation)

Example integration:

```python
# In services/query/executor.py
from services.prompts.token_budget import safe_inject_context
from services.prompts.schema_scoper import scope_schema_to_query

async def generate_sql(...):
    # 1. Scope schema to relevant columns
    scoped_schema = scope_schema_to_query(
        full_schema, user_query, top_k=15
    )
    
    # 2. Get template and measure it
    template = get_sql_generation_prompt(
        column_schema="", sample_data="", ...
        include_context=False,
    )
    
    # 3. Trim context if needed
    safe_context, budget = safe_inject_context(
        template=template,
        context=scoped_schema,
        role="sql_generator",
        model="deepseek_v3",
    )
    
    # 4. Build full prompt
    full_prompt = get_sql_generation_prompt(
        column_schema=safe_context,
        ...
    )
    
    # 5. Router handles model selection
    response = await llm_router.call(
        prompt=full_prompt,
        model_role="sql_generator",
    )
```

---

## Quick Wins Already Applied

These reductions are immediate and safe (no quality loss):

| Prompt Section | Tokens Saved | Impact |
|---|---|---|
| COMMON QUERY PATTERNS (condensed) | ~200 | Generic examples still present |
| INTEGER YEAR HANDLING (deduplicated) | ~100 | Removed verbose variant |
| BMW-specific examples (trimmed) | ~150+ | Generic case-insensitive matching works just as well |

**Total immediate savings: ~400–500 tokens per SQL call**

---

## Logging Output

You'll see messages like:

```
[template_baseline] sql_generator: 1,847 tokens (+1500 reserve = 3,347 min window) ✅ OK
[token_budget] 'sql_generator/context' trimmed: 2,847 → 2,000 tokens (847 tokens dropped)
[router] Model 'stepfun_flash' fits role 'sql_generator': 2,891 + 1500 = 4,391 / 8,192
[router] Skipping 'stepfun_flash' for 'chart_engine': prompt 3,847T + reserve 1,200T = 5,047T exceeds window 8,192T
[executor] SQL prompt budget: template=1847, context=1203, remaining=125153, safe=True
```

---

## Testing & Validation

### 1. Measure Baseline

```bash
# Start the app and check logs
backend$ python -m uvicorn main:app --reload
# Look for [template_baseline] messages
```

### 2. Check a Heavy Query

```python
# Send a query with a wide dataset (40+ columns, 100+ rows sample)
# Watch logs for:
# - [token_budget] ... context trimmed
# - [router] Skipping models
# - [router] Model XYZ fits
```

### 3. Verify Outputs

Check that:
- SQL queries are still valid (not truncated)
- Chart JSON still parses
- No "Binder Error" or truncation signs in logs

---

## Future Enhancements

1. **Dynamic Completion Reserve Estimation**: Measure actual output sizes instead of hardcoding
2. **Embedding-based Schema Scoping**: Use vector DB for semantic column relevance (currently substring matching)
3. **Prompt Compression**: Summarize long contexts into synthetic distillations before injection
4. **Fallback-Specific Prompt Variants**: Use simpler prompts for 8k models vs. 128k models

---

## Configuration Checklist

- [x] `MODEL_CONTEXT_WINDOWS` updated with all available models
- [x] `COMPLETION_RESERVES` set per role based on expected output sizes
- [x] `CONTEXT_MAX_TOKENS` limits applied per role
- [x] Template baseline measurement runs at startup
- [x] Router uses `_prompt_fits_model` for fallback selection
- [x] Prompt templates trimmed to remove bloat (COMMON QUERY PATTERNS, BMW examples, etc.)
- [x] (Optional) Schema scoping integrated into query executor

---

## Troubleshooting

**Q: "No model in fallback chain can safely handle prompt" error**

A: Your prompt + completion reserve exceeds all available models. Options:
1. Use `scope_schema_to_query()` to reduce schema size
2. Trim data samples passed to prompt (`safe_inject_context` does this)
3. Switch to a larger primary model (Claude 3.5, GPT-4)

**Q: Logs show "Skipping 'stepfun_flash'" repeatedly**

A: Fallback is correctly detecting it can't fit. This is working as designed. Move it lower in fallback chain or check if context can be trimmed.

**Q: No `[template_baseline]` messages at startup**

A: Check that `init_token_budgets()` was called in `main.py` and that import paths are correct.

---

## References

- Token counting: `services/prompts/token_budget.py::count_tokens()`
- Context trimming: `services/prompts/token_budget.py::trim_to_token_limit()`
- Safe injection: `services/prompts/token_budget.py::safe_inject_context()`
- Router integration: `services/llm/router.py::_prompt_fits_model()`
- Schema scoping: `services/prompts/schema_scoper.py`
