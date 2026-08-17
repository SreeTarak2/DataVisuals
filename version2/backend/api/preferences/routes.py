"""
Preferences API Routes
======================

Exposes the progressive learning system's outputs:
- ``GET /preferences/{dataset_id}`` → preference profile for a specific dataset
- ``GET /preferences/summary``     → cross-dataset summary for the current user
- ``POST /preferences/{dataset_id}/refresh`` → force recompute a profile
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{dataset_id}")
@limiter.limit(RateLimits.DATASET_GET)
async def get_dataset_preferences(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the learned preference profile for a specific dataset.

    The profile shows which KPIs, charts, and query topics the user has
    interacted with most, ranked by a decayed interaction score.
    """
    from services.learning.preference_learner import preference_learner

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)

    profile = await preference_learner.compute_profile(
        user_id=user_id,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
    )

    return {
        "profile": profile.to_api_summary(),
        "has_data": profile.signal_count > 0,
        "dataset_id": dataset_id,
    }


@router.get("/summary")
@limiter.limit(RateLimits.DATASET_GET)
async def get_preferences_summary(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Return a cross-dataset preference summary for the user.

    Shows what the system has learned about the user's analytics style
    across all their datasets — top KPIs, chart types, and overall
    confidence in the learned profile.
    """
    from services.learning.preference_learner import preference_learner

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)

    summary = await preference_learner.get_user_summary(
        user_id=user_id,
        workspace_id=workspace_id,
    )

    return {
        "summary": summary.to_dict(),
        "has_data": summary.total_signals > 0,
    }


@router.get("/trust-correlation")
@limiter.limit(RateLimits.DATASET_GET)
async def get_trust_correlation(
    request: Request,
    dataset_id: str | None = None,
    days_back: int = 90,
    lookahead_minutes: int = 5,
    current_user: dict = Depends(get_current_user),
):
    """
    Return a trust correlation report showing how trust adjustments correlate
    with user engagement.

    For each metric semantic definition that was triggered by user queries,
    the report shows:
    - How often it was triggered (``trigger_count``)
    - How many follow-up queries, corrections, and delight signals occurred
      within the ``lookahead_minutes`` window after each adjustment
    - A ``satisfaction_score`` from -1.0 to 1.0 (positive = users respond well)
    - An ``engagement_rate`` showing what fraction of adjustments led to
      further interaction

    The response also includes summary-level metrics (``overall_engagement_rate``,
    ``overall_satisfaction``) and ranked lists of the most and least satisfying
    metrics.

    Query Parameters:
    - ``dataset_id``: Optional filter to a specific dataset
    - ``days_back``: How many days of history to analyze (default 90)
    - ``lookahead_minutes``: Window after each adjustment to measure
      engagement (default 5)
    """
    from services.learning.trust_correlation import trust_correlation_service

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)

    report = await trust_correlation_service.correlate(
        workspace_id=workspace_id,
        user_id=user_id,
        dataset_id=dataset_id,
        days_back=days_back,
        lookahead_minutes=lookahead_minutes,
    )

    return {
        "report": report.to_dict(),
        "has_data": report.total_trust_adjustments > 0,
    }


@router.post("/{dataset_id}/refresh")
@limiter.limit(RateLimits.DATASET_UPDATE)
async def refresh_preferences(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Force recompute the preference profile for a dataset.

    Useful for debugging or when the user wants to see updated preferences
    immediately (e.g., after significant interaction).
    """
    from services.learning.preference_learner import preference_learner

    user_id = current_user["id"]
    workspace_id = current_user.get("workspace_id", user_id)

    profile = await preference_learner.compute_profile(
        user_id=user_id,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        force_refresh=True,
    )

    return {
        "profile": profile.to_api_summary(),
        "signal_count": profile.signal_count,
        "confidence": profile.confidence,
        "dataset_id": dataset_id,
    }
