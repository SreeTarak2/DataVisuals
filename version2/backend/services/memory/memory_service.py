"""
Memory Service — Mem0-Inspired Memory Extraction & Retrieval
-------------------------------------------------------------
Extracts salient facts from conversation message pairs and stores them
as structured memories in MongoDB, scoped per user+dataset.

Architecture (inspired by Mem0 paper — arxiv 2504.19413v1):
  Phase 1: EXTRACTION — After each response, extract key facts from the
           user query + AI response pair using an LLM.
  Phase 2: UPDATE — Compare extracted memories against existing ones via
           text similarity and decide: ADD / UPDATE / NOOP.

Memory is scoped per (user_id, dataset_id) so insights persist across
conversations about the same dataset.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId

from db.database import get_database
from services.llm_router import llm_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Memory categories for structured extraction
# ---------------------------------------------------------------------------
MEMORY_CATEGORIES = {
    "data_insight": "A factual insight about the data (e.g., 'Revenue peaks in Q4')",
    "user_preference": "A user preference or interest (e.g., 'User prefers bar charts')",
    "chart_generated": "A chart that was generated (e.g., 'Created scatter plot of price vs rating')",
    "analysis_outcome": "A conclusion from analysis (e.g., 'No correlation between age and spending')",
    "column_relationship": "A relationship between columns (e.g., 'Revenue strongly correlates with units_sold')",
}


class MemoryService:
    """
    Manages long-term memory extraction, storage, and retrieval.
    
    Memories are stored in MongoDB `memories` collection with structure:
    {
        user_id: str,
        dataset_id: str,
        fact: str,              # The extracted memory text
        category: str,          # One of MEMORY_CATEGORIES
        source_query: str,      # The user query that produced this memory
        created_at: datetime,
        updated_at: datetime,
        relevance_count: int,   # How many times this memory was retrieved
    }
    """

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    # -------------------------------------------------------------------
    # PHASE 1: EXTRACTION — Extract memories from a message pair
    # -------------------------------------------------------------------

    async def extract_and_store(
        self,
        user_query: str,
        ai_response: str,
        user_id: str,
        dataset_id: str,
        conversation_summary: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Extract salient memories from a (user_query, ai_response) pair
        and store them. This should be called asynchronously after each
        response is saved (fire-and-forget pattern).

        Args:
            user_query: The user's original question
            ai_response: The AI's response
            user_id: User identifier
            dataset_id: Dataset identifier
            conversation_summary: Rolling summary for context

        Returns:
            List of stored memory dicts
        """
        try:
            # Step 1: Extract candidate memories via LLM
            from core.prompt_templates import get_memory_extraction_prompt

            message_pair = (
                f"User: {user_query}\n"
                f"AI Response: {ai_response[:800]}"  # Truncate long responses
            )

            prompt = get_memory_extraction_prompt(message_pair, conversation_summary)

            extracted = await llm_router.call(
                prompt=prompt,
                model_role="memory_extraction",
                expect_json=True,
                temperature=0.2,
                max_tokens=500
            )

            memories = extracted.get("memories", [])
            if not memories:
                logger.debug("Memory extraction: no salient memories found in this exchange")
                return []

            # Step 2: For each extracted memory, decide ADD or UPDATE
            stored = []
            for mem in memories[:5]:  # Cap at 5 memories per exchange
                fact = mem.get("fact", "").strip()
                category = mem.get("category", "data_insight")

                if not fact or len(fact) < 10:
                    continue

                # Validate category
                if category not in MEMORY_CATEGORIES:
                    category = "data_insight"

                result = await self._add_or_update_memory(
                    fact=fact,
                    category=category,
                    source_query=user_query[:200],
                    user_id=user_id,
                    dataset_id=dataset_id
                )
                if result:
                    stored.append(result)

            logger.info(
                f"Memory extraction: {len(stored)} memories stored "
                f"from {len(memories)} candidates for dataset {dataset_id}"
            )
            return stored

        except Exception as e:
            # Memory extraction is non-critical — log and continue
            logger.warning(f"Memory extraction failed (non-critical): {e}")
            return []

    # -------------------------------------------------------------------
    # PHASE 2: UPDATE — ADD / UPDATE / NOOP against existing memories
    # -------------------------------------------------------------------

    async def _add_or_update_memory(
        self,
        fact: str,
        category: str,
        source_query: str,
        user_id: str,
        dataset_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compare a new memory against existing ones and decide:
        - ADD: No similar memory exists → insert new
        - UPDATE: Similar memory exists → update with richer version
        - NOOP: Exact or near-exact duplicate → skip

        Uses text-based similarity (case-insensitive substring matching)
        for simplicity. Can be upgraded to vector similarity later.
        """
        try:
            # Find existing memories for this user+dataset
            existing = await self.db.memories.find(
                {"user_id": user_id, "dataset_id": dataset_id, "category": category}
            ).to_list(length=50)

            fact_lower = fact.lower()

            for existing_mem in existing:
                existing_fact = existing_mem.get("fact", "").lower()

                # NOOP: Near-exact duplicate
                if fact_lower == existing_fact or fact_lower in existing_fact:
                    logger.debug(f"Memory NOOP: '{fact[:50]}' is duplicate")
                    return None

                # UPDATE: Existing memory is a subset of new (richer version)
                if existing_fact in fact_lower and len(fact) > len(existing_mem.get("fact", "")):
                    await self.db.memories.update_one(
                        {"_id": existing_mem["_id"]},
                        {
                            "$set": {
                                "fact": fact,
                                "source_query": source_query,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    logger.debug(f"Memory UPDATE: '{fact[:50]}' replaced older version")
                    return {"action": "updated", "fact": fact, "category": category}

            # ADD: No similar memory found
            memory_doc = {
                "user_id": user_id,
                "dataset_id": dataset_id,
                "fact": fact,
                "category": category,
                "source_query": source_query,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "relevance_count": 0
            }

            result = await self.db.memories.insert_one(memory_doc)
            memory_doc["_id"] = result.inserted_id
            logger.debug(f"Memory ADD: '{fact[:50]}' (category: {category})")
            return {"action": "added", "fact": fact, "category": category}

        except Exception as e:
            logger.warning(f"Memory add/update failed: {e}")
            return None

    # -------------------------------------------------------------------
    # RETRIEVAL — Get relevant memories for a query
    # -------------------------------------------------------------------

    async def retrieve_relevant_memories(
        self,
        query: str,
        user_id: str,
        dataset_id: str,
        top_k: int = 5
    ) -> List[str]:
        """
        Retrieve the most relevant memories for a given query.

        Uses a simple keyword-overlap scoring approach.
        Can be upgraded to vector similarity (FAISS) later.

        Args:
            query: Current user query
            user_id: User identifier
            dataset_id: Dataset identifier
            top_k: Maximum memories to return

        Returns:
            List of memory fact strings, ordered by relevance
        """
        try:
            # Get all memories for this user+dataset
            memories = await self.db.memories.find(
                {"user_id": user_id, "dataset_id": dataset_id}
            ).to_list(length=100)

            if not memories:
                return []

            # Score each memory by keyword overlap with the query
            query_words = set(query.lower().split())
            scored = []
            for mem in memories:
                fact = mem.get("fact", "")
                fact_words = set(fact.lower().split())
                overlap = len(query_words & fact_words)
                # Boost chart-related and insight memories
                category_boost = {
                    "data_insight": 2,
                    "analysis_outcome": 2,
                    "chart_generated": 1,
                    "column_relationship": 1,
                    "user_preference": 1
                }.get(mem.get("category", ""), 0)
                score = overlap + category_boost
                scored.append((score, mem))

            # Sort by score descending, take top_k
            scored.sort(key=lambda x: x[0], reverse=True)
            top_memories = [mem["fact"] for score, mem in scored[:top_k] if score > 0]

            # Update relevance counts for retrieved memories
            if top_memories:
                fact_ids = [mem["_id"] for score, mem in scored[:top_k] if score > 0]
                if fact_ids:
                    await self.db.memories.update_many(
                        {"_id": {"$in": fact_ids}},
                        {"$inc": {"relevance_count": 1}}
                    )

            logger.debug(
                f"Memory retrieval: {len(top_memories)} relevant memories "
                f"from {len(memories)} total for dataset {dataset_id}"
            )
            return top_memories

        except Exception as e:
            logger.warning(f"Memory retrieval failed (non-critical): {e}")
            return []

    # -------------------------------------------------------------------
    # UTILITY — Get memory stats for a user+dataset
    # -------------------------------------------------------------------

    async def get_memory_stats(
        self,
        user_id: str,
        dataset_id: str
    ) -> Dict[str, Any]:
        """Get statistics about stored memories."""
        try:
            pipeline = [
                {"$match": {"user_id": user_id, "dataset_id": dataset_id}},
                {"$group": {
                    "_id": "$category",
                    "count": {"$sum": 1}
                }}
            ]
            categories = {}
            async for doc in self.db.memories.aggregate(pipeline):
                categories[doc["_id"]] = doc["count"]

            total = sum(categories.values())
            return {
                "total_memories": total,
                "by_category": categories,
                "user_id": user_id,
                "dataset_id": dataset_id
            }
        except Exception as e:
            logger.warning(f"Memory stats failed: {e}")
            return {"total_memories": 0, "by_category": {}}

    # -------------------------------------------------------------------
    # CLEANUP — Prune old or low-relevance memories
    # -------------------------------------------------------------------

    async def prune_memories(
        self,
        user_id: str,
        dataset_id: str,
        max_memories: int = 100
    ) -> int:
        """
        Prune least-relevant memories when count exceeds threshold.
        Keeps the most recently updated and most frequently retrieved.
        """
        try:
            count = await self.db.memories.count_documents(
                {"user_id": user_id, "dataset_id": dataset_id}
            )

            if count <= max_memories:
                return 0

            # Find memories to prune: lowest relevance_count, oldest updated_at
            to_prune = await self.db.memories.find(
                {"user_id": user_id, "dataset_id": dataset_id}
            ).sort([
                ("relevance_count", 1),  # Least retrieved first
                ("updated_at", 1)        # Oldest first
            ]).limit(count - max_memories).to_list(length=count - max_memories)

            if to_prune:
                ids_to_delete = [m["_id"] for m in to_prune]
                result = await self.db.memories.delete_many(
                    {"_id": {"$in": ids_to_delete}}
                )
                pruned = result.deleted_count
                logger.info(
                    f"Memory pruning: removed {pruned} memories "
                    f"for user {user_id}, dataset {dataset_id}"
                )
                return pruned

            return 0

        except Exception as e:
            logger.warning(f"Memory pruning failed: {e}")
            return 0


# Singleton instance
memory_service = MemoryService()
