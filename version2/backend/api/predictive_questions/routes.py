"""
api/predictive_questions/routes.py — Predictive Questions REST API

Generates business-user questions from a dataset's intelligence profile
so users know what to ask before building a dashboard.

Usage:
    GET /api/datasets/{dataset_id}/predictive-questions
    → { "questions": [...], "by_layer": {...}, "metadata": {...} }

No LLM calls — deterministic template-filling from column semantics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from services.predictive_questions.generator import predictive_question_generator
from services.predictive_questions.templates import AnalyticalLayer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/datasets/{dataset_id}/predictive-questions")
async def get_predictive_questions(
    dataset_id: str,
    max_questions: int = Query(30, ge=1, le=100, description="Maximum questions to generate"),
    use_llm: bool = Query(True, description="Enable LLM enrichment for context-aware questions"),
    layer: str = Query(
        None,
        description="Filter by analytical layer: strategic, diagnostic, root_cause, exploratory, forecast",
    ),
    current_user: dict = Depends(get_current_user),
):
    """Generate predictive business questions from dataset intelligence.

    Two-stage generation:
      1. Deterministic metric-dimension matrix (fast, no LLM cost)
      2. Optional LLM enrichment (rewrites into context-aware human questions)

    Returns questions organized by analytical layer:
      - **strategic**: High-level overview (first 5 seconds)
      - **diagnostic**: How is this period going?
      - **root_cause**: Why did this happen?
      - **exploratory**: What else is interesting?
      - **forecast**: What will happen next?
    """
    # ── 1. Fetch dataset intelligence ────────────────────────────────────
    intelligence = await enhanced_dataset_service.get_dataset_intelligence(
        dataset_id, current_user["id"]
    )
    if not intelligence:
        # Try legacy metadata path
        try:
            dataset = await enhanced_dataset_service.get_dataset(
                dataset_id, current_user["id"]
            )
            meta = dataset.get("metadata", {})
            intelligence = meta.get("unified_intelligence")
            if not intelligence:
                raise HTTPException(
                    status_code=404,
                    detail="Dataset intelligence not found. Ensure the dataset has finished processing.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch intelligence for {dataset_id}: {e}")
            raise HTTPException(
                status_code=404,
                detail="Dataset not found or intelligence not available.",
            )

    # ── 2. Parse layer filter ────────────────────────────────────────────
    layers = None
    if layer:
        try:
            parsed = AnalyticalLayer(layer)
            layers = [parsed]
        except ValueError:
            valid = [l.value for l in AnalyticalLayer]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid layer '{layer}'. Valid options: {', '.join(valid)}",
            )

    # ── 3. Generate questions (async with optional LLM) ──────────────────
    result = await predictive_question_generator.generate_for_dataset_async(
        dataset_intelligence=intelligence,
        max_questions=max_questions,
        use_llm=use_llm,
        user_id=current_user.get("id"),
    )

    # If layer filter was specified, filter the output
    if layers:
        target = layers[0].value
        result["questions"] = [
            q for q in result["questions"] if q["layer"] == target
        ]
        result["by_layer"] = {
            target: result["by_layer"].get(target, [])
        }
        result["metadata"]["total"] = len(result["questions"])

    # Attach dataset info
    result["dataset_id"] = dataset_id

    logger.info(
        "[PredictiveQuestions] %d questions generated for dataset %s (generator=%s)",
        result["metadata"]["total"],
        dataset_id[:8],
        result["metadata"].get("generator", "unknown"),
    )

    return result
