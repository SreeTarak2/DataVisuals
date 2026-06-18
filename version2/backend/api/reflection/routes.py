"""
API endpoint for the InsightReflectionAgent.

Evaluates the quality of AI-generated outputs (insights, KPIs, narratives)
on four dimensions: novelty, actionability, specificity, correctness.

Returns quality scores, identified failure modes, and prompt adjustments
to improve future generations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ReflectionRequest(BaseModel):
    """Request body for insight quality reflection."""
    dataset_id: str
    user_query: str = ""
    ai_output: str
    output_type: str = "insight"  # "kpi", "insight", "chart", "narrative"


@router.post("/datasets/{dataset_id}/reflect")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def reflect_insight(
    request: Request,
    dataset_id: str,
    body: ReflectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Evaluate the quality of an AI-generated insight/output.

    Scores on four dimensions (0.0–1.0):
    - novelty: Is this new information or generic?
    - actionability: Can the user act on this?
    - specificity: How data-grounded is it?
    - correctness: Does it accurately reflect the data?

    Returns quality scores, failure modes, and prompt adjustments.
    """
    user_id = current_user["id"]

    # ── Get dataset context ────────────────────────────────────────────────
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    metadata = dataset.get("metadata", {})
    column_metadata = metadata.get("column_metadata", [])
    domain_info = metadata.get("domain_intelligence", {})

    # Build compact schema context for the reflection prompt
    schema_lines = []
    for c in column_metadata[:15]:
        name = c.get("name", "?")
        col_type = c.get("type", "?")
        nulls = c.get("null_percentage", 0)
        schema_lines.append(f"- {name} ({col_type}): nulls={nulls}%")

    schema_context = "\n".join(schema_lines)
    dataset_type = domain_info.get("domain", "general")

    # ── Run reflection ────────────────────────────────────────────────────
    from services.insight_reflection import InsightReflectionAgent

    reflector = InsightReflectionAgent()
    try:
        score = await reflector.reflect(
            user_query=body.user_query,
            ai_output=body.ai_output,
            schema_context=schema_context,
            dataset_type=dataset_type,
            output_type=body.output_type,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"[Reflection] Reflection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Insight reflection failed")

    # ── Return results ────────────────────────────────────────────────────
    return {
        "quality_score": {
            "overall_score": score.overall_score,
            "novelty": score.novelty,
            "actionability": score.actionability,
            "specificity": score.specificity,
            "correctness": score.correctness,
            "failure_modes": score.failure_modes,
        },
        "prompt_adjustments": score.prompt_adjustments,
        "threshold_updates": score.threshold_updates,
        "dataset_type": dataset_type,
        "output_type": body.output_type,
    }


@router.get("/datasets/{dataset_id}/reflect/trends")
@limiter.limit(RateLimits.DATASET_GET)
async def get_reflection_trends(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get quality trend data for AI-generated outputs from this dataset.

    Returns historical quality scores, common failure modes, and
    current threshold calibrations.
    """
    user_id = current_user["id"]

    # Get dataset context for type
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    metadata = dataset.get("metadata", {})
    domain_info = metadata.get("domain_intelligence", {})
    dataset_type = domain_info.get("domain", "general")

    from services.insight_reflection import InsightReflectionAgent

    reflector = InsightReflectionAgent()

    results = {}
    for output_type in ("kpi", "insight", "narrative"):
        results[output_type] = reflector.get_trend(dataset_type, output_type)

    thresholds = reflector.get_thresholds()

    return {
        "trends": results,
        "calibrated_thresholds": thresholds,
        "dataset_id": dataset_id,
    }
