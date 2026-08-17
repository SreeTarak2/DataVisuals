"""
Stuck-pipeline recovery for the dataset processing pipeline.

Pipeline runs are fire-and-forget ``asyncio.create_task`` calls. If the
server restarts (or a dev ``--reload`` triggers while a large file is being
processed), the background task dies and the dataset doc keeps whatever
``processing_status`` / ``processing_progress`` it had — e.g. stuck at
``"loading"`` / 5% forever. Nothing ever advances it: the frontend shows
"Analyzing Dataset" indefinitely, the dataset blocks duplicate re-uploads,
and the user has no way to recover.

On startup we sweep every non-terminal dataset and:

* **File present** → reset to ``pending``, clear stale stage records, and
  re-dispatch ``process_dataset`` (the pipeline's compare-and-swap claim
  makes concurrent spawns safe — only one task wins).
* **File missing** → mark ``failed`` with a clear message so the frontend
  shows "Processing Failed" (with Retry) instead of spinning forever, and
  so re-uploading the same file is not blocked by duplicate detection.

Runnable standalone (from version2/backend/):

    python -m services.pipeline.recovery            # re-queue stuck docs, then exit
    python -m services.pipeline.recovery --wait     # re-queue AND wait for processing
    python -m services.pipeline.recovery --dry-run  # report only, no writes

Note: standalone runs re-queue docs for the *next* server start to process;
use ``--wait`` to process them in this process instead.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

# Statuses that mean "processing finished (or is beyond recovery)".
TERMINAL_STATUSES = {"completed", "success", "failed", "error", "cancelled"}


async def _get_db():
    from db.database import get_database

    return get_database()


def _recoverable(doc: dict) -> bool:
    """A dataset is stuck if it's active and not in a terminal state."""
    if not doc.get("is_active", True):
        return False
    status = doc.get("processing_status", "")
    return status not in TERMINAL_STATUSES


async def _recover_one(db, doc: dict, spawn: bool) -> tuple[str, str, object | None]:
    """Recover a single stuck dataset.

    Returns ``(dataset_id, outcome, task_or_none)`` where outcome is one of
    ``"requeued"`` / ``"failed_missing_file"`` and ``task_or_none`` is the
    background processing task when one was spawned.
    """
    dataset_id = str(doc["_id"])
    file_path = doc.get("file_path", "")
    s3_key = doc.get("s3_parquet_key")
    status = doc.get("processing_status", "")

    # Display name for recovery notifications
    dataset_name = doc.get("name") or doc.get("original_filename") or "your dataset"

    # A dataset whose source file is gone can never be processed — mark it
    # failed with a clear message instead of re-queuing into a guaranteed
    # failure loop. (S3-backed datasets still have a local file_path copy.)
    file_missing = not file_path or not Path(file_path).exists()
    if file_missing and not (settings.S3_ENABLED and s3_key):
        await db.uploads.update_one(
            {"_id": dataset_id},
            {
                "$set": {
                    "is_processed": True,
                    "processing_status": "failed",
                    "processing_progress": 0,
                    "processing_error": (
                        "Processing was interrupted (likely a server restart) and the "
                        "source file is no longer available. Re-upload the dataset."
                    ),
                    "error_type": "InterruptedPipeline",
                    "failed_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                }
            },
        )
        logger.warning(
            "[Recovery] Dataset %s stuck in %r but source file missing → marked failed",
            dataset_id[:8],
            status,
        )
        # Notify the user their interrupted upload could not be recovered
        try:
            from services.notifications.service import (
                CTA_RETRY_PROCESSING,
                TYPE_DATASET_FAILED,
                create_notification,
            )

            await create_notification(
                user_id=doc.get("user_id", "unknown"),
                workspace_id=doc.get("workspace_id", doc.get("user_id", "unknown")),
                notif_type=TYPE_DATASET_FAILED,
                title=f"⚠️ Processing interrupted: {dataset_name}",
                body=(
                    f"We couldn't finish processing \"{dataset_name}\" — the upload was "
                    "interrupted and the source file is no longer available. "
                    "Please re-upload the file."
                ),
                cta={"text": "Re-upload", "action": CTA_RETRY_PROCESSING},
                dataset_id=dataset_id,
                dataset_name=dataset_name,
            )
        except Exception as e:
            logger.warning(f"[Recovery] Failed to notify user about missing file: {e}")
        return dataset_id, "failed_missing_file", None

    # Reset to pending and clear stale stage records so the frontend /stages
    # view starts fresh. The next claim (pending → running) re-arms the
    # compare-and-swap guard, so concurrent spawns are safe.
    await db.pipeline_stages.delete_many({"dataset_id": dataset_id})
    await db.uploads.update_one(
        {"_id": dataset_id},
        {
            "$set": {
                "processing_status": "pending",
                "processing_progress": 0,
                "current_stage_label": None,
                "processing_error": None,
                "error_type": None,
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
            },
            "$unset": {"failed_at": ""},
        },
    )

    task = None
    if spawn:
        from services.pipeline.process import process_dataset

        task = asyncio.create_task(
            process_dataset(
                dataset_id,
                file_path,
                doc.get("user_id", "unknown"),
                workspace_id=doc.get("workspace_id"),
            )
        )
        logger.info(
            "[Recovery] Dataset %s re-queued (was stuck in %r @ %s%%)",
            dataset_id[:8],
            status,
            doc.get("processing_progress", 0),
        )
        # Notify the user their interrupted upload is being reprocessed
        try:
            from services.notifications.service import (
                CTA_OPEN_DASHBOARD,
                TYPE_DATASET_RESUMED,
                create_notification,
            )

            await create_notification(
                user_id=doc.get("user_id", "unknown"),
                workspace_id=doc.get("workspace_id", doc.get("user_id", "unknown")),
                notif_type=TYPE_DATASET_RESUMED,
                title=f"🔄 Processing resumed: {dataset_name}",
                body=(
                    f"We noticed \"{dataset_name}\" was interrupted and have "
                    "automatically resumed processing it."
                ),
                cta={"text": "Open dashboard", "action": CTA_OPEN_DASHBOARD},
                dataset_id=dataset_id,
                dataset_name=dataset_name,
            )
        except Exception as e:
            logger.warning(f"[Recovery] Failed to notify user about resume: {e}")
    else:
        logger.info(
            "[Recovery] Dataset %s reset to pending (was stuck in %r @ %s%%)",
            dataset_id[:8],
            status,
            doc.get("processing_progress", 0),
        )
    return dataset_id, "requeued", task


async def recover_stuck_datasets(
    db=None,
    dry_run: bool = False,
    spawn: bool = True,
    wait: bool = False,
) -> dict:
    """Find stuck datasets and recover them.

    Args:
        db:      Database handle (resolved lazily when None).
        dry_run: Report only — no writes, no task spawns.
        spawn:   Re-dispatch ``process_dataset`` for re-queued docs. When
                 False the doc is reset to ``pending`` for the next server
                 start to claim (standalone diagnostics).
        wait:    Await the spawned processing tasks (standalone ``--wait``).

    Returns a summary dict with lists of dataset ids per outcome, plus a
    ``would_recover`` list in dry-run mode.
    """
    db = db if db is not None else await _get_db()
    cursor = db.uploads.find(
        {"is_active": True, "processing_status": {"$nin": list(TERMINAL_STATUSES)}}
    )

    summary = {
        "requeued": [],
        "failed_missing_file": [],
        "would_recover": [],
    }
    tasks: list = []

    async for doc in cursor:
        if not _recoverable(doc):
            continue
        if dry_run:
            summary["would_recover"].append(str(doc["_id"]))
            logger.info(
                "[Recovery][dry-run] Would recover %s (status=%r @ %s%%)",
                str(doc["_id"])[:8],
                doc.get("processing_status", ""),
                doc.get("processing_progress", 0),
            )
            continue
        dataset_id, outcome, task = await _recover_one(db, doc, spawn=spawn)
        summary[outcome].append(dataset_id)
        if task is not None:
            tasks.append(task)

    if wait and tasks:
        logger.info("[Recovery] Waiting for %d re-queued pipeline task(s)...", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)

    return summary


async def _standalone(args) -> None:
    from db.database import close_mongo_connection, connect_to_mongo

    await connect_to_mongo()
    db = await _get_db()
    try:
        summary = await recover_stuck_datasets(
            db=db,
            dry_run=args.dry_run,
            spawn=not args.dry_run,
            wait=args.wait and not args.dry_run,
        )
        print("\nRecovery summary:")
        if args.dry_run:
            print(f"  would recover:     {len(summary['would_recover'])}")
        else:
            print(f"  requeued:          {len(summary['requeued'])}")
            print(f"  failed (missing):  {len(summary['failed_missing_file'])}")
        if not args.dry_run and not args.wait and summary["requeued"]:
            print(
                "  Note: re-queued datasets will be processed on the next server "
                "start (or use --wait to process them now)."
            )
        print("Done.")
    finally:
        await close_mongo_connection()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for re-queued pipeline tasks to finish (standalone)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s [%(correlation_id)s] %(message)s",
    )

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_standalone(args))


if __name__ == "__main__":
    main()
