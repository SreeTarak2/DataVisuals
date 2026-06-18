"""
PipelineTracker
================
Tracks per-stage execution of the dataset processing pipeline.

Each stage records: name, label, status (running/done/failed), start/end time,
duration in ms, and error (if any). Stages are persisted to a
``pipeline_stages`` MongoDB collection as they complete, so the API can
serve them to the frontend in real time.

The tracker also updates ``processing_status``, ``current_stage_label``, and
``processing_progress`` on the dataset doc so the legacy polling endpoint
continues to work without changes.

Usage:
    tracker = PipelineTracker(dataset_id, user_id, db)
    async with tracker.stage("loading", "Loading Dataset"):
        df = load_dataset(file_path)
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


_PROGRESS_MAP: Dict[str, int] = {
    "loading": 5,
    "cleaning": 15,
    "metadata": 25,
    "domain_detection": 35,
    "kpi_pipeline": 42,
    "profiling": 45,
    "analysis": 55,
    "quis_analysis": 65,
    "charts": 70,
    "quality": 80,
    "consolidating": 85,
    "saving": 90,
    "artifact_generation": 94,
    "strategic_advisor": 94,
    "vector_indexing": 97,
    "completed": 100,
}


class PipelineTracker:
    """
    Context-manager-based stage tracker for the dataset pipeline.

    Stages are written to MongoDB *after* they complete (or fail), keeping
    write overhead out of the critical path. The dataset doc is updated
    synchronously with ``processing_status``, ``processing_progress``, and
    ``current_stage_label`` so the legacy progress-polling endpoint still
    works during a stage.

    Graceful degradation: if MongoDB writes fail, the tracker logs a warning
    and the pipeline continues unaffected.
    """

    def __init__(self, dataset_id: str, user_id: str, db) -> None:
        """
        Args:
            dataset_id: MongoDB ``_id`` of the dataset being processed.
            user_id:   Owner of the dataset.
            db:        Sync PyMongo database instance (``_get_db()``).
        """
        self.dataset_id = dataset_id
        self.user_id = user_id
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def stage(self, name: str, label: str):
        """
        Async context manager that wraps a single pipeline stage.

        Usage::

            async with tracker.stage("loading", "Loading Dataset"):
                df = load_dataset(file_path)

        Args:
            name:  Machine-readable stage key (e.g. ``"loading"``,
                   ``"domain_detection"``). Written to
                   ``processing_status`` on the dataset doc.
            label: Human-readable label (e.g. ``"Loading Dataset"``).
                   Written to ``current_stage_label`` on the dataset doc.
        """
        start_time = datetime.utcnow()
        stage_record: Dict[str, Any] = {
            "dataset_id": self.dataset_id,
            "user_id": self.user_id,
            "name": name,
            "label": label,
            "status": "running",
            "start_time": start_time.isoformat(),
            "end_time": None,
            "duration_ms": None,
            "error": None,
        }

        # Update dataset doc so legacy polling sees the current stage
        self._update_dataset_status(name, label)

        try:
            yield
        except Exception as exc:
            stage_record["status"] = "failed"
            stage_record["error"] = str(exc)[:500]
            raise
        else:
            stage_record["status"] = "done"
        finally:
            end_time = datetime.utcnow()
            stage_record["end_time"] = end_time.isoformat()
            stage_record["duration_ms"] = int(
                (end_time - start_time).total_seconds() * 1000
            )
            self._persist_stage(stage_record)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_dataset_status(self, name: str, label: str) -> None:
        """Write current stage info + derived progress to the dataset doc."""
        progress_pct = _PROGRESS_MAP.get(name, 50)
        try:
            self.db.uploads.update_one(
                {"_id": self.dataset_id},
                {
                    "$set": {
                        "processing_status": name,
                        "current_stage_label": label,
                        "processing_progress": progress_pct,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as exc:
            logger.warning(
                "[Tracker] Failed to update dataset status for %s: %s",
                self.dataset_id,
                exc,
            )

    def _persist_stage(self, stage_record: Dict[str, Any]) -> None:
        """Write the completed (or failed) stage record to MongoDB."""
        try:
            self.db.pipeline_stages.insert_one(stage_record)

            # Keep only the most recent 50 stages per dataset to prevent
            # unbounded growth from repeated reprocessing.
            older_id = self.db.pipeline_stages.find_one(
                {"dataset_id": self.dataset_id},
                sort=[("_id", -1)],
                projection={"_id": 1},
                skip=50,
            )
            if older_id:
                self.db.pipeline_stages.delete_many(
                    {
                        "dataset_id": self.dataset_id,
                        "_id": {"$lt": older_id["_id"]},
                    }
                )
        except Exception as exc:
            logger.warning(
                "[Tracker] Failed to persist stage for %s: %s",
                self.dataset_id,
                exc,
            )


__all__ = ["PipelineTracker"]
