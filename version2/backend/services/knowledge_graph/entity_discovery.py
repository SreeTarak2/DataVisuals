"""
Entity Discovery — Orchestrator
=================================

Wires together: SignalEngine → GroupingEngine → EntityValidator
to produce a DatasetUnderstandingReport.

This is the main entry point for the new Layer 1 + Layer 2 pipeline.
"""

import logging
from typing import List, Optional

from .models import (
    ColumnProfile,
    SchemaProfile,
    ColumnRole,
    SemanticCandidate,
    EvidenceSource,
    EntityCluster,
    DiscoveredEntity,
    DatasetUnderstandingReport,
)
from .signal_engine import signal_engine, SignalEngine
from .grouping_engine import grouping_engine, GroupingEngine
from .entity_validator import entity_validator, EntityValidator

logger = logging.getLogger(__name__)


class EntityDiscovery:
    """
    Orchestrates the full entity discovery pipeline:

    1. Signal extraction + ColumnRole classification (per column)
    2. Semantic candidate extraction (per column)
    3. Grouping (columns → entity clusters)
    4. Validation (clusters → discovered entities)
    5. Report generation
    """

    def __init__(
        self,
        signal_eng: Optional[SignalEngine] = None,
        group_eng: Optional[GroupingEngine] = None,
        validator: Optional[EntityValidator] = None,
    ):
        self.signal_engine = signal_eng or signal_engine
        self.grouping_engine = group_eng or grouping_engine
        self.validator = validator or entity_validator

    def discover(
        self,
        columns: List[ColumnProfile],
        table_name: str = "",
    ) -> DatasetUnderstandingReport:
        """
        Run the full entity discovery pipeline on a set of columns.

        Args:
            columns: List of column profiles from the schema profiler
            table_name: Table/file name for context

        Returns:
            DatasetUnderstandingReport with discovered entities
        """
        # Step 1: Classify each column → ColumnRole + SemanticCandidates
        classified: List = []
        for col in columns:
            role, candidates, evidence = self.signal_engine.classify_column(col)
            classified.append((col.name, role, candidates))

        # Step 2: Group columns into entity clusters
        clusters = self.grouping_engine.group(classified, table_name)

        # Step 3: Validate each cluster
        all_grouped_cols: set = set()
        discovered_entities: List[DiscoveredEntity] = []
        for cluster in clusters:
            entity = self.validator.validate(cluster)
            discovered_entities.append(entity)
            all_grouped_cols.update(entity.columns)

        # Step 4: Identify unknown columns (not assigned to any valid entity)
        unknown_cols: List[str] = []
        for col_name, _, _ in classified:
            if col_name not in all_grouped_cols:
                unknown_cols.append(col_name)

        # Step 5: Compute data quality score — valid entity column coverage
        valid_entities = [e for e in discovered_entities if e.is_valid]
        total_cols = len(columns)
        valid_cols = len({c for e in valid_entities for c in e.columns})
        unknown_count = len(unknown_cols)

        if total_cols > 0:
            coverage_ratio = valid_cols / total_cols
            quality_score = round(coverage_ratio * 100, 1)
        else:
            quality_score = 0.0

        # Step 6: Compute trust score based on confidence-weighted validation results
        if discovered_entities:
            avg_entity_conf = sum(e.confidence for e in discovered_entities) / len(
                discovered_entities
            )
            valid_ratio = sum(1 for e in discovered_entities if e.is_valid) / len(
                discovered_entities
            )
            trust_score = round((avg_entity_conf * 0.6 + valid_ratio * 0.4) * 100, 1)
        else:
            trust_score = 0.0

        return DatasetUnderstandingReport(
            table_name=table_name or "unknown",
            entities=valid_entities,
            unknown_columns=unknown_cols,
            data_quality_score=quality_score,
            trust_score=trust_score,
            column_count=total_cols,
            entity_count=len(valid_entities),
        )

    def single_column(
        self,
        column: ColumnProfile,
        table_name: str = "",
    ) -> dict:
        """
        Classify a single column (no grouping).

        Useful for real-time preview or quick column analysis.
        """
        role, candidates, evidence = self.signal_engine.classify_column(column)
        return {
            "column_name": column.name,
            "column_role": role.value,
            "semantic_candidates": [c.model_dump() for c in candidates],
            "evidence_count": len(evidence),
            "table_name": table_name,
        }


entity_discovery = EntityDiscovery()

__all__ = ["EntityDiscovery", "entity_discovery"]
