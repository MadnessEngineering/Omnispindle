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
    Prefers email over Auth0 'sub' for consistent database naming.
    MongoDB database names cannot contain certain characters.
    """
    # Prefer email as primary identifier (more stable than Auth0 sub)
    # This matches the Inventorium backend logic for consistency
    user_id = None
    if 'email' in user_context and user_context['email']:
        user_id = user_context['email']
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id).lower()
        database_name = f"user_{sanitized}"
        print(f"✅ Database naming: Using email: {user_id} -> {database_name}")
    elif 'sub' in user_context and user_context['sub']:
        user_id = user_context['sub']
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', user_id).lower()
        database_name = f"user_{sanitized}"
        print(f"✅ Database naming: Using Auth0 sub: {user_id} -> {database_name}")
    else:
        # Fallback to shared database if no personal identifier available
        database_name = "swarmonomicon"
        user_info = user_context.get('id', 'unknown')
        print(f"⚠️ Database naming: No email or Auth0 sub found for user {user_info}")
        print(f"⚠️ Database naming: Using shared database: {database_name}")

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
        if self.client is None:
            raise RuntimeError("MongoDB client not initialized")

        # If no user context, return shared database
        if not user_context:
            print("⚠️ Database routing: No user context provided, using shared database")
            return self.shared_db

        # Check for Auth0 'sub' field - the canonical user identifier
        if not user_context.get('sub'):
            user_info = user_context.get('email', user_context.get('id', 'unknown'))
            print(f"⚠️ Database routing: No Auth0 'sub' for user {user_info}, using shared database")
            return self.shared_db

        db_name = sanitize_database_name(user_context)

        # Return cached database if we have it
        if db_name in self._user_databases:
            return self._user_databases[db_name]

        # Create and cache new user database
        user_db = self.client[db_name]
        self._user_databases[db_name] = user_db

        user_id = user_context.get('sub', user_context.get('email', 'unknown'))
        print(f"✅ Database routing: Initialized user database: {db_name} for user {user_id}")
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
        """
        Legacy property for todos collection from shared database
        """
        return self.shared_db["todos"] if self.shared_db is not None else None

    @property
    def lessons(self) -> Collection:
        """
        Legacy property for lessons_learned collection from shared database
        """
        return self.shared_db["lessons_learned"] if self.shared_db is not None else None

    @property
    def tags_cache(self) -> Collection:
        """
        Legacy property for tags_cache collection from shared database
        """
        return self.shared_db["tags_cache"] if self.shared_db is not None else None

    @property
    def projects(self) -> Collection:
        """
        Legacy property for projects collection from shared database
        """
        return self.shared_db["projects"] if self.shared_db is not None else None
    
    @property
    def explanations(self) -> Collection:
        """
        Legacy property for explanations collection from shared database
        """
        return self.shared_db["explanations"] if self.shared_db is not None else None

    @property
    def logs(self) -> Collection:

        return self.shared_db["todo_logs"] if self.shared_db is not None else None


# Export a single instance for the application to use
db_connection = Database()
