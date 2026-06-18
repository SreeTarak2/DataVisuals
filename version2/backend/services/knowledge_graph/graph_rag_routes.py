"""
Graph-RAG API Routes — FastAPI Endpoints
============================================

API endpoints for the Graph-RAG hybrid retrieval service.

Endpoints:
- GET /api/graph-rag/context — Get enriched context for a user query
- POST /api/graph-rag/context — Post a query and get enriched context back
- GET /api/graph-rag/health — Health check for all Graph-RAG components
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .graph_rag_service import GraphRAGService, GraphRAGContext, graph_rag_service

logger = logging.getLogger(__name__)


# ── Router ───────────────────────────────────────────────────────────────────

graph_rag_router = APIRouter(tags=["9. Graph-RAG Integration"])


# ── Dependencies ─────────────────────────────────────────────────────────────


def get_graph_rag_service() -> GraphRAGService:
    """Dependency injector for GraphRAGService singleton."""
    return graph_rag_service


# ── GET: Quick Context ───────────────────────────────────────────────────────


@graph_rag_router.get("/api/graph-rag/context")
async def get_graph_rag_context(
    query: str = Query(..., description="Natural language query"),
    dataset_id: str = Query(..., description="Dataset ID for filtering"),
    user_id: Optional[str] = Query(None, description="User ID for vector search filtering"),
    top_k: int = Query(5, description="Number of top results to return"),
    fusion_method: str = Query("rrf", description="Fusion method: rrf, linear, weighted"),
    enable_synthesis: bool = Query(True, description="Enable LLM answer synthesis"),
    service: GraphRAGService = Depends(get_graph_rag_service),
):
    """
    Get enriched context combining graph + vector retrieval for a user query.

    Args:
        query: Natural language query from user
        dataset_id: Dataset ID for filtering
        user_id: Optional user ID for vector search
        top_k: Number of fused results to return
        fusion_method: Fusion strategy (rrf, linear, weighted)
        enable_synthesis: Whether to generate LLM-synthesized answer

    Returns:
        GraphRAGContext with combined context, sources, and optional answer
    """
    from .fusion_engine import FusionMethod

    # Validate fusion method
    try:
        method = FusionMethod(fusion_method.lower())
    except ValueError:
        method = FusionMethod.RRF

    try:
        context: GraphRAGContext = await service.get_enriched_context(
            user_query=query,
            dataset_id=dataset_id,
            user_id=user_id,
            top_k=top_k,
            fusion_method=method,
            enable_synthesis=enable_synthesis,
        )

        if context.error:
            logger.warning(f"GraphRAG context generated with error: {context.error}")
            # Return partial results instead of failing
            return _context_to_response(context)

        return _context_to_response(context)

    except Exception as e:
        logger.error(f"GraphRAG context endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Graph-RAG context retrieval failed: {str(e)}",
        )


# ── POST: Full Context ──────────────────────────────────────────────────────


@graph_rag_router.post("/api/graph-rag/context")
async def post_graph_rag_context(
    body: Dict[str, Any],
    service: GraphRAGService = Depends(get_graph_rag_service),
):
    """
    Post a query and receive enriched context (same as GET but with POST body).

    Request body:
    ```json
    {
        "query": "Which customers have the highest revenue?",
        "dataset_id": "ds_123",
        "user_id": "user_456",
        "top_k": 10,
        "fusion_method": "rrf",
        "enable_synthesis": true
    }
    ```
    """
    from .fusion_engine import FusionMethod

    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="'query' field is required")

    dataset_id = body.get("dataset_id", "")
    if not dataset_id:
        raise HTTPException(status_code=400, detail="'dataset_id' field is required")

    fusion_method_str = body.get("fusion_method", "rrf")
    try:
        method = FusionMethod(fusion_method_str.lower())
    except ValueError:
        method = FusionMethod.RRF

    try:
        context = await service.get_enriched_context(
            user_query=query,
            dataset_id=dataset_id,
            user_id=body.get("user_id"),
            top_k=body.get("top_k", 5),
            fusion_method=method,
            enable_synthesis=body.get("enable_synthesis", True),
        )
        return _context_to_response(context)

    except Exception as e:
        logger.error(f"GraphRAG POST context failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Graph-RAG context retrieval failed: {str(e)}",
        )


# ── Health Check ─────────────────────────────────────────────────────────────


@graph_rag_router.get("/api/graph-rag/health")
async def graph_rag_health(
    service: GraphRAGService = Depends(get_graph_rag_service),
):
    """Check health of all Graph-RAG components."""
    try:
        health = await service.health_check()
        return health
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Graph-RAG health check failed: {str(e)}",
        )


# ── Response Formatter ────────────────────────────────────────────────────────


def _context_to_response(context: GraphRAGContext) -> Dict[str, Any]:
    """Convert GraphRAGContext to a clean API response dict."""
    return {
        "intent": context.intent,
        "entity_types_detected": context.entity_types_detected,
        "combined_context": context.combined_context,
        "sources": context.sources,
        "relevance_scores": context.relevance_scores,
        "answer": context.answer,
        "evidence": context.evidence,
        "confidence": context.confidence,
        "execution_time_ms": context.execution_time_ms,
        "graph_entities_count": len(context.graph_entities),
        "graph_relationships_count": len(context.graph_relationships),
        "vector_chunks_count": len(context.vector_chunks),
        "error": context.error,
    }


__all__ = ["graph_rag_router"]
