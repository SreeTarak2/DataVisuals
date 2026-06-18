import math
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl
from bson import ObjectId

logger = logging.getLogger(__name__)


def convert_types_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: convert_types_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_types_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, pl.Date, pl.Datetime)):
        return obj.isoformat()
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif hasattr(obj, "item"):
        return obj.item()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def update_progress(
    datasets_collection,
    dataset_id: str,
    status: str,
    progress: int,
    stage: Optional[str] = None,
):
    """
    Update dataset processing progress in MongoDB.
    Replaces the Celery task update_state with direct DB writes.
    """
    update_doc = {
        "processing_status": stage or status.lower().replace(" ", "_"),
        "processing_progress": progress,
        "updated_at": datetime.utcnow(),
    }

    datasets_collection.update_one({"_id": dataset_id}, {"$set": update_doc})
    logger.info(f"[{dataset_id}] {status} ({progress}%)")


def extract_sample_rows(df: pl.DataFrame, n: int = 5) -> List[Dict]:
    try:
        sample_df = df.head(n)
        return sample_df.to_dicts()
    except Exception as e:
        logger.warning(f"Failed to extract sample rows: {e}")
        return []


__all__ = ["convert_types_for_json", "update_progress", "extract_sample_rows"]
