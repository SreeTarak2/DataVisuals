import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from core.rate_limiter import limiter, RateLimits
from api.auth import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service
from db.database import get_database

router = APIRouter()


# ---------------------------------------------------------------------------
# Alpha state helpers — per-user α parameter persisted in MongoDB
# ---------------------------------------------------------------------------

_ALPHA_COLLECTION = "user_settings"
_DEFAULT_ALPHA = 0.6  # Per paper §III.E


async def _get_user_alpha(user_id: str) -> float:
    """Load the user's current α from MongoDB, falling back to 0.6."""
    try:
        db = get_database()
        doc = await db[_ALPHA_COLLECTION].find_one({"user_id": user_id}, {"alpha": 1})
        if doc and "alpha" in doc:
            return float(doc["alpha"])
    except Exception:
        pass
    return _DEFAULT_ALPHA


async def _save_user_alpha(user_id: str, alpha: float) -> None:
    """Persist the user's α to MongoDB."""
    try:
        db = get_database()
        await db[_ALPHA_COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": {"alpha": alpha, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
            upsert=True,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class DismissInsightRequest(BaseModel):
    """
    Body for POST /{insight_id}/dismiss.

    Attributes:
        insight_text: The full text of the dismissed insight
        dataset_id: Optional — the dataset this insight belongs to
        metric_name: Optional — name of the metric, for Bayesian surprise
        metric_value: Optional — numeric value of the metric
    """
    insight_text: str = Field(..., min_length=10, max_length=2000)
    dataset_id: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None


# ---------------------------------------------------------------------------
# Accept / useful feedback
# ---------------------------------------------------------------------------

class AcceptInsightRequest(BaseModel):
    """
    Body for POST /accept.

    Attributes:
        insight_text: The full text of the accepted (thumbs-up) insight
        dataset_id: Optional — the dataset this insight belongs to
    """
    insight_text: str = Field(..., min_length=10, max_length=2000)
    dataset_id: Optional[str] = None


@router.post("/accept")
@limiter.limit(RateLimits.INSIGHT_DISMISS)
async def accept_insight(
    request: Request,
    body: AcceptInsightRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Mark an insight as "useful" (thumbs up).

    Stores the insight in the Belief Store (ChromaDB) with confidence 0.7
    so it becomes a known belief. Unlike dismiss, this does NOT update α
    because the user is not saying "I already knew this" — they're saying
    "this was a good insight."

    Returns the belief_id so the frontend can track it.
    """
    from agents.belief.belief_store import get_belief_store

    user_id = current_user["id"]
    store = get_belief_store()
    belief_id = await store.accept_insight(
        user_id=user_id,
        insight_text=body.insight_text,
        dataset_id=body.dataset_id,
    )

    logger.info(f"[ACCEPT] User {user_id} accepted insight (belief_id={belief_id})")

    return {
        "belief_id": belief_id,
        "status": "accepted",
    }


# ---------------------------------------------------------------------------
# Reject / thumbs-down feedback (quality signal, NOT SND)
# ---------------------------------------------------------------------------

class RejectInsightRequest(BaseModel):
    """
    Body for POST /reject.

    Attributes:
        insight_text: The full text of the rejected insight
        dataset_id: Optional — the dataset this insight belongs to
        reason: Optional — why the user rejected it
    """
    insight_text: str = Field(..., min_length=1, max_length=2000)
    dataset_id: Optional[str] = None
    reason: Optional[str] = None


@router.post("/reject")
@limiter.limit(RateLimits.INSIGHT_DISMISS)
async def reject_insight(
    request: Request,
    body: RejectInsightRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Log a thumbs-down rejection with an optional reason.

    This is a quality signal for improving AI responses. It does NOT
    store in ChromaDB (this isn't something the user already knew)
    and does NOT update alpha. It's logged for aggregate analytics.
    """
    user_id = current_user["id"]
    logger.info(
        f"[REJECT] User {user_id} rejected insight "
        f"(reason={body.reason}, text={body.insight_text[:80]}…)"
    )
    return {"status": "logged"}


# ---------------------------------------------------------------------------
# Dismiss / "already knew" feedback
# ---------------------------------------------------------------------------

class DismissInsightRequest(BaseModel):
    """
    Body for POST /{insight_id}/dismiss.

    Attributes:
        insight_text: The full text of the dismissed insight
        dataset_id: Optional — the dataset this insight belongs to
        metric_name: Optional — name of the metric, for Bayesian surprise
        metric_value: Optional — numeric value of the metric
    """
    insight_text: str = Field(..., min_length=10, max_length=2000)
    dataset_id: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None


@router.post("/{insight_id}/dismiss")
@limiter.limit(RateLimits.INSIGHT_DISMISS)
async def dismiss_insight(
    request: Request,
    insight_id: str,
    body: DismissInsightRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Mark an insight as "already known" — real-time alpha adaptation.

    Does three things:
    1. Stores the insight in the Belief Store (ChromaDB) as a known belief
       so it won't be shown as novel again (confidence=0.95)
    2. Computes Bayesian surprise for the associated metric to determine
       whether this rejection was "expected" or "surprising"
    3. Updates the user's adaptive α via EMA (Paper Eq. 8):
       - If user rejected despite high Bayesian surprise → semantics missed
         it → α increases (weigh semantics more next time)
       - If user rejected with low Bayesian surprise → nothing special → α unchanged
    4. Persists the updated α to MongoDB so it survives server restarts

    Returns the new α so the frontend can display it (e.g., in settings).
    """
    from agents.belief.belief_store import get_belief_store, get_bayesian_tracker, BeliefStore

    user_id = current_user["id"]

    # ── Step 1: Store in Belief Store ──
    store = get_belief_store()
    belief_id = await store.mark_as_known(
        user_id=user_id,
        insight_text=body.insight_text,
        dataset_id=body.dataset_id,
    )

    # ── Step 2: Compute Bayesian surprise for the associated metric ──
    bayesian = await get_bayesian_tracker()
    had_high_bayesian = False
    if body.metric_name is not None and body.metric_value is not None:
        surprise = bayesian.calculate_surprise(body.metric_name, body.metric_value)
        had_high_bayesian = surprise > 0.5
        logger.info(
            f"[ALPHA] Insight dismissed: metric={body.metric_name}, "
            f"value={body.metric_value}, bayesian_surprise={surprise:.3f}, "
            f"had_high_bayesian={had_high_bayesian}"
        )

    # ── Step 3: Update α via EMA ──
    current_alpha = await _get_user_alpha(user_id)
    new_alpha = BeliefStore.update_alpha(
        current_alpha=current_alpha,
        was_rejected=True,
        had_high_bayesian=had_high_bayesian,
    )

    # ── Step 4: Persist α ──
    await _save_user_alpha(user_id, new_alpha)

    logger.info(
        f"[ALPHA] User {user_id}: α {current_alpha:.3f} → {new_alpha:.3f} "
        f"(insight {insight_id[:12]}… dismissed, had_high_bayesian={had_high_bayesian})"
    )

    # Persist updated Bayesian priors to MongoDB (multi-replica safe)
    await bayesian.persist()

    return {
        "belief_id": belief_id,
        "alpha_previous": current_alpha,
        "alpha_updated": new_alpha,
    }
