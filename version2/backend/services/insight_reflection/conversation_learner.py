"""
ConversationLearner — Per-Conversation Instruction Memory
==========================================================
Stores learned prompt instructions scoped to a single conversation.

When InsightReflectionAgent.reflect() detects a failure mode (e.g.
"overly_generic", "hallucination"), it returns prompt_adjustments
with an instruction_add string. This service stores those instructions
per conversation so they can be injected into the system prompt on the
next turn.

Architecture:
    Primary: In-memory dict keyed by conversation_id → list of adjustment dicts
    Optional: MongoDB persistence for survival across restarts
    Capped at MAX_INSTRUCTIONS per conversation (oldest evicted).
    Thread-safe via asyncio.Lock.

Each entry stores:
    - instruction: The prompt instruction text
    - temperature_change: Suggested temperature delta (negative = lower temp)
    - add_examples: Whether to include few-shot examples
    - failure_modes: The failure modes that triggered this adjustment

Usage:
    learner = conversation_learner
    await learner.add_adjustment(conv_id, adjustment_dict)
    instructions = await learner.get_instructions(conv_id)  # ["Be specific..."]
    await learner.clear(conv_id)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ConversationLearner:
    """
    Per-conversation store of learned prompt adjustments.

    Instructions are accumulated as the conversation progresses and are
    injected into the system prompt on subsequent turns. The store
    optionally persists to MongoDB so learned instructions survive
    server restarts.

    Limits:
        MAX_INSTRUCTIONS: Maximum instructions kept per conversation
        MAX_INSTRUCTION_LENGTH: Maximum characters per instruction
    """

    MAX_INSTRUCTIONS = 3
    MAX_INSTRUCTION_LENGTH = 200

    def __init__(self):
        self._store: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()
        self._db = None

    @property
    def db(self):
        """Lazy-loaded MongoDB handle."""
        if self._db is None:
            try:
                from db.database import get_database
                self._db = get_database()
            except Exception:
                self._db = None
        return self._db

    async def add_adjustment(
        self,
        conversation_id: str,
        adjustment: Dict[str, Any],
    ) -> None:
        """
        Add a learned adjustment for a conversation.

        Args:
            conversation_id: The conversation to attach this to
            adjustment: Dict with keys:
                - instruction: str (the prompt instruction text)
                - temperature_change: float (temperature delta, default 0.0)
                - add_examples: bool (whether to include examples, default False)
                - failure_modes: list[str] (triggering failure modes)
        """
        instruction = adjustment.get("instruction", "").strip()
        if not instruction:
            return

        # Truncate to length limit
        instruction = instruction[: self.MAX_INSTRUCTION_LENGTH]

        entry = {
            "instruction": instruction,
            "temperature_change": adjustment.get("temperature_change", 0.0),
            "add_examples": adjustment.get("add_examples", False),
            "failure_modes": adjustment.get("failure_modes", []),
            "created_at": datetime.utcnow().isoformat(),
        }

        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []

            # Avoid exact duplicates
            if any(e["instruction"] == instruction for e in self._store[conversation_id]):
                return

            self._store[conversation_id].append(entry)

            # Evict oldest if over cap
            if len(self._store[conversation_id]) > self.MAX_INSTRUCTIONS:
                self._store[conversation_id] = self._store[conversation_id][
                    -self.MAX_INSTRUCTIONS :
                ]

        # Persist to MongoDB (fire-and-forget, non-blocking)
        if self.db is not None:
            try:
                await self.db.conversation_instructions.update_one(
                    {
                        "conversation_id": conversation_id,
                        "instruction": instruction,
                    },
                    {"$set": {**entry, "updated_at": datetime.utcnow().isoformat()}},
                    upsert=True,
                )
            except Exception as e:
                logger.warning(f"[ConversationLearner] MongoDB persist failed: {e}")

        logger.debug(
            f"[ConversationLearner] Added adjustment for conv {conversation_id[:12]}...: "
            f"'{instruction[:60]}...' "
            f"(now {len(self._store[conversation_id])} adjustments)"
        )

    async def add_instruction(self, conversation_id: str, instruction: str) -> None:
        """
        Legacy wrapper — adds a simple instruction-only adjustment.

        Args:
            conversation_id: The conversation to attach this to
            instruction: The prompt instruction text
        """
        await self.add_adjustment(conversation_id, {
            "instruction": instruction,
            "temperature_change": 0.0,
            "add_examples": False,
            "failure_modes": [],
        })

    async def get_adjustments(
        self, conversation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all learned adjustments for a conversation.

        Returns:
            List of adjustment dicts, newest first. Empty list if none.
        """
        async with self._lock:
            instructions = self._store.get(conversation_id, [])
            # Return newest first for recency bias
            return list(reversed(instructions))

    async def get_instructions(
        self, conversation_id: str
    ) -> List[str]:
        """
        Get all learned instruction texts for a conversation.

        Returns:
            List of instruction strings, newest first. Empty list if none.
        """
        adjustments = await self.get_adjustments(conversation_id)
        return [a["instruction"] for a in adjustments]

    async def get_aggregated_temperature(
        self, conversation_id: str
    ) -> float:
        """
        Get the accumulated temperature change for a conversation.

        Returns:
            Sum of all temperature_change values, clamped to [-0.5, 0.0]
        """
        adjustments = await self.get_adjustments(conversation_id)
        total = sum(a.get("temperature_change", 0.0) for a in adjustments)
        return max(-0.5, min(0.0, total))

    async def needs_examples(self, conversation_id: str) -> bool:
        """
        Check if any adjustment requested examples.

        Returns:
            True if any adjustment has add_examples=True
        """
        adjustments = await self.get_adjustments(conversation_id)
        return any(a.get("add_examples", False) for a in adjustments)

    async def has_instructions(self, conversation_id: str) -> bool:
        """Check if a conversation has any learned instructions."""
        async with self._lock:
            return bool(self._store.get(conversation_id))

    async def clear(self, conversation_id: str) -> None:
        """Clear all instructions for a conversation."""
        async with self._lock:
            self._store.pop(conversation_id, None)

        # Also clear from MongoDB
        if self.db is not None:
            try:
                await self.db.conversation_instructions.delete_many(
                    {"conversation_id": conversation_id}
                )
            except Exception as e:
                logger.warning(f"[ConversationLearner] MongoDB clear failed: {e}")

        logger.debug(
            f"[ConversationLearner] Cleared instructions for conv {conversation_id[:12]}..."
        )

    async def format_for_prompt(
        self,
        conversation_id: str,
        domain_adjustments_block: str = "",
    ) -> str:
        """
        Format learned instructions as a block for system prompt injection.

        Args:
            conversation_id: The conversation ID
            domain_adjustments_block: Optional domain-level adjustments to append

        Returns:
            Empty string if no instructions, otherwise a formatted block like:
            "LEARNED QUALITY IMPROVEMENTS (apply these to your response):

            • Be specific — cite exact columns and values.
            • Include time-based context when discussing trends.

            DOMAIN-SPECIFIC QUALITY IMPROVEMENTS (ecommerce):
            • Frame findings in business terms: what decision does this inform?"
        """
        adjustments = await self.get_adjustments(conversation_id)
        if not adjustments and not domain_adjustments_block:
            return ""

        lines = []
        if adjustments:
            lines.append(
                "LEARNED QUALITY IMPROVEMENTS (apply these to your response):"
            )
            for adj in adjustments:
                instruction = adj.get("instruction", "")
                if instruction:
                    lines.append(f"• {instruction}")

        if domain_adjustments_block:
            if lines:
                lines.append("")
            lines.append(domain_adjustments_block)

        return "\n".join(lines)


# Singleton instance
conversation_learner = ConversationLearner()
