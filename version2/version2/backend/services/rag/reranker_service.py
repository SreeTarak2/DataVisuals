# services/rag/reranker_service.py
"""
Re-ranking Service for RAG Pipeline
====================================
Provides post-retrieval re-ranking to improve relevance filtering.

Strategies:
1. Score Threshold - Filter by minimum similarity score
2. Diversity Rerank - Reduce redundancy in results
3. Cross-Encoder (optional) - BGE-reranker for semantic re-ranking
"""

import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Re-ranks retrieved chunks to improve relevance and diversity.
    """
    
    def __init__(self):
        self.cross_encoder = None
        self.use_cross_encoder = False
        
        # Default thresholds
        self.default_score_threshold = 0.5
        self.diversity_penalty = 0.3
    
    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        use_diversity: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Re-rank retrieved chunks using multiple strategies.
        
        Args:
            query: Original user query
            chunks: List of chunks with similarity scores
            top_k: Number of results to return
            score_threshold: Minimum similarity score (default: 0.5)
            use_diversity: Apply diversity re-ranking
            
        Returns:
            Re-ranked and filtered chunks
        """
        if not chunks:
            return []
        
        threshold = score_threshold or self.default_score_threshold
        
        # Step 1: Score threshold filtering
        filtered = self._filter_by_score(chunks, threshold)
        
        if not filtered:
            logger.debug(f"All chunks filtered out by score threshold {threshold}")
            return []
        
        # Step 2: Diversity re-ranking (reduce redundant chunk types)
        if use_diversity:
            filtered = self._diversity_rerank(filtered)
        
        # Step 3: Cross-encoder re-ranking (if available)
        if self.use_cross_encoder and self.cross_encoder:
            filtered = self._cross_encoder_rerank(query, filtered, top_k)
        
        # Return top_k results
        return filtered[:top_k]
    
    def _filter_by_score(
        self, 
        chunks: List[Dict[str, Any]], 
        threshold: float
    ) -> List[Dict[str, Any]]:
        """Filter chunks below score threshold."""
        return [
            chunk for chunk in chunks 
            if chunk.get("similarity", 0) >= threshold
        ]
    
    def _diversity_rerank(
        self, 
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Re-rank to ensure diversity across chunk types.
        Prevents over-representation of any single chunk type.
        """
        # Group by chunk type
        type_groups = defaultdict(list)
        for chunk in chunks:
            chunk_type = chunk.get("chunk_type", "unknown")
            type_groups[chunk_type].append(chunk)
        
        # Interleave chunk types for diversity
        result = []
        max_per_type = 2  # Max chunks per type in first pass
        
        # First pass: take top 2 from each type
        for chunk_type in ["schema", "column", "statistics", "relationship", "sample"]:
            if chunk_type in type_groups:
                type_chunks = type_groups[chunk_type][:max_per_type]
                result.extend(type_chunks)
        
        # Add remaining chunks from unknown types
        for chunk_type, group_chunks in type_groups.items():
            if chunk_type not in ["schema", "column", "statistics", "relationship", "sample"]:
                result.extend(group_chunks[:max_per_type])
        
        # Re-sort by similarity to maintain ranking within diversity constraint
        result.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return result
    
    def _cross_encoder_rerank(
        self, 
        query: str, 
        chunks: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Re-rank using cross-encoder model for better semantic matching.
        Requires: sentence-transformers with cross-encoder model.
        
        This is optional and only used if cross_encoder is initialized.
        """
        if not self.cross_encoder:
            return chunks
        
        try:
            # Prepare pairs for cross-encoder
            pairs = [(query, chunk.get("content", "")) for chunk in chunks]
            
            # Get cross-encoder scores
            scores = self.cross_encoder.predict(pairs)
            
            # Update chunks with cross-encoder scores
            for chunk, score in zip(chunks, scores):
                chunk["cross_encoder_score"] = float(score)
            
            # Sort by cross-encoder score
            chunks.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
            
            return chunks[:top_k]
            
        except Exception as e:
            logger.warning(f"Cross-encoder re-ranking failed: {e}")
            return chunks[:top_k]
    
    def enable_cross_encoder(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        Enable cross-encoder re-ranking with specified model.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        try:
            from sentence_transformers import CrossEncoder
            
            self.cross_encoder = CrossEncoder(model_name)
            self.use_cross_encoder = True
            logger.info(f"Cross-encoder enabled: {model_name}")
            
        except ImportError:
            logger.warning("sentence-transformers not installed, cross-encoder disabled")
            self.use_cross_encoder = False
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            self.use_cross_encoder = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get re-ranker configuration stats."""
        return {
            "cross_encoder_enabled": self.use_cross_encoder,
            "default_score_threshold": self.default_score_threshold,
            "diversity_penalty": self.diversity_penalty
        }


# Singleton instance
reranker_service = RerankerService()
