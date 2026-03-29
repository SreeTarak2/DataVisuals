from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database = None


# Create database instance
db = Database()


async def connect_to_mongo():
    """Create database connection"""
    try:
        # MongoDB connection string
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = os.getenv("DATABASE_NAME", "datasage_ai")

        # Create async client
        db.client = AsyncIOMotorClient(mongo_url)
        db.database = db.client[database_name]

        # Test the connection
        await db.client.admin.command("ping")
        logger.info(f"Connected to MongoDB at {mongo_url}")
        logger.info(f"Using database: {database_name}")

        # Create indexes for better performance
        await create_indexes()

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e


async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB")


async def create_indexes():
    """
    Create database indexes for better performance and query optimization.

    Index strategy:
    - Single field indexes for unique constraints (email, username)
    - Compound indexes for common query patterns (user_id + is_active, user_id + created_at)
    - Content hash index for duplicate detection
    """
    try:
        # ============================================================
        # Users Collection
        # ============================================================
        await db.database.users.create_index("email", unique=True)
        await db.database.users.create_index("username", unique=True)

        # ============================================================
        # Uploads Collection (renamed from datasets)
        # ============================================================
        await db.database.uploads.create_index("user_id")
        await db.database.uploads.create_index("created_at")
        await db.database.uploads.create_index("filename")

        # COMPOUND: User's active uploads (most common query pattern)
        await db.database.uploads.create_index(
            [("user_id", 1), ("is_active", 1)], name="idx_user_active_uploads"
        )

        # COMPOUND: Duplicate detection (content_hash + user_id)
        await db.database.uploads.create_index(
            [("content_hash", 1), ("user_id", 1)], name="idx_duplicate_detection"
        )

        # COMPOUND: User's uploads sorted by creation (for listing)
        await db.database.uploads.create_index(
            [("user_id", 1), ("created_at", -1)], name="idx_user_uploads_sorted"
        )

        # ============================================================
        # Dataset Analytics Collection (NEW)
        # ============================================================
        await db.database.dataset_analytics.create_index("dataset_id")
        await db.database.dataset_analytics.create_index("user_id")

        # COMPOUND: User's analytics by dataset
        await db.database.dataset_analytics.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_analytics"
        )

        # COMPOUND: Analytics sorted by computation time
        await db.database.dataset_analytics.create_index(
            [("user_id", 1), ("computed_at", -1)], name="idx_user_analytics_computed"
        )

        # ============================================================
        # Reports Collection (NEW)
        # ============================================================
        await db.database.reports.create_index("dataset_id")
        await db.database.reports.create_index("user_id")
        await db.database.reports.create_index("generated_at")

        # COMPOUND: User's reports by dataset
        await db.database.reports.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_reports"
        )

        # COMPOUND: User's reports sorted by generation time
        await db.database.reports.create_index(
            [("user_id", 1), ("generated_at", -1)], name="idx_user_reports_generated"
        )

        # ============================================================
        # Charts Collection
        # ============================================================
        await db.database.charts.create_index("user_id")
        await db.database.charts.create_index("dataset_id")
        await db.database.charts.create_index("created_at")

        # ============================================================
        # Insights Collection
        # ============================================================
        await db.database.insights.create_index("user_id")
        await db.database.insights.create_index("dataset_id")
        await db.database.insights.create_index("created_at")

        # ============================================================
        # Conversations Collection
        # ============================================================
        await db.database.conversations.create_index(
            [("user_id", 1), ("dataset_id", 1)], name="idx_user_dataset_conversations"
        )

        await db.database.conversations.create_index(
            [("user_id", 1), ("updated_at", -1)], name="idx_user_recent_conversations"
        )

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")


def get_database():
    """Get database instance with safety check"""
    if db.database is None:
        logger.error("Database accessed before connect_to_mongo() was called.")
        raise ConnectionError(
            "Database not initialized. Ensure connect_to_mongo() is awaited at worker startup."
        )
    return db.database
