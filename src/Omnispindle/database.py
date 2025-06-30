import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB", "swarmonomicon")

class Database:
    """A singleton class to manage the MongoDB connection."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            try:
                cls._instance.client = MongoClient(MONGODB_URI)
                # Ping the server to verify the connection
                cls._instance.client.admin.command('ping')
                print("MongoDB connection successful.")
            except Exception as e:
                print(f"Error connecting to MongoDB: {e}")
                cls._instance.client = None
            
            # Initialize db and collections
            if cls._instance.client is not None:
                cls._instance.db = cls._instance.client[MONGODB_DB_NAME]
                cls._instance.todos = cls._instance.db["todos"]
                cls._instance.lessons = cls._instance.db["lessons_learned"]
                cls._instance.tags_cache = cls._instance.db["tags_cache"]
                cls._instance.projects = cls._instance.db["projects"]
                cls._instance.explanations = cls._instance.db["explanations"]
                cls._instance.logs = cls._instance.db["todo_logs"]
            else:
                cls._instance.db = None
                cls._instance.todos = None
                cls._instance.lessons = None
                cls._instance.tags_cache = None
                cls._instance.projects = None
                cls._instance.explanations = None
                cls._instance.logs = None

        return cls._instance

# Export a single instance for the application to use
db_connection = Database() 
