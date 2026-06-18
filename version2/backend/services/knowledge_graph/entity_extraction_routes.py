"""
Entity Extraction API Routes (Phase 4)
========================================

FastAPI endpoints for dynamic entity extraction.

Endpoints:
- POST /api/entity-extraction/extract — Extract entities from column definitions and sample data
- GET  /api/entity-extraction/health — Health check for extraction service
- POST /api/entity-extraction/corrections — Apply a user correction
- GET  /api/entity-extraction/corrections/stats — Get correction statistics
- GET  /api/entity-extraction/corrections — Get corrections for a dataset
- DELETE /api/entity-extraction/corrections — Clear corrections for a dataset
- GET  /api/entity-extraction/explain — Get detailed confidence explanation for a column
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .entity_extractor import entity_extractor
from .entity_discovery import entity_discovery
from .models import (
    ColumnProfile,
    SchemaProfile,
    EntityCandidate,
    ExtractionResult,
    DatasetUnderstandingReport,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/entity-extraction", tags=["8. Entity Extraction"])


# ── Request / Response Schemas ──


class ExtractionRequestColumn(BaseModel):
    """A single column definition in an extraction request"""

    name: str
    type: str = "unknown"
    sample_values: List[str] = []


class ExtractionRequest(BaseModel):
    """Request to extract entities from a dataset"""

    columns: List[ExtractionRequestColumn]
    rows: List[Dict[str, Any]] = []
    table_name: str = "unknown"
    dataset_id: Optional[str] = None


class SingleColumnRequest(BaseModel):
    """Request to analyze a single column"""

    column_name: str
    data_type: str = "string"
    sample_values: List[str] = []
    table_name: Optional[str] = None
    neighboring_columns: List[str] = []


class CorrectionRequest(BaseModel):
    """Request to apply a user correction"""

    dataset_id: str
    table_name: str
    column_name: str
    original_entity: str = "GenericEntity"
    corrected_entity: str
    user_id: Optional[str] = None


class DiscoverRequest(BaseModel):
    """Request to run the new entity discovery pipeline"""

    columns: List[ExtractionRequestColumn]
    table_name: str = "unknown"


class SingleColumnDiscoverRequest(BaseModel):
    """Request to classify a single column using new pipeline"""

    column_name: str
    data_type: str = "string"
    sample_values: List[str] = []


class ExplainRequest(BaseModel):
    """Request to explain confidence for a column"""

    column_name: str
    entity_type: str = "GenericEntity"
    confidence: float = 0.5
    rationale: str = ""
    signals: List[Dict[str, Any]] = []


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/extract", response_model=Dict[str, Any])
async def extract_entities(request: ExtractionRequest):
    """
    Extract entity classifications from column definitions and sample data.

    Accepts a list of column definitions with optional sample data,
    returns entity type predictions with confidence scores and rationale.
    """
    try:
        # Convert to the format expected by the extractor
        col_defs = [{"name": c.name, "type": c.type} for c in request.columns]
        row_data = request.rows if request.rows else _generate_sample_rows(request.columns)

        result = await entity_extractor.extract_from_columns(
            columns=col_defs,
            rows=row_data,
            table_name=request.table_name,
            dataset_id=request.dataset_id,
        )

        return _result_to_response(result)

    except Exception as e:
        logger.error(f"Extraction endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/single", response_model=Dict[str, Any])
async def extract_single_column(request: SingleColumnRequest):
    """
    Extract entity type for a single column.

    Useful for real-time analysis of a specific column without full schema context.
    """
    try:
        candidate = await entity_extractor.extract_single_column(
            column_name=request.column_name,
            data_type=request.data_type,
            sample_values=request.sample_values,
            table_name=request.table_name,
            neighboring_columns=request.neighboring_columns,
        )

        return _candidate_to_response(candidate)

    except Exception as e:
        logger.error(f"Single column extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/discover", response_model=Dict[str, Any])
async def discover_entities(request: DiscoverRequest):
    """
    Run the new Layer 1 + Layer 2 entity discovery pipeline.

    Classifies columns by ColumnRole, extracts semantic candidates,
    groups into entity clusters, and validates into discovered entities.
    """
    try:
        from .models import ColumnProfile as KGColumnProfile

        profiles = [
            KGColumnProfile(
                name=c.name,
                data_type=c.type or "string",
                sample_values=c.sample_values[:10],
                distinct_count=len(set(c.sample_values)) if c.sample_values else 0,
                distinct_ratio=(
                    len(set(c.sample_values)) / len(c.sample_values) if c.sample_values else 0.0
                ),
            )
            for c in request.columns
        ]

        report = entity_discovery.discover(profiles, request.table_name)
        return _report_to_response(report)

    except Exception as e:
        logger.error(f"Discover endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.post("/discover/single", response_model=Dict[str, Any])
async def discover_single_column(request: SingleColumnDiscoverRequest):
    """
    Classify a single column using the new pipeline (no grouping).
    """
    try:
        from .models import ColumnProfile as KGColumnProfile

        profile = KGColumnProfile(
            name=request.column_name,
            data_type=request.data_type,
            sample_values=request.sample_values[:10],
            distinct_count=len(set(request.sample_values)),
            distinct_ratio=(
                len(set(request.sample_values)) / len(request.sample_values)
                if request.sample_values
                else 0.0
            ),
        )

        result = entity_discovery.single_column(profile)
        return result

    except Exception as e:
        logger.error(f"Single discover endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check for the entity extraction service"""
    health = await entity_extractor.health_check()
    return {
        "status": "healthy" if all(health.values()) else "degraded",
        "components": health,
        "corrections_count": len(entity_extractor.correction_memory.corrections),
        "persistence_enabled": entity_extractor._has_persistence,
    }


@router.post("/corrections", response_model=Dict[str, Any])
async def apply_correction(request: CorrectionRequest):
    """
    Apply a user correction to improve future entity extraction.

    The correction is stored and used as a prior in future extractions
    for the same dataset and column.
    """
    try:
        success = entity_extractor.apply_correction(
            dataset_id=request.dataset_id,
            table_name=request.table_name,
            column_name=request.column_name,
            original_entity=request.original_entity,
            corrected_entity=request.corrected_entity,
            user_id=request.user_id,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to apply correction")

        return {
            "success": True,
            "message": f"Correction applied: {request.column_name} → {request.corrected_entity}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Correction endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Correction failed: {str(e)}")


@router.get("/corrections/stats", response_model=Dict[str, Any])
async def get_correction_stats():
    """Get statistics about stored corrections"""
    return entity_extractor.get_correction_stats()


@router.get("/corrections", response_model=List[Dict[str, Any]])
async def get_corrections(dataset_id: Optional[str] = Query(None)):
    """
    Get corrections, optionally filtered by dataset_id.
    """
    corrections = entity_extractor.correction_memory.corrections

    if dataset_id:
        corrections = [c for c in corrections if c.dataset_id == dataset_id]

    return [
        {
            "dataset_id": c.dataset_id,
            "table_name": c.table_name,
            "column_name": c.column_name,
            "original_entity": c.original_entity.value,
            "corrected_entity": c.corrected_entity.value,
            "timestamp": c.correction_timestamp.isoformat(),
            "user_id": c.user_id,
        }
        for c in reversed(corrections)  # Most recent first
    ]


@router.delete("/corrections", response_model=Dict[str, Any])
async def clear_corrections(dataset_id: str = Query(...)):
    """
    Clear all corrections for a specific dataset.
    """
    removed = entity_extractor.correction_memory.clear_dataset_corrections(dataset_id)
    return {
        "success": True,
        "dataset_id": dataset_id,
        "removed_count": removed,
    }


@router.post("/explain", response_model=Dict[str, Any])
async def explain_confidence(request: ExplainRequest):
    """
    Get a detailed breakdown of confidence scoring for a candidate.

    Useful for debugging and understanding why a particular entity type was chosen.
    """
    try:
        # Build a candidate from the request
        from .models import EntityType, SignalResult, SignalType, EntityCandidate
        from .confidence_scorer import confidence_scorer

        signals = []
        for s in request.signals:
            try:
                signal_type = SignalType(s.get("type", "column_name"))
            except ValueError:
                signal_type = SignalType.COLUMN_NAME
            signals.append(
                SignalResult(
                    signal_type=signal_type,
                    matched_pattern=s.get("pattern"),
                    confidence=s.get("confidence", 0.5),
                    evidence=s.get("evidence", ""),
                )
            )

        candidate = EntityCandidate(
            column_name=request.column_name,
            entity_type=EntityType(request.entity_type),
            confidence=request.confidence,
            rationale=request.rationale,
            signals=signals,
        )

        explanation = confidence_scorer.explain_confidence(candidate)
        return explanation

    except Exception as e:
        logger.error(f"Explain endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def _generate_sample_rows(columns: List[ExtractionRequestColumn]) -> List[Dict[str, Any]]:
    """Generate sample rows from column definitions if actual rows not provided"""
    rows = []
    max_samples = max((len(c.sample_values) for c in columns), default=0)
    for i in range(max_samples):
        row = {}
        for c in columns:
            row[c.name] = c.sample_values[i] if i < len(c.sample_values) else None
        rows.append(row)
    return rows


def _result_to_response(result: ExtractionResult) -> Dict[str, Any]:
    """Convert ExtractionResult to API response format"""
    return {
        "table_name": result.table_name,
        "entity_count": len(result.entities),
        "entities": [_candidate_to_response(e) for e in result.entities],
        "statistics": {
            "strong_confidence": result.strong_confidence_count,
            "good_confidence": result.good_confidence_count,
            "tentative_confidence": result.tentative_confidence_count,
            "uncertain_confidence": result.uncertain_confidence_count,
            "fallback_count": result.fallback_count,
            "review_required": result.review_required,
        },
        "extraction_timestamp": result.extraction_timestamp.isoformat(),
    }


def _candidate_to_response(candidate: EntityCandidate) -> Dict[str, Any]:
    """Convert EntityCandidate to API response format"""
    resp = {
        "column_name": candidate.column_name,
        "entity_type": candidate.entity_type.value,
        "confidence": candidate.confidence,
        "confidence_level": candidate.confidence_level.value,
        "rationale": candidate.rationale,
        "needs_review": candidate.needs_review,
        "is_fallback": candidate.is_fallback,
        "alternatives": [
            {"type": a.get("alt_type"), "confidence": a.get("score")}
            for a in candidate.alternatives
        ],
        "signals_summary": [
            {
                "type": s.signal_type.value,
                "confidence": s.confidence,
                "evidence": s.evidence[:100],
            }
            for s in candidate.signals[:3]
        ],
    }
    # NEW: include column_role and semantic_candidates if available
    if candidate.column_role:
        resp["column_role"] = candidate.column_role.value
    if candidate.semantic_candidates:
        resp["semantic_candidates"] = [
            {"label": sc.label, "confidence": sc.confidence, "source": sc.source}
            for sc in candidate.semantic_candidates
        ]
    if candidate.evidence_sources:
        resp["evidence_sources"] = [
            {
                "source_type": es.source_type,
                "value": es.value,
                "reliability": es.reliability.value,
                "confidence": es.confidence,
                "detail": es.detail,
            }
            for es in candidate.evidence_sources
        ]
    return resp


def _report_to_response(report: DatasetUnderstandingReport) -> Dict[str, Any]:
    """Convert DatasetUnderstandingReport to API response format"""
    return {
        "table_name": report.table_name,
        "entity_count": report.entity_count,
        "column_count": report.column_count,
        "data_quality_score": report.data_quality_score,
        "trust_score": report.trust_score,
        "entities": [
            {
                "label": e.label,
                "columns": e.columns,
                "identifier_column": e.identifier_column,
                "role_counts": e.role_counts,
                "role_confidence": e.role_confidence,
                "candidate_confidence": e.candidate_confidence,
                "entity_confidence": e.entity_confidence,
                "confidence": e.confidence,
                "validation_notes": e.validation_notes,
                "is_valid": e.is_valid,
            }
            for e in report.entities
        ],
        "unknown_columns": report.unknown_columns,
        "generated_at": report.generated_at.isoformat(),
    }
