from fastapi import APIRouter, Depends, Request
from datetime import datetime
from core.rate_limiter import limiter, RateLimits
from api.auth import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

router = APIRouter()


@router.get("/{dataset_id}")
@limiter.limit(RateLimits.DATASET_GET)
async def get_comprehensive_insights(
    request: Request,
    dataset_id: str,
    force_refresh: bool = False,
    filters: str = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Get comprehensive insights for a dataset.
    
    Returns:
        - insights: List of discovered insights with titles, descriptions, contexts
        - summary: Executive summary of the dataset
        - story_status: Status of narrative story generation (not_started, generating, ready, failed)
        - is_story_available: Whether the narrative story is ready
        - generated_at: Timestamp of when insights were generated
    """
    # Fetch full dataset with analytics
    combined = await enhanced_dataset_service.get_full_dataset_with_analytics(
        dataset_id,
        current_user["id"],
    )

    analytics = combined.get("analytics") or {}
    metadata = combined.get("metadata") or {}

    # Extract deep analysis insights
    deep_analysis = analytics.get("deep_analysis") or metadata.get("deep_analysis") or {}
    summary = deep_analysis.get("executive_summary") or ""

    # Extract insights from various possible locations
    insights_raw = (
        deep_analysis.get("quis_insights", {}).get("top_insights")
        or deep_analysis.get("quis_insights", {}).get("insights")
        or deep_analysis.get("insights")
        or []
    )

    # Format insights
    insights = []
    for idx, item in enumerate(insights_raw):
        insight = {
            "id": item.get("id") or f"insight_{idx}",
            "title": item.get("title") or item.get("question") or "Insight",
            "description": item.get("description") or item.get("insight") or item.get("finding") or "",
            "type": item.get("type") or "insight",
            "confidence": item.get("confidence"),
            "effect_size": item.get("effect_size"),
            "p_value": item.get("p_value"),
            "columns": item.get("columns") or [],
            "severity": item.get("severity") or "neutral",
            "value": item.get("value"),
            "context": item.get("context") or {},
        }
        insights.append(insight)

    # Check narrative story status from artifact_status
    artifact_status = combined.get("artifact_status") or {}
    narrative_story_status = artifact_status.get("narrative_story") or "not_started"
    is_story_available = narrative_story_status == "ready"

    return {
        "insights": insights,
        "summary": summary,
        "story_status": narrative_story_status,
        "is_story_available": is_story_available,
        "generated_at": datetime.utcnow().isoformat(),
    }
