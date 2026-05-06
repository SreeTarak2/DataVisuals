from workers.celery_app import celery_app
from workers.database import get_db, init_worker_db
from workers.async_helper import run_async

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="datasage.generate_narrative_story", max_retries=2)
def generate_narrative_story_task(self, dataset_id: str, user_id: str = "unknown"):
    logger.info(f"╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║ NARRATIVE STORY GENERATION STARTED: {dataset_id:<25} ║")
    logger.info(f"╚════════════════════════════════════════════════════════════════╝")

    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    datasets_collection = db.uploads

    try:
        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "artifact_status.narrative_story": "generating",
                    "story_generation_started_at": datetime.utcnow(),
                }
            },
        )

        from services.narrative.story_weaver import story_weaver

        dataset_doc = datasets_collection.find_one({"_id": dataset_id})
        if not dataset_doc:
            raise ValueError(f"Dataset not found: {dataset_id}")

        dataset_name = dataset_doc.get("name", "Unknown")
        domain = dataset_doc.get("domain", "general")
        metadata = dataset_doc.get("metadata", {})
        deep_analysis = metadata.get("deep_analysis", {})
        statistical_findings = metadata.get("statistical_findings", {})

        narrative_story = run_async(
            story_weaver.weave_story(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                domain=domain,
                correlations=[],
                anomalies=[],
                trends=[],
                segments=[],
                key_findings=[],
                distributions=[],
                driver_analysis=[],
                data_quality={},
                recommendations=[],
            )
        )

        if narrative_story:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "cached_narrative_story": narrative_story,
                        "cached_story_generated_at": datetime.utcnow(),
                        "cached_story_version": "2.0",
                        "artifact_status.narrative_story": "ready",
                        "story_generation_completed_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"✓ Narrative story generated and cached for {dataset_id}")

            return {
                "status": "success",
                "dataset_id": dataset_id,
                "story_generated": True,
            }
        else:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "artifact_status.narrative_story": "failed",
                        "story_generation_error": "Story generation returned None",
                        "story_generation_completed_at": datetime.utcnow(),
                    }
                },
            )
            return {
                "status": "failed",
                "dataset_id": dataset_id,
                "story_generated": False,
                "error": "Story generation returned None",
            }

    except Exception as e:
        logger.error(f"✗ Narrative story generation failed for {dataset_id}: {e}")

        datasets_collection.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "artifact_status.narrative_story": "failed",
                    "story_generation_error": str(e)[:500],
                    "story_generation_completed_at": datetime.utcnow(),
                }
            },
        )

        if self.request.retries < self.max_retries:
            retry_in = 2**self.request.retries * 10
            logger.info(
                f"Retrying story generation in {retry_in}s... (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=retry_in)

        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "story_generated": False,
            "error": str(e),
        }
