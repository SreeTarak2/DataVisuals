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

Retrieval now uses vector similarity (cosine) via the shared BeliefStore
embedding model, with keyword-overlap fallback when embeddings are unavailable.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

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
        embedding: [float],     # Pre-computed vector (computed at write time)
        created_at: datetime,
        updated_at: datetime,
        relevance_count: int,   # How many times this memory was retrieved
    }

    Retrieval uses pre-computed embeddings (stored alongside each memory)
    for O(1) encoding cost — only the query is embedded at retrieval time.
    Keywords are used as a fallback for memories stored before embeddings
    were added (zero backfill required).
    """

    def __init__(self):
        self._db = None
        self._embedder = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    # -------------------------------------------------------------------
    # EMBEDDING — Shared access to the BeliefStore embedding model
    # -------------------------------------------------------------------

    def _get_embedder(self):
        """
        Lazy-access the shared BeliefStore for its embedding capability.

        Stores a reference to the BeliefStore singleton so that
        ``_compute_vector_similarities`` can call:
        1. ``store.embedding_model.encode()`` for fast batch encoding (preferred)
        2. ``store._embed()`` for per-text embedding with mock fallback

        Returns the BeliefStore instance, or None if unavailable.
        """
        if self._embedder is None:
            try:
                from agents.belief.belief_store import get_belief_store

                store = get_belief_store()
                if store.embedding_model:
                    logger.debug(
                        "[MemoryService] Using shared embedding model for vector retrieval"
                    )
                else:
                    logger.debug(
                        "[MemoryService] Embedding model not loaded — "
                        "will use BeliefStore._embed() mock fallback"
                    )
                self._embedder = store
            except Exception as e:
                logger.warning(
                    f"[MemoryService] Failed to access BeliefStore (non-critical): {e}"
                )
                self._embedder = None
        return self._embedder

    async def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """
        Compute a single embedding vector for a text string.

        Uses the shared BeliefStore model. The result is stored alongside
        the memory in MongoDB so retrieval only needs to embed the query.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector), or None if unavailable.
        """
        store = self._get_embedder()
        if store is None:
            return None

        try:
            if store.embedding_model is not None:
                embeddings = await asyncio.to_thread(
                    store.embedding_model.encode,
                    [text],
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return embeddings[0].tolist()
            else:
                return await store._embed(text)
        except Exception as e:
            logger.warning(f"[MemoryService] Embedding computation failed: {e}")
            return None

    async def _compute_query_similarities(
        self, query: str, memory_embeddings: List[tuple[str, List[float]]]
    ) -> List[float]:
        """
        Compute cosine similarity between a query and stored memory embeddings.

        Unlike ``_compute_vector_similarities`` (which embedded every fact at
        query time), this method uses pre-computed embeddings stored in MongoDB
        — only the query needs to be embedded, making retrieval O(1) for
        encoding vs O(N).

        Args:
            query: The user's query text
            memory_embeddings: List of (fact_id, embedding_vector) tuples

        Returns:
            List of similarity scores in [0, 1], one per memory.
            Returns empty list if the query cannot be embedded.
        """
        store = self._get_embedder()
        if store is None or not memory_embeddings:
            return []

        try:
            # Embed the query only (1 call instead of N+1)
            if store.embedding_model is not None:
                query_vec = await asyncio.to_thread(
                    store.embedding_model.encode,
                    [query],
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                query_emb = query_vec[0]
            else:
                query_emb = await store._embed(query)

            # Dot product against each stored embedding (fast, no model calls)
            similarities = []
            for _fact_id, fact_emb in memory_embeddings:
                dot = sum(q * f for q, f in zip(query_emb, fact_emb))
                similarities.append(max(0.0, float(dot)))

            return similarities

        except Exception as e:
            logger.warning(
                f"[MemoryService] Query similarity computation failed: {e}"
            )
            return []

    # -------------------------------------------------------------------
    # PHASE 1: EXTRACTION — Extract memories from a message pair
    # -------------------------------------------------------------------

    async def extract_and_store(
        self,
        user_query: str,
        ai_response: str,
        user_id: str,
        dataset_id: str,
        conversation_summary: str = "",
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
                max_tokens=500,
            )

            memories = extracted.get("memories", [])
            if not memories:
                logger.debug(
                    "Memory extraction: no salient memories found in this exchange"
                )
                return []

            # Step 2: For each extracted memory, decide ADD or UPDATE
            stored = []
            for mem in memories[:5]:  # Cap at 5 memories per exchange
                fact = mem.get("fact", "").strip()
                category = mem.get("category", "data_insight")

                if not fact or len(fact) < 10:
                    continue

                # Filter out response preambles and artifacts
                import re

                response_artifact_pattern = re.compile(
                    r"^(here'?s|i found|based on|looking at|the data|according to|"
                    r"this means|it appears|you can|i can|let me|a breakdown|"
                    r"the results?|this shows|this tells|this is|what i)",
                    re.IGNORECASE,
                )
                if response_artifact_pattern.match(fact):
                    logger.debug(
                        f"Skipping response preamble as memory: {fact[:50]}"
                    )
                    continue

                # Validate that the fact contains specific data references
                if (
                    not any(char.isdigit() for char in fact)
                    and category == "data_insight"
                ):
                    logger.debug(
                        f"Skipping non-specific memory (no numbers): {fact[:50]}"
                    )
                    continue

                # Validate category
                if category not in MEMORY_CATEGORIES:
                    category = "data_insight"

                result = await self._add_or_update_memory(
                    fact=fact,
                    category=category,
                    source_query=user_query[:200],
                    user_id=user_id,
                    dataset_id=dataset_id,
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
        dataset_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Compare a new memory against existing ones and decide:
        - ADD: No similar memory exists → insert new
        - UPDATE: Similar memory exists → update with richer version
        - NOOP: Exact or near-exact duplicate → skip

        Uses text-based similarity (case-insensitive substring matching)
        for simplicity.
        """
        try:
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
                if (
                    existing_fact in fact_lower
                    and len(fact) > len(existing_mem.get("fact", ""))
                ):
                    # Re-compute embedding for the updated fact
                    embedding = await self._compute_embedding(fact)
                    update_doc = {
                        "fact": fact,
                        "source_query": source_query,
                        "updated_at": datetime.utcnow(),
                    }
                    if embedding is not None:
                        update_doc["embedding"] = embedding

                    await self.db.memories.update_one(
                        {"_id": existing_mem["_id"]},
                        {"$set": update_doc},
                    )
                    logger.debug(
                        f"Memory UPDATE: '{fact[:50]}' replaced older version"
                    )
                    return {"action": "updated", "fact": fact, "category": category}

            # ADD: No similar memory found — pre-compute embedding
            embedding = await self._compute_embedding(fact)
            memory_doc = {
                "user_id": user_id,
                "dataset_id": dataset_id,
                "fact": fact,
                "category": category,
                "source_query": source_query,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "relevance_count": 0,
            }
            if embedding is not None:
                memory_doc["embedding"] = embedding

            result = await self.db.memories.insert_one(memory_doc)
            memory_doc["_id"] = result.inserted_id
            logger.debug(f"Memory ADD: '{fact[:50]}' (category: {category})")
            return {"action": "added", "fact": fact, "category": category}

        except Exception as e:
            logger.warning(f"Memory add/update failed: {e}")
            return None

    # -------------------------------------------------------------------
    # RETRIEVAL — Get relevant memories for a query (VECTOR + KEYWORD)
    # -------------------------------------------------------------------

    async def retrieve_relevant_memories(
        self,
        query: str,
        user_id: str,
        dataset_id: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Retrieve the most relevant memories for a given query.

        Uses vector similarity (cosine) via the shared BeliefStore embedding
        model for semantic matching — "sales trends" will match a memory
        about "revenue grew 15%". Falls back to keyword-overlap scoring
        when embeddings are unavailable (e.g., model not loaded).

        Category boosts are applied on top of the similarity score to
        prioritize data insights and analysis outcomes.

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

            facts = [mem.get("fact", "") for mem in memories]

            # Step 1: Collect memories with pre-computed embeddings
            embedded_memories: List[tuple[int, Dict, List[float]]] = []  # (index, doc, embedding)
            unembedded: List[tuple[int, Dict]] = []  # (index, doc) — fallback to keyword
            for i, mem in enumerate(memories):
                emb = mem.get("embedding")
                if emb and isinstance(emb, list) and len(emb) > 0:
                    embedded_memories.append((i, mem, emb))
                else:
                    unembedded.append((i, mem))

            # Step 2: Score embedded memories via pre-computed vectors (fast)
            use_stored = bool(embedded_memories)
            scored: List[tuple[float, Dict]] = []

            if embedded_memories:
                memory_embeddings = [
                    (str(mem.get("_id", "")), emb)
                    for _, mem, emb in embedded_memories
                ]
                vector_scores = await self._compute_query_similarities(
                    query, memory_embeddings
                )
                if len(vector_scores) == len(embedded_memories):
                    for (i, mem, _emb), score in zip(embedded_memories, vector_scores):
                        category_boost = {
                            "data_insight": 0.15,
                            "analysis_outcome": 0.15,
                            "chart_generated": 0.05,
                            "column_relationship": 0.10,
                            "user_preference": 0.05,
                        }.get(mem.get("category", ""), 0.0)
                        scored.append((score + category_boost, mem))

            # Step 3: Score unembedded memories via keyword fallback
            for i, mem in unembedded:
                fact = mem.get("fact", "")
                query_words = set(query.lower().split())
                fact_words = set(fact.lower().split())
                union = query_words | fact_words
                overlap = len(query_words & fact_words)
                score = overlap / max(len(union), 1)

                category_boost = {
                    "data_insight": 0.15,
                    "analysis_outcome": 0.15,
                    "chart_generated": 0.05,
                    "column_relationship": 0.10,
                    "user_preference": 0.05,
                }.get(mem.get("category", ""), 0.0)
                scored.append((score + category_boost, mem))

            # Step 4: Sort by score descending, apply minimum threshold
            min_score = 0.25 if use_stored else 0.0
            scored.sort(key=lambda x: x[0], reverse=True)
            top_memories = [
                mem["fact"] for score, mem in scored[:top_k] if score >= min_score
            ]

            # Step 3: Update relevance counts for retrieved memories
            if top_memories:
                retrieved_docs = [
                    mem for score, mem in scored[:top_k] if score >= min_score
                ]
                fact_ids = [mem["_id"] for mem in retrieved_docs]
                if fact_ids:
                    await self.db.memories.update_many(
                        {"_id": {"$in": fact_ids}},
                        {"$inc": {"relevance_count": 1}},
                    )

            method = "vector" if use_vector else "keyword"
            if scored and scored[0][0] > 0:
                logger.debug(
                    f"Memory retrieval ({method}): {len(top_memories)} relevant "
                    f"from {len(memories)} total for dataset {dataset_id} "
                    f"(top score: {scored[0][0]:.3f})"
                )
            else:
                logger.debug(
                    f"Memory retrieval ({method}): {len(top_memories)} relevant "
                    f"from {len(memories)} total for dataset {dataset_id}"
                )
            return top_memories

        except Exception as e:
            logger.warning(f"Memory retrieval failed (non-critical): {e}")
            return []

    # -------------------------------------------------------------------
    # UTILITY — Get memory stats for a user+dataset
    # -------------------------------------------------------------------

    async def get_memory_stats(self, user_id: str, dataset_id: str) -> Dict[str, Any]:
        """Get statistics about stored memories."""
        try:
            pipeline = [
                {"$match": {"user_id": user_id, "dataset_id": dataset_id}},
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            ]
            categories = {}
            async for doc in self.db.memories.aggregate(pipeline):
                categories[doc["_id"]] = doc["count"]

            total = sum(categories.values())
            return {
                "total_memories": total,
                "by_category": categories,
                "user_id": user_id,
                "dataset_id": dataset_id,
            }
        except Exception as e:
            logger.warning(f"Memory stats failed: {e}")
            return {"total_memories": 0, "by_category": {}}

    # -------------------------------------------------------------------
    # CLEANUP — Prune old or low-relevance memories
    # -------------------------------------------------------------------

    async def prune_memories(
        self, user_id: str, dataset_id: str, max_memories: int = 100
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
            to_prune = (
                await self.db.memories.find(
                    {"user_id": user_id, "dataset_id": dataset_id}
                )
                .sort([
                    ("relevance_count", 1),  # Least retrieved first
                    ("updated_at", 1),        # Oldest first
                ])
                .limit(count - max_memories)
                .to_list(length=count - max_memories)
            )

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
