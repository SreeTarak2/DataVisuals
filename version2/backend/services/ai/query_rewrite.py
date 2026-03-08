"""
Query Rewriter (Meaning-Preserving)
-----------------------------------
Used internally before:
- RAG / FAISS search
- Dashboard generation
- Chart insight generation
- Conversational reasoning

IMPORTANT:
- NEVER shown to end-users.
- MUST preserve meaning strictly.
"""

import logging
from typing import Optional
from services.llm_router import llm_router
from core.prompt_templates import REWRITE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)



def _post_validate(original: str, rewritten: str) -> str:
    """
    Validate rewritten query. If it's empty, too short, or malformed,
    fall back to original user query.
    """
    if not rewritten or rewritten.strip() == "":
        return original

    # If rewritten is drastically shorter → danger: meaning dropped
    if len(rewritten.split()) <= max(3, len(original.split()) // 4):
        logger.warning("Query rewrite too short — reverting to original.")
        return original

    # Rewrite must not be identical to original (failed rewrite)
    if rewritten.strip().lower() == original.strip().lower():
        return original

    # Detect when the LLM ANSWERED the query instead of rewriting it
    # These phrases are hallmarks of conversational responses, not rewrites
    answer_indicators = [
        "i'm here to help", "i am here to help",
        "i don't have", "i do not have",
        "i can help", "let me help",
        "sure!", "of course!", "absolutely!",
        "here's", "here is",
        "based on the", "looking at the",
        "it seems", "it appears",
        "you might want to", "you may want to",
        "to get started", "to begin",
        "unfortunately", "however,",
        "great question", "good question",
    ]
    rewritten_lower = rewritten.strip().lower()
    for indicator in answer_indicators:
        if rewritten_lower.startswith(indicator) or f"\n{indicator}" in rewritten_lower:
            logger.warning(f"Query rewrite looks like an answer ('{indicator}') — reverting to original.")
            return original

    # If rewrite is much longer than original (>3x), LLM likely elaborated/answered
    if len(rewritten.split()) > len(original.split()) * 3:
        logger.warning("Query rewrite suspiciously long — reverting to original.")
        return original

    return rewritten


async def rewrite_query(user_query: str, dataset_context: Optional[str] = None) -> str:
    """
    Rewrite user's query without changing meaning.
    Internal use only.
    """
    if not user_query or user_query.strip() == "":
        return user_query

    prompt = [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": f"User Query:\n{user_query}"}
    ]

    if dataset_context:
        prompt.append({
            "role": "user",
            "content": f"Dataset Context (for understanding only, DO NOT add info):\n{dataset_context}"
        })

    try:
        rewritten = await llm_router.call(
            prompt=prompt,
            model_role="rewrite_engine",
            expect_json=False
        )
    except Exception as e:
        logger.error(f"Rewrite engine failed: {e}")
        return user_query

    if isinstance(rewritten, dict):
        rewritten = rewritten.get("response", user_query)

    validated = _post_validate(user_query, rewritten.strip())
    return validated
