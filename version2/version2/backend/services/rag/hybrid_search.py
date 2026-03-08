# services/rag/hybrid_search.py
"""
Hybrid Search Service for RAG Pipeline
=======================================
Combines dense (vector) and sparse (BM25) retrieval for better coverage.

Fusion Methods:
1. Reciprocal Rank Fusion (RRF) - Combines rankings from multiple sources
2. Linear Combination - Weighted score combination
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Hybrid search combining dense (vector) and sparse (BM25) retrieval.
    """
    
    def __init__(self):
        self.bm25_indices = {}  # dataset_id -> BM25 index
        self.corpus_store = {}  # dataset_id -> list of documents
        self.bm25_available = self._check_bm25_available()
        
        # Default fusion parameters
        self.rrf_k = 60  # RRF constant
        self.dense_weight = 0.7
        self.sparse_weight = 0.3
    
    def _check_bm25_available(self) -> bool:
        """Check if BM25 library is available."""
        try:
            from rank_bm25 import BM25Okapi
            return True
        except ImportError:
            logger.warning("rank_bm25 not installed. Install with: pip install rank-bm25")
            return False
    
    def build_bm25_index(
        self, 
        dataset_id: str, 
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Build BM25 index for a dataset's chunks.
        
        Args:
            dataset_id: Dataset identifier
            chunks: List of chunk dicts with 'content' field
            
        Returns:
            True if index built successfully
        """
        if not self.bm25_available:
            return False
        
        try:
            from rank_bm25 import BM25Okapi
            
            # Tokenize documents
            tokenized_corpus = []
            for chunk in chunks:
                content = chunk.get("content", "")
                tokens = self._tokenize(content)
                tokenized_corpus.append(tokens)
            
            # Build BM25 index
            self.bm25_indices[dataset_id] = BM25Okapi(tokenized_corpus)
            self.corpus_store[dataset_id] = chunks
            
            logger.info(f"Built BM25 index for dataset {dataset_id} with {len(chunks)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            return False
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace tokenization with lowercasing."""
        import re
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        return text.split()
    
    def bm25_search(
        self, 
        query: str, 
        dataset_id: str, 
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 sparse retrieval.
        
        Args:
            query: Search query
            dataset_id: Dataset to search in
            k: Number of results to return
            
        Returns:
            List of chunks with BM25 scores
        """
        if not self.bm25_available:
            return []
        
        if dataset_id not in self.bm25_indices:
            logger.debug(f"No BM25 index for dataset {dataset_id}")
            return []
        
        try:
            bm25 = self.bm25_indices[dataset_id]
            corpus = self.corpus_store[dataset_id]
            
            # Tokenize query
            query_tokens = self._tokenize(query)
            
            # Get BM25 scores
            scores = bm25.get_scores(query_tokens)
            
            # Get top-k results
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include non-zero scores
                    chunk = corpus[idx].copy()
                    chunk["bm25_score"] = float(scores[idx])
                    results.append(chunk)
            
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def hybrid_search(
        self,
        query: str,
        dense_results: List[Dict[str, Any]],
        dataset_id: str,
        k: int = 5,
        fusion_method: str = "rrf"
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining dense and sparse results.
        
        Args:
            query: Search query
            dense_results: Results from vector (dense) search
            dataset_id: Dataset identifier
            k: Number of final results
            fusion_method: "rrf" or "linear"
            
        Returns:
            Fused results combining dense and sparse retrieval
        """
        # Get BM25 results
        sparse_results = self.bm25_search(query, dataset_id, k=k*2)
        
        if not sparse_results:
            # If no BM25 results, return dense results only
            return dense_results[:k]
        
        # Fuse results
        if fusion_method == "rrf":
            return self._reciprocal_rank_fusion(dense_results, sparse_results, k)
        else:
            return self._linear_fusion(dense_results, sparse_results, k)
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int
    ) -> List[Dict[str, Any]]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).
        
        RRF Score = sum(1 / (k + rank)) across all rankings
        """
        # Create score map by chunk_id
        rrf_scores = defaultdict(float)
        chunk_map = {}
        
        # Add dense scores
        for rank, chunk in enumerate(dense_results, start=1):
            chunk_id = chunk.get("chunk_id") or id(chunk)
            rrf_scores[chunk_id] += 1.0 / (self.rrf_k + rank)
            chunk_map[chunk_id] = chunk
        
        # Add sparse scores
        for rank, chunk in enumerate(sparse_results, start=1):
            chunk_id = chunk.get("chunk_id") or id(chunk)
            rrf_scores[chunk_id] += 1.0 / (self.rrf_k + rank)
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk
        
        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        # Build result list
        results = []
        for chunk_id in sorted_ids[:k]:
            chunk = chunk_map[chunk_id].copy()
            chunk["rrf_score"] = rrf_scores[chunk_id]
            # Preserve original similarity for compatibility
            if "similarity" not in chunk and "bm25_score" in chunk:
                chunk["similarity"] = min(chunk["bm25_score"] / 10, 1.0)  # Normalize
            results.append(chunk)
        
        return results
    
    def _linear_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int
    ) -> List[Dict[str, Any]]:
        """
        Combine results using weighted linear combination.
        """
        # Normalize scores
        combined_scores = defaultdict(float)
        chunk_map = {}
        
        # Normalize and add dense scores
        if dense_results:
            max_dense = max(c.get("similarity", 0) for c in dense_results) or 1
            for chunk in dense_results:
                chunk_id = chunk.get("chunk_id") or id(chunk)
                norm_score = chunk.get("similarity", 0) / max_dense
                combined_scores[chunk_id] += self.dense_weight * norm_score
                chunk_map[chunk_id] = chunk
        
        # Normalize and add sparse scores
        if sparse_results:
            max_sparse = max(c.get("bm25_score", 0) for c in sparse_results) or 1
            for chunk in sparse_results:
                chunk_id = chunk.get("chunk_id") or id(chunk)
                norm_score = chunk.get("bm25_score", 0) / max_sparse
                combined_scores[chunk_id] += self.sparse_weight * norm_score
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = chunk
        
        # Sort by combined score
        sorted_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)
        
        results = []
        for chunk_id in sorted_ids[:k]:
            chunk = chunk_map[chunk_id].copy()
            chunk["combined_score"] = combined_scores[chunk_id]
            chunk["similarity"] = combined_scores[chunk_id]  # For compatibility
            results.append(chunk)
        
        return results
    
    def delete_index(self, dataset_id: str) -> bool:
        """Remove BM25 index for a dataset."""
        if dataset_id in self.bm25_indices:
            del self.bm25_indices[dataset_id]
        if dataset_id in self.corpus_store:
            del self.corpus_store[dataset_id]
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hybrid search stats."""
        return {
            "bm25_available": self.bm25_available,
            "indexed_datasets": list(self.bm25_indices.keys()),
            "rrf_k": self.rrf_k,
            "dense_weight": self.dense_weight,
            "sparse_weight": self.sparse_weight
        }


# Singleton instance
hybrid_search_service = HybridSearchService()
