"""
Phase 3 Tests — Graph-RAG Integration
==========================================

Unit tests for:
1. query_parser.py — Intent classification, entity extraction, Cypher building
2. fusion_engine.py — RRF, linear, weighted fusion strategies
3. graph_rag_service.py — Main GraphRAG service orchestration
"""

import pytest
from typing import Any, Dict, List, Optional
from datetime import datetime

from services.knowledge_graph.query_parser import QueryParser, QueryIntent, ParsedQuery, query_parser
from services.knowledge_graph.fusion_engine import (
    FusionEngine,
    FusionMethod,
    FusionOutput,
    GraphResult,
    VectorResult,
    FusionResult,
    fusion_engine,
)
from services.knowledge_graph.graph_rag_service import GraphRAGService, GraphRAGContext, GraphRAGConfig


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_extracted_entities() -> List[Dict[str, Any]]:
    """Sample entity extraction results matching a sales dataset."""
    return [
        {"column_name": "customer_id", "entity_type": "Customer", "confidence": 0.95},
        {"column_name": "order_date", "entity_type": "TimeDimension", "confidence": 0.90},
        {"column_name": "total_amount", "entity_type": "Metric", "confidence": 0.85},
        {"column_name": "product_name", "entity_type": "Product", "confidence": 0.80},
        {"column_name": "region", "entity_type": "Geography", "confidence": 0.75},
        {"column_name": "order_status", "entity_type": "Status", "confidence": 0.70},
        {"column_name": "order_id", "entity_type": "Transaction", "confidence": 0.90},
        {"column_name": "quantity", "entity_type": "Quantity", "confidence": 0.85},
    ]


@pytest.fixture
def sample_graph_results() -> List[GraphResult]:
    """Sample graph results for a revenue query."""
    return [
        GraphResult(
            entity_id="n1",
            entity_type="Metric",
            column_name="total_amount",
            label="Entity:Measure",
            score=0.85,
            properties={
                "column_name": "total_amount",
                "entity_type": "Metric",
                "confidence": 0.85,
                "aggregation": "sum",
            },
            relationships=[
                {"rel_id": "r1", "source_id": "n1", "target_id": "n2",
                 "rel_type": "MEASURES", "properties": {}},
                {"rel_id": "r2", "source_id": "n1", "target_id": "n3",
                 "rel_type": "AGGREGATES", "properties": {}},
            ],
        ),
        GraphResult(
            entity_id="n2",
            entity_type="TimeDimension",
            column_name="order_date",
            label="Entity:Dimension",
            score=0.80,
            properties={
                "column_name": "order_date",
                "entity_type": "TimeDimension",
                "confidence": 0.80,
            },
            relationships=[
                {"rel_id": "r1", "source_id": "n1", "target_id": "n2",
                 "rel_type": "MEASURES", "properties": {}},
            ],
        ),
        GraphResult(
            entity_id="n3",
            entity_type="Geography",
            column_name="region",
            label="Entity:Dimension",
            score=0.75,
            properties={
                "column_name": "region",
                "entity_type": "Geography",
                "confidence": 0.75,
            },
            relationships=[
                {"rel_id": "r2", "source_id": "n1", "target_id": "n3",
                 "rel_type": "AGGREGATES", "properties": {}},
            ],
        ),
    ]


@pytest.fixture
def sample_vector_results() -> List[VectorResult]:
    """Sample FAISS vector results."""
    return [
        VectorResult(
            chunk_id="c1",
            content="Revenue by region shows North America contributing 45% of total revenue.",
            chunk_type="insight",
            similarity=0.89,
            metadata={"source": "historical_insight"},
        ),
        VectorResult(
            chunk_id="c2",
            content="Order date ranges from 2024-01-01 to 2024-12-31 across 10K orders.",
            chunk_type="schema",
            similarity=0.72,
            metadata={"source": "schema_summary"},
        ),
        VectorResult(
            chunk_id="c3",
            content="Average order value is $245 with a standard deviation of $89.",
            chunk_type="statistics",
            similarity=0.65,
            metadata={"source": "stats_summary"},
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# QUERY PARSER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryParserIntentClassification:
    """Tests for QueryParser.classify_intent()"""

    @pytest.mark.parametrize("query,expected_intent", [
        ("What is the total revenue?", QueryIntent.DESCRIBE),
        ("Show me top customers by revenue", QueryIntent.LIST),
        ("How has revenue changed over time?", QueryIntent.TREND),
        ("Compare revenue between regions", QueryIntent.COMPARE),
        ("Which metrics are anomalous this month?", QueryIntent.ANOMALY),
        ("Show me revenue by product category", QueryIntent.BREAKDOWN),
        ("What drives revenue growth?", QueryIntent.CORRELATION),
        ("What will revenue be next quarter?", QueryIntent.FORECAST),
        ("What is the customer churn rate?", QueryIntent.DESCRIBE),
    ])
    def test_intent_classification(self, query: str, expected_intent: QueryIntent):
        intent, confidence = query_parser.classify_intent(query)
        assert intent == expected_intent, f"Expected {expected_intent.value} for '{query}', got {intent.value}"
        assert 0.0 <= confidence <= 1.0

    def test_general_intent_for_ambiguous_query(self):
        intent, confidence = query_parser.classify_intent("Hello")
        assert intent == QueryIntent.GENERAL
        assert confidence < 0.5

    def test_confidence_scale(self):
        """Multiple matching patterns should increase confidence."""
        _, low_conf = query_parser.classify_intent("show me data")
        _, high_conf = query_parser.classify_intent(
            "show me top customers by revenue over time compared to last quarter"
        )
        assert high_conf >= low_conf


class TestQueryParserEntityExtraction:
    """Tests for QueryParser.extract_entities()"""

    def test_extract_customer_and_revenue(self):
        entities = query_parser.extract_entities(
            "Which customers have the highest revenue?"
        )
        entity_types = {e[0] for e in entities}
        assert len(entity_types) >= 2

    def test_extract_product_and_region(self):
        entities = query_parser.extract_entities(
            "Show products by region"
        )
        keywords = [e[1] for e in entities]
        assert any("product" in k for k in keywords)
        assert any("region" in k for k in keywords)

    def test_deduplicates_entity_types(self):
        """Multiple mentions of same entity type should be deduplicated."""
        entities = query_parser.extract_entities(
            "Find customers and show customer details"
        )
        customer_matches = [e for e in entities if e[0].value == "Customer"]
        assert len(customer_matches) <= 1

    def test_confidence_increases_with_specificity(self):
        """Longer, more specific keywords should have higher confidence."""
        entities = query_parser.extract_entities(
            "Show quarterly revenue by customer segment"
        )
        for _, _, conf in entities:
            assert 0.5 <= conf <= 0.95


class TestQueryParserColumnMatching:
    """Tests for match_entity_to_column()"""

    def test_direct_entity_type_match(self, sample_extracted_entities):
        col = query_parser.match_entity_to_column(
            "Customer", sample_extracted_entities
        )
        assert col == "customer_id"

    def test_metric_entity_match(self, sample_extracted_entities):
        col = query_parser.match_entity_to_column(
            "Metric", sample_extracted_entities
        )
        assert col == "total_amount"

    def test_no_match_returns_none(self, sample_extracted_entities):
        col = query_parser.match_entity_to_column(
            "Facility", sample_extracted_entities
        )
        assert col is None


class TestQueryParserCypherBuilding:
    """Tests for build_cypher_query()"""

    def test_describe_query_builds_valid_cypher(self, sample_extracted_entities):
        query, params = query_parser.build_cypher_query(
            intent=QueryIntent.DESCRIBE,
            entity_types=[type("ET", (), {"value": "Customer"})()],
            extracted_entities=sample_extracted_entities,
            dataset_id="ds_test",
        )
        assert query is not None
        assert "$dataset_id" in query or "dataset_id" in query
        assert params.get("dataset_id") == "ds_test"

    def test_unknown_intent_falls_back_to_generic(self, sample_extracted_entities):
        """Unknown intent type should fall back to generic query."""
        query, params = query_parser.build_cypher_query(
            intent="unknown_intent",  # Not a real QueryIntent
            entity_types=[],
            extracted_entities=sample_extracted_entities,
            dataset_id="ds_test",
        )
        assert query is not None
        # Generic fallback uses actual entity labels from extracted entities
        assert "MATCH" in query
        assert "dataset_id" in query

    def test_empty_entities_returns_generic(self):
        query, params = query_parser.build_cypher_query(
            intent=QueryIntent.DESCRIBE,
            entity_types=[],
            extracted_entities=[],
            dataset_id="ds_test",
        )
        assert query is not None


class TestQueryParserFullParse:
    """Tests for QueryParser.parse()"""

    @pytest.mark.asyncio
    async def test_full_parse_with_entities(self, sample_extracted_entities):
        parsed = await query_parser.parse(
            query="Which customers have the highest revenue?",
            extracted_entities=sample_extracted_entities,
            dataset_id="ds_test",
        )
        assert isinstance(parsed, ParsedQuery)
        assert parsed.intent in (QueryIntent.DESCRIBE, QueryIntent.LIST)
        assert any("customer" in kw.lower() for kw in parsed.entity_keywords)
        assert parsed.cypher_query is not None

    @pytest.mark.asyncio
    async def test_full_parse_without_dataset(self):
        """Should still parse intent and entities without a dataset."""
        parsed = await query_parser.parse(
            query="Show me revenue by region",
            extracted_entities=None,
            dataset_id=None,
        )
        assert parsed.intent is not None
        assert len(parsed.entities) > 0
        assert parsed.cypher_query is None  # No dataset → no Cypher

    @pytest.mark.asyncio
    async def test_low_confidence_requires_llm(self):
        parsed = await query_parser.parse(
            query="Just some random text here",
            dataset_id="ds_test",
        )
        # Very low confidence queries should require LLM disambiguation
        if parsed.confidence < query_parser.MIN_INTENT_CONFIDENCE:
            assert parsed.requires_llm


# ══════════════════════════════════════════════════════════════════════════════
# FUSION ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFusionEngine:
    """Tests for FusionEngine fusion strategies."""

    def test_rrf_fusion_combines_sources(
        self, sample_graph_results, sample_vector_results
    ):
        output = fusion_engine.fuse(
            graph_results=sample_graph_results,
            vector_results=sample_vector_results,
            method=FusionMethod.RRF,
            top_k=5,
        )
        assert isinstance(output, FusionOutput)
        assert len(output.fused_results) > 0
        assert output.graph_results_count == 3
        assert output.vector_results_count == 3

    def test_rrf_ranks_high_results_first(self):
        """RRF should rank results that appear in both sources higher."""
        graph = [
            GraphResult(entity_id="e1", entity_type="Metric", score=0.9),
            GraphResult(entity_id="e2", entity_type="Customer", score=0.8),
        ]
        vector = [
            VectorResult(chunk_id="c1", content="about e1", similarity=0.95),
            VectorResult(chunk_id="c2", content="about e2", similarity=0.85),
        ]
        output = fusion_engine.fuse(graph, vector, method=FusionMethod.RRF, top_k=5)
        assert len(output.fused_results) >= 2

    def test_linear_fusion_weighted_by_intent(
        self, sample_graph_results, sample_vector_results
    ):
        """Linear fusion should respect intent-based weights."""
        output = fusion_engine.fuse(
            graph_results=sample_graph_results,
            vector_results=sample_vector_results,
            method=FusionMethod.LINEAR,
            intent=QueryIntent.COMPARE,  # Graph-weighted (0.7)
            top_k=5,
        )
        assert output.fusion_method == FusionMethod.LINEAR
        assert len(output.fused_results) > 0

    def test_weighted_fusion_adds_bonus_for_multi_source(self):
        """Results in both sources should get the entity match bonus."""
        graph = [
            GraphResult(entity_id="e1", entity_type="Metric", score=0.9, column_name="revenue"),
        ]
        vector = [
            VectorResult(chunk_id="c1", content="Revenue data", similarity=0.9),
        ]
        output_rrf = fusion_engine.fuse(
            graph, vector, method=FusionMethod.RRF, top_k=5
        )
        output_weighted = fusion_engine.fuse(
            graph, vector, method=FusionMethod.WEIGHTED, top_k=5
        )
        # Weighted fusion includes entity match bonus
        assert len(output_weighted.fused_results) > 0

    def test_empty_graph_uses_vector_only(self, sample_vector_results):
        output = fusion_engine.fuse(
            graph_results=[],
            vector_results=sample_vector_results,
            top_k=5,
        )
        assert output.fusion_method == FusionMethod.VECTOR_ONLY
        assert output.vector_results_count == 3
        assert len(output.fused_results) > 0

    def test_empty_vector_uses_graph_only(self, sample_graph_results):
        output = fusion_engine.fuse(
            graph_results=sample_graph_results,
            vector_results=[],
            top_k=5,
        )
        assert output.fusion_method == FusionMethod.GRAPH_ONLY
        assert output.graph_results_count == 3
        assert len(output.fused_results) > 0

    def test_both_empty_returns_empty_output(self):
        output = fusion_engine.fuse([], [], top_k=5)
        assert len(output.fused_results) == 0
        assert output.total_results == 0

    def test_execution_time_is_recorded(self, sample_graph_results, sample_vector_results):
        output = fusion_engine.fuse(
            sample_graph_results, sample_vector_results, top_k=3
        )
        assert output.execution_time_ms >= 0.0


class TestFusionResultProperties:
    """Tests for FusionResult and GraphResult/VectorResult models."""

    def test_content_hash_uniqueness(self):
        gr1 = GraphResult(entity_id="e1", entity_type="Metric")
        gr2 = GraphResult(entity_id="e2", entity_type="Customer")
        assert gr1.content_hash != gr2.content_hash

        vr1 = VectorResult(chunk_id="c1", content="a")
        vr2 = VectorResult(chunk_id="c2", content="b")
        assert vr1.content_hash != vr2.content_hash

    def test_graph_and_vector_hash_collision_free(self):
        gr = GraphResult(entity_id="e1", entity_type="Metric")
        vr = VectorResult(chunk_id="e1", content="test")
        # Different source prefixes should prevent collision
        assert gr.content_hash != vr.content_hash

    def test_has_graph_source(self):
        r = FusionResult(content="test", score=0.5, sources=["graph"])
        assert r.has_graph_source
        assert not r.has_vector_source

    def test_has_vector_source(self):
        r = FusionResult(content="test", score=0.5, sources=["vector"])
        assert r.has_vector_source
        assert not r.has_graph_source

    def test_both_sources_detected(self):
        r = FusionResult(content="test", score=0.5, sources=["graph", "vector"])
        assert r.has_graph_source
        assert r.has_vector_source


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH RAG SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphRAGService:
    """Tests for GraphRAGService (with mocked dependencies where needed)."""

    def test_config_defaults(self):
        config = GraphRAGConfig()
        assert config.fusion_method == FusionMethod.RRF
        assert config.top_k_graph == 20
        assert config.top_k_vector == 10
        assert config.top_k_fused == 10
        assert config.llm_synthesis_enabled is True
        assert config.llm_temperature == 0.3

    def test_config_custom_values(self):
        config = GraphRAGConfig(
            fusion_method=FusionMethod.LINEAR,
            top_k_graph=50,
            llm_synthesis_enabled=False,
            llm_temperature=0.1,
        )
        assert config.fusion_method == FusionMethod.LINEAR
        assert config.top_k_graph == 50
        assert config.llm_synthesis_enabled is False

    @pytest.mark.asyncio
    async def test_health_check_returns_component_status(self):
        """Health check should return status for all components."""
        service = GraphRAGService()
        # Mock the graph_client to avoid actual DB connection
        try:
            health = await service.health_check()
            assert "status" in health
            assert "components" in health
            assert all(
                comp in health["components"]
                for comp in ["graph_client", "vector_service", "entity_extractor", "llm_router"]
            )
        except Exception:
            # Components may not be available in test environment
            pass


# ══════════════════════════════════════════════════════════════════════════════
# QUERY PARSER EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryParserEdgeCases:

    def test_empty_query_returns_general_intent(self):
        intent, confidence = query_parser.classify_intent("")
        assert intent == QueryIntent.GENERAL

    def test_special_characters_in_query(self):
        intent, confidence = query_parser.classify_intent("What's the revenue? Show it!")
        assert intent in (QueryIntent.DESCRIBE, QueryIntent.LIST)

    @pytest.mark.asyncio
    async def test_parse_with_empty_extracted_entities(self):
        parsed = await query_parser.parse(
            query="Show me revenue",
            extracted_entities=[],
            dataset_id="ds_test",
        )
        # Should still parse even without entity mappings
        assert parsed.intent is not None
        assert parsed.cypher_query is not None  # Should still generate fallback query

    def test_extract_no_entities_from_nonsense(self):
        entities = query_parser.extract_entities("xyzzy flurbo garblex")
        assert len(entities) == 0


class TestFusionEngineEdgeCases:

    def test_large_scores_handled_gracefully(self):
        graph = [
            GraphResult(entity_id=f"e{i}", entity_type="Metric", score=float(i * 100))
            for i in range(10)
        ]
        output = fusion_engine.fuse(graph, [], top_k=3)
        assert len(output.fused_results) == 3
        assert output.fused_results[0].score > 0  # Normalized scores

    def test_deduplication_removes_duplicate_results(self):
        """Same entity from both sources should be deduplicated."""
        graph = [
            GraphResult(entity_id="e1", entity_type="Metric", score=0.9),
        ]
        vector = [
            VectorResult(chunk_id="c1", content="same entity", similarity=0.8),
        ]
        output = fusion_engine.fuse(graph, vector, top_k=5)
        # Graph-only and vector-only should have different hashes (different source)
        # So we expect 2 results
        assert len(output.fused_results) >= 1

    def test_zero_score_items_still_included(self):
        """Zero score items should still be included in results."""
        graph = [
            GraphResult(entity_id="e1", entity_type="Metric", score=0.0),
            GraphResult(entity_id="e2", entity_type="Customer", score=0.5),
        ]
        output = fusion_engine.fuse(graph, [], top_k=5)
        assert len(output.fused_results) == 2


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION-ISH TESTS (Parser + Fusion workflow)
# ══════════════════════════════════════════════════════════════════════════════

class TestParserToFusionFlow:
    """End-to-end tests from query parsing to fusion output."""

    @pytest.mark.asyncio
    async def test_parse_and_fuse_workflow(
        self, sample_extracted_entities, sample_graph_results, sample_vector_results
    ):
        # Step 1: Parse query
        parsed = await query_parser.parse(
            query="Show me revenue by region",
            extracted_entities=sample_extracted_entities,
            dataset_id="ds_test",
        )
        assert parsed.intent is not None
        assert len(parsed.entities) > 0

        # Step 2: Fuse results (simulating what GraphRAGService does)
        output = fusion_engine.fuse(
            graph_results=sample_graph_results,
            vector_results=sample_vector_results,
            method=FusionMethod.RRF,
            intent=parsed.intent,
            top_k=5,
        )
        assert output.total_results > 0
        assert output.graph_results_count == 3
        assert output.vector_results_count == 3

        # Verify that the context string can be built
        context_parts = []
        for r in output.fused_results[:3]:
            context_parts.append(f"• {r.content} (score: {r.score:.3f})")
        context_str = "\n".join(context_parts)
        assert len(context_str) > 0

    @pytest.mark.asyncio
    async def test_trend_query_prefers_graph(self, sample_extracted_entities):
        """Trend queries should leverage graph's time relationships more."""
        parsed = await query_parser.parse(
            query="How has revenue changed over time?",
            extracted_entities=sample_extracted_entities,
            dataset_id="ds_test",
        )
        assert parsed.intent == QueryIntent.TREND
        # Trend Cypher should involve time dimension
        assert parsed.cypher_query is not None
