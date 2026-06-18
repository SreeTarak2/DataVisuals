"""
Graph-RAG Service — Hybrid Graph + Vector Context Retrieval
=============================================================

Core service that combines knowledge graph traversal with vector similarity search
to produce enriched context for LLM reasoning.

Pipeline:
  1. Parse user query → intent + entity references
  2. Extract entities from dataset schema (EntityExtractor integration)
  3. Query FalkorDB knowledge graph for related entities and relationships
  4. Query FAISS vector store for semantically similar historical chunks
  5. Fuse results using configured fusion strategy (RRF, linear, weighted)
  6. Synthesize LLM answer with evidence extraction and citation generation

Architecture:
  GraphRAGService
    ├── QueryParser         — NL → intent + entities + Cypher
    ├── EntityExtractor     — Dataset schema → entity candidates
    ├── FalkorDBClient      — Graph storage for entity relationships
    ├── FAISSVectorService  — Vector search for semantic chunks
    ├── FusionEngine        — Combine graph + vector results
    └── LLMRouter           — LLM synthesis with evidence grounding
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .query_parser import QueryParser, QueryIntent, ParsedQuery, query_parser
from .fusion_engine import (
    FusionEngine,
    FusionMethod,
    FusionOutput,
    GraphResult,
    VectorResult,
    fusion_engine,
)
from .graph_client import FalkorDBClient, get_client
from .entity_extractor import EntityExtractor, entity_extractor

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


@dataclass
class GraphRAGContext:
    """Enriched context combining graph + vector retrieval for LLM consumption."""

    combined_context: str = ""
    graph_entities: List[Dict[str, Any]] = field(default_factory=list)
    graph_relationships: List[Dict[str, Any]] = field(default_factory=list)
    vector_chunks: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    relevance_scores: Dict[str, float] = field(default_factory=dict)
    intent: str = "general"
    entity_types_detected: List[str] = field(default_factory=list)
    answer: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    execution_time_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class GraphRAGConfig:
    """Configuration for the GraphRAG service."""

    fusion_method: FusionMethod = FusionMethod.RRF
    top_k_graph: int = 20
    top_k_vector: int = 10
    top_k_fused: int = 10
    graph_traversal_depth: int = 2
    llm_synthesis_enabled: bool = True
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3
    llm_model_role: str = "simple_query"
    vector_score_threshold: float = 0.5
    enable_entity_extraction: bool = True


# ── Prompt Template for LLM Synthesis ────────────────────────────────────────

_GRAPH_RAG_SYNTHESIS_PROMPT = """You are a data analyst with access to structured knowledge graph context and historical data context. Answer the user's question using ONLY the evidence provided below.

## Knowledge Graph Context
The following entities and relationships were found in the knowledge graph:
{graph_context}

## Historical Data Context
The following historical data and schema information was retrieved:
{vector_context}

## Instructions
1. Answer the question based ONLY on the evidence above.
2. If the evidence doesn't contain enough information, say so clearly.
3. For each claim, cite the source (graph entity ID or chunk type).
4. Be specific with numbers, names, and relationships when available.
5. If there are contradictions in the evidence, flag them.
6. Format your response clearly with bullet points for multiple findings.

## User Question
{user_query}

## Your Analysis
"""


# ── Main Service ─────────────────────────────────────────────────────────────


class GraphRAGService:
    """
    Hybrid graph + vector context retrieval service.

    Combines structured knowledge graph data with semantic vector search
    to produce enriched, grounded context for LLM reasoning.

    Usage:
        context = await graph_rag_service.get_enriched_context(
            user_query="Which customers have the highest revenue?",
            dataset_id="ds_123",
        )
        # context.combined_context → formatted context string
        # context.answer → LLM-synthesized answer (if synthesis enabled)
        # context.evidence → cited evidence nodes
    """

    def __init__(
        self,
        config: Optional[GraphRAGConfig] = None,
        graph_client: Optional[FalkorDBClient] = None,
        parser: Optional[QueryParser] = None,
        fusion: Optional[FusionEngine] = None,
        extractor: Optional[EntityExtractor] = None,
    ):
        self.config = config or GraphRAGConfig()
        self.parser = parser or query_parser
        self.fusion = fusion or fusion_engine
        self.extractor = extractor or entity_extractor

        # Lazy initialization for optional dependencies
        self._graph_client = graph_client
        self._llm_router = None
        self._vector_service = None

        logger.info("GraphRAGService initialized")

    # ── Lazy Dependencies ───────────────────────────────────────────────────

    @property
    def graph_client(self) -> FalkorDBClient:
        """Lazy-initialized FalkorDB client."""
        if self._graph_client is None:
            self._graph_client = get_client()
        return self._graph_client

    @property
    def llm_router(self):
        """Lazy-initialized LLM router (avoids import-time dependency)."""
        if self._llm_router is None:
            from services.llm.router import llm_router

            self._llm_router = llm_router
        return self._llm_router

    @property
    def vector_service(self):
        """Lazy-initialized FAISS vector service."""
        if self._vector_service is None:
            from services.datasets.faiss_vector_service import faiss_vector_service

            self._vector_service = faiss_vector_service
        return self._vector_service

    # ── Main Entry Point ─────────────────────────────────────────────────────

    async def get_enriched_context(
        self,
        user_query: str,
        dataset_id: str,
        user_id: Optional[str] = None,
        top_k: int = 5,
        fusion_method: Optional[FusionMethod] = None,
        enable_synthesis: Optional[bool] = None,
    ) -> GraphRAGContext:
        """
        Get enriched context combining graph + vector retrieval.

        Flow:
        1. Parse query for intent and entity extraction
        2. Extract entities from dataset schema (if enabled)
        3. Query knowledge graph for related entities + relationships
        4. Query vector store for similar historical context
        5. Fuse results with relevance ranking
        6. (Optional) Synthesize LLM answer with evidence

        Args:
            user_query: Natural language query from user
            dataset_id: Dataset ID for filtering
            user_id: Optional user ID for vector search filtering
            top_k: Number of fused results to return
            fusion_method: Override fusion strategy
            enable_synthesis: Override LLM synthesis setting

        Returns:
            GraphRAGContext with combined context, sources, and optional answer
        """
        start_time = time.time()
        context = GraphRAGContext(intent="general")

        try:
            # ── Step 1: Extract entities from dataset schema ────────────
            extracted_entities: List[Dict[str, Any]] = []
            if self.config.enable_entity_extraction:
                try:
                    extracted_entities = await self._get_dataset_entities(dataset_id)
                except Exception as e:
                    logger.debug(f"Entity extraction skipped for {dataset_id}: {e}")

            # ── Step 2: Parse the user query ───────────────────────────
            parsed: ParsedQuery = await self.parser.parse(
                query=user_query,
                extracted_entities=extracted_entities,
                dataset_id=dataset_id,
            )
            context.intent = parsed.intent.value
            context.entity_types_detected = [e.value for e in parsed.entities]

            # ── Step 3: Query knowledge graph ──────────────────────────
            graph_results: List[GraphResult] = []
            if parsed.cypher_query:
                try:
                    graph_results = await self._query_graph(
                        parsed=parsed,
                        dataset_id=dataset_id,
                    )
                except Exception as e:
                    logger.warning(f"Graph query failed: {e}")
            else:
                # Fallback: use entity types from parsed query
                try:
                    graph_results = await self._query_graph_by_entities(
                        entity_types=[e.value for e in parsed.entities],
                        extracted_entities=extracted_entities,
                        dataset_id=dataset_id,
                    )
                except Exception as e:
                    logger.debug(f"Entity-based graph query failed: {e}")

            # Format graph results for context
            context.graph_entities = [
                {
                    "id": gr.entity_id,
                    "type": gr.entity_type,
                    "label": gr.label,
                    "column": gr.column_name,
                    "properties": gr.properties,
                }
                for gr in graph_results
            ]
            context.graph_relationships = list(
                dict.fromkeys(r for gr in graph_results for r in gr.relationships)
            )

            # ── Step 4: Query vector store ─────────────────────────────
            vector_chunks: List[Dict[str, Any]] = []
            try:
                vector_chunks = await self._query_vector_store(
                    query=user_query,
                    dataset_id=dataset_id,
                    user_id=user_id or "",
                )
            except Exception as e:
                logger.debug(f"Vector search skipped: {e}")
            context.vector_chunks = vector_chunks

            # ── Step 5: Fuse results ──────────────────────────────────
            method = fusion_method or self.config.fusion_method
            vector_results_formatted = [
                VectorResult(
                    chunk_id=vc.get("chunk_id", f"v{i}"),
                    content=vc.get("content", ""),
                    chunk_type=vc.get("chunk_type", "sample"),
                    similarity=vc.get("similarity", 0.0),
                    metadata=vc.get("metadata", {}),
                )
                for i, vc in enumerate(vector_chunks)
            ]

            fusion_output: FusionOutput = self.fusion.fuse(
                graph_results=graph_results,
                vector_results=vector_results_formatted,
                method=method,
                intent=parsed.intent,
                top_k=top_k,
            )

            # ── Step 6: Build combined context string ─────────────────
            context.sources = self._collect_sources(fusion_output)
            context.relevance_scores = {
                f"result_{i}": round(r.score, 3)
                for i, r in enumerate(fusion_output.fused_results[:5])
            }
            context.combined_context = self._build_context_string(fusion_output, parsed)

            # ── Step 7: (Optional) LLM synthesis ──────────────────────
            synthesis_enabled = (
                enable_synthesis
                if enable_synthesis is not None
                else self.config.llm_synthesis_enabled
            )
            if synthesis_enabled and context.combined_context.strip():
                try:
                    synthesis_result = await self._synthesize_answer(
                        user_query=user_query,
                        graph_context=context.combined_context,
                    )
                    context.answer = synthesis_result.get("answer")
                    context.evidence = synthesis_result.get("evidence", [])
                    context.confidence = synthesis_result.get("confidence", 0.5)
                except Exception as e:
                    logger.warning(f"LLM synthesis failed: {e}")
                    context.error = f"Synthesis failed: {str(e)}"

            execution_time = (time.time() - start_time) * 1000
            context.execution_time_ms = round(execution_time, 2)

            logger.info(
                f"GraphRAG context ready for query: "
                f"intent={context.intent}, "
                f"entities={context.entity_types_detected}, "
                f"graph={len(graph_results)}, vector={len(vector_chunks)}, "
                f"fused={len(fusion_output.fused_results)}, "
                f"synthesis={'yes' if context.answer else 'no'}, "
                f"time={context.execution_time_ms}ms"
            )

        except Exception as e:
            logger.error(f"GraphRAG enrichment failed: {e}", exc_info=True)
            context.error = str(e)

        return context

    # ── Step 3a: Query Graph via Cypher ─────────────────────────────────────

    async def _query_graph(
        self,
        parsed: ParsedQuery,
        dataset_id: str,
    ) -> List[GraphResult]:
        """Execute a Cypher query on the knowledge graph and format results."""
        if not parsed.cypher_query:
            return []

        try:
            # Execute Cypher query
            result = await self.graph_client.execute_query(
                query=parsed.cypher_query,
                parameters=parsed.cypher_params,
                timeout_ms=5000,
            )

            # Convert to GraphResults
            graph_results = []
            for node in result.nodes:
                props = node.properties or {}
                graph_results.append(
                    GraphResult(
                        entity_id=node.node_id,
                        entity_type=props.get("entity_type", "Unknown"),
                        column_name=props.get("column_name"),
                        label=":".join(node.labels) if node.labels else "Entity",
                        score=float(props.get("confidence", 0.5)),
                        properties=props,
                        relationships=[],  # Populated separately below
                    )
                )

            # Add relationships
            for rel in result.relationships:
                rel_dict = {
                    "rel_id": rel.rel_id,
                    "source_id": rel.source_node_id,
                    "target_id": rel.target_node_id,
                    "rel_type": rel.rel_type,
                    "properties": rel.properties,
                }
                # Attach to relevant graph results
                for gr in graph_results:
                    if gr.entity_id in (rel.source_node_id, rel.target_node_id):
                        gr.relationships.append(rel_dict)

            return graph_results

        except Exception as e:
            logger.warning(f"Graph Cypher query failed: {e}")
            return []

    # ── Step 3b: Query Graph by Entity Types (Fallback) ─────────────────────

    async def _query_graph_by_entities(
        self,
        entity_types: List[str],
        extracted_entities: List[Dict[str, Any]],
        dataset_id: str,
    ) -> List[GraphResult]:
        """
        Fallback graph query using entity types directly.

        Finds all nodes matching extracted entity types/column names
        and their immediate relationships.
        """
        if not entity_types and not extracted_entities:
            return []

        graph_results: List[GraphResult] = []

        # Query using entity type labels
        for et in entity_types:
            try:
                nodes = await self.graph_client.find_nodes(
                    label=et,
                    property_filters={"dataset_id": dataset_id},
                    dataset_id=dataset_id,
                    limit=20,
                )

                for node in nodes:
                    props = node.properties or {}
                    # Get relationships for this node
                    relationships = await self.graph_client.get_relationships(
                        node_id=node.node_id,
                        direction="both",
                    )

                    rel_dicts = [
                        {
                            "rel_id": r.rel_id,
                            "source_id": r.source_node_id,
                            "target_id": r.target_node_id,
                            "rel_type": r.rel_type,
                            "properties": r.properties,
                        }
                        for r in relationships
                    ]

                    graph_results.append(
                        GraphResult(
                            entity_id=node.node_id,
                            entity_type=et,
                            column_name=props.get("column_name"),
                            label=":".join(node.labels) if node.labels else et,
                            score=float(props.get("confidence", 0.5)),
                            properties=props,
                            relationships=rel_dicts,
                        )
                    )
            except Exception as e:
                logger.debug(f"Graph query for {et} failed: {e}")

        # Also query by column_name if extracted_entities available
        for entity in extracted_entities:
            if isinstance(entity, dict):
                col_name = entity.get("column_name", "")
                et = entity.get("entity_type", "")
                if col_name and et:
                    try:
                        nodes = await self.graph_client.find_nodes(
                            label="Entity",
                            property_filters={
                                "column_name": col_name,
                                "dataset_id": dataset_id,
                            },
                            dataset_id=dataset_id,
                            limit=5,
                        )
                        for node in nodes:
                            # Skip if already added
                            if any(gr.entity_id == node.node_id for gr in graph_results):
                                continue
                            props = node.properties or {}
                            relationships = await self.graph_client.get_relationships(
                                node_id=node.node_id, direction="both"
                            )
                            rel_dicts = [
                                {
                                    "rel_id": r.rel_id,
                                    "source_id": r.source_node_id,
                                    "target_id": r.target_node_id,
                                    "rel_type": r.rel_type,
                                    "properties": r.properties,
                                }
                                for r in relationships
                            ]
                            graph_results.append(
                                GraphResult(
                                    entity_id=node.node_id,
                                    entity_type=props.get("entity_type", et),
                                    column_name=col_name,
                                    label="Entity",
                                    score=float(props.get("confidence", 0.5)),
                                    properties=props,
                                    relationships=rel_dicts,
                                )
                            )
                    except Exception:
                        continue

        return graph_results

    # ── Step 4: Vector Store Query ──────────────────────────────────────────

    async def _query_vector_store(
        self,
        query: str,
        dataset_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Query FAISS vector store for semantically relevant chunks."""
        try:
            chunks = await self.vector_service.search_relevant_chunks(
                query=query,
                dataset_id=dataset_id,
                user_id=user_id,
                k=self.config.top_k_vector,
                score_threshold=self.config.vector_score_threshold,
            )
            return chunks or []
        except Exception as e:
            logger.debug(f"Vector search failed: {e}")
            return []

    # ── Step 6: Context String Assembly ─────────────────────────────────────

    def _build_context_string(
        self,
        fusion_output: FusionOutput,
        parsed: ParsedQuery,
    ) -> str:
        """Assemble fused results into a formatted context string for LLM ingestion."""
        if not fusion_output.fused_results:
            return ""

        parts: List[str] = []

        # Summary header
        parts.append(
            f"Query Analysis: intent={parsed.intent.value}, "
            f"entities={', '.join(parsed.entity_keywords)}, "
            f"confidence={parsed.confidence:.2f}"
        )

        # Graph entities section
        graph_entities = [r for r in fusion_output.fused_results if r.has_graph_source]
        if graph_entities:
            parts.append("\n--- Graph Entities ---")
            for r in graph_entities:
                parts.append(f"• {r.content} (relevance: {r.score:.3f})")
                if r.relationships:
                    for rel in r.relationships[:3]:  # Show top 3 relationships
                        parts.append(f"  └─ {rel.get('rel_type', 'related')}")

        # Vector chunks section
        vector_only = [r for r in fusion_output.fused_results if r.has_vector_source]
        if vector_only:
            parts.append("\n--- Historical Context ---")
            for r in vector_only:
                content_preview = r.content[:300] if r.content else "No content"
                parts.append(f"• {content_preview} (relevance: {r.score:.3f})")

        return "\n".join(parts)

    # ── Step 7: LLM Synthesis ───────────────────────────────────────────────

    async def _synthesize_answer(
        self,
        user_query: str,
        graph_context: str,
    ) -> Dict[str, Any]:
        """
        Synthesize an LLM answer from the fused context with evidence extraction.

        Returns:
            Dict with 'answer' (str), 'evidence' (list), 'confidence' (float)
        """
        prompt = _GRAPH_RAG_SYNTHESIS_PROMPT.format(
            graph_context=graph_context[:6000],  # Truncate to fit context window
            vector_context="(embedded in graph context above)",
            user_query=user_query,
        )

        try:
            response = await self.llm_router.call(
                prompt=prompt,
                model_role=self.config.llm_model_role,
                expect_json=False,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            )

            if not response or not isinstance(response, str):
                return {"answer": None, "evidence": [], "confidence": 0.0}

            return {
                "answer": response.strip(),
                "evidence": self._extract_evidence_from_response(response),
                "confidence": 0.7,  # Base confidence — could be refined
            }

        except Exception as e:
            logger.warning(f"LLM synthesis call failed: {e}")
            return {"answer": None, "evidence": [], "confidence": 0.0}

    # ── Entity Extraction from Dataset ──────────────────────────────────────

    async def _get_dataset_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Extract entity candidates for a dataset using the EntityExtractor.

        Falls back to graph-stored entities if extraction pipeline is not available.

        Returns:
            List of dicts with 'column_name' and 'entity_type' keys
        """
        try:
            # Try to get entities already stored in the graph
            nodes = await self.graph_client.find_nodes(
                label="Entity",
                property_filters={"dataset_id": dataset_id},
                dataset_id=dataset_id,
                limit=100,
            )
            if nodes:
                return [
                    {
                        "column_name": n.properties.get("column_name", ""),
                        "entity_type": n.properties.get("entity_type", "GenericEntity"),
                        "confidence": n.properties.get("confidence", 0.5),
                    }
                    for n in nodes
                    if n.properties.get("column_name")
                ]
        except Exception:
            pass

        # If nothing in graph, try to use the extraction pipeline
        # (requires dataset with schema information)
        return []

    # ── Evidence Extraction ─────────────────────────────────────────────────

    @staticmethod
    def _extract_evidence_from_response(response: str) -> List[Dict[str, Any]]:
        """
        Extract cited evidence from an LLM response.

        Looks for:
        - Entity IDs (entity_xxx or similar patterns)
        - Quoted references to specific data points
        - Bullet-pointed findings that reference specific entities
        """
        import re

        evidence: List[Dict[str, Any]] = []

        # Pattern 1: Entity references like "Entity: Customer" or "Customer (revenue)"
        entity_refs = re.findall(r"(?:Entity|entity)[:\s]+([A-Z][a-zA-Z]+)", response)
        for ref in entity_refs:
            evidence.append(
                {
                    "type": "entity_reference",
                    "value": ref,
                    "source": "graph",
                }
            )

        # Pattern 2: Numeric data points
        data_points = re.findall(
            r"(\$?[\d,]+\.?\d*\s*(?:%|million|billion|thousand|K|M|B)?)",
            response,
        )
        for point in data_points[:5]:
            evidence.append(
                {
                    "type": "data_point",
                    "value": point.strip(),
                    "source": "context",
                }
            )

        # Pattern 3: Relationship references
        rel_refs = re.findall(
            r"(\w+)\s+(?:is|are|was|were)\s+(?:related|connected|linked|associated)\s+(?:to|with)\s+(\w+)",
            response,
            re.IGNORECASE,
        )
        for source, target in rel_refs:
            evidence.append(
                {
                    "type": "relationship",
                    "source_entity": source,
                    "target_entity": target,
                    "source": "graph",
                }
            )

        return evidence

    # ── Source Collection ───────────────────────────────────────────────────

    @staticmethod
    def _collect_sources(fusion_output: FusionOutput) -> List[str]:
        """Collect unique source types from fused results."""
        sources = set()
        for r in fusion_output.fused_results:
            sources.update(r.sources)
        return sorted(sources)

    # ── Quick Context (Non-Synthesis) ───────────────────────────────────────

    async def get_quick_context(
        self,
        user_query: str,
        dataset_id: str,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Get enriched context as a plain string (no LLM synthesis).

        Useful as a drop-in enhancement for existing chat pipelines.
        """
        context = await self.get_enriched_context(
            user_query=user_query,
            dataset_id=dataset_id,
            user_id=user_id,
            enable_synthesis=False,
        )
        return context.combined_context

    # ── Health Check ────────────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Check availability of all dependencies."""
        status = {
            "status": "ok",
            "components": {},
        }

        # Check graph client
        try:
            graph_ok = (
                self.graph_client.is_connected()
                if hasattr(self.graph_client, "is_connected")
                else False
            )
            if callable(graph_ok):
                graph_ok = graph_ok()
            status["components"]["graph_client"] = {
                "available": graph_ok,
                "type": "falkordb" if graph_ok else "unavailable",
            }
        except Exception as e:
            status["components"]["graph_client"] = {
                "available": False,
                "error": str(e),
            }

        # Check vector service
        try:
            vs = self.vector_service
            status["components"]["vector_service"] = {
                "available": vs.enable_vector_search
                if hasattr(vs, "enable_vector_search")
                else False,
            }
        except Exception as e:
            status["components"]["vector_service"] = {"available": False, "error": str(e)}

        # Check entity extractor
        try:
            ex = await self.extractor.health_check()
            status["components"]["entity_extractor"] = (
                ex if isinstance(ex, dict) else {"available": True}
            )
        except Exception as e:
            status["components"]["entity_extractor"] = {"available": False, "error": str(e)}

        # Check LLM router
        try:
            lr = self.llm_router
            status["components"]["llm_router"] = {
                "available": lr.use_openrouter if hasattr(lr, "use_openrouter") else False,
            }
        except Exception as e:
            status["components"]["llm_router"] = {"available": False, "error": str(e)}

        # Overall status
        all_available = all(c.get("available", False) for c in status["components"].values())
        status["status"] = "ok" if all_available else "degraded"

        return status


# Singleton instance
graph_rag_service = GraphRAGService()

__all__ = [
    "GraphRAGService",
    "GraphRAGContext",
    "GraphRAGConfig",
    "graph_rag_service",
]
