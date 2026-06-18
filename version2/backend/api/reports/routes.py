import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from bson import ObjectId

from db.database import get_database
from services.auth_service import get_current_user
from services.report.pdf_generator import generate_pdf_report

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_owned_dataset(dataset_id: str, user_id: str):
    db = get_database()
    dataset = None
    try:
        dataset = await db.uploads.find_one({"_id": ObjectId(dataset_id), "user_id": user_id})
    except Exception:
        pass
    if not dataset:
        dataset = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found or access denied")
    return dataset


@router.get("/reports/{dataset_id}/pdf")
async def download_pdf_report(
    dataset_id: str,
    include_charts: bool = Query(True),
    preview: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    dataset = await _get_owned_dataset(dataset_id, current_user["id"])
    try:
        result = await generate_pdf_report(
            dataset_id=dataset_id,
            include_charts=include_charts,
            preview=preview,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"PDF generation failed for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")

    if preview:
        return Response(content=result, media_type="text/html")

    dataset_name = dataset.get("name", "report").replace(" ", "_").lower()
    filename = f"{dataset_name}_signal_report.pdf"
    return Response(
        content=result,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(result)),
        },
    )


@router.get("/reports/{dataset_id}/report-info")
async def get_report_info(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    dataset = await _get_owned_dataset(dataset_id, current_user["id"])
    insights = dataset.get("insights", {})
    dq = insights.get("data_quality", dataset.get("data_quality", {}))

    has_story = bool(
        dataset.get("cached_narrative_story") or insights.get("story")
    )

    try:
        db = get_database()
        ds_doc = await db.datasets.find_one({"dataset_id": dataset_id})
        if not ds_doc:
            try:
                ds_doc = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
            except Exception:
                pass
        if ds_doc and ds_doc.get("insights_cache", {}).get("story"):
            has_story = True
    except Exception:
        pass

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.get("name", "Untitled"),
        "has_story": has_story,
        "has_analysis": bool(insights),
        "row_count": dataset.get("row_count", 0),
        "column_count": dataset.get("column_count", 0),
        "health_score": dq.get("health_score", 0),
        "count_findings": len(insights.get("key_findings", [])),
        "count_correlations": len(insights.get("correlations", [])),
        "count_trends": len(insights.get("trends", [])),
        "count_anomalies": len(insights.get("anomalies", [])),
        "ready_for_pdf": bool(insights),
    }
