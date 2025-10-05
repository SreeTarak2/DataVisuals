from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

async def connect_to_mongo():
    """Create database connection."""
    try:
        Database.client = AsyncIOMotorClient(settings.mongodb_uri)
        Database.db = Database.client[settings.mongodb_db]
        logger.info("Connected to MongoDB.")
        
        # Test connection
        await Database.client.admin.command('ping')
        logger.info("MongoDB connection test successful.")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    """Close database connection."""
    if Database.client:
        Database.client.close()
        logger.info("MongoDB connection closed.")

def get_database():
    """Get database instance."""
    return Database.db

def get_collection(collection_name: str):
    """Get collection instance."""
    return Database.db[collection_name]


