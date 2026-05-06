import logging
import asyncio
from pymongo import MongoClient

from workers.config import MONGO_URL, DATABASE_NAME

logger = logging.getLogger(__name__)

db_conn = None
_worker_loop = None


def init_worker_db():
    global db_conn, _worker_loop
    logger.info("Initializing database connection for worker process...")
    try:
        client = MongoClient(MONGO_URL, maxPoolSize=10, minPoolSize=1)
        db_conn = client[DATABASE_NAME]

        from db.database import connect_to_mongo

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_loop = loop
        loop.run_until_complete(connect_to_mongo())

        logger.info("✓ Database connections initialized successfully (sync + async)")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database connection: {e}")
        raise


def get_db():
    return db_conn


__all__ = ["db_conn", "init_worker_db", "get_db"]
