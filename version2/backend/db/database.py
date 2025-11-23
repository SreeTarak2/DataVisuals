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
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        await db.database.users.create_index("email", unique=True)
        await db.database.users.create_index("username", unique=True)
        
        # Datasets collection indexes
        await db.database.datasets.create_index("user_id")
        await db.database.datasets.create_index("created_at")
        await db.database.datasets.create_index("filename")
        
        # Charts collection indexes
        await db.database.charts.create_index("user_id")
        await db.database.charts.create_index("dataset_id")
        await db.database.charts.create_index("created_at")
        
        # Insights collection indexes
        await db.database.insights.create_index("user_id")
        await db.database.insights.create_index("dataset_id")
        await db.database.insights.create_index("created_at")
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

def get_database():
    """Get database instance"""
    # if db.database is None:
    #     raise Exception("Database not connected. Make sure to call connect_to_mongo() first.")
    return db.database


