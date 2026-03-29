"""PDF Report Generation API.

Endpoints for generating professional PDF reports.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse

from services.report import generate_pdf_report
from services.auth_service import get_current_user
from db.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter()


async def _track_report_download(
    dataset_id: str,
    user_id: str,
    title: str,
    include_charts: bool,
    status: str,
    file_size: int,
    findings_count: int,
    warnings_count: int,
    domain: str,
    charts_included: list,
):
    """Track report download in the reports collection."""
    try:
        db = get_database()
        report_doc = {
            "_id": str(uuid.uuid4()),
            "dataset_id": dataset_id,
            "user_id": user_id,
            "title": title,
            "generated_at": datetime.utcnow(),
            "include_charts": include_charts,
            "status": status,
            "file_size": file_size,
            "findings_count": findings_count,
            "warnings_count": warnings_count,
            "domain": domain,
            "charts_included": charts_included,
        }
        await db.reports.insert_one(report_doc)
        logger.info(f"Tracked report download: {report_doc['_id']}")
    except Exception as e:
        logger.warning(f"Failed to track report download: {e}")


@router.get("/reports/{dataset_id}/pdf")
async def generate_report_pdf(
    dataset_id: str,
    preview: bool = Query(False, description="Return HTML preview instead of PDF"),
    include_charts: bool = Query(
        True, description="Include AI-selected charts in report"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a professional PDF report for a dataset.

    The report includes:
    - Executive summary with story narrative
    - All key findings with technical details
    - Full statistical analysis (correlations, p-values, etc.)
    - AI-selected supporting visualizations
    - Anomaly detection results
    - Data quality assessment
    - Actionable recommendations
    - Appendix with raw statistics

    Args:
        dataset_id: The ID of the dataset to generate report for
        preview: If True, returns HTML instead of PDF (for debugging)
        include_charts: Whether to include AI-selected charts

    Returns:
        PDF file download or HTML preview
    """
    user_id = current_user["id"]
    try:
        logger.info(
            f"Generating PDF report for dataset: {dataset_id}, user: {user_id}, preview={preview}"
        )

        # Generate report (PDF bytes or HTML string)
        result = await generate_pdf_report(
            dataset_id=dataset_id, include_charts=include_charts, preview=preview
        )

        if preview:
            # Return HTML for preview
            from fastapi.responses import HTMLResponse

            return HTMLResponse(content=result, media_type="text/html")

        # Get report info for tracking
        report_info = await _get_report_summary(dataset_id, user_id)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analytical_report_{dataset_id}_{timestamp}.pdf"

        # Track the download
        await _track_report_download(
            dataset_id=dataset_id,
            user_id=user_id,
            title=report_info.get("title", "Analytical Report"),
            include_charts=include_charts,
            status="completed",
            file_size=len(result),
            findings_count=report_info.get("findings_count", 0),
            warnings_count=report_info.get("warnings_count", 0),
            domain=report_info.get("domain", "general"),
            charts_included=report_info.get("charts_included", []),
        )

        # Return PDF as streaming response
        return StreamingResponse(
            iter([result]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(result)),
            },
        )

    except ValueError as e:
        logger.error(f"Dataset not found: {dataset_id}")
        # Track failed attempt
        await _track_report_download(
            dataset_id=dataset_id,
            user_id=user_id,
            title="Analytical Report",
            include_charts=include_charts,
            status="failed",
            file_size=0,
            findings_count=0,
            warnings_count=0,
            domain="unknown",
            charts_included=[],
        )
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate PDF report: {str(e)}"
        )


async def _get_report_summary(dataset_id: str, user_id: str) -> dict:
    """Get summary info from dataset for report tracking."""
    try:
        db = get_database()
        try:
            from bson import ObjectId

            dataset = await db.uploads.find_one(
                {"_id": ObjectId(dataset_id), "user_id": user_id}
            )
        except Exception:
            dataset = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})

        if not dataset:
            return {
                "title": "Analytical Report",
                "domain": "unknown",
                "findings_count": 0,
                "warnings_count": 0,
                "charts_included": [],
            }

        insights = dataset.get("insights", {})
        story = insights.get("story", insights.get("report", {}))

        return {
            "title": f"{dataset.get('name', 'Analytical Report')} Report",
            "domain": dataset.get("domain", "general"),
            "findings_count": len(story.get("findings", [])),
            "warnings_count": len(
                story.get("warnings", story.get("complications", []))
            ),
            "charts_included": [
                c.get("title", "Chart") for c in dataset.get("charts_data", [])[:5]
            ],
        }
    except Exception:
        return {
            "title": "Analytical Report",
            "domain": "unknown",
            "findings_count": 0,
            "warnings_count": 0,
            "charts_included": [],
        }


@router.get("/reports/{dataset_id}/report-info")
async def get_report_info(
    dataset_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get metadata about what would be included in a report.

    Useful for previewing report contents before generation.
    """
    user_id = current_user["id"]
    try:
        db = get_database()
        try:
            from bson import ObjectId

            dataset = await db.uploads.find_one(
                {"_id": ObjectId(dataset_id), "user_id": user_id}
            )
        except Exception:
            dataset = await db.uploads.find_one({"_id": dataset_id, "user_id": user_id})

        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        insights = dataset.get("insights", {})
        story = insights.get("story", insights.get("report", {}))

        return {
            "dataset_id": str(dataset.get("_id", "")),
            "dataset_name": dataset.get("name", "Untitled"),
            "domain": dataset.get("domain", "general"),
            "total_records": dataset.get("row_count", 0),
            "total_columns": dataset.get("column_count", 0),
            # Report content summary
            "story_title": story.get(
                "title", story.get("opening", {}).get("hook", "N/A")
            ),
            "findings_count": len(story.get("findings", [])),
            "warnings_count": len(
                story.get("warnings", story.get("complications", []))
            ),
            # Technical data counts
            "correlations_count": len(insights.get("correlations", [])),
            "trends_count": len(insights.get("trends", [])),
            "anomalies_count": len(insights.get("anomalies", [])),
            # Data quality
            "data_quality": {
                "health_score": insights.get("data_quality", {}).get("health_score", 0),
                "completeness": insights.get("data_quality", {}).get("completeness", 0),
            },
            # Charts available
            "charts_available": len(dataset.get("charts_data", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/history")
async def get_report_history(
    limit: int = Query(20, description="Number of reports to return"),
    skip: int = Query(0, description="Number of reports to skip"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get report download history for the current user.

    Returns a list of previously generated/downloaded reports.
    """
    user_id = current_user["id"]
    try:
        db = get_database()
        cursor = (
            db.reports.find({"user_id": user_id})
            .sort("generated_at", -1)
            .skip(skip)
            .limit(limit)
        )

        reports = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            reports.append(doc)

        total = await db.reports.count_documents({"user_id": user_id})

        return {
            "reports": reports,
            "total": total,
            "limit": limit,
            "skip": skip,
            "has_more": (skip + limit) < total,
        }

    except Exception as e:
        logger.error(f"Error getting report history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
