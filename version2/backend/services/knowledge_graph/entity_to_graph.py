"""
Entity to Graph Transformer
=============================

Transforms entity extraction results into graph storage operations.

Converts:
- Entity candidates → Graph nodes
- Column relationships → Graph edges
- Metadata → Node properties

Key features:
- Automatic relationship detection between entities
- Confidence-based filtering
- Batch operations for performance
- Correction-aware updates
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime

from .models import EntityCandidate, ExtractionResult, EntityType
from .graph_client import GraphNode, GraphRelationship, FalkorDBClient

logger = logging.getLogger(__name__)


class EntityToGraphTransformer:
    """
    Transforms entity extraction results into graph operations.

    Key transformations:
    1. Entity candidates → Nodes with labels = entity types
    2. Column co-occurrence → Implicit relationships
    3. Schema relationships → Explicit edges
    4. Confidence scores → Node properties
    """

    # Relationship types for different entity connections
    RELATIONSHIP_TYPES = {
        # Dimension → Metric relationships
        (EntityType.TIMEDIMENSION, EntityType.METRIC): "MEASURES",
        (EntityType.TIMEDIMENSION, EntityType.AMOUNT): "MEASURES",
        (EntityType.TIMEDIMENSION, EntityType.QUANTITY): "MEASURES",
        # Geography → Metric relationships
        (EntityType.GEOGRAPHY, EntityType.METRIC): "AGGREGATES",
        (EntityType.GEOGRAPHY, EntityType.AMOUNT): "AGGREGATES",
        # Entity → Transaction relationships
        (EntityType.CUSTOMER, EntityType.TRANSACTION): "PLACES",
        (EntityType.EMPLOYEE, EntityType.TRANSACTION): "PROCESSES",
        (EntityType.PATIENT, EntityType.TRANSACTION): "UNDERGOES",
        # Entity → Product relationships
        (EntityType.CUSTOMER, EntityType.PRODUCT): "PURCHASES",
        (EntityType.ORDER, EntityType.PRODUCT): "CONTAINS",
        # Classification relationships
        (EntityType.GEOGRAPHY, EntityType.CLASSIFICATION): "CLASSIFIES",
        # Category → related
        (EntityType.CATEGORY, EntityType.METRIC): "CATEGORIZES",
    }

    def __init__(self, graph_client: FalkorDBClient):
        self.graph_client = graph_client

    async def transform_and_store(
        self,
        extraction_result: ExtractionResult,
        dataset_id: str,
        store_relationships: bool = True,
    ) -> Dict[str, Any]:
        """
        Transform extraction result and store in graph.

        Args:
            extraction_result: Result from entity extractor
            dataset_id: Dataset identifier
            store_relationships: Whether to create relationships

        Returns:
            Summary of stored nodes and relationships
        """
        logger.info(
            f"Transforming {len(extraction_result.entities)} entities for dataset {dataset_id}"
        )

        # Step 1: Create entity nodes
        node_ids = await self._create_entity_nodes(
            extraction_result.entities, dataset_id
        )

        # Step 2: Create relationships between entities
        relationship_ids = []
        if store_relationships:
            relationship_ids = await self._create_entity_relationships(
                extraction_result.entities, node_ids, dataset_id
            )

        return {
            "nodes_created": len(node_ids),
            "relationships_created": len(relationship_ids),
            "dataset_id": dataset_id,
            "table_name": extraction_result.table_name,
        }

    async def _create_entity_nodes(
        self,
        entities: List[EntityCandidate],
        dataset_id: str,
    ) -> Dict[str, str]:
        """
        Create graph nodes for entities.

        Returns:
            Dict mapping column_name to node_id
        """
        node_id_map: Dict[str, str] = {}

        # Filter by confidence threshold
        min_confidence = 0.30
        relevant_entities = [e for e in entities if e.confidence >= min_confidence]

        logger.info(
            f"Creating {len(relevant_entities)} entity nodes (filtered from {len(entities)})"
        )

        for entity in relevant_entities:
            try:
                # Get labels from entity type
                labels = self._get_node_labels(entity.entity_type)

                # Build properties
                properties = {
                    "column_name": entity.column_name,
                    "entity_type": entity.entity_type.value,
                    "confidence": entity.confidence,
                    "confidence_level": entity.confidence_level.value,
                    "rationale": entity.rationale[:500],  # Limit length
                    "needs_review": entity.needs_review,
                    "is_fallback": entity.is_fallback,
                    # Include alternatives as JSON string
                    "alternatives": ",".join(
                        [a.get("alt_type", "") for a in entity.alternatives[:3]]
                    )
                    if entity.alternatives
                    else "",
                }

                # Add sample signal info
                if entity.signals:
                    signal_summary = [
                        f"{s.signal_type.value}:{s.confidence:.2f}"
                        for s in entity.signals[:3]
                    ]
                    properties["signal_summary"] = "|".join(signal_summary)

                # Create node
                node_id = await self.graph_client.create_node(
                    labels=labels,
                    properties=properties,
                    dataset_id=dataset_id,
                )

                node_id_map[entity.column_name] = node_id

            except Exception as e:
                logger.warning(f"Failed to create node for {entity.column_name}: {e}")
                continue

        logger.info(f"Created {len(node_id_map)} entity nodes")
        return node_id_map

    async def _create_entity_relationships(
        self,
        entities: List[EntityCandidate],
        node_id_map: Dict[str, str],
        dataset_id: str,
    ) -> List[str]:
        """
        Create relationships between entity nodes.

        Detects relationships based on:
        - Entity type combinations (dimension → metric)
        - Schema proximity (adjacent columns)
        - Confidence levels
        """
        relationship_ids = []

        # Group entities by type
        entities_by_type: Dict[str, List[Tuple[EntityCandidate, str]]] = {}
        for entity in entities:
            if entity.column_name not in node_id_map:
                continue

            etype = entity.entity_type.value
            if etype not in entities_by_type:
                entities_by_type[etype] = []
            entities_by_type[etype].append((entity, node_id_map[entity.column_name]))

        # Find relationships based on type combinations
        # Use a set to track processed pairs (avoids lexicographic comparison bug)
        processed_pairs: Set[Tuple[str, str]] = set()

        for etype1, entities1 in entities_by_type.items():
            for etype2, entities2 in entities_by_type.items():
                # Create a canonical pair key to avoid duplicates
                pair = tuple(sorted([etype1, etype2]))
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)

                # Check if this combination has a defined relationship
                try:
                    entity_type1 = EntityType(etype1)
                    entity_type2 = EntityType(etype2)
                except ValueError:
                    continue

                key = (entity_type1, entity_type2)
                rel_type = self.RELATIONSHIP_TYPES.get(key)

                if rel_type:
                    # Create relationships between all matching entities
                    for _, node_id1 in entities1:
                        for _, node_id2 in entities2:
                            try:
                                rel_id = await self.graph_client.create_relationship(
                                    source_node_id=node_id1,
                                    target_node_id=node_id2,
                                    rel_type=rel_type,
                                    properties={
                                        "dataset_id": dataset_id,
                                        "confidence": 0.8,  # Inferred relationship
                                    },
                                )
                                relationship_ids.append(rel_id)
                            except Exception as e:
                                logger.debug(f"Failed to create relationship: {e}")

        # Also create relationships between adjacent columns in schema
        entity_list = [e for e in entities if e.column_name in node_id_map]
        for i in range(len(entity_list) - 1):
            e1, e2 = entity_list[i], entity_list[i + 1]

            # Only link if both have decent confidence
            if e1.confidence >= 0.5 and e2.confidence >= 0.5:
                n1, n2 = node_id_map[e1.column_name], node_id_map[e2.column_name]

                try:
                    rel_id = await self.graph_client.create_relationship(
                        source_node_id=n1,
                        target_node_id=n2,
                        rel_type="ADJACENT_TO",
                        properties={
                            "dataset_id": dataset_id,
                            "position": f"{i}-{i + 1}",
                        },
                    )
                    relationship_ids.append(rel_id)
                except Exception:
                    pass

        logger.info(f"Created {len(relationship_ids)} relationships")
        return relationship_ids

    def _get_node_labels(self, entity_type: EntityType) -> List[str]:
        """
        Get node labels from entity type.

        Always includes:
        - The specific entity type (e.g., "Customer")
        - "Entity" as base label
        """
        labels = [entity_type.value, "Entity"]

        # Add category labels based on entity type
        if entity_type in (
            EntityType.CUSTOMER,
            EntityType.PERSON,
            EntityType.EMPLOYEE,
            EntityType.PATIENT,
            EntityType.VENDOR,
            EntityType.SUPPLIER,
        ):
            labels.append("Actor")

        elif entity_type in (
            EntityType.PRODUCT,
            EntityType.ORDER,
            EntityType.TRANSACTION,
            EntityType.INVOICE,
        ):
            labels.append("Object")

        elif entity_type in (
            EntityType.TIMEDIMENSION,
            EntityType.GEOGRAPHY,
            EntityType.FACILITY,
        ):
            labels.append("Dimension")

        elif entity_type in (EntityType.METRIC, EntityType.AMOUNT, EntityType.QUANTITY):
            labels.append("Measure")

        elif entity_type in (
            EntityType.CLASSIFICATION,
            EntityType.CATEGORY,
            EntityType.STATUS,
            EntityType.INDICATOR,
            EntityType.CODE,
        ):
            labels.append("Attribute")

        # Add Generic fallback label if applicable
        if entity_type in (
            EntityType.GENERIC_ENTITY,
            EntityType.GENERIC_REFERENCE,
            EntityType.GENERIC_ATTRIBUTE,
        ):
            labels.append("Unclassified")

        return labels

    async def update_entity_in_graph(
        self,
        dataset_id: str,
        column_name: str,
        corrected_entity_type: str,
    ) -> bool:
        """
        Update entity classification in graph (from user correction).

        Args:
            dataset_id: Dataset identifier
            column_name: Column that was corrected
            corrected_entity_type: New entity type

        Returns:
            True if successful
        """
        try:
            # Find the node
            nodes = await self.graph_client.find_nodes(
                label="Entity",
                property_filters={
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                },
                limit=1,
            )

            if not nodes:
                logger.warning(
                    f"Node not found for {column_name} in dataset {dataset_id}"
                )
                return False

            node = nodes[0]

            # Update properties
            properties = {
                "entity_type": corrected_entity_type,
                "confidence": 1.0,  # User confirmed
                "confidence_level": "strong",
                "corrected_at": datetime.utcnow().isoformat(),
                "was_fallback": node.properties.get("is_fallback", False),
            }

            await self.graph_client.update_node(node.node_id, properties)

            logger.info(f"Updated node {node.node_id} to {corrected_entity_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to update entity in graph: {e}")
            return False

    async def get_entity_graph(
        self,
        dataset_id: str,
        column_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get entity with its relationships from graph.

        Args:
            dataset_id: Dataset identifier
            column_name: Column name

        Returns:
            Entity data with relationships
        """
        try:
            # Find node
            nodes = await self.graph_client.find_nodes(
                label="Entity",
                property_filters={
                    "column_name": column_name,
                    "dataset_id": dataset_id,
                },
                limit=1,
            )

            if not nodes:
                return None

            node = nodes[0]

            # Get relationships
            relationships = await self.graph_client.get_relationships(node.node_id)

            return {
                "node": node.to_dict(),
                "relationships": [r.to_dict() for r in relationships],
            }

        except Exception as e:
            logger.error(f"Failed to get entity graph: {e}")
            return None


# Factory function
def create_transformer(graph_client: FalkorDBClient) -> EntityToGraphTransformer:
    return EntityToGraphTransformer(graph_client)


__all__ = [
    "EntityToGraphTransformer",
    "create_transformer",
]
