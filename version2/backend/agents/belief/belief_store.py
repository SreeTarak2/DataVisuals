# backend/services/agents/belief_store.py

"""
Belief Store: User Knowledge Persistence
========================================
ChromaDB-based vector store for maintaining user's prior knowledge.

This enables Subjective Novelty Detection by:
1. Storing confirmed insights as embeddings
2. Retrieving similar beliefs when new insights are generated
3. Computing Semantic Surprisal (1 - max similarity)

The Belief Store is partitioned by user_id for multi-tenancy.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import uuid
import json

# MongoDB collection for Bayesian priors
_BAYESIAN_PRIORS_COLLECTION = "bayesian_priors"

logger = logging.getLogger(__name__)

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidArgumentError

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    InvalidArgumentError = Exception
    logger.warning("ChromaDB not installed. Run: pip install chromadb")

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")


class BeliefStore:
    """
    Manages user beliefs for Subjective Novelty Detection.

    Each user has their own collection of beliefs (prior knowledge).
    When a new insight is generated, we compute its similarity to
    existing beliefs to determine if it's truly novel.

    Belief Schema:
    {
        "id": "belief_uuid",
        "document": "Natural language belief statement",
        "embedding": [1024-dim vector],
        "metadata": {
            "user_id": "user_123",
            "dataset_id": "dataset_456",  # Optional
            "source": "user_confirmed" | "auto_generated" | "document_ingested",
            "confidence": 0.95,
            "created_at": "2026-01-12T10:00:00Z",
            "decay_rate": 0.01  # Confidence decay per day
        }
    }
    """

    # Collection name prefix for multi-tenancy
    COLLECTION_PREFIX = "beliefs_"

    def __init__(self, persist_directory: str = "./chroma_db", embedding_model: str = None):
        """
        Initialize the Belief Store.

        Args:
            persist_directory: Where to store ChromaDB data
            embedding_model: HuggingFace model name for embeddings
                             (defaults to Settings.EMBEDDING_MODEL from config)
        """
        self.persist_directory = persist_directory

        # Use the same embedding model as the RAG pipeline (from config.py)
        if embedding_model is None:
            try:
                from core.config import settings

                embedding_model = settings.EMBEDDING_MODEL
            except Exception:
                embedding_model = "BAAI/bge-large-en-v1.5"
        self.embedding_model_name = embedding_model

        # Initialize ChromaDB
        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            logger.info(f"ChromaDB initialized at {persist_directory}")
        else:
            self.client = None
            logger.warning("ChromaDB not available - Belief Store disabled")

        # Initialize embedding model (lazy — loaded on first use)
        self.embedding_model = None
        if not EMBEDDINGS_AVAILABLE:
            logger.warning("Embeddings not available - using mock embeddings")

    def _ensure_embedding_model(self):
        if self.embedding_model is not None:
            return
        if not EMBEDDINGS_AVAILABLE:
            return
        try:
            import os

            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Loaded embedding model: {self.embedding_model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.embedding_model = None

    def _get_collection(self, user_id: str):
        """Get or create a collection for a specific user."""
        if not self.client:
            return None

        collection_name = f"{self.COLLECTION_PREFIX}{user_id}"

        # ChromaDB collection names have restrictions
        # Replace invalid characters
        collection_name = collection_name.replace("-", "_")[:63]

        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": f"Belief store for user {user_id}"},
        )

    def _handle_dimension_mismatch(self, user_id: str, error: Exception) -> bool:
        """
        Recover from old Chroma collections created with a different embedding size.
        Returns True when a collection reset was attempted successfully.
        """
        message = str(error)
        if "expecting embedding with dimension" not in message:
            return False

        collection_name = f"{self.COLLECTION_PREFIX}{user_id}".replace("-", "_")[:63]
        logger.warning(
            "Belief store embedding dimension mismatch for user %s. "
            "Resetting collection '%s' to match current model '%s'. Error: %s",
            user_id,
            collection_name,
            self.embedding_model_name,
            message,
        )
        try:
            self.client.delete_collection(collection_name)
        except Exception as delete_error:
            logger.error(
                "Failed to reset mismatched belief collection %s: %s",
                collection_name,
                delete_error,
            )
            return False
        return True

    async def _embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        self._ensure_embedding_model()
        if self.embedding_model:
            import asyncio

            embedding = await asyncio.to_thread(
                self.embedding_model.encode,
                text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.tolist()
        else:
            # Mock embedding for testing (1024-dim vector to match BAAI/bge-large-en-v1.5)
            import hashlib
            import numpy as np

            # Deterministic "embedding" based on text hash
            hash_bytes = hashlib.sha256(text.encode()).digest()
            np.random.seed(int.from_bytes(hash_bytes[:4], "big"))
            return np.random.randn(1024).tolist()

    async def add_belief(
        self,
        user_id: str,
        belief_text: str,
        source: str = "user_confirmed",
        dataset_id: str = None,
        confidence: float = 0.95,
    ) -> str:
        """
        Add a new belief to the user's store.

        Args:
            user_id: User identifier
            belief_text: Natural language statement of the belief
            source: How this belief was acquired
            dataset_id: Optional dataset this belief relates to
            confidence: Initial confidence (0-1)

        Returns:
            belief_id: Unique identifier for the belief
        """
        collection = self._get_collection(user_id)
        if not collection:
            logger.warning("Belief Store unavailable - skipping add")
            return None

        belief_id = str(uuid.uuid4())
        embedding = await self._embed(belief_text)

        metadata = {
            "user_id": user_id,
            "source": source,
            "confidence": confidence,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "decay_rate": 0.01,  # 1% per day
        }

        if dataset_id:
            metadata["dataset_id"] = dataset_id

        try:
            collection.add(
                ids=[belief_id],
                embeddings=[embedding],
                documents=[belief_text],
                metadatas=[metadata],
            )
        except InvalidArgumentError as error:
            if self._handle_dimension_mismatch(user_id, error):
                collection = self._get_collection(user_id)
                if collection is None:
                    logger.warning("Belief Store unavailable after collection reset - skipping add")
                    return None
                collection.add(
                    ids=[belief_id],
                    embeddings=[embedding],
                    documents=[belief_text],
                    metadatas=[metadata],
                )
            else:
                raise

        logger.info(f"Added belief {belief_id} for user {user_id}: {belief_text[:50]}...")
        return belief_id

    async def query_similar_beliefs(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
        min_confidence: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Find beliefs similar to the query text.

        Args:
            user_id: User identifier
            query_text: Text to compare against beliefs
            n_results: Maximum number of results
            min_confidence: Minimum confidence threshold

        Returns:
            List of similar beliefs with similarity scores
        """
        collection = self._get_collection(user_id)
        if not collection:
            return []

        # Check if collection has any documents
        if collection.count() == 0:
            return []

        query_embedding = await self._embed(query_text)

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except InvalidArgumentError as error:
            if self._handle_dimension_mismatch(user_id, error):
                return []
            raise

        beliefs = []
        beliefs_to_persist = []  # FIX §7: track beliefs needing decay write-back
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]

            # Apply confidence decay
            stored_confidence = metadata.get("confidence", 1.0)
            confidence = self._apply_decay(
                stored_confidence,
                metadata.get("created_at"),
                metadata.get("decay_rate", 0.01),
            )

            if confidence >= min_confidence:
                # Convert distance to similarity (ChromaDB uses L2 by default)
                # For normalized vectors, L2 distance relates to cosine: d = sqrt(2 - 2*cos)
                # So cos = 1 - d²/2
                similarity = max(0, 1 - (distance**2) / 2)

                # FIX §7: If decay has meaningfully changed the confidence,
                # schedule it for write-back to ChromaDB metadata.
                if abs(confidence - stored_confidence) > 0.05:
                    beliefs_to_persist.append((results["ids"][0][i], confidence))

                beliefs.append(
                    {
                        "id": results["ids"][0][i],
                        "document": doc,
                        "similarity": similarity,
                        "confidence": confidence,
                        "metadata": metadata,
                    }
                )

        # FIX §7: Persist decayed confidence back to ChromaDB metadata.
        # CRITICAL: Must merge into full metadata — ChromaDB update() replaces
        # the ENTIRE metadata object, not just the confidence field.
        # Writing {"confidence": X} alone would wipe user_id, source, created_at,
        # decay_rate, dataset_id — breaking decay computations and promotions.
        if beliefs_to_persist:
            try:
                # Build a lookup of full metadata by belief ID
                meta_by_id = {b["id"]: b["metadata"] for b in beliefs if "id" in b}
                for belief_id, decayed_conf in beliefs_to_persist:
                    full_meta = dict(meta_by_id.get(belief_id, {}))
                    full_meta["confidence"] = decayed_conf
                    collection.update(
                        ids=[belief_id],
                        metadatas=[full_meta],
                    )
                logger.debug(f"Persisted decayed confidence for {len(beliefs_to_persist)} beliefs")
            except Exception as e:
                logger.warning(f"Failed to persist decayed confidence (non-critical): {e}")

        # Sort by similarity descending
        beliefs.sort(key=lambda x: x["similarity"], reverse=True)

        return beliefs

    def _apply_decay(self, initial_confidence: float, created_at: str, decay_rate: float) -> float:
        """Apply temporal decay to confidence."""
        if not created_at:
            return initial_confidence

        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            days_elapsed = (now - created.replace(tzinfo=None)).days

            # Exponential decay: c(t) = c0 * e^(-λt)
            import math

            decayed = initial_confidence * math.exp(-decay_rate * days_elapsed)
            return max(0.3, decayed)  # Floor at 0.3 (paper §V.C)
        except Exception:
            return initial_confidence

    async def calculate_semantic_surprisal(
        self, user_id: str, insight_text: str
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate Semantic Surprisal for an insight.

        S_sem(f | B) = 1 - max_{b ∈ B} cos(φ(f), φ(b))

        Args:
            user_id: User identifier
            insight_text: The new insight to evaluate

        Returns:
            (surprisal_score, similar_beliefs)
            - surprisal_score: 0.0 (identical to known) to 1.0 (completely novel)
            - similar_beliefs: List of retrieved similar beliefs
        """
        similar = await self.query_similar_beliefs(user_id, insight_text, n_results=5)

        if not similar:
            # No beliefs = everything is novel
            return 1.0, []

        max_similarity = max(b["similarity"] for b in similar)
        surprisal = 1.0 - max_similarity

        return surprisal, similar

    async def mark_as_known(self, user_id: str, insight_text: str, dataset_id: str = None) -> str:
        """
        Mark an insight as "already known" by the user.

        This is called when user clicks "I already knew this" button.
        Adds the insight to the Belief Store with high confidence.

        Args:
            user_id: User identifier
            insight_text: The insight text
            dataset_id: Optional dataset reference

        Returns:
            belief_id of the created belief
        """
        return await self.add_belief(
            user_id=user_id,
            belief_text=insight_text,
            source="user_dismissed",
            dataset_id=dataset_id,
            confidence=0.95,  # Paper §V.B: explicit confirmation c₀ = 0.95
        )

    async def accept_insight(self, user_id: str, insight_text: str, dataset_id: str = None) -> str:
        """
        Accept an insight as useful (thumbs up).

        Adds to Belief Store with moderate confidence.

        Args:
            user_id: User identifier
            insight_text: The insight text
            dataset_id: Optional dataset reference

        Returns:
            belief_id of the created belief
        """
        return await self.add_belief(
            user_id=user_id,
            belief_text=insight_text,
            source="user_accepted",
            dataset_id=dataset_id,
            confidence=0.7,  # Moderate - user found it useful
        )

    async def get_belief_count(self, user_id: str) -> int:
        """Get the number of beliefs for a user."""
        collection = self._get_collection(user_id)
        if not collection:
            return 0
        return collection.count()

    async def delete_belief(self, user_id: str, belief_id: str) -> bool:
        """Delete a specific belief."""
        collection = self._get_collection(user_id)
        if not collection:
            return False

        try:
            collection.delete(ids=[belief_id])
            logger.info(f"Deleted belief {belief_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete belief: {e}")
            return False

    async def clear_user_beliefs(self, user_id: str) -> bool:
        """Clear all beliefs for a user (use with caution!)."""
        if not self.client:
            return False

        collection_name = f"{self.COLLECTION_PREFIX}{user_id}".replace("-", "_")[:63]

        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Cleared all beliefs for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear beliefs: {e}")
            return False

    @staticmethod
    def update_alpha(
        current_alpha: float,
        was_rejected: bool,
        had_high_bayesian: bool,
        beta: float = 0.9,
    ) -> float:
        """
        Adaptive α update via EMA (Paper Eq. 8).

        α_{t+1} = β·α_t + (1-β)·α̂_t

        where α̂_t = 1 when the rejected insight had high Bayesian
        surprise (meaning α should rise to weight semantics more),
        and 0 otherwise.

        Args:
            current_alpha: Current α weight
            was_rejected: User marked insight as "I already knew this"
            had_high_bayesian: Bayesian surprise was above 0.5
            beta: Smoothing factor (default 0.9 per paper)

        Returns:
            Updated α, clipped to [0.3, 0.9] for stability
        """
        if not was_rejected:
            return current_alpha

        # If user rejected despite high Bayesian → semantics missed it → raise α
        alpha_hat = 1.0 if had_high_bayesian else 0.0
        new_alpha = beta * current_alpha + (1 - beta) * alpha_hat

        # Clip to prevent extreme values
        return max(0.3, min(0.9, new_alpha))

    async def ingest_document(
        self, user_id: str, document_text: str, chunk_size: int = 500, overlap: int = 50
    ) -> List[str]:
        """
        Ingest a document as prior knowledge.

        Splits document into chunks and adds each as a belief.

        Args:
            user_id: User identifier
            document_text: Full document text
            chunk_size: Characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of belief_ids created
        """
        # Simple chunking (could use more sophisticated methods)
        chunks = []
        start = 0
        while start < len(document_text):
            end = start + chunk_size
            chunk = document_text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap

        belief_ids = []
        for chunk in chunks:
            belief_id = await self.add_belief(
                user_id=user_id,
                belief_text=chunk,
                source="document_ingested",
                confidence=0.80,  # Paper §V.B: document ingestion c₀ = 0.80
            )
            if belief_id:
                belief_ids.append(belief_id)

        logger.info(f"Ingested document into {len(belief_ids)} beliefs for user {user_id}")
        return belief_ids

    async def decay_all_collections(self) -> int:
        """
        Apply temporal confidence decay to ALL beliefs across ALL users.

        Iterates every ChromaDB collection managed by this BeliefStore,
        computes the decayed confidence for each belief using the same
        _apply_decay() formula as query_similar_beliefs(), and writes
        back the updated confidence to ChromaDB metadata.

        This is called by the scheduled belief_decay_task background
        worker (services/maintenance/belief_decay_task.py). Without
        it, beliefs about topics users never revisit stay at their
        initial confidence forever.

        Returns:
            Total number of beliefs whose confidence was updated.
        """
        if not self.client:
            logger.warning("[Decay] ChromaDB client unavailable — skipping decay pass")
            return 0

        total_updated = 0
        try:
            # List all ChromaDB collections, filter to our managed ones
            all_collections = self.client.list_collections()
            belief_collections = [
                c for c in all_collections if c.name.startswith(self.COLLECTION_PREFIX)
            ]

            if not belief_collections:
                logger.debug("[Decay] No belief collections found — nothing to decay")
                return 0

            logger.info(f"[Decay] Running decay pass on {len(belief_collections)} collections")

            for collection in belief_collections:
                try:
                    col_name = collection.name
                    count = collection.count()
                    if count == 0:
                        continue

                    # Get all documents with full metadata
                    all_data = collection.get(
                        include=["metadatas", "documents"],
                    )

                    ids = all_data.get("ids", [])
                    metadatas = all_data.get("metadatas", [])
                    if not ids:
                        continue

                    updated_in_collection = 0
                    for i in range(len(ids)):
                        meta = metadatas[i] if i < len(metadatas) else {}
                        stored_confidence = meta.get("confidence", 1.0)
                        created_at = meta.get("created_at")
                        decay_rate = meta.get("decay_rate", 0.01)

                        decayed = self._apply_decay(stored_confidence, created_at, decay_rate)

                        # Only write back if decay meaningfully changed the value
                        if abs(decayed - stored_confidence) > 0.01:
                            updated_meta = dict(meta)
                            updated_meta["confidence"] = decayed
                            try:
                                collection.update(
                                    ids=[ids[i]],
                                    metadatas=[updated_meta],
                                )
                                updated_in_collection += 1
                            except Exception as update_err:
                                logger.debug(
                                    f"[Decay] Failed to update belief {ids[i][:12]}…: {update_err}"
                                )

                    if updated_in_collection > 0:
                        logger.debug(
                            f"[Decay] Decayed {updated_in_collection}/{count} beliefs "
                            f"in collection {col_name[:40]}…"
                        )
                        total_updated += updated_in_collection

                except Exception as col_err:
                    logger.warning(
                        f"[Decay] Failed to process collection {getattr(collection, 'name', 'unknown')}: {col_err}"
                    )
                    continue

        except Exception as e:
            logger.error(f"[Decay] Decay pass failed: {e}")

        return total_updated


# ============================================================
# BAYESIAN SURPRISE TRACKER
# ============================================================


class BayesianTracker:
    """
    Tracks probabilistic distributions for key metrics.

    Computes Bayesian Surprise when new data is observed:
    S_bayes = D_KL(P(θ|D) || P(θ))

    For Gaussian distributions (most business metrics):
    S = 0.5 * [σ0²/σ1² + (μ1-μ0)²/σ1² - 1 + ln(σ1²/σ0²)]
    """

    def __init__(self):
        """Initialize the tracker."""
        # Store priors as {metric_name: {"mean": μ, "std": σ, "n": count}}
        self.priors: Dict[str, Dict[str, float]] = {}

    def update_prior(
        self, metric_name: str, observed_value: float, learning_rate: float = 0.1
    ) -> float:
        """
        Update the prior distribution with a new observation.

        Uses exponential moving average for online learning.

        Args:
            metric_name: Name of the metric
            observed_value: New observed value
            learning_rate: How fast to adapt (0-1)

        Returns:
            Bayesian surprise for this observation
        """
        import math

        if metric_name not in self.priors:
            # Initialize prior with first observation
            self.priors[metric_name] = {
                "mean": observed_value,
                "std": abs(observed_value) * 0.1 + 1.0,  # 10% of value + 1
                "n": 1,
            }
            return 1.0  # First observation is maximally surprising

        prior = self.priors[metric_name]
        μ0, σ0 = prior["mean"], prior["std"]

        # Calculate surprise before updating
        surprise = self.calculate_surprise(metric_name, observed_value)

        # Update using exponential moving average
        α = learning_rate
        new_mean = (1 - α) * μ0 + α * observed_value
        new_var = (1 - α) * (σ0**2) + α * ((observed_value - new_mean) ** 2)
        new_std = math.sqrt(max(new_var, 0.01))  # Floor to prevent zero std

        self.priors[metric_name] = {
            "mean": new_mean,
            "std": new_std,
            "n": prior["n"] + 1,
        }

        return surprise

    def calculate_surprise(self, metric_name: str, observed_value: float) -> float:
        """
        Calculate Bayesian Surprise for an observation.

        Uses analytical KL divergence for Gaussians.

        Args:
            metric_name: Name of the metric
            observed_value: Observed value

        Returns:
            Surprise score (higher = more surprising)
        """
        import math

        if metric_name not in self.priors:
            return 1.0  # Unknown metric = maximally surprising

        prior = self.priors[metric_name]
        μ0, σ0 = prior["mean"], prior["std"]

        # Posterior after single observation
        # Paper Eq. 4: posterior mean = observed, variance slightly reduced
        μ1 = observed_value
        σ1 = σ0 * 0.95  # Slightly reduce uncertainty

        # KL divergence for Gaussians (Paper Eq. 4)
        # D_KL(P(θ|D) || P(θ)) = 0.5 * [σ0²/σ1² + (μ1-μ0)²/σ1² - 1 + ln(σ1²/σ0²)]
        try:
            kl = 0.5 * (
                (σ0**2) / (σ1**2) + ((μ1 - μ0) ** 2) / (σ1**2) - 1 + math.log((σ1**2) / (σ0**2))
            )
            # Normalize to [0,1] with sigmoid, k=2 (Paper Eq. 5)
            surprise = 2 / (1 + math.exp(-2 * kl)) - 1
            return max(0, min(1, surprise))
        except (ValueError, ZeroDivisionError):
            return 0.5  # Default moderate surprise on error

    def get_prior(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get the current prior for a metric."""
        return self.priors.get(metric_name)

    def list_tracked_metrics(self) -> List[str]:
        """List all tracked metric names."""
        return list(self.priors.keys())

    # ── MongoDB Persistence (replaces old JSON file approach) ──
    # Priors are stored in the "bayesian_priors" collection with documents:
    #   {"_id": metric_name, "mean": μ, "std": σ, "n": count}
    # This survives multi-replica deploys — every worker reads from the
    # same MongoDB cluster instead of a local JSON file.

    async def persist(self) -> None:
        """
        Upsert all priors into MongoDB.

        Each prior becomes a document in the bayesian_priors collection
        keyed by metric name. Uses individual update_one with upsert
        (≤50 priors — network overhead is negligible).
        """
        if not self.priors:
            return
        try:
            from db.database import get_database

            db = get_database()
            collection = db[_BAYESIAN_PRIORS_COLLECTION]

            updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            for metric_name, prior in self.priors.items():
                await collection.update_one(
                    {"_id": metric_name},
                    {
                        "$set": {
                            "mean": prior["mean"],
                            "std": prior["std"],
                            "n": prior["n"],
                            "updated_at": updated_at,
                        }
                    },
                    upsert=True,
                )

            logger.debug(f"Persisted {len(self.priors)} Bayesian priors to MongoDB")
        except Exception as e:
            logger.warning(f"Failed to persist Bayesian priors to MongoDB (non-critical): {e}")

    @classmethod
    async def load(cls) -> "BayesianTracker":
        """
        Load priors from MongoDB into a new tracker.

        Returns:
            BayesianTracker with loaded priors, or empty tracker if
            collection doesn't exist or is empty.
        """
        tracker = cls()
        try:
            from db.database import get_database

            db = get_database()
            collection = db[_BAYESIAN_PRIORS_COLLECTION]

            cursor = collection.find({})
            count = 0
            async for doc in cursor:
                metric_name = doc.get("_id")
                if metric_name and "mean" in doc and "std" in doc and "n" in doc:
                    tracker.priors[metric_name] = {
                        "mean": doc["mean"],
                        "std": doc["std"],
                        "n": doc["n"],
                    }
                    count += 1

            if count > 0:
                logger.info(f"Loaded {count} Bayesian priors from MongoDB")
            else:
                logger.debug("No Bayesian priors found in MongoDB — starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load Bayesian priors from MongoDB (non-critical): {e}")

        return tracker


# ============================================================
# PASSIVE BELIEF INGESTION (Implicit Signal Collection)
# ============================================================
# Instead of relying on explicit user feedback (thumbs up/down),
# we passively extract beliefs from every AI interaction.
# This solves the cold-start problem — the belief store populates
# itself automatically as the user chats and views dashboards.
# ============================================================


class PassiveBeliefIngestion:
    """
    Implicit belief collection — no explicit user feedback required.

    Architecture (per ChatGPT / senior-ML-engineer review):

        LLM Response
            ↓
        Fact Extractor  (heuristic, zero LLM cost)
            ↓
        Candidate Belief Store   confidence = 0.25
            ↓
        Engagement Tracker        similarity-gated (cosine > 0.6)
            ↓
        Confidence Updater        follow-up +0.15, dashboard +0.10
            ↓
        Promotion Engine           promoted when confidence ≥ 0.55
            ↓
        Belief Graph  ←  only promoted beliefs enter novelty filter

    Also handles:
    • Contradiction detection  (cosine > 0.85 AND numeric delta → replace)
    • Cold-start bootstrapping (dashboard KPIs, document ingestion)
    """

    # ── Confidence tiers ────────────────────────────────────
    CANDIDATE_CONFIDENCE = 0.25  # just extracted, user merely saw it
    DASHBOARD_CONFIDENCE = 0.20  # KPI on screen — may not have read it
    PROMOTION_THRESHOLD = 0.55  # only promoted beliefs affect novelty
    EXPLICIT_CONFIDENCE = 0.90  # rare explicit feedback

    BOOST_FOLLOWUP = 0.15  # user asked a related follow-up
    BOOST_DASHBOARD_VIEW = 0.10  # user opened a dashboard with this KPI
    BOOST_EXPORT = 0.20  # user exported / downloaded

    SIMILARITY_GATE = 0.60  # must exceed before boosting
    CONTRADICTION_SIM = 0.85  # same topic
    DEDUP_SIM = 0.88  # skip if near-duplicate exists

    # ── Fact extraction ─────────────────────────────────────

    @staticmethod
    def _extract_factual_statements(text: str, max_statements: int = 5) -> List[str]:
        """
        Heuristic extraction of data-bearing sentences from AI text.
        Zero latency — no LLM call, just regex.
        """
        import re

        # Strip markdown
        clean = re.sub(r"[#>]", "", text)
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        clean = re.sub(r"```[\s\S]*?```", "", clean)
        clean = re.sub(r"---+", "", clean)
        clean = re.sub(r"\|[^\n]+\|", "", clean)

        sentences = re.split(r"(?<=[.!?])\s+", clean)

        factual: List[str] = []
        for sent in sentences:
            sent = sent.strip().lstrip("- •")
            if len(sent) < 25 or len(sent) > 300:
                continue
            if re.match(
                r"^(Here\s|Here'|Let me|I can|Sure|I\'ll|I will|Great|Of course|"
                r"Absolutely|You can|Feel free|Would you|Do you want|I found|Based on|Looking at|The data|According to|"
                r"This means|It appears|The results?|This shows|What i|In the)",
                sent,
                re.I,
            ):
                continue
            has_data = bool(
                re.search(
                    r"\d+\.?\d*\s*%|"
                    r"\$[\d,.]+|"
                    r"\b\d{2,}[,.]?\d*\b|"
                    r"\b(increased|decreased|grew|declined|dropped|rose|fell)\b|"
                    r"\b(highest|lowest|top|bottom|peak|minimum|maximum)\b|"
                    r"\b(average|total|median|sum|count|mean)\b|"
                    r"\b(correlation|trend|pattern|outlier|anomaly)\b|"
                    r"\b(\d+x|\d+\.\d+x)\b",
                    sent,
                    re.I,
                )
            )
            if has_data:
                factual.append(sent)
        return factual[:max_statements]

    # ── Numeric extraction for contradiction detection ──────

    @staticmethod
    def _extract_numbers(text: str) -> List[float]:
        """Pull all numbers (incl. decimals, $, %) from a string."""
        import re

        raw = re.findall(r"[\$]?([\d,]+\.?\d*)", text)
        nums: List[float] = []
        for r in raw:
            try:
                nums.append(float(r.replace(",", "")))
            except ValueError:
                pass
        return nums

    # ── Semantic number comparison (FIX §9: replaces position-dependent zip) ──

    # ── Multiplier map for K/M/B suffixes ─────────────────
    _NUM_SUFFIX_MAP = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
    }

    @staticmethod
    def _parse_number_with_suffix(raw: str) -> float:
        """
        Parse a number string with optional K/M/B suffix.
        "120K" → 120000, "$1.5M" → 1500000, "30" → 30
        """
        import re

        raw = raw.replace(",", "").replace("$", "").strip()
        suffix_match = re.search(r"([kmb])", raw, re.I)
        if suffix_match:
            suffix = suffix_match.group(1).lower()
            numeric = raw[: suffix_match.start()]
            multiplier = PassiveBeliefIngestion._NUM_SUFFIX_MAP.get(suffix, 1)
            return float(numeric) * multiplier if numeric else 0.0
        return float(raw)

    # Common stopwords that should not be used as metric labels
    _LABEL_STOPWORDS = frozenset(
        {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "not",
            "no",
            "nor",
            "but",
            "or",
            "and",
            "if",
            "then",
            "else",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "because",
            "as",
            "until",
            "while",
            "of",
            "at",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "from",
            "up",
            "down",
            "in",
            "out",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "once",
            "here",
            "there",
            "this",
            "that",
            "these",
            "those",
        }
    )

    @staticmethod
    def _numbers_differ_semantic(old_text: str, new_text: str, threshold: float = 0.05) -> bool:
        """
        Check if the same metric has a different value in two texts.

        Fixes §9: old code used zip(old_nums, new_nums) which paired numbers
        by position — "Revenue is $120K, profit is $30K" vs "Profit is $28K"
        would falsely flag a contradiction because zip pairs (120, 28).

        This version extracts (label, value) pairs by finding each number,
        then looking backwards up to 40 chars for the nearest MEANINGFUL
        keyword (skipping stopwords like "is", "the", "of") as the metric
        label. Handles K/M/B suffixes: "120K" → 120000.
        """
        import re

        def extract_labeled_numbers(text: str):
            """Extract (label, value) pairs by looking backwards for the label."""
            pairs = []
            # Find all numbers with optional $ prefix and K/M/B suffix
            for match in re.finditer(
                r"(\$?[\d,]+(?:\.\d+)?)([KkMmBb]?)",
                text,
            ):
                raw_num = match.group(1)
                suffix = match.group(2).lower()
                multiplier = PassiveBeliefIngestion._NUM_SUFFIX_MAP.get(suffix, 1)
                try:
                    value = float(raw_num.replace(",", "").replace("$", "")) * multiplier
                    # Look backwards up to 40 chars for the nearest meaningful keyword
                    before = text[max(0, match.start() - 40) : match.start()]
                    words = re.findall(r"[A-Za-z]\w+", before)
                    # Find the last non-stopword
                    label = ""
                    for w in reversed(words):
                        wl = w.lower()
                        if wl not in PassiveBeliefIngestion._LABEL_STOPWORDS:
                            label = wl
                            break
                    pairs.append((label, value))
                except (ValueError, TypeError):
                    pass
            return pairs

        old_pairs = extract_labeled_numbers(old_text)
        new_pairs = extract_labeled_numbers(new_text)

        for old_label, old_val in old_pairs:
            for new_label, new_val in new_pairs:
                # Match if labels share a common keyword
                if (
                    old_label
                    and new_label
                    and (old_label == new_label or old_label in new_label or new_label in old_label)
                ):
                    if abs(old_val - new_val) / max(abs(old_val), 1) > threshold:
                        return True
        return False

    # ── Core: ingest candidates from AI response ────────────

    @staticmethod
    async def auto_ingest_from_response(
        belief_store: "BeliefStore",
        user_id: str,
        ai_response: str,
        dataset_id: str = None,
        max_beliefs: int = 3,
    ) -> List[str]:
        """
        Extract factual sentences → store as **candidate** beliefs (0.25).
        Handles deduplication AND contradiction detection:
        - Near-duplicate (>0.88 cosine, numbers match) → skip
        - Contradiction  (>0.85 cosine, numbers differ) → replace old belief
        """
        statements = PassiveBeliefIngestion._extract_factual_statements(
            ai_response, max_statements=max_beliefs + 2
        )
        if not statements:
            return []

        belief_ids: List[str] = []
        for stmt in statements:
            if len(belief_ids) >= max_beliefs:
                break

            try:
                similar = await belief_store.query_similar_beliefs(user_id, stmt, n_results=1)
                if similar:
                    top = similar[0]
                    sim = top["similarity"]

                    # ── Contradiction detection ──
                    if sim > PassiveBeliefIngestion.CONTRADICTION_SIM:
                        # FIX §9: Semantic number comparison — match by label, not position
                        numbers_differ = PassiveBeliefIngestion._numbers_differ_semantic(
                            top["document"], stmt
                        )
                        if numbers_differ:
                            # Replace stale belief
                            await belief_store.delete_belief(user_id, top["id"])
                            logger.info(
                                f"Belief contradiction: replaced '{top['document'][:50]}…' "
                                f"with '{stmt[:50]}…'"
                            )
                        else:
                            # Near-duplicate, skip
                            logger.debug(f"Belief dedup: skipping '{stmt[:50]}…' (sim={sim:.2f})")
                            continue

                    elif sim > PassiveBeliefIngestion.DEDUP_SIM:
                        continue  # too similar, not contradictory

            except Exception:
                pass

            belief_id = await belief_store.add_belief(
                user_id=user_id,
                belief_text=stmt,
                source="candidate",
                dataset_id=dataset_id,
                confidence=PassiveBeliefIngestion.CANDIDATE_CONFIDENCE,
            )
            if belief_id:
                belief_ids.append(belief_id)

        if belief_ids:
            logger.info(
                f"Passive belief ingestion: {len(belief_ids)} candidates from "
                f"{len(statements)} facts for user {user_id}"
            )
        return belief_ids

    # ── Similarity-gated confidence boosting ─────────────────

    @staticmethod
    async def boost_related_beliefs(
        belief_store: "BeliefStore",
        user_id: str,
        query_text: str,
        boost_amount: float = None,
        signal: str = "followup",
    ) -> int:
        """
        Implicit engagement signal → boost related beliefs.

        Critical fix: similarity gate at 0.60 prevents random boosts
        when the follow-up question is on a different topic.

        Signals & boost amounts:
            followup   +0.15  (user asked related question)
            dashboard  +0.10  (user opened dashboard)
            export     +0.20  (user exported chart/data)
        """
        boost_map = {
            "followup": PassiveBeliefIngestion.BOOST_FOLLOWUP,
            "dashboard": PassiveBeliefIngestion.BOOST_DASHBOARD_VIEW,
            "export": PassiveBeliefIngestion.BOOST_EXPORT,
        }
        amount = boost_amount if boost_amount is not None else boost_map.get(signal, 0.15)

        try:
            similar = await belief_store.query_similar_beliefs(user_id, query_text, n_results=5)
        except Exception:
            return 0

        boosted = 0
        for belief in similar:
            # ── SIMILARITY GATE: only boost if topic actually matches ──
            if belief["similarity"] < PassiveBeliefIngestion.SIMILARITY_GATE:
                continue

            collection = belief_store._get_collection(user_id)
            if not collection:
                continue

            new_confidence = min(0.95, belief["confidence"] + amount)
            updated_meta = {**belief["metadata"], "confidence": new_confidence}

            # Track promotion pathway
            old_source = updated_meta.get("source", "")
            if (
                old_source == "candidate"
                and new_confidence >= PassiveBeliefIngestion.PROMOTION_THRESHOLD
            ):
                updated_meta["source"] = "promoted"
                updated_meta["promoted_at"] = (
                    datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                )
                logger.info(
                    f"Belief promoted: '{belief['document'][:60]}…' "
                    f"(confidence {belief['confidence']:.2f} → {new_confidence:.2f})"
                )
            elif old_source == "candidate":
                updated_meta["source"] = "implicitly_engaged"

            try:
                collection.update(
                    ids=[belief["id"]],
                    metadatas=[updated_meta],
                )
                boosted += 1
            except Exception:
                pass

        if boosted:
            logger.debug(f"Implicit boost ({signal}): {boosted} beliefs for user {user_id}")
        return boosted

    # ── Dashboard KPI ingestion ──────────────────────────────

    @staticmethod
    async def ingest_dashboard_kpis(
        belief_store: "BeliefStore",
        user_id: str,
        components: List[Dict[str, Any]],
        dataset_id: str = None,
    ) -> List[str]:
        """
        Dashboard viewed → KPI values become candidate beliefs (0.20).
        Lower than chat candidates because users may skim dashboards.
        """
        belief_ids: List[str] = []

        for comp in components:
            if comp.get("type", "") != "kpi":
                continue

            title = comp.get("title", "")
            value = comp.get("value")
            if not title or value is None:
                continue

            unit = comp.get("unit", "")
            prefix = comp.get("prefix", "")
            suffix = comp.get("suffix", "")
            dv = f"{prefix}{value}{suffix}" if prefix or suffix else str(value)
            if unit:
                dv = f"{dv} {unit}"
            belief_text = f"The {title} is {dv}."

            change = comp.get("change")
            if change is not None:
                direction = "up" if change > 0 else "down"
                belief_text += f" It is {direction} {abs(change):.1f}%."

            # Dedup / contradiction (same logic as chat)
            try:
                similar = await belief_store.query_similar_beliefs(
                    user_id, belief_text, n_results=1
                )
                if similar:
                    top = similar[0]
                    if top["similarity"] > PassiveBeliefIngestion.CONTRADICTION_SIM:
                        # FIX §9: Semantic number comparison — match by label, not position
                        numbers_differ = PassiveBeliefIngestion._numbers_differ_semantic(
                            top["document"], belief_text
                        )
                        if numbers_differ:
                            await belief_store.delete_belief(user_id, top["id"])
                        else:
                            continue  # same value, skip
                    elif top["similarity"] > PassiveBeliefIngestion.DEDUP_SIM:
                        continue
            except Exception:
                pass

            belief_id = await belief_store.add_belief(
                user_id=user_id,
                belief_text=belief_text,
                source="dashboard_candidate",
                dataset_id=dataset_id,
                confidence=PassiveBeliefIngestion.DASHBOARD_CONFIDENCE,
            )
            if belief_id:
                belief_ids.append(belief_id)

        if belief_ids:
            logger.info(
                f"Dashboard belief ingestion: {len(belief_ids)} KPI candidates for user {user_id}"
            )
        return belief_ids

    # ── Novelty context for prompt injection ─────────────────

    @staticmethod
    async def get_novelty_context(
        belief_store: "BeliefStore",
        user_id: str,
        query_text: str,
        max_beliefs: int = 5,
    ) -> List[str]:
        """
        Retrieve what the user **already knows** about a topic.
        Injected into LLM prompt so it avoids repeating stale insights.

        Critical: only returns **promoted** beliefs (confidence ≥ 0.55).
        Candidate beliefs (0.25) are never shown — they haven't been
        validated by engagement signals yet.
        """
        try:
            similar = await belief_store.query_similar_beliefs(
                user_id, query_text, n_results=max_beliefs
            )
            return [
                b["document"]
                for b in similar
                if b["similarity"] > 0.45
                and b["confidence"] >= PassiveBeliefIngestion.PROMOTION_THRESHOLD
            ]
        except Exception:
            return []


# ============================================================
# SINGLETON INSTANCES
# ============================================================

# Global instances (initialized lazily)
_belief_store: Optional[BeliefStore] = None
_bayesian_tracker: Optional[BayesianTracker] = None


def get_belief_store(persist_directory: str = "./chroma_db") -> BeliefStore:
    """Get or create the global BeliefStore instance."""
    global _belief_store
    if _belief_store is None:
        _belief_store = BeliefStore(persist_directory=persist_directory)
    return _belief_store


async def get_bayesian_tracker() -> BayesianTracker:
    """
    Get or create the global BayesianTracker instance.

    Loads persisted priors from MongoDB on first initialization
    so Bayesian surprise scores survive server restarts across
    all replicas (no more single-node JSON file).
    """
    global _bayesian_tracker
    if _bayesian_tracker is None:
        _bayesian_tracker = await BayesianTracker.load()
    return _bayesian_tracker
