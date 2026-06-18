"""
API endpoint for the ProactiveNotificationAgent.

Composes and delivers proactive notification events (anomaly alerts,
data quality notifications, strategic advice summaries) that are
pushed to the user's dashboard or chat stream.

Designed to be called by other services (pipeline, anomaly detector,
scheduled tasks) as a fire-and-forget notification channel.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerNotificationRequest(BaseModel):
    """Request body to trigger a proactive notification."""
    trigger_type: str  # "anomaly_alert", "weekly_digest", "new_insight", "data_quality", "strategic_advice"
    dataset_id: str
    trigger_data: dict = {}
    known_context: str = ""


@router.post("/notifications/trigger")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def trigger_notification(
    request: Request,
    body: TriggerNotificationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger a proactive notification.

    The ProactiveNotificationAgent will:
    1. Check rate limits (prevent notification spam)
    2. Check relevance via BeliefStore (skip if user already knows)
    3. Compose appropriate content (deterministic or LLM-based)
    4. Return NotificationEvent ready for delivery

    Supported trigger types:
    - anomaly_alert: ⚠️ Data anomaly detected
    - data_quality: 📊 Quality issues found
    - new_insight: 💡 New insight generated
    - strategic_advice: 🎯 Strategic recommendations
    - weekly_digest: 📋 Periodic summary
    """
    user_id = current_user["id"]

    from services.proactive_notifications import ProactiveNotificationAgent

    notifier = ProactiveNotificationAgent()
    try:
        events = await notifier.process_trigger(
            trigger_type=body.trigger_type,
            trigger_data=body.trigger_data,
            user_id=user_id,
            dataset_id=body.dataset_id,
            known_context=body.known_context,
        )
    except Exception as e:
        logger.error(f"[Notifications] Trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Notification trigger failed")

    # Convert dataclass instances to dicts for JSON serialization
    events_dict = []
    for evt in events:
        events_dict.append({
            "event_type": evt.event_type,
            "priority": evt.priority,
            "title": evt.title,
            "body": evt.body,
            "cta": evt.cta,
            "dataset_id": evt.dataset_id,
            "metadata": evt.metadata,
        })

    return {
        "notifications": events_dict,
        "count": len(events_dict),
        "user_id": user_id,
        "dataset_id": body.dataset_id,
    }


@router.get("/notifications/status")
@limiter.limit(RateLimits.DATASET_GET)
async def get_notification_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Get current notification rate limit status for the user.

    Returns how many notifications of each type are remaining
    within the current rate limit window (1 hour).
    """
    from services.proactive_notifications import ProactiveNotificationAgent
    from services.proactive_notifications.notifier import TriggerType

    notifier = ProactiveNotificationAgent()
    user_id = current_user["id"]

    limits = {
        TriggerType.ANOMALY_ALERT: 5,
        TriggerType.WEEKLY_DIGEST: 1,
        TriggerType.NEW_INSIGHT: 3,
        TriggerType.DATA_QUALITY: 2,
        TriggerType.STRATEGIC_ADVICE: 2,
    }

    status = {}
    now_ts = datetime.utcnow().timestamp()

    for trigger_type, max_per_hour in limits.items():
        key = f"{user_id}__{trigger_type}"
        deliveries = notifier._recent_deliveries.get(key, [])
        # Prune expired entries
        recent = [ts for ts in deliveries if now_ts - ts < 3600]
        remaining = max(0, max_per_hour - len(recent))
        status[f"{trigger_type}_remaining"] = remaining

    return status
