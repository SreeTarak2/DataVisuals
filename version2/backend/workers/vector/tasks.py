from workers.celery_app import celery_app
from workers.database import get_db, init_worker_db
from workers.async_helper import run_async
from workers.helpers import convert_types_for_json

import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="datasage.index_dataset_vector", max_retries=3)
def index_dataset_to_vector_db(
    self, dataset_id: str, dataset_metadata: dict, user_id: str
):
    logger.info(f"Indexing dataset {dataset_id} to vector database...")

    try:
        from services.datasets.faiss_vector_service import faiss_vector_service

        success = run_async(
            faiss_vector_service.add_dataset_to_vector_db(
                dataset_id=dataset_id,
                dataset_metadata=dataset_metadata,
                user_id=user_id,
            )
        )

        if success:
            logger.info(f"✓ Successfully indexed dataset {dataset_id}")
        else:
            logger.warning(f"⚠ Vector indexing returned False for {dataset_id}")

        return success

    except Exception as e:
        logger.error(f"✗ Vector indexing failed for {dataset_id}: {e}")

        if self.request.retries < self.max_retries:
            retry_in = 2**self.request.retries
            logger.info(
                f"Retrying in {retry_in} seconds... (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=retry_in)
        else:
            logger.error(f"Max retries reached for dataset {dataset_id}")
            return False


@celery_app.task(name="datasage.add_query_history")
def add_query_to_vector_history(
    query_text: str, dataset_id: str, response: str, user_id: str
):
    try:
        from services.datasets.faiss_vector_service import faiss_vector_service

        success = run_async(
            faiss_vector_service.add_query_to_history(
                query_text=query_text,
                dataset_id=dataset_id,
                response=response,
                user_id=user_id,
            )
        )

        if success:
            logger.info(f"✓ Added query to history: '{query_text[:50]}...'")

        return success

    except Exception as e:
        logger.error(f"✗ Failed to add query to history: {e}")
        return False
