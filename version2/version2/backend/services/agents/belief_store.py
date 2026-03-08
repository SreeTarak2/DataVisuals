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
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
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
    
    # Embedding model (BGE is recommended for semantic similarity)
    DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        embedding_model: str = None
    ):
        """
        Initialize the Belief Store.
        
        Args:
            persist_directory: Where to store ChromaDB data
            embedding_model: HuggingFace model name for embeddings
        """
        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model or self.DEFAULT_MODEL
        
        # Initialize ChromaDB
        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"ChromaDB initialized at {persist_directory}")
        else:
            self.client = None
            logger.warning("ChromaDB not available - Belief Store disabled")
        
        # Initialize embedding model
        if EMBEDDINGS_AVAILABLE:
            try:
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
            metadata={"description": f"Belief store for user {user_id}"}
        )
    
    def _embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.embedding_model:
            embedding = self.embedding_model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        else:
            # Mock embedding for testing (random 384-dim vector)
            import hashlib
            import numpy as np
            
            # Deterministic "embedding" based on text hash
            hash_bytes = hashlib.sha256(text.encode()).digest()
            np.random.seed(int.from_bytes(hash_bytes[:4], 'big'))
            return np.random.randn(384).tolist()
    
    async def add_belief(
        self,
        user_id: str,
        belief_text: str,
        source: str = "user_confirmed",
        dataset_id: str = None,
        confidence: float = 0.95
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
            "decay_rate": 0.01  # 1% per day
        }
        
        if dataset_id:
            metadata["dataset_id"] = dataset_id
        
        collection.add(
            ids=[belief_id],
            embeddings=[embedding],
            documents=[belief_text],
            metadatas=[metadata]
        )
        
        logger.info(f"Added belief {belief_id} for user {user_id}: {belief_text[:50]}...")
        return belief_id
    
    async def query_similar_beliefs(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
        min_confidence: float = 0.3
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
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        beliefs = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            
            # Apply confidence decay
            confidence = self._apply_decay(
                metadata.get("confidence", 1.0),
                metadata.get("created_at"),
                metadata.get("decay_rate", 0.01)
            )
            
            if confidence >= min_confidence:
                # Convert distance to similarity (ChromaDB uses L2 by default)
                # For normalized vectors, L2 distance relates to cosine: d = sqrt(2 - 2*cos)
                # So cos = 1 - d²/2
                similarity = max(0, 1 - (distance ** 2) / 2)
                
                beliefs.append({
                    "id": results["ids"][0][i],
                    "document": doc,
                    "similarity": similarity,
                    "confidence": confidence,
                    "metadata": metadata
                })
        
        # Sort by similarity descending
        beliefs.sort(key=lambda x: x["similarity"], reverse=True)
        
        return beliefs
    
    def _apply_decay(
        self,
        initial_confidence: float,
        created_at: str,
        decay_rate: float
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
            return max(0.1, decayed)  # Floor at 0.1
        except Exception:
            return initial_confidence
    
    async def calculate_semantic_surprisal(
        self,
        user_id: str,
        insight_text: str
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
        self,
        user_id: str,
        insight_text: str,
        dataset_id: str = None
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
            confidence=0.99  # Very high - user explicitly said they know this
        )
    
    async def accept_insight(
        self,
        user_id: str,
        insight_text: str,
        dataset_id: str = None
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
            confidence=0.7  # Moderate - user found it useful
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
    
    async def ingest_document(
        self,
        user_id: str,
        document_text: str,
        chunk_size: int = 500,
        overlap: int = 50
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
                confidence=0.6  # Lower confidence for auto-ingested
            )
            if belief_id:
                belief_ids.append(belief_id)
        
        logger.info(f"Ingested document into {len(belief_ids)} beliefs for user {user_id}")
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
        self,
        metric_name: str,
        observed_value: float,
        learning_rate: float = 0.1
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
                "n": 1
            }
            return 1.0  # First observation is maximally surprising
        
        prior = self.priors[metric_name]
        μ0, σ0 = prior["mean"], prior["std"]
        
        # Calculate surprise before updating
        surprise = self.calculate_surprise(metric_name, observed_value)
        
        # Update using exponential moving average
        α = learning_rate
        new_mean = (1 - α) * μ0 + α * observed_value
        new_var = (1 - α) * (σ0 ** 2) + α * ((observed_value - new_mean) ** 2)
        new_std = math.sqrt(max(new_var, 0.01))  # Floor to prevent zero std
        
        self.priors[metric_name] = {
            "mean": new_mean,
            "std": new_std,
            "n": prior["n"] + 1
        }
        
        return surprise
    
    def calculate_surprise(
        self,
        metric_name: str,
        observed_value: float
    ) -> float:
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
        
        # Posterior after single observation (simplified)
        # In reality, this depends on the likelihood model
        # Here we assume the observation IS the posterior mean
        μ1 = observed_value
        σ1 = σ0 * 0.95  # Slightly reduce uncertainty
        
        # KL divergence for Gaussians
        # D_KL(N(μ1,σ1) || N(μ0,σ0)) = log(σ0/σ1) + (σ1² + (μ1-μ0)²)/(2σ0²) - 0.5
        try:
            kl = (
                math.log(σ0 / σ1) +
                (σ1 ** 2 + (μ1 - μ0) ** 2) / (2 * σ0 ** 2) -
                0.5
            )
            # Normalize to 0-1 range using sigmoid-like function
            surprise = 2 / (1 + math.exp(-kl)) - 1
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
