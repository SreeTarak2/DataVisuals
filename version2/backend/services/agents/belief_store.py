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
from datetime import datetime
import uuid
import json

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
    logger.warning(
        "sentence-transformers not installed. Run: pip install sentence-transformers"
    )


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

    def __init__(
        self, persist_directory: str = "./chroma_db", embedding_model: str = None
    ):
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

        # Initialize embedding model
        if EMBEDDINGS_AVAILABLE:
            try:
                import os
                # Use cached model without pinging huggingface.co on every cold start.
                # If the model is not cached yet, this will be set temporarily to trigger
                # a fresh download on the NEXT restart (with the env var unset).
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info(f"Loaded embedding model: {self.embedding_model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self.embedding_model = None

        else:
            self.embedding_model = None
            logger.warning("Embeddings not available - using mock embeddings")

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

    def _embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.embedding_model:
            embedding = self.embedding_model.encode(text, normalize_embeddings=True)
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
        embedding = self._embed(belief_text)

        metadata = {
            "user_id": user_id,
            "source": source,
            "confidence": confidence,
            "created_at": datetime.utcnow().isoformat(),
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
                    logger.warning(
                        "Belief Store unavailable after collection reset - skipping add"
                    )
                    return None
                collection.add(
                    ids=[belief_id],
                    embeddings=[embedding],
                    documents=[belief_text],
                    metadatas=[metadata],
                )
            else:
                raise

        logger.info(
            f"Added belief {belief_id} for user {user_id}: {belief_text[:50]}..."
        )
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

        query_embedding = self._embed(query_text)

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
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]

            # Apply confidence decay
            confidence = self._apply_decay(
                metadata.get("confidence", 1.0),
                metadata.get("created_at"),
                metadata.get("decay_rate", 0.01),
            )

            if confidence >= min_confidence:
                # Convert distance to similarity (ChromaDB uses L2 by default)
                # For normalized vectors, L2 distance relates to cosine: d = sqrt(2 - 2*cos)
                # So cos = 1 - d²/2
                similarity = max(0, 1 - (distance**2) / 2)

                beliefs.append(
                    {
                        "id": results["ids"][0][i],
                        "document": doc,
                        "similarity": similarity,
                        "confidence": confidence,
                        "metadata": metadata,
                    }
                )

        # Sort by similarity descending
        beliefs.sort(key=lambda x: x["similarity"], reverse=True)

        return beliefs

    def _apply_decay(
        self, initial_confidence: float, created_at: str, decay_rate: float
    ) -> float:
        """Apply temporal decay to confidence."""
        if not created_at:
            return initial_confidence

        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.utcnow()
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

    async def mark_as_known(
        self, user_id: str, insight_text: str, dataset_id: str = None
    ) -> str:
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

    async def accept_insight(
        self, user_id: str, insight_text: str, dataset_id: str = None
    ) -> str:
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

        logger.info(
            f"Ingested document into {len(belief_ids)} beliefs for user {user_id}"
        )
        return belief_ids


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
                (σ0**2) / (σ1**2)
                + ((μ1 - μ0) ** 2) / (σ1**2)
                - 1
                + math.log((σ1**2) / (σ0**2))
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

    def save_state(self) -> Dict[str, Any]:
        """Serialize state for persistence."""
        return {"priors": self.priors}

    def load_state(self, state: Dict[str, Any]):
        """Load state from persistence."""
        self.priors = state.get("priors", {})


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
                r"^(Here\s|Let me|I can|Sure|I\'ll|I will|Great|Of course|"
                r"Absolutely|You can|Feel free|Would you|Do you want)",
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
                similar = await belief_store.query_similar_beliefs(
                    user_id, stmt, n_results=1
                )
                if similar:
                    top = similar[0]
                    sim = top["similarity"]

                    # ── Contradiction detection ──
                    if sim > PassiveBeliefIngestion.CONTRADICTION_SIM:
                        old_nums = PassiveBeliefIngestion._extract_numbers(
                            top["document"]
                        )
                        new_nums = PassiveBeliefIngestion._extract_numbers(stmt)
                        numbers_differ = (
                            old_nums
                            and new_nums
                            and any(
                                abs(o - n) / max(abs(o), 1) > 0.05
                                for o, n in zip(old_nums, new_nums)
                            )
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
                            logger.debug(
                                f"Belief dedup: skipping '{stmt[:50]}…' (sim={sim:.2f})"
                            )
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
        amount = (
            boost_amount if boost_amount is not None else boost_map.get(signal, 0.15)
        )

        try:
            similar = await belief_store.query_similar_beliefs(
                user_id, query_text, n_results=5
            )
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
                updated_meta["promoted_at"] = datetime.utcnow().isoformat()
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
            logger.debug(
                f"Implicit boost ({signal}): {boosted} beliefs for user {user_id}"
            )
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
                        old_nums = PassiveBeliefIngestion._extract_numbers(
                            top["document"]
                        )
                        new_nums = PassiveBeliefIngestion._extract_numbers(belief_text)
                        if (
                            old_nums
                            and new_nums
                            and any(
                                abs(o - n) / max(abs(o), 1) > 0.05
                                for o, n in zip(old_nums, new_nums)
                            )
                        ):
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
                f"Dashboard belief ingestion: {len(belief_ids)} KPI candidates "
                f"for user {user_id}"
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


def get_bayesian_tracker() -> BayesianTracker:
    """Get or create the global BayesianTracker instance."""
    global _bayesian_tracker
    if _bayesian_tracker is None:
        _bayesian_tracker = BayesianTracker()
    return _bayesian_tracker
