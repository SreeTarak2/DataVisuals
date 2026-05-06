from workers.celery_app import celery_app
from workers.database import get_db, init_worker_db

import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="cleanup_expired_datasets")
def cleanup_expired_datasets(self):
    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    try:
        privacy_collection = db["privacy_settings"]
        datasets_collection = db["uploads"]
        users_collection = db["users"]

        all_datasets = list(datasets_collection.find({}))

        deleted_count = 0
        warned_count = 0

        for dataset in all_datasets:
            user_id = dataset.get("user_id")
            dataset_id = dataset.get("_id")
            created_at = dataset.get("created_at")

            if not created_at or not user_id:
                continue

            user_privacy = privacy_collection.find_one({"user_id": user_id})
            retention_days = 90

            if user_privacy:
                retention_days = user_privacy.get("global_defaults", {}).get(
                    "data_retention_days", 90
                )

            if retention_days == -1:
                continue

            expiration_date = created_at + timedelta(days=retention_days)
            warning_date = expiration_date - timedelta(days=7)
            now = datetime.utcnow()

            if warning_date <= now < expiration_date:
                if user_privacy.get("global_defaults", {}).get(
                    "send_retention_warnings", True
                ):
                    user = users_collection.find_one({"_id": user_id})
                    if user and user.get("email"):
                        logger.info(
                            f"[RETENTION] Warning for dataset {dataset_id} to user {user_id}"
                        )
                        warned_count += 1

            if now >= expiration_date:
                file_path = dataset.get("file_path")
                parquet_path = dataset.get("parquet_path")

                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                if parquet_path and os.path.exists(parquet_path):
                    os.remove(parquet_path)

                datasets_collection.delete_one({"_id": dataset_id})
                db["conversations"].delete_many({"dataset_id": str(dataset_id)})
                db["audit_logs"].delete_many({"dataset_id": str(dataset_id)})

                logger.info(
                    f"[RETENTION] Deleted expired dataset {dataset_id} for user {user_id}"
                )
                deleted_count += 1

        return {
            "status": "success",
            "datasets_deleted": deleted_count,
            "warnings_sent": warned_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[RETENTION] Cleanup task failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="cleanup_privacy_audit_logs")
def cleanup_privacy_audit_logs(self):
    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    try:
        audit_collection = db["privacy_audit_log"]
        cutoff = datetime.utcnow() - timedelta(days=90)

        result = audit_collection.delete_many({"timestamp": {"$lt": cutoff}})
        logger.info(f"[PRIVACY] Deleted {result.deleted_count} old audit logs")

        return {
            "status": "success",
            "logs_deleted": result.deleted_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[PRIVACY] Audit log cleanup failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}
