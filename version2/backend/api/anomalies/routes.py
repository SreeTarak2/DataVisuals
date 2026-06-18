"""
API endpoint for the AnomalyInvestigatorAgent.

Accepts anomaly data (or dataset ID to auto-detect) and runs a full
root cause investigation pipeline: detect → root causes → impact →
recommendations → narrative.

Caches results in dataset_analytics for fast re-fetching.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from core.rate_limiter import limiter, RateLimits
from services.auth_service import get_current_user
from services.datasets.enhanced_dataset_service import enhanced_dataset_service

logger = logging.getLogger(__name__)
router = APIRouter()


class AnomalyInvestigationRequest(BaseModel):
    """Request body for anomaly investigation. Anomalies are optional — will auto-detect if omitted."""
    columns: Optional[list[dict]] = None
    anomalies: Optional[list[dict]] = None
    investigation_id: Optional[str] = ""


@router.post("/datasets/{dataset_id}/investigate-anomalies")
@limiter.limit(RateLimits.AI_INSIGHTS)
async def investigate_anomalies(
    request: Request,
    dataset_id: str,
    body: AnomalyInvestigationRequest,
    force_refresh: bool = Query(False, description="Regenerate even if cached"),
    current_user: dict = Depends(get_current_user),
):
    """
    Run a full anomaly investigation.

    If anomalies are not provided in the request body, the agent will
    auto-detect them from the dataset's numeric columns.

    Returns an AnomalyReport with:
    - anomalies: List of detected anomalies
    - root_causes: Identified root causes with explanations
    - impact: Business impact assessment
    - recommendations: Corrective actions
    - narrative: Business-friendly summary
    - confidence: Overall confidence score
    """
    from db.database import get_database

    user_id = current_user["id"]
    db = get_database()

    # ── Check cache (unless force refresh) ──────────────────────────────────
    if not force_refresh:
        try:
            analytics = await db.dataset_analytics.find_one(
                {"dataset_id": dataset_id, "user_id": user_id},
                {"anomaly_investigation": 1},
            )
            if analytics and analytics.get("anomaly_investigation"):
                return {
                    "anomaly_report": analytics["anomaly_investigation"],
                    "source": "cache",
                    "dataset_id": dataset_id,
                }
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] Cache read failed: {e}")

    # ── Load dataset metadata ──────────────────────────────────────────────
    try:
        dataset = await enhanced_dataset_service.get_dataset(dataset_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AnomalyInvestigator] Failed to get dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dataset.")

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.get("is_processed"):
        raise HTTPException(status_code=202, detail="Dataset still processing — try again shortly")

    metadata = dataset.get("metadata", {})
    columns = body.columns or metadata.get("column_metadata", [])
    row_count = dataset.get("row_count", 0)
    sample_rows = metadata.get("sample_data", [])

    # ── Load DataFrame for auto-detection (if no anomalies provided) ────────
    df = None
    if not body.anomalies:
        try:
            df = await enhanced_dataset_service.load_dataset_data(dataset_id, user_id)
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] Could not load DF: {e}")

    # ── Run investigation ──────────────────────────────────────────────────
    from services.anomaly_investigator import AnomalyInvestigatorAgent

    investigator = AnomalyInvestigatorAgent()
    investigation_id = body.investigation_id or str(uuid.uuid4())

    try:
        report = await investigator.investigate(
            dataset_id=dataset_id,
            columns=columns,
            anomalies=body.anomalies,
            df=df,
            sample_rows=sample_rows[:3] if sample_rows else None,
            row_count=row_count,
            investigation_id=investigation_id,
        )
    except Exception as e:
        logger.error(f"[AnomalyInvestigator] Investigation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Anomaly investigation failed")

    # ── Build response dict ────────────────────────────────────────────────
    report_dict = {
        "anomalies": report.anomalies,
        "root_causes": report.root_causes,
        "impact": report.impact,
        "narrative": report.narrative,
        "recommendations": report.recommendations,
        "investigation_id": report.investigation_id,
        "dataset_id": report.dataset_id,
        "confidence": report.confidence,
        "investigated_at": datetime.utcnow().isoformat(),
    }

    # ── Cache for future requests ──────────────────────────────────────────
    try:
        await db.dataset_analytics.update_one(
            {"dataset_id": dataset_id, "user_id": user_id},
            {
                "$set": {
                    "anomaly_investigation": report_dict,
                    "anomaly_investigation_generated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[AnomalyInvestigator] Cache write failed: {e}")

    return {
        "anomaly_report": report_dict,
        "source": "generated",
        "dataset_id": dataset_id,
    }
