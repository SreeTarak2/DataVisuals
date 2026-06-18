"""
Entity Extractor - Main Service Orchestrator
==============================================

The main service that orchestrates the entity extraction pipeline:

LEGACY pipeline (backward compatible):
1. Profile the schema
2. Extract signals
3. Classify entities
4. Calculate confidence
5. Apply fallback for uncertain cases
6. Return results with review flags

NEW pipeline (Layer 1 + Layer 2):
1. Signal extraction → ColumnRole classification
2. Semantic candidate extraction
3. Column grouping → entity clusters
4. Generic validation → discovered entities
5. DatasetUnderstandingReport generation
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .models import (
    ColumnProfile,
    SchemaProfile,
    ColumnRole,
    EntityCandidate,
    ExtractionResult,
    EntityCorrection,
    CorrectionMemory,
    SemanticCandidate,
    EvidenceSource,
    DatasetUnderstandingReport,
    column_role_to_legacy_entity_type,
)
from .schema_profiler import schema_profiler, SchemaProfiler
from .signal_engine import signal_engine, SignalEngine
from .entity_classifier import entity_classifier, EntityClassifier
from .confidence_scorer import confidence_scorer, ConfidenceScorer
from .fallback_handler import fallback_handler, FallbackHandler
from .entity_discovery import entity_discovery, EntityDiscovery
from .config import kg_config

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Structured audit logging for entity extraction operations.

    Logs key events with structured metadata for observability.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or os.getenv(
            "ENTITY_EXTRACTION_AUDIT_LOG", "./entity_extraction_audit.jsonl"
        )
        # Ensure log directory exists at init time
        try:
            log_dir = os.path.dirname(self.log_path) or "."
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass

    def log_extraction(
        self,
        table_name: str,
        dataset_id: Optional[str],
        entity_count: int,
        strong_count: int,
        fallback_count: int,
        review_count: int,
        duration_ms: float,
    ):
        """Log an extraction event"""
        event = {
            "event": "entity_extraction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "table_name": table_name,
            "dataset_id": dataset_id,
            "entity_count": entity_count,
            "strong_confidence": strong_count,
            "fallback_count": fallback_count,
            "review_required": review_count,
            "duration_ms": round(duration_ms, 2),
        }
        self._write_event(event)
        logger.info(
            f"Audit: Extracted {entity_count} entities from {table_name} "
            f"({strong_count} strong, {fallback_count} fallbacks, {review_count} need review) "
            f"in {duration_ms:.0f}ms"
        )

    def log_correction(
        self,
        dataset_id: str,
        column_name: str,
        original_entity: str,
        corrected_entity: str,
        user_id: Optional[str],
    ):
        """Log a correction event"""
        event = {
            "event": "entity_correction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_id": dataset_id,
            "column_name": column_name,
            "original_entity": original_entity,
            "corrected_entity": corrected_entity,
            "user_id": user_id,
        }
        self._write_event(event)
        logger.info(
            f"Audit: Correction applied — {column_name}: {original_entity} → {corrected_entity}"
        )

    def log_error(
        self,
        operation: str,
        table_name: Optional[str],
        error_message: str,
    ):
        """Log an error event"""
        event = {
            "event": "entity_extraction_error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "table_name": table_name,
            "error": error_message,
        }
        self._write_event(event)
        logger.error(f"Audit error: {operation} failed — {error_message}")

    def _write_event(self, event: Dict[str, Any]):
        """Write event to audit log file"""
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")


class EntityExtractionError(Exception):
    """Raised when entity extraction fails"""

    pass


class EntityExtractor:
    """
    Main orchestrator for dynamic entity extraction.

    Pipeline:
    1. Profile schema (if not already done)
    2. Extract signals for each column
    3. Classify into entity types
    4. Calculate confidence scores
    5. Apply fallback for low-confidence cases
    6. Apply correction memory if available

    Key Features:
    - Multi-signal inference (name + type + value + context)
    - Confidence scoring with review flags
    - Safe fallback for uncertain cases
    - Correction memory for learning
    """

    def __init__(self):
        self.profiler = schema_profiler
        self.signal_engine = signal_engine
        self.classifier = entity_classifier
        self.confidence_scorer = confidence_scorer
        self.fallback_handler = fallback_handler
        self.correction_memory = CorrectionMemory()
        self.audit_logger = AuditLogger()
        self.entity_discovery = entity_discovery

        # Configure persistence if enabled
        if kg_config.CORRECTION_MEMORY_ENABLED:
            self.correction_memory.configure_persistence(kg_config.CORRECTION_MEMORY_PATH)
            logger.info(f"Correction memory persistence: {kg_config.CORRECTION_MEMORY_PATH}")

        logger.info("EntityExtractor initialized")

    @property
    def _has_persistence(self) -> bool:
        return self.correction_memory._persistence_path is not None

    async def extract_from_schema(
        self, schema: SchemaProfile, dataset_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract entities from an existing schema profile.

        Args:
            schema: Pre-computed schema profile
            dataset_id: Optional dataset ID for correction memory lookup

        Returns:
            ExtractionResult with all entity candidates
        """
        start_time = datetime.now(timezone.utc)
        try:
            logger.info(f"Starting entity extraction for {schema.table_name}")

            entities = []

            for column in schema.columns:
                # Check for prior correction
                prior_entity = None
                if dataset_id:
                    prior_entity = self.correction_memory.get_prior_entity(dataset_id, column.name)

                # Extract signals
                signals = self.signal_engine.extract_all_signals(column, schema)

                # If we have a strong prior correction, use it directly
                if prior_entity:
                    fallback_candidate = self.classifier._create_fallback_candidate(
                        column=column, reason="Using prior correction"
                    )
                    # Override with correction
                    candidate = self.classifier.apply_correction(fallback_candidate, prior_entity)
                    entities.append(candidate)
                    continue

                # Classify using signals
                try:
                    candidate = await self.classifier.classify_column(column, schema)

                    # Recalculate confidence using scorer
                    candidate = self.confidence_scorer.score_entity_candidate(candidate)

                    # Apply fallback if confidence too low
                    if candidate.confidence < 0.50:
                        candidate = self.fallback_handler.get_fallback(
                            column=column,
                            reason=f"Low confidence ({candidate.confidence})",
                            signals=candidate.signals,
                        )

                    entities.append(candidate)

                except Exception as e:
                    logger.warning(f"Classification failed for {column.name}: {e}")
                    self.audit_logger.log_error(
                        operation="classify_column",
                        table_name=schema.table_name,
                        error_message=f"Column {column.name}: {str(e)}",
                    )
                    # Use fallback for failed classifications
                    fallback = self.fallback_handler.get_fallback(
                        column=column,
                        reason=f"Classification error: {str(e)}",
                        signals=[],
                    )
                    entities.append(fallback)

            # Build result
            result = ExtractionResult(table_name=schema.table_name, entities=entities)

            # Audit logging with timing
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.audit_logger.log_extraction(
                table_name=schema.table_name,
                dataset_id=dataset_id,
                entity_count=len(entities),
                strong_count=result.strong_confidence_count,
                fallback_count=result.fallback_count,
                review_count=len(result.review_required),
                duration_ms=elapsed,
            )

            return result

        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.audit_logger.log_error(
                operation="extract_from_schema",
                table_name=schema.table_name,
                error_message=str(e),
            )
            logger.error(f"Entity extraction failed: {e}")
            raise EntityExtractionError(f"Extraction failed: {e}") from e

    async def extract_from_columns(
        self,
        columns: List[Dict[str, Any]],
        rows: List[Dict[str, Any]],
        table_name: str = "unknown",
        dataset_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract entities from raw column definitions and row data.

        This is the main entry point - provides schema and gets entities.

        Args:
            columns: List of column definitions [{name, type}, ...]
            rows: List of row data (dictionaries)
            table_name: Name of the table/file
            dataset_id: Optional dataset ID for correction memory

        Returns:
            ExtractionResult with entity candidates
        """
        try:
            # Step 1: Profile the schema
            schema = await self.profiler.profile_columns(
                columns=columns, rows=rows, table_name=table_name
            )

            # Step 2: Extract entities
            return await self.extract_from_schema(schema, dataset_id)

        except Exception as e:
            logger.error(f"Extraction from columns failed: {e}")
            raise EntityExtractionError(f"Failed to extract from columns: {e}") from e

    async def extract_single_column(
        self,
        column_name: str,
        data_type: str,
        sample_values: List[str],
        table_name: Optional[str] = None,
        neighboring_columns: Optional[List[str]] = None,
    ) -> EntityCandidate:
        """
        Extract entity for a single column.

        Useful for real-time analysis of a specific column.

        Args:
            column_name: Name of the column
            data_type: Data type
            sample_values: Sample values for analysis
            table_name: Optional table context
            neighboring_columns: Optional neighboring columns

        Returns:
            EntityCandidate for this column
        """
        # Create minimal profile
        profile = ColumnProfile(
            name=column_name,
            data_type=data_type,
            sample_values=sample_values[:10],  # Limit samples
            distinct_count=len(set(sample_values)) if sample_values else 0,
            distinct_ratio=len(set(sample_values)) / len(sample_values) if sample_values else 0,
        )

        # Create minimal schema if table_name provided
        schema = None
        if table_name:
            neighbor_profiles = []
            if neighboring_columns:
                for nc in neighboring_columns:
                    neighbor_profiles.append(ColumnProfile(name=nc, data_type="string"))

            schema = SchemaProfile(
                table_name=table_name,
                columns=[profile] + neighbor_profiles,
                row_count=len(sample_values) * 10,  # Estimate
            )

        # Extract
        return await self.classifier.classify_column(profile, schema)

    def apply_correction(
        self,
        dataset_id: str,
        table_name: str,
        column_name: str,
        original_entity: str,
        corrected_entity: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Apply user correction to improve future extraction.

        Stores correction in memory for future extraction sessions.

        Args:
            dataset_id: Dataset identifier
            table_name: Table name
            column_name: Column that was corrected
            original_entity: Original entity type
            corrected_entity: Corrected entity type
            user_id: Optional user ID

        Returns:
            True if correction applied successfully
        """
        try:
            from .models import EntityType, EntityCorrection

            correction = EntityCorrection(
                dataset_id=dataset_id,
                table_name=table_name,
                column_name=column_name,
                original_entity=EntityType(original_entity),
                corrected_entity=EntityType(corrected_entity),
                original_confidence=1.0,  # User override
                user_id=user_id,
            )

            self.correction_memory.add_correction(correction)

            # Audit log the correction
            self.audit_logger.log_correction(
                dataset_id=dataset_id,
                column_name=column_name,
                original_entity=original_entity,
                corrected_entity=corrected_entity,
                user_id=user_id,
            )

            return True

        except Exception as e:
            self.audit_logger.log_error(
                operation="apply_correction",
                table_name=table_name,
                error_message=f"Column {column_name}: {str(e)}",
            )
            logger.error(f"Failed to apply correction: {e}")
            return False

    def get_correction_stats(self) -> Dict[str, Any]:
        """Get statistics about stored corrections"""
        return {
            "total_corrections": len(self.correction_memory.corrections),
            "by_entity_type": self._count_corrections_by_entity(),
        }

    def _count_corrections_by_entity(self) -> Dict[str, int]:
        """Count corrections by target entity type"""
        from collections import Counter

        entities = [c.corrected_entity.value for c in self.correction_memory.corrections]
        return dict(Counter(entities))

    async def health_check(self) -> Dict[str, bool]:
        """Check health of the extraction service"""
        return {
            "profiler_available": self.profiler is not None,
            "signal_engine_available": self.signal_engine is not None,
            "classifier_available": self.classifier is not None,
            "confidence_scorer_available": self.confidence_scorer is not None,
            "fallback_handler_available": self.fallback_handler is not None,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Entity Discovery Pipeline (Layer 1 + Layer 2)
    # ──────────────────────────────────────────────────────────────────────────

    def discover(
        self,
        columns: List[ColumnProfile],
        table_name: str = "",
    ) -> DatasetUnderstandingReport:
        """
        Run the new entity discovery pipeline.

        Uses: signal_engine.classify_column() → grouping_engine.group()
              → entity_validator.validate()

        Args:
            columns: Column profiles
            table_name: Table/file name for context

        Returns:
            DatasetUnderstandingReport
        """
        return self.entity_discovery.discover(columns, table_name)

    async def discover_from_schema(
        self,
        schema: SchemaProfile,
    ) -> DatasetUnderstandingReport:
        """
        Run entity discovery from a SchemaProfile.

        Args:
            schema: Pre-computed schema profile

        Returns:
            DatasetUnderstandingReport
        """
        return self.discover(schema.columns, schema.table_name)

    async def discover_from_columns(
        self,
        columns: List[Dict[str, Any]],
        rows: List[Dict[str, Any]],
        table_name: str = "unknown",
    ) -> DatasetUnderstandingReport:
        """
        Run entity discovery from raw column definitions and rows.

        Args:
            columns: Column definitions [{name, type}, ...]
            rows: Sample row data
            table_name: Table/file name

        Returns:
            DatasetUnderstandingReport
        """
        schema = await self.profiler.profile_columns(
            columns=columns, rows=rows, table_name=table_name
        )
        return self.discover(schema.columns, table_name)


# Singleton instance
entity_extractor = EntityExtractor()

__all__ = ["EntityExtractor", "EntityExtractionError", "entity_extractor"]
