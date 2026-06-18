"""
Knowledge Graph Services
=========================

Dynamic entity extraction and graph storage for Signal.

This module provides:
- Schema profiling: Extract column metadata from any dataset
- Signal extraction: Multi-signal inference (name, type, value, context)
- Entity classification: Map signals to business entity types
- Confidence scoring: Weighted confidence with review flags
- Fallback handling: Safe fallback for uncertain cases
- Graph storage: FalkorDB/Neo4j integration for knowledge graphs
- Entity-to-graph: Transform extraction results to graph operations

Key Features:
- Works with ANY user-uploaded data (CSV, Excel, SQL)
- Domain-agnostic (no pre-loaded ontology required)
- Multi-signal inference for precision
- Confidence scoring with human-in-the-loop
- Correction memory for learning
- Graph storage for relationship-aware queries

Example Usage:
```python
from services.knowledge_graph import entity_extractor

# Extract entities from data
result = await entity_extractor.extract_from_columns(
    columns=[
        {"name": "customer_id", "type": "uuid"},
        {"name": "order_date", "type": "date"},
        {"name": "total_amount", "type": "decimal"},
    ],
    rows=rows_data,
    table_name="orders"
)

# Get results
for entity in result.entities:
    print(f"{entity.column_name} -> {entity.entity_type} (conf: {entity.confidence})")
```
"""

# Core models
from .models import (
    # NEW
    ColumnRole,
    EvidenceReliability,
    SemanticCandidate,
    EvidenceSource,
    EntityCluster,
    DiscoveredEntity,
    DatasetUnderstandingReport,
    # LEGACY
    EntityType,
    SignalType,
    ConfidenceLevel,
    ColumnProfile,
    SchemaProfile,
    SignalResult,
    EntityCandidate,
    ExtractionResult,
    ColumnAnalysisRequest,
    EntityCorrection,
    CorrectionMemory,
)

# Services
from .schema_profiler import SchemaProfiler, SchemaProfilingError, schema_profiler
from .signal_engine import SignalEngine, SignalExtractionError, signal_engine

# NEW: Layer 1 + Layer 2 pipeline
from .grouping_engine import GroupingEngine, grouping_engine
from .entity_validator import EntityValidator, entity_validator
from .entity_discovery import EntityDiscovery, entity_discovery

from .entity_classifier import (
    EntityClassifier,
    EntityClassificationError,
    entity_classifier,
)
from .confidence_scorer import (
    ConfidenceScorer,
    ConfidenceScoringError,
    confidence_scorer,
)
from .fallback_handler import FallbackHandler, fallback_handler
from .entity_extractor import EntityExtractor, EntityExtractionError, entity_extractor

# Graph storage (Phase 2)
from .exceptions import (
    GraphStorageError,
    GraphConnectionError,
    NodeNotFoundError,
    RelationshipError,
    QueryError,
    GraphTimeoutError,
)
from .graph_client import (
    FalkorDBClient,
    Neo4jClient,
    GraphNode,
    GraphRelationship,
    GraphQueryResult,
    get_graph_client,
    get_client,
)
from .entity_to_graph import EntityToGraphTransformer, create_transformer

# Entity Extraction API (Phase 4)
from .entity_extraction_routes import router as entity_extraction_router
from .entity_extraction_routes import (
    ExtractionRequest,
    SingleColumnRequest,
    CorrectionRequest,
    ExplainRequest,
)

# Graph-RAG Integration (Phase 3)
from .query_parser import QueryParser, QueryIntent, ParsedQuery, query_parser
from .fusion_engine import (
    FusionEngine,
    FusionMethod,
    FusionOutput,
    GraphResult,
    VectorResult,
    FusionResult,
    fusion_engine,
)
from .graph_rag_service import GraphRAGService, GraphRAGContext, GraphRAGConfig, graph_rag_service
from .graph_rag_routes import graph_rag_router

# Config
from .config import KnowledgeGraphConfig, kg_config


__all__ = [
    # NEW Models
    "ColumnRole",
    "EvidenceReliability",
    "SemanticCandidate",
    "EvidenceSource",
    "EntityCluster",
    "DiscoveredEntity",
    "DatasetUnderstandingReport",
    # Legacy Models
    "EntityType",
    "SignalType",
    "ConfidenceLevel",
    "ColumnProfile",
    "SchemaProfile",
    "SignalResult",
    "EntityCandidate",
    "ExtractionResult",
    "ColumnAnalysisRequest",
    "EntityCorrection",
    "CorrectionMemory",
    # Entity Extraction Services
    "SchemaProfiler",
    "SchemaProfilingError",
    "schema_profiler",
    "SignalEngine",
    "SignalExtractionError",
    "signal_engine",
    "EntityClassifier",
    "EntityClassificationError",
    "entity_classifier",
    "ConfidenceScorer",
    "ConfidenceScoringError",
    "confidence_scorer",
    "FallbackHandler",
    "fallback_handler",
    "EntityExtractor",
    "EntityExtractionError",
    "entity_extractor",
    # NEW: Layer 1 + Layer 2 pipeline
    "GroupingEngine",
    "grouping_engine",
    "EntityValidator",
    "entity_validator",
    "EntityDiscovery",
    "entity_discovery",
    # Graph Storage (Phase 2)
    "GraphStorageError",
    "GraphConnectionError",
    "NodeNotFoundError",
    "RelationshipError",
    "QueryError",
    "GraphTimeoutError",
    "FalkorDBClient",
    "Neo4jClient",
    "GraphNode",
    "GraphRelationship",
    "GraphQueryResult",
    "get_graph_client",
    "get_client",
    "EntityToGraphTransformer",
    "create_transformer",
    # Config
    "KnowledgeGraphConfig",
    "kg_config",
    # Graph-RAG Integration (Phase 3)
    "QueryParser",
    "QueryIntent",
    "ParsedQuery",
    "query_parser",
    "FusionEngine",
    "FusionMethod",
    "FusionOutput",
    "GraphResult",
    "VectorResult",
    "FusionResult",
    "fusion_engine",
    "GraphRAGService",
    "GraphRAGContext",
    "GraphRAGConfig",
    "graph_rag_service",
    "graph_rag_router",
]


__version__ = "1.1.0"
