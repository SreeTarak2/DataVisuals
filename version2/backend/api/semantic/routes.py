"""
api/semantic/routes.py — Governed Semantic Query REST API
=========================================================

Production-grade REST endpoint for the "LLM as translator" pipeline.

POST /api/v2/semantic/query
  Accepts: {query: "show me revenue by month for 2024"}
       Or: {intent: {metrics: [...], dimensions: [...], filters: [...]}}
  Returns: {success, sql, data, response, pipeline_trace}

The endpoint runs the full governed pipeline:
  Intent extraction → validation → metric resolution → SQL compilation → SQL validation → execution

Key design decisions:
- Accepts raw NLQ (frontend uses this for chat) OR structured intent (programmatic use)
- Both paths go through the same validation + compilation
- Returns pipeline trace for observability (intent, validation, resolved metrics)
- Single execution path — no LLM-SQL fallback for metric queries
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.semantic.semantic_query_service import semantic_query_service
from services.semantic.query_intent import QueryIntent
from services.semantic.checkpoint_gate import checkpoint_gate

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request/Response schemas ────────────────────────────────────────────────


class StructuredIntentRequest(BaseModel):
    """Structured intent input for programmatic API usage.

    When provided, the endpoint skips LLM-based intent extraction and
    uses this intent directly. This is useful for:
    - Programmatic clients that already know what they want
    - Testing and debugging the compiler independently
    """

    metrics: List[Dict[str, Any]] = []
    dimensions: List[Dict[str, Any]] = []
    filters: List[Dict[str, Any]] = []
    order: List[Dict[str, str]] = []
    limit: Optional[int] = None


class SemanticQueryRequest(BaseModel):
    """Request body for the semantic query endpoint.

    Either `query` (NLQ) or `intent` (structured) must be provided.
    If both are provided, `intent` takes precedence.
    """

    query: Optional[str] = None
    intent: Optional[StructuredIntentRequest] = None
    dataset_id: str = ""
    return_raw: bool = False


class SemanticQueryResponse(BaseModel):
    """Response body for the semantic query endpoint."""

    success: bool
    response: str = ""
    sql: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    requires_confirmation: bool = False
    checkpoint_id: Optional[str] = None
    pipeline: Optional[Dict[str, Any]] = None


class ConfirmQueryRequest(BaseModel):
    """Request body for confirming a pending query."""

    checkpoint_id: str
    dataset_id: str
    return_raw: bool = False


# ── Helper to convert structured intent request ────────────────────────────


def _parse_structured_intent(intent: StructuredIntentRequest) -> QueryIntent:
    """Convert a StructuredIntentRequest to a QueryIntent."""
    from services.semantic.query_intent import (
        DimensionIntent,
        FilterIntent,
        FilterOperator,
        MetricIntent,
        OrderDirection,
        OrderIntent,
    )

    metrics = [
        MetricIntent(name=m.get("name", ""), alias=m.get("alias"), aggregation=m.get("aggregation"))
        for m in intent.metrics
        if m.get("name")
    ]

    dimensions = [
        DimensionIntent(column=d.get("column", ""), grain=d.get("grain"), alias=d.get("alias"))
        for d in intent.dimensions
        if d.get("column")
    ]

    filters = []
    for f in intent.filters:
        col = f.get("column")
        if not col:
            continue
        op_str = f.get("operator", "=")
        try:
            operator = FilterOperator(op_str)
        except ValueError:
            operator = FilterOperator.EQ
        filters.append(FilterIntent(column=col, operator=operator, value=f.get("value")))

    order = [
        OrderIntent(
            column=o.get("column"),
            metric=o.get("metric"),
            direction=OrderDirection(o.get("direction", "desc")),
        )
        for o in intent.order
    ]

    return QueryIntent(
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        order=order,
        limit=intent.limit,
        has_aggregations=len(metrics) > 0,
        confidence=1.0,
    )


# ── Endpoint ────────────────────────────────────────────────────────────────


@router.post("/semantic/query")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def semantic_query(
    request: Request,
    body: SemanticQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Execute a governed semantic query against a dataset.

    Accepts either:
    - Natural language query (NLQ): {"query": "show me revenue by month", "dataset_id": "..."}
    - Structured intent: {"intent": {"metrics": [...], "dimensions": [...]}, "dataset_id": "..."}

    Returns:
    - SQL + data + natural language response
    - Pipeline trace for observability
    - Structured error on failure
    """
    user_id = str(current_user.get("id", ""))
    dataset_id = body.dataset_id

    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required")

    if not body.query and not body.intent:
        raise HTTPException(status_code=400, detail="Either 'query' or 'intent' must be provided")

    # Load the dataset and its data
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = await enhanced_dataset_service.load_dataset_data(
            dataset.get("id"),
            user_id,
        )
        if df is None:
            raise HTTPException(status_code=400, detail="Dataset has no data")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    # If structured intent was provided, skip LLM extraction
    if body.intent:
        parsed_intent = _parse_structured_intent(body.intent)
        query_str = " ".join(m.name for m in parsed_intent.metrics)
        result = await semantic_query_service.execute(
            query=query_str,
            df=df,
            dataset_id=dataset_id,
            user_id=user_id,
            return_raw=body.return_raw,
            intent=parsed_intent,  # Pass pre-parsed intent to skip LLM extraction
        )
    else:
        # Run through full pipeline (extraction → validation → compile → execute)
        result = await semantic_query_service.execute(
            query=body.query or "",
            df=df,
            dataset_id=dataset_id,
            user_id=user_id,
            return_raw=body.return_raw,
        )

    response = SemanticQueryResponse(
        success=result.success,
        response=result.response,
        sql=result.sql,
        data=result.data,
        columns=result.columns,
        row_count=result.row_count,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
        requires_confirmation=result.path == "checkpoint_required",
        checkpoint_id=result.checkpoint_id,
        pipeline={
            "path": result.path,
            "intent": result.intent,
            "validation": result.validation.to_dict() if result.validation else None,
            "resolved_metrics": result.resolved_metrics,
            "validation_gates": result.validation_gates,
        },
    )

    return response


# ── Confirmation endpoint ──────────────────────────────────────────────────


@router.post("/semantic/query/confirm")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def confirm_semantic_query(
    request: Request,
    body: ConfirmQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Confirm a pending query checkpoint and execute it.

    When the /semantic/query endpoint returns `requires_confirmation=True`
    along with a `checkpoint_id`, the frontend should show a confirmation
    dialog to the user. If the user confirms, this endpoint is called with
    the checkpoint_id to execute the query.

    Args:
        checkpoint_id: The checkpoint ID from the original query response
        dataset_id: The dataset to query
        return_raw: If True, returns raw tabular data instead of NL interpretation
    """
    user_id = str(current_user.get("id", ""))
    dataset_id = body.dataset_id
    checkpoint_id = body.checkpoint_id

    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id is required")

    if not checkpoint_id:
        raise HTTPException(status_code=400, detail="checkpoint_id is required")

    # Retrieve and validate the pending query (two-phase commit: step 1)
    # This does NOT delete the checkpoint yet — if execution fails, the user can retry.
    pending = await checkpoint_gate.acknowledge(checkpoint_id=checkpoint_id, user_id=user_id)
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="Checkpoint not found or expired. Please re-submit your query.",
        )

    # Reload the dataset and its data
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = await enhanced_dataset_service.load_dataset_data(
            dataset.get("id"),
            user_id,
        )
        if df is None:
            raise HTTPException(status_code=400, detail="Dataset has no data")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    # Re-execute with skip_checkpoint=True
    result = await semantic_query_service.execute(
        query=pending.query,
        df=df,
        dataset_id=dataset_id,
        user_id=user_id,
        return_raw=body.return_raw,
        skip_checkpoint=True,
    )

    # Two-phase commit: step 2 — delete the checkpoint only AFTER successful execution.
    # This also records execution history so future queries from this user
    # on this dataset won't trigger the "first_query_on_dataset" checkpoint.
    await checkpoint_gate.complete(checkpoint_id, user_id=user_id, dataset_id=dataset_id)

    return SemanticQueryResponse(
        success=result.success,
        response=result.response,
        sql=result.sql,
        data=result.data,
        columns=result.columns,
        row_count=result.row_count,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
        requires_confirmation=False,
        checkpoint_id=None,
        pipeline={
            "path": result.path,
            "intent": result.intent,
            "validation": result.validation.to_dict() if result.validation else None,
            "resolved_metrics": result.resolved_metrics,
            "validation_gates": result.validation_gates,
        },
    )
