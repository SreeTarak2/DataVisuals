"""Stage 12: Auto-Data Guardrails - Generate and enforce data quality rules"""

from workers.celery_app import celery_app
from workers.database import get_db, init_worker_db
from workers.helpers import convert_types_for_json

import polars as pl
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="datasage.stage_12_guardrails")
def stage_12_guardrails_task(
    self, dataset_id: str, user_id: str = "unknown"
) -> Dict[str, Any]:
    """Stage 12: Auto-Data Guardrails"""
    logger.info(f"[Stage 12] Starting Auto-Data Guardrails for dataset {dataset_id}")

    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    datasets_collection = db.uploads

    try:
        dataset_doc = datasets_collection.find_one({"_id": dataset_id})
        if not dataset_doc:
            return {
                "success": False,
                "error": f"Dataset {dataset_id} not found",
                "stage": 12,
            }

        parquet_path = dataset_doc.get("parquet_path")
        if not parquet_path:
            return {"success": False, "error": "No Parquet file found", "stage": 12}

        logger.info(f"[Stage 12] Loading dataset from {parquet_path}")
        df = pl.read_parquet(parquet_path)
        logger.info(f"[Stage 12] Loaded {len(df)} rows, {len(df.columns)} columns")

        logger.info("[Stage 12] Inferring data quality rules...")
        from workers.guardrails.inferencer import GuardrailInferencer
        from workers.guardrails.validator import GuardrailValidator
        from workers.guardrails.reporter import GuardrailReporter

        inferencer = GuardrailInferencer(sample_size=1000)
        inferred_rules = inferencer.infer_rules(df, dataset_id)
        logger.info(f"[Stage 12] Generated {len(inferred_rules)} guardrail rules")

        logger.info("[Stage 12] Validating dataset against guardrails...")
        validator = GuardrailValidator()
        validation_result = validator.validate(df, inferred_rules, dataset_id)

        reporter = GuardrailReporter()
        api_response = reporter.generate_api_response(validation_result)
        summary = reporter.generate_summary(validation_result)

        update_data = {
            "guardrails_applied": True,
            "guardrails_timestamp": datetime.utcnow(),
            "guardrails_status": validation_result.status,
            "guardrails_passed": validation_result.passed,
            "guardrails_total_rules": validation_result.total_rules_checked,
            "guardrails_violations": validation_result.total_violations,
            "guardrails_critical": validation_result.critical_violations,
            "guardrails_warning": validation_result.warning_violations,
            "guardrail_rules": convert_types_for_json(
                [r.model_dump() for r in inferred_rules]
            ),
            "guardrail_summary": summary,
        }

        if not validation_result.passed:
            update_data["quarantined"] = True
            update_data["quarantine_reason"] = validation_result.quarantine_reason
            update_data["processing_status"] = "quarantined"
        else:
            update_data["processing_status"] = "guardrails_passed"

        datasets_collection.update_one({"_id": dataset_id}, {"$set": update_data})

        logger.info(
            f"[Stage 12] Guardrails validation completed: {validation_result.status}"
        )

        return {
            "success": True,
            "stage": 12,
            "dataset_id": dataset_id,
            "rules_generated": len(inferred_rules),
            "validation_result": api_response,
            "status": validation_result.status,
            "passed": validation_result.passed,
        }

    except Exception as e:
        logger.error(f"[Stage 12] Error: {str(e)}")
        import traceback

        traceback.print_exc()

        if db is not None:
            datasets_collection.update_one(
                {"_id": dataset_id},
                {
                    "$set": {
                        "guardrails_applied": False,
                        "guardrails_error": str(e),
                        "processing_status": "guardrails_failed",
                    }
                },
            )

        return {
            "success": False,
            "error": str(e),
            "stage": 12,
            "dataset_id": dataset_id,
        }


@celery_app.task(bind=True, name="datasage.revalidate_guardrails")
def revalidate_guardrails_task(
    self, dataset_id: str, user_id: str = "unknown"
) -> Dict[str, Any]:
    """Re-validate an existing dataset against its stored guardrail rules"""
    logger.info(
        f"[Revalidate] Starting guardrail re-validation for dataset {dataset_id}"
    )

    db = get_db()
    if db is None:
        init_worker_db()
        db = get_db()

    datasets_collection = db.uploads

    try:
        dataset_doc = datasets_collection.find_one({"_id": dataset_id})
        if not dataset_doc:
            return {"success": False, "error": "Dataset not found"}

        parquet_path = dataset_doc.get("parquet_path")
        if not parquet_path:
            return {"success": False, "error": "No Parquet file found"}

        existing_rules = dataset_doc.get("guardrail_rules", [])
        if not existing_rules:
            logger.info("[Revalidate] No existing rules found, running full inference")
            return stage_12_guardrails_task(dataset_id, user_id)

        from workers.guardrails.models import GuardrailRule
        from workers.guardrails.validator import GuardrailValidator
        from workers.guardrails.reporter import GuardrailReporter

        rules = [GuardrailRule(**doc) for doc in existing_rules]

        df = pl.read_parquet(parquet_path)

        validator = GuardrailValidator()
        validation_result = validator.validate(df, rules, dataset_id)

        reporter = GuardrailReporter()
        api_response = reporter.generate_api_response(validation_result)

        update_data = {
            "guardrails_last_revalidated": datetime.utcnow(),
            "guardrails_status": validation_result.status,
            "guardrails_passed": validation_result.passed,
        }

        if not validation_result.passed:
            update_data["quarantined"] = True
            update_data["quarantine_reason"] = validation_result.quarantine_reason

        datasets_collection.update_one({"_id": dataset_id}, {"$set": update_data})

        logger.info(f"[Revalidate] Completed: {validation_result.status}")

        return {
            "success": True,
            "dataset_id": dataset_id,
            "is_revalidation": True,
            "validation_result": api_response,
            "status": validation_result.status,
        }

    except Exception as e:
        logger.error(f"[Revalidate] Error: {str(e)}")
        return {"success": False, "error": str(e)}


__all__ = ["stage_12_guardrails_task", "revalidate_guardrails_task"]
