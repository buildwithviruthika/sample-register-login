"""User models for MongoDB."""
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId


class User:
    """User model for MongoDB operations."""
    
    def __init__(self, user_data: Dict[str, Any]):
        """Initialize user with MongoDB document data.
        
        Args:
            user_data: MongoDB user document
        """
        self._data = user_data
        self.id = str(user_data.get("_id", "")) if "_id" in user_data else user_data.get("id", "")
        self.username = user_data.get("username", "")
        self.email = user_data.get("email", "")
        self.password = user_data.get("password", "")
        self.created_at = user_data.get("created_at", datetime.utcnow())
        self.updated_at = user_data.get("updated_at", datetime.utcnow())
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get user data as dictionary.
        
        Returns:
            User data dictionary
        """
        return self._data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary with string ID.
        
        Returns:
            User dictionary with string ID
        """
        result = self._data.copy()
        if "_id" in result:
            result["id"] = str(result["_id"])
            del result["_id"]
        
        # Convert datetime to string for template compatibility
        if isinstance(result.get("created_at"), datetime):
            result["created_at"] = result["created_at"].strftime('%B %d, %Y')
        if isinstance(result.get("updated_at"), datetime):
            result["updated_at"] = result["updated_at"].strftime('%B %d, %Y')
            
        return result
    
    @staticmethod
    def create_new(username: str, email: str, hashed_password: str) -> Dict[str, Any]:
        """Create a new user document.
        
        Args:
            username: User's username
            email: User's email
            hashed_password: Hashed password
            
        Returns:
            New user document
        """
        return {
            "username": username,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    @staticmethod
    def from_mongo_doc(doc: Dict[str, Any]) -> 'User':
        """Create User instance from MongoDB document.
        
        Args:
            doc: MongoDB document
            
        Returns:
            User instance
        """
        return User(doc)
    
    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
