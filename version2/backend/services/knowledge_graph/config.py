"""
Knowledge Graph Configuration
==============================

Configuration for entity extraction and graph services.
"""

import os
from typing import Optional


class KnowledgeGraphConfig:
    """Configuration for knowledge graph services"""

    # Entity Extraction
    ENTITY_EXTRACTION_ENABLED = (
        os.getenv("ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
    )
    ENTITY_EXTRACTION_SAMPLE_SIZE = int(
        os.getenv("ENTITY_EXTRACTION_SAMPLE_SIZE", "100")
    )

    # Confidence thresholds
    CONFIDENCE_STRONG_THRESHOLD = 0.90
    CONFIDENCE_GOOD_THRESHOLD = 0.70
    CONFIDENCE_TENTATIVE_THRESHOLD = 0.50

    # Signal weights
    SIGNAL_WEIGHT_COLUMN_NAME = float(os.getenv("SIGNAL_WEIGHT_COLUMN_NAME", "0.40"))
    SIGNAL_WEIGHT_DATA_TYPE = float(os.getenv("SIGNAL_WEIGHT_DATA_TYPE", "0.25"))
    SIGNAL_WEIGHT_SAMPLE_VALUES = float(
        os.getenv("SIGNAL_WEIGHT_SAMPLE_VALUES", "0.20")
    )
    SIGNAL_WEIGHT_CARDINALITY = float(os.getenv("SIGNAL_WEIGHT_CARDINALITY", "0.10"))
    SIGNAL_WEIGHT_DOMAIN_CONTEXT = float(
        os.getenv("SIGNAL_WEIGHT_DOMAIN_CONTEXT", "0.15")
    )

    # Fallback settings
    FALLBACK_ENABLED = True

    # Learning/Corrections
    CORRECTION_MEMORY_ENABLED = (
        os.getenv("CORRECTION_MEMORY_ENABLED", "true").lower() == "true"
    )
    CORRECTION_MEMORY_PATH = os.getenv(
        "CORRECTION_MEMORY_PATH", "./correction_memory.json"
    )

    # ========================================================================
    # Graph Storage Configuration (Phase 2)
    # ========================================================================

    # Graph database type: "falkordb" (recommended) or "neo4j" (alternative)
    GRAPH_DB_TYPE = os.getenv("GRAPH_DB_TYPE", "falkordb").lower()

    # FalkorDB configuration (recommended - open source, fast)
    FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
    FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD", "")
    FALKORDB_TIMEOUT = int(os.getenv("FALKORDB_TIMEOUT", "30"))
    FALKORDB_MAX_CONNECTIONS = int(os.getenv("FALKORDB_MAX_CONNECTIONS", "10"))

    # Neo4j configuration (alternative)
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

    # Graph operations
    GRAPH_BATCH_SIZE = int(os.getenv("GRAPH_BATCH_SIZE", "100"))
    GRAPH_QUERY_TIMEOUT_MS = int(os.getenv("GRAPH_QUERY_TIMEOUT_MS", "5000"))

    # Relationship detection
    AUTO_CREATE_RELATIONSHIPS = (
        os.getenv("AUTO_CREATE_RELATIONSHIPS", "true").lower() == "true"
    )
    MIN_CONFIDENCE_FOR_RELATIONSHIP = float(
        os.getenv("MIN_CONFIDENCE_FOR_RELATIONSHIP", "0.50")
    )

    @classmethod
    def to_dict(cls) -> dict:
        """Return config as dictionary (excluding passwords)"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if key.isupper()
            and not key.startswith("_")
            and "PASSWORD" not in key  # Exclude passwords
        }

    @classmethod
    def is_graph_available(cls) -> bool:
        """Check if graph database is configured"""
        if cls.GRAPH_DB_TYPE == "falkordb":
            return cls.FALKORDB_HOST is not None
        elif cls.GRAPH_DB_TYPE == "neo4j":
            return cls.NEO4J_URI is not None
        return False


# Singleton config instance
kg_config = KnowledgeGraphConfig()

__all__ = ["KnowledgeGraphConfig", "kg_config"]
