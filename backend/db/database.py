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
        await db.client.admin.command('ping')
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
        # Datasets Collection
        # ============================================================
        # Basic single-field indexes
        await db.database.datasets.create_index("user_id")
        await db.database.datasets.create_index("created_at")
        await db.database.datasets.create_index("filename")
        
        # COMPOUND: User's active datasets (most common query pattern)
        await db.database.datasets.create_index(
            [("user_id", 1), ("is_active", 1)],
            name="idx_user_active_datasets"
        )
        
        # COMPOUND: Duplicate detection (content_hash + user_id)
        await db.database.datasets.create_index(
            [("content_hash", 1), ("user_id", 1)],
            name="idx_duplicate_detection"
        )
        
        # COMPOUND: User's datasets sorted by creation (for listing)
        await db.database.datasets.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_user_datasets_sorted"
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
        # COMPOUND: User's conversations for a dataset
        await db.database.conversations.create_index(
            [("user_id", 1), ("dataset_id", 1)],
            name="idx_user_dataset_conversations"
        )
        
        # COMPOUND: User's recent conversations (for listing)
        await db.database.conversations.create_index(
            [("user_id", 1), ("updated_at", -1)],
            name="idx_user_recent_conversations"
        )
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

def get_database():
    """Get database instance"""
    # if db.database is None:
    #     raise Exception("Database not connected. Make sure to call connect_to_mongo() first.")
    return db.database


