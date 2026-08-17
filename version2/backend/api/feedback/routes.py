import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user
from services.feedback.context_store import context_store

logger = logging.getLogger(__name__)
router = APIRouter()


class CaptureSemanticRequest(BaseModel):
    query_context: Optional[str] = None


@router.post("/corrections/{rule_id}/capture-semantic")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def capture_correction_semantic(
    request: Request,
    rule_id: str,
    body: CaptureSemanticRequest,
    current_user: dict = Depends(get_current_user),
):
    """Explicitly capture a correction as a semantic metric definition."""
    semantic = await context_store.capture_semantic_from_correction(
        rule_id=rule_id,
        query_context=body.query_context,
    )

    if not semantic:
        raise HTTPException(
            status_code=400,
            detail="Could not extract semantic definition from this correction. "
            "The correction must follow a semantic pattern like 'X means Y' or 'X refers to Y'.",
        )

    return {"semantic": semantic.model_dump()}
