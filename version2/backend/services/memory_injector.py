"""
MemoryInjector — Unified Memory API
====================================

Aggregates the 3 persistent memory types (episodic, semantic, procedural)
into a single ``get_context()`` call so that agents never need to import
individual memory services.

Short-term / working memory (``ContextWindowManager``) is intentionally
excluded — it lives in ``ai_service.py`` and is a single call already.
This avoids circular imports and keeps the injector focused on the three
memory types that were scattered across the codebase.

Before::

    memories = await memory_service.retrieve_relevant_memories(...)
    known_facts = await PassiveBeliefIngestion.get_novelty_context(...)
    instructions = await conversation_learner.format_for_prompt(...)

After::

    ctx = await memory_injector.get_context(
        user_id=user_id,
        dataset_id=dataset_id,
        query=enhanced_query,
        conversation_id=conv_id_str,
    )
    # ctx.memories, ctx.belief_context, ctx.instructions_override
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """
    Structured context that carries all persistent memory signals for one turn.

    Every field has a safe default — callers can always unpack the result
    without ``None``-guards.
    """

    # ── Episodic — past interactions about this dataset ─────────
    memories: List[str] = field(default_factory=list)

    # ── Semantic — facts the user already knows (avoid repetition) ─
    belief_context: List[str] = field(default_factory=list)

    # ── Procedural — learned instructions (how to answer) ──────
    instructions_override: Optional[str] = None


class MemoryInjector:
    """
    Single entry point for episodic, semantic, and procedural memory.

    Usage in a chat pipeline::

        ctx = await memory_injector.get_context(
            user_id=user_id,
            dataset_id=dataset_id,
            query=enhanced_query,
            conversation_id=str(conv["_id"]),
        )
        prompt = factory.get_prompt(
            PromptType.CONVERSATIONAL,
            ...,
            memories=ctx.memories,
            belief_context=ctx.belief_context,
        )
        response = await llm_router.call(
            prompt,
            instructions_override=ctx.instructions_override,
        )

    All three memory types run in sequence (episodic → semantic → procedural)
    so that the semantic query can use the enhanced query from the caller.
    Each is independently guarded — a failure in one does not block the others.
    """

    async def get_context(
        self,
        user_id: str,
        dataset_id: str,
        query: str,
        conversation_id: str,
        *,
        skip_episodic: bool = False,
        skip_semantic: bool = False,
        skip_procedural: bool = False,
    ) -> MemoryContext:
        """
        Gather all available persistent memory signals for the current turn.

        Args:
            user_id: Current user identifier.
            dataset_id: Active dataset identifier.
            query: The user's query (preferably the enhanced/rewritten version
                   so that semantic matching works on the full intent).
            conversation_id: MongoDB conversation ID string.

        Keyword args:
            skip_episodic: Skip episodic memory retrieval.
            skip_semantic: Skip semantic / belief-context retrieval.
            skip_procedural: Skip learned-instruction retrieval.

        Returns:
            A populated ``MemoryContext``.  All fields default to empty/None
            so callers can destructure without guards.
        """
        ctx = MemoryContext()

        # ── 1. Episodic — past interaction memories ────────
        if not skip_episodic and dataset_id:
            try:
                from services.memory.memory_service import memory_service

                ctx.memories = await memory_service.retrieve_relevant_memories(
                    query, user_id, dataset_id
                )
            except Exception as e:
                logger.warning(
                    f"[MemoryInjector] Episodic retrieval failed "
                    f"(non-critical): {e}"
                )

        # ── 2. Semantic — facts the user already knows ─────
        if not skip_semantic:
            try:
                from agents.belief.belief_store import (
                    get_belief_store,
                    PassiveBeliefIngestion,
                )

                belief_store = get_belief_store()
                ctx.belief_context = (
                    await PassiveBeliefIngestion.get_novelty_context(
                        belief_store, user_id, query
                    )
                )
                if ctx.belief_context:
                    logger.info(
                        f"[MemoryInjector] {len(ctx.belief_context)} known facts "
                        f"injected for user {user_id[:12]}... — preventing repetition"
                    )
            except Exception as e:
                logger.warning(
                    f"[MemoryInjector] Semantic retrieval failed "
                    f"(non-critical): {e}"
                )

        # ── 3. Procedural — learned instructions ───────────
        if not skip_procedural and conversation_id:
            try:
                from services.insight_reflection.conversation_learner import (
                    conversation_learner,
                )

                learned = await conversation_learner.format_for_prompt(
                    conversation_id
                )
                if learned:
                    ctx.instructions_override = learned
            except Exception as e:
                logger.warning(
                    f"[MemoryInjector] Procedural retrieval failed "
                    f"(non-critical): {e}"
                )

        return ctx


# Singleton — one import, zero config
memory_injector = MemoryInjector()
