"""
Fusion Engine — Hybrid Graph + Vector Result Fusion
=====================================================

Combines results from graph database traversal and FAISS vector search into
a single ranked, deduplicated, relevance-scored result set.

Supports three fusion strategies:
1. **RRF (Reciprocal Rank Fusion)** — Default. Robust across score scales.
   Score = sum(1 / (k + rank)) for each result appearing in any source.
2. **Linear combination** — Configurable weights for graph vs. vector importance.
   Score = w_graph * graph_score + w_vector * vector_score.
3. **Weighted scoring** — Score = graph_weight * normalized_graph_score +
   vector_weight * normalized_vector_score + entity_match_bonus.

Key design choices:
- Results are deduplicated by content hash or entity ID
- Scores are normalized per source before fusion
- Fusion weights are configurable per query intent (e.g., trend queries prefer graph)
- Empty sources are handled gracefully (non-empty source dominates)
"""

from __future__ import annotations

import logging
import math
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .query_parser import QueryIntent

logger = logging.getLogger(__name__)


# ── Fusion Strategy ───────────────────────────────────────────────────────────


class FusionMethod(str, Enum):
    """Supported fusion methods for combining graph and vector results."""

    RRF = "rrf"                     # Reciprocal Rank Fusion (default)
    LINEAR = "linear"               # Weighted linear combination
    WEIGHTED = "weighted"           # Weighted with entity match bonus
    GRAPH_ONLY = "graph_only"       # Only use graph results
    VECTOR_ONLY = "vector_only"     # Only use vector results


# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class GraphResult:
    """A single result from graph traversal."""

    entity_id: str
    entity_type: str
    column_name: Optional[str] = None
    label: str = ""
    score: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "graph"

    @property
    def content_hash(self) -> str:
        """Unique identifier for deduplication."""
        return f"graph:{self.entity_id}"


@dataclass
class VectorResult:
    """A single result from FAISS vector search."""

    chunk_id: str
    content: str
    chunk_type: str = "sample"
    similarity: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "vector"

    @property
    def content_hash(self) -> str:
        """Unique identifier for deduplication."""
        return f"vector:{self.chunk_id}"


@dataclass
class FusionResult:
    """A single fused result combining graph and vector signals."""

    content: str
    score: float
    sources: List[str]                       # ["graph"], ["vector"], or ["graph", "vector"]
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    chunk_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_graph_source(self) -> bool:
        return "graph" in self.sources

    @property
    def has_vector_source(self) -> bool:
        return "vector" in self.sources


@dataclass
class FusionOutput:
    """Complete output from the fusion engine."""

    fused_results: List[FusionResult] = field(default_factory=list)
    graph_results_count: int = 0
    vector_results_count: int = 0
    fusion_method: FusionMethod = FusionMethod.RRF
    execution_time_ms: float = 0.0

    @property
    def total_results(self) -> int:
        return len(self.fused_results)


# ── Intent-Based Weight Configuration ────────────────────────────────────────

# Default fusion weights per query intent (used by LINEAR and WEIGHTED methods)
_INTENT_WEIGHTS: Dict[QueryIntent, Dict[str, float]] = {
    QueryIntent.TREND: {"graph": 0.6, "vector": 0.4},          # Graph captures time relationships
    QueryIntent.COMPARE: {"graph": 0.7, "vector": 0.3},        # Graph captures entity relationships
    QueryIntent.ANOMALY: {"graph": 0.5, "vector": 0.5},        # Both are useful
    QueryIntent.BREAKDOWN: {"graph": 0.7, "vector": 0.3},      # Graph has dimension breakdowns
    QueryIntent.DESCRIBE: {"graph": 0.4, "vector": 0.6},       # Vector has descriptive context
    QueryIntent.LIST: {"graph": 0.5, "vector": 0.5},           # Equal
    QueryIntent.CORRELATION: {"graph": 0.8, "vector": 0.2},    # Graph has relationship edges
    QueryIntent.FORECAST: {"graph": 0.3, "vector": 0.7},       # Vector has historical context
    QueryIntent.GENERAL: {"graph": 0.5, "vector": 0.5},        # Default equal weights
}


# ── Fusion Engine ─────────────────────────────────────────────────────────────



class FusionEngine:
    """
    Combines graph and vector search results into a unified, ranked result set.

    Key features:
    - Multiple fusion strategies (RRF, linear, weighted)
    - Intent-aware weight configuration
    - Deduplication across sources
    - Normalized scoring per source
    - Graceful handling of empty sources
    """

    # RRF constant (prevents division by zero)
    RRF_K = 60

    # Entity match bonus for results confirmed by both sources
    ENTITY_MATCH_BONUS = 0.15

    # ── Main Entry Point ────────────────────────────────────────────────────

    def fuse(
        self,
        graph_results: List[GraphResult],
        vector_results: List[VectorResult],
        method: FusionMethod = FusionMethod.RRF,
        intent: Optional[QueryIntent] = None,
        top_k: int = 10,
    ) -> FusionOutput:
        """
        Fuse graph and vector results into a single ranked list.

        Args:
            graph_results: Results from graph traversal
            vector_results: Results from FAISS vector search
            method: Fusion strategy to use
            intent: Query intent for weight configuration (LINEAR/WEIGHTED only)
            top_k: Maximum number of results to return

        Returns:
            FusionOutput with ranked, deduplicated results
        """
        start = time.time()

        # Handle empty sources
        if not graph_results and not vector_results:
            return FusionOutput(fusion_method=method, execution_time_ms=0.0)

        if not graph_results:
            return self._vector_only(vector_results, top_k, start)

        if not vector_results:
            return self._graph_only(graph_results, top_k, start)

        # Choose and execute fusion strategy
        if method == FusionMethod.RRF:
            fused = self._rrf_fusion(graph_results, vector_results, top_k)
        elif method == FusionMethod.LINEAR:
            weights = _INTENT_WEIGHTS.get(intent, _INTENT_WEIGHTS[QueryIntent.GENERAL])
            fused = self._linear_fusion(graph_results, vector_results, weights, top_k)
        elif method == FusionMethod.WEIGHTED:
            weights = _INTENT_WEIGHTS.get(intent, _INTENT_WEIGHTS[QueryIntent.GENERAL])
            fused = self._weighted_fusion(graph_results, vector_results, weights, top_k)
        else:
            # Fallback to RRF
            fused = self._rrf_fusion(graph_results, vector_results, top_k)

        execution_time = (time.time() - start) * 1000

        return FusionOutput(
            fused_results=fused,
            graph_results_count=len(graph_results),
            vector_results_count=len(vector_results),
            fusion_method=method,
            execution_time_ms=round(execution_time, 2),
        )

    # ── RRF Fusion ──────────────────────────────────────────────────────────

    def _rrf_fusion(
        self,
        graph_results: List[GraphResult],
        vector_results: List[VectorResult],
        top_k: int,
    ) -> List[FusionResult]:
        """
        Reciprocal Rank Fusion: robust, score-scale-independent.

        Each result's RRF score = sum over all sources of 1 / (RRF_K + rank_in_source).

        This favours results that appear high in multiple rankings without being
        sensitive to absolute score values.
        """
        # Build ranked lists
        graph_ranked = self._rank_graph(graph_results)
        vector_ranked = self._rank_vector(vector_results)

        # Build content_hash → FusionResult accumulator
        fusion_map: Dict[str, FusionResult] = {}

        for rank, gr in enumerate(graph_results):
            h = gr.content_hash
            if h not in fusion_map:
                # Convert GraphResult to FusionResult
                content = self._format_graph_content(gr)
                fusion_map[h] = FusionResult(
                    content=content,
                    score=0.0,
                    sources=[],
                    entity_id=gr.entity_id,
                    entity_type=gr.entity_type,
                    metadata=gr.properties,
                    relationships=gr.relationships,
                )
            fusion_map[h].score += 1.0 / (self.RRF_K + rank + 1)
            if "graph" not in fusion_map[h].sources:
                fusion_map[h].sources.append("graph")

        for rank, vr in enumerate(vector_results):
            h = vr.content_hash
            if h not in fusion_map:
                fusion_map[h] = FusionResult(
                    content=vr.content,
                    score=0.0,
                    sources=[],
                    chunk_id=vr.chunk_id,
                    metadata=vr.metadata,
                )
            fusion_map[h].score += 1.0 / (self.RRF_K + rank + 1)
            if "vector" not in fusion_map[h].sources:
                fusion_map[h].sources.append("vector")

        # Sort by score descending
        results = sorted(fusion_map.values(), key=lambda r: -r.score)

        # Apply entity match bonus: results appearing in BOTH sources get a boost
        for r in results:
            if len(r.sources) > 1:
                r.score += self.ENTITY_MATCH_BONUS

        # Re-sort after bonus
        results.sort(key=lambda r: -r.score)

        return results[:top_k]

    # ── Linear Fusion ───────────────────────────────────────────────────────

    def _linear_fusion(
        self,
        graph_results: List[GraphResult],
        vector_results: List[VectorResult],
        weights: Dict[str, float],
        top_k: int,
    ) -> List[FusionResult]:
        """
        Weighted linear combination of normalized scores.

        Each source's scores are min-max normalized to [0, 1], then combined:
        final_score = w_graph * norm(graph_score) + w_vector * norm(vector_score)
        """
        w_graph = weights.get("graph", 0.5)
        w_vector = weights.get("vector", 0.5)

        # Normalize scores per source
        norm_graph = self._normalize_scores([gr.score for gr in graph_results])
        norm_vector = self._normalize_scores([vr.similarity for vr in vector_results])

        # Build content_hash index for graph results
        graph_map: Dict[str, Tuple[GraphResult, float]] = {}
        for i, gr in enumerate(graph_results):
            graph_map[gr.content_hash] = (gr, norm_graph[i])

        # Build content_hash index for vector results
        vector_map: Dict[str, Tuple[VectorResult, float]] = {}
        for i, vr in enumerate(vector_results):
            vector_map[vr.content_hash] = (vr, norm_vector[i])

        # Combine: for results appearing in both, linear combination
        # For results in only one source, use that source's weight directly
        fusion_map: Dict[str, FusionResult] = {}
        all_hashes = set(graph_map.keys()) | set(vector_map.keys())

        for h in all_hashes:
            g_entry = graph_map.get(h)
            v_entry = vector_map.get(h)

            score = 0.0
            sources = []

            if g_entry and v_entry:
                # Both sources: weighted combination
                gr, g_norm = g_entry
                vr, v_norm = v_entry
                score = (w_graph * g_norm) + (w_vector * v_norm)
                sources = ["graph", "vector"]
                content = self._format_graph_content(gr)
                fusion_map[h] = FusionResult(
                    content=content,
                    score=score,
                    sources=sources,
                    entity_id=gr.entity_id,
                    entity_type=gr.entity_type,
                    chunk_id=vr.chunk_id,
                    metadata={**gr.properties, **vr.metadata},
                    relationships=gr.relationships,
                )
            elif g_entry:
                # Only graph: weight * normalized score
                gr, g_norm = g_entry
                score = w_graph * g_norm
                content = self._format_graph_content(gr)
                fusion_map[h] = FusionResult(
                    content=content,
                    score=score,
                    sources=["graph"],
                    entity_id=gr.entity_id,
                    entity_type=gr.entity_type,
                    metadata=gr.properties,
                    relationships=gr.relationships,
                )
            elif v_entry:
                # Only vector: weight * normalized score
                vr, v_norm = v_entry
                score = w_vector * v_norm
                fusion_map[h] = FusionResult(
                    content=vr.content,
                    score=score,
                    sources=["vector"],
                    chunk_id=vr.chunk_id,
                    metadata=vr.metadata,
                )

        # Sort and limit
        results = sorted(fusion_map.values(), key=lambda r: -r.score)
        return results[:top_k]

    # ── Weighted Fusion ─────────────────────────────────────────────────────

    def _weighted_fusion(
        self,
        graph_results: List[GraphResult],
        vector_results: List[VectorResult],
        weights: Dict[str, float],
        top_k: int,
    ) -> List[FusionResult]:
        """
        Weighted scoring with entity match bonus.

        Same as linear fusion but adds a bonus when the same entity/chunk appears
        in both sources, encouraging cross-source confirmed results.
        """
        w_graph = weights.get("graph", 0.5)
        w_vector = weights.get("vector", 0.5)

        norm_graph = self._normalize_scores([gr.score for gr in graph_results])
        norm_vector = self._normalize_scores([vr.similarity for vr in vector_results])

        graph_map: Dict[str, Tuple[GraphResult, float]] = {}
        for i, gr in enumerate(graph_results):
            graph_map[gr.content_hash] = (gr, norm_graph[i])

        vector_map: Dict[str, Tuple[VectorResult, float]] = {}
        for i, vr in enumerate(vector_results):
            vector_map[vr.content_hash] = (vr, norm_vector[i])

        all_hashes = set(graph_map.keys()) | set(vector_map.keys())
        fusion_map: Dict[str, FusionResult] = {}

        for h in all_hashes:
            g_entry = graph_map.get(h)
            v_entry = vector_map.get(h)
            score = 0.0
            sources = []

            if g_entry and v_entry:
                gr, g_norm = g_entry
                vr, v_norm = v_entry
                # Weighted combination + entity match bonus
                score = (w_graph * g_norm) + (w_vector * v_norm) + self.ENTITY_MATCH_BONUS
                sources = ["graph", "vector"]
                content = self._format_graph_content(gr)
                fusion_map[h] = FusionResult(
                    content=content,
                    score=score,
                    sources=sources,
                    entity_id=gr.entity_id,
                    entity_type=gr.entity_type,
                    chunk_id=vr.chunk_id,
                    metadata={**gr.properties, **vr.metadata},
                    relationships=gr.relationships,
                )
            elif g_entry:
                gr, g_norm = g_entry
                score = w_graph * g_norm
                content = self._format_graph_content(gr)
                fusion_map[h] = FusionResult(
                    content=content,
                    score=score,
                    sources=["graph"],
                    entity_id=gr.entity_id,
                    entity_type=gr.entity_type,
                    metadata=gr.properties,
                    relationships=gr.relationships,
                )
            elif v_entry:
                vr, v_norm = v_entry
                score = w_vector * v_norm
                fusion_map[h] = FusionResult(
                    content=vr.content,
                    score=score,
                    sources=["vector"],
                    chunk_id=vr.chunk_id,
                    metadata=vr.metadata,
                )

        results = sorted(fusion_map.values(), key=lambda r: -r.score)
        return results[:top_k]

    # ── Source-Only Methods ─────────────────────────────────────────────────

    def _graph_only(
        self,
        graph_results: List[GraphResult],
        top_k: int,
        start_time: float,
    ) -> FusionOutput:
        """Only graph results available — rank by graph score."""
        fused = []
        for gr in graph_results[:top_k]:
            content = self._format_graph_content(gr)
            score = self._normalize_value(gr.score)
            fused.append(FusionResult(
                content=content,
                score=score,
                sources=["graph"],
                entity_id=gr.entity_id,
                entity_type=gr.entity_type,
                metadata=gr.properties,
                relationships=gr.relationships,
            ))

        execution_time = (time.time() - start_time) * 1000
        return FusionOutput(
            fused_results=fused,
            graph_results_count=len(graph_results),
            vector_results_count=0,
            fusion_method=FusionMethod.GRAPH_ONLY,
            execution_time_ms=round(execution_time, 2),
        )

    def _vector_only(
        self,
        vector_results: List[VectorResult],
        top_k: int,
        start_time: float,
    ) -> FusionOutput:
        """Only vector results available — rank by similarity score."""
        fused = []
        for vr in vector_results[:top_k]:
            score = self._normalize_value(vr.similarity)
            fused.append(FusionResult(
                content=vr.content,
                score=score,
                sources=["vector"],
                chunk_id=vr.chunk_id,
                metadata=vr.metadata,
            ))

        execution_time = (time.time() - start_time) * 1000
        return FusionOutput(
            fused_results=fused,
            graph_results_count=0,
            vector_results_count=len(vector_results),
            fusion_method=FusionMethod.VECTOR_ONLY,
            execution_time_ms=round(execution_time, 2),
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _rank_graph(graph_results: List[GraphResult]) -> Dict[str, int]:
        """Assign 0-based rank to graph results by score descending."""
        sorted_results = sorted(
            enumerate(graph_results), key=lambda x: -x[1].score
        )
        return {gr.content_hash: rank for rank, (_, gr) in enumerate(sorted_results)}

    @staticmethod
    def _rank_vector(vector_results: List[VectorResult]) -> Dict[str, int]:
        """Assign 0-based rank to vector results by similarity descending."""
        sorted_results = sorted(
            enumerate(vector_results), key=lambda x: -x[1].similarity
        )
        return {vr.content_hash: rank for rank, (_, vr) in enumerate(sorted_results)}

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        """Min-max normalize scores to [0, 1] range."""
        if not scores:
            return []
        min_s = min(scores)
        max_s = max(scores)
        if max_s == min_s:
            return [0.5] * len(scores)  # All equal → flat middle value
        return [(s - min_s) / (max_s - min_s) for s in scores]

    @staticmethod
    def _normalize_value(value: float) -> float:
        """Sigmoid-like normalization of a single value to [0, 1]."""
        return 1.0 / (1.0 + (math.e ** (-value)))

    @staticmethod
    def _format_graph_content(gr: GraphResult) -> str:
        """Format a GraphResult into a human-readable content string."""
        parts = []
        if gr.label:
            parts.append(gr.label)
        if gr.column_name:
            parts.append(f"Column: {gr.column_name}")
        if gr.entity_type:
            parts.append(f"Type: {gr.entity_type}")

        # Add key properties
        props = gr.properties
        if props:
            key_fields = ["entity_type", "column_name", "confidence", "rationale", "aggregation"]
            extras = []
            for k in key_fields:
                v = props.get(k)
                if v is not None and k not in ("entity_type", "column_name"):
                    extras.append(f"{k}: {v}")
            if extras:
                parts.extend(extras)

        # Add relationship summary
        if gr.relationships:
            rel_types = set(r.get("rel_type", "related") for r in gr.relationships)
            if rel_types:
                parts.append(f"Relationships: {', '.join(sorted(rel_types))}")

        return " | ".join(parts) if parts else f"Entity {gr.entity_id}"


# Singleton
fusion_engine = FusionEngine()

__all__ = [
    "FusionEngine",
    "FusionMethod",
    "GraphResult",
    "VectorResult",
    "FusionResult",
    "FusionOutput",
    "fusion_engine",
]
