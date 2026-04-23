"""MongoDB database configuration and connection management."""
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any, Optional

# Load environment variables from .env
load_dotenv()

# MongoDB connection settings from .env
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "log_res")

# Async MongoDB client for FastAPI
async_client = None
async_database = None

# Sync MongoDB client for direct operations
sync_client = MongoClient(MONGODB_URL)
sync_database = sync_client[DATABASE_NAME]
sync_users_collection = sync_database["users"]


async def get_mongodb():
    """Get MongoDB database connection.
    
    Returns:
        MongoDB database instance
    """
    global async_client, async_database
    
    if async_client is None:
        async_client = AsyncIOMotorClient(MONGODB_URL)
        async_database = async_client[DATABASE_NAME]
    
    return async_database


async def get_users_collection():
    """Get users collection from MongoDB.
    
    Returns:
        MongoDB users collection
    """
    db = await get_mongodb()
    return db["users"]


def get_sync_users_collection():
    """Get synchronous users collection.
    
    Returns:
        MongoDB users collection (sync)
    """
    return sync_users_collection


async def close_mongodb():
    """Close MongoDB connection."""
    global async_client
    if async_client:
        async_client.close()
        async_client = None


class MongoDBUser:
    """MongoDB user document helper class."""
    
    @staticmethod
    def create_user_dict(username: str, email: str, hashed_password: str) -> Dict[str, Any]:
        """Create a user document dictionary.
        
        Args:
            username: User's username
            email: User's email
            hashed_password: Hashed password
            
        Returns:
            User document dictionary
        """
        return {
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    @staticmethod
    def serialize_user(user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize MongoDB document to user-friendly format.
        
        Args:
            user_doc: MongoDB user document
            
        Returns:
            Serialized user dictionary
        """
        if "_id" in user_doc:
            user_doc["id"] = str(user_doc["_id"])
            del user_doc["_id"]
        
        # Convert datetime objects to strings
        if "created_at" in user_doc and user_doc["created_at"]:
            user_doc["created_at"] = user_doc["created_at"].isoformat()
        if "updated_at" in user_doc and user_doc["updated_at"]:
            user_doc["updated_at"] = user_doc["updated_at"].isoformat()
            
        return user_doc
