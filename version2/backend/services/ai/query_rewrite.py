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

logger = logging.getLogger(__name__)


REWRITE_SYSTEM_PROMPT = """
You are a STRICT meaning-preserving query rewriter.
Your task is:

1. Rewrite the user's query to be clearer, more explicit,
   and more structured — WITHOUT changing meaning.
2. Preserve EVERY detail, intent, requirement, and constraint.
3. Remove filler words, ambiguity, and vague phrasing.
4. Do NOT:
   - add new information
   - remove anything important
   - reinterpret intent
   - shorten meaning incorrectly
5. Output ONLY the rewritten query, NO explanations.
"""


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
