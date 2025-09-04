import os
import re
from typing import Optional, Dict, Any
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

# Load environment variables from .env file
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB", "swarmonomicon")  # Fallback/shared database


def sanitize_database_name(user_context: Dict[str, Any]) -> str:
    """
    Convert user context to a valid MongoDB database name.
    Uses email-based naming for consistency with Inventorium.
    MongoDB database names cannot contain certain characters.
    """
    # Prefer email-based naming (consistent with Inventorium)
    if 'email' in user_context:
        email = user_context['email']
        if '@' in email:
            username, domain = email.split('@', 1)
            # Create safe database name from email components
            safe_username = re.sub(r'[^a-zA-Z0-9]', '_', username)
            safe_domain = re.sub(r'[^a-zA-Z0-9]', '_', domain)
            database_name = f"user_{safe_username}_{safe_domain}"
        else:
            # Fallback if email format is unexpected
            safe_email = re.sub(r'[^a-zA-Z0-9]', '_', email)
            database_name = f"user_{safe_email}"
    elif 'sub' in user_context:
        # Fallback to sub-based naming if no email
        user_id = user_context['sub']
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id)
        database_name = f"user_{sanitized}"
    else:
        # Last resort fallback
        database_name = "user_unknown"
    
    # MongoDB database names are limited to 64 characters
    if len(database_name) > 64:
        database_name = database_name[:64]
    
    return database_name


class Database:
    """A singleton class to manage MongoDB connections with user-scoped databases."""
    _instance = None
    client: MongoClient | None = None
    shared_db: MongoDatabase | None = None  # The original swarmonomicon database
    _user_databases: Dict[str, MongoDatabase] = {}  # Cache of user databases

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._user_databases = {}
            try:
                cls._instance.client = MongoClient(MONGODB_URI)
                # Ping the server to verify the connection
                cls._instance.client.admin.command('ping')
                print("MongoDB connection successful.")
            except Exception as e:
                print(f"Error connecting to MongoDB: {e}")
                cls._instance.client = None

            # Initialize shared database (legacy swarmonomicon)
            if cls._instance.client is not None:
                cls._instance.shared_db = cls._instance.client[MONGODB_DB_NAME]
            else:
                cls._instance.shared_db = None

        return cls._instance

    def get_user_database(self, user_context: Optional[Dict[str, Any]] = None) -> MongoDatabase:
        """
        Get the appropriate database for a user context.
        Returns user-specific database if user is authenticated, otherwise shared database.
        """
        if not self.client:
            raise RuntimeError("MongoDB client not initialized")

        # If no user context, return shared database
        if not user_context or not user_context.get('sub'):
            return self.shared_db

        db_name = sanitize_database_name(user_context)
        
        # Return cached database if we have it
        if db_name in self._user_databases:
            return self._user_databases[db_name]
        
        # Create and cache new user database
        user_db = self.client[db_name]
        self._user_databases[db_name] = user_db
        
        user_id = user_context.get('sub', user_context.get('email', 'unknown'))
        print(f"Initialized user database: {db_name} for user {user_id}")
        return user_db

    def get_collections(self, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Collection]:
        """
        Get all collections for the appropriate database (user-scoped or shared).
        """
        db = self.get_user_database(user_context)
        collections_dict = {
            'todos': db["todos"],
            'lessons': db["lessons_learned"],
            'tags_cache': db["tags_cache"],
            'projects': db["projects"], 
            'explanations': db["explanations"],
            'logs': db["todo_logs"]
        }
        # Add database reference for custom collection access
        collections_dict['database'] = db
        return collections_dict

    # Legacy properties for backward compatibility (use shared database)
    @property
    def db(self) -> MongoDatabase:
        """Legacy property - returns shared database"""
        return self.shared_db

    @property 
    def todos(self) -> Collection:
        """Legacy property - returns shared todos collection"""
        return self.shared_db["todos"] if self.shared_db else None

    @property
    def lessons(self) -> Collection:
        """Legacy property - returns shared lessons collection"""
        return self.shared_db["lessons_learned"] if self.shared_db else None

    @property
    def tags_cache(self) -> Collection:
        """Legacy property - returns shared tags_cache collection"""
        return self.shared_db["tags_cache"] if self.shared_db else None

    @property
    def projects(self) -> Collection:
        """Legacy property - returns shared projects collection"""
        return self.shared_db["projects"] if self.shared_db else None

    @property
    def explanations(self) -> Collection:
        """Legacy property - returns shared explanations collection"""
        return self.shared_db["explanations"] if self.shared_db else None

    @property
    def logs(self) -> Collection:
        """Legacy property - returns shared logs collection"""
        return self.shared_db["todo_logs"] if self.shared_db else None


# Export a single instance for the application to use
db_connection = Database()
