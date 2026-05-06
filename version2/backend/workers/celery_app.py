import logging
from datetime import datetime
from celery import Celery

from workers.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_CONFIG

logger = logging.getLogger(__name__)

celery_app = Celery(
    "datasage_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND
)
celery_app.conf.update(CELERY_CONFIG)


__all__ = ["celery_app"]
