# TODO: REMOVE after Phase 9 — re-export shim
from prompts.token_budget import (  # noqa: F401
    count_tokens, PromptBudget, safe_inject_context,
    check_prompt_fits_model, trim_to_token_limit,
    MODEL_CONTEXT_WINDOWS, COMPLETION_RESERVES, CONTEXT_MAX_TOKENS,
)
