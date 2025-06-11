"""
Todo Log Service

This module provides a service that:
1. Logs all changes (create, update, delete, complete) to a separate todo_logs collection
2. Provides API for querying and displaying log data
3. Supports direct logging from todo operations rather than monitoring

This approach:
- Logs changes directly during operations
- Provides reliable tracking regardless of MongoDB configuration
- Simplifies the architecture by eliminating stream monitoring
"""

import json
import logging
import os
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Union

import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv

# Import MQTT functionality
from .mqtt import mqtt_publish

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")
MONGODB_LOGS_COLLECTION = os.getenv("MONGODB_LOGS_COLLECTION", "todo_logs")

class TodoLogService:
    """
    A service for logging and retrieving todo changes.
    """

    def __init__(self, mongo_uri: str = MONGODB_URI,
                 db_name: str = MONGODB_DB,
                 todos_collection: str = MONGODB_COLLECTION,
                 logs_collection: str = MONGODB_LOGS_COLLECTION):
        """
        Initialize the TodoLogService.
        
        Args:
            mongo_uri: MongoDB connection URI
            db_name: Database name
            todos_collection: Collection name for todos
            logs_collection: Collection name for todo logs
        """
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.todos_collection_name = todos_collection
        self.logs_collection_name = logs_collection

        # Will be initialized in start()
        self.mongo_client = None
        self.db = None
        self.todos_collection = None
        self.logs_collection = None
        self.running = False  # Track service state

        logger.info(f"TodoLogService initialized with db={db_name}, todos={todos_collection}, logs={logs_collection}")

    async def initialize_db(self) -> bool:
        """
        Initialize database connections and ensure collections exist.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Initializing database connection to {self.mongo_uri}")
            
            # Create MongoDB connection
            self.mongo_client = MongoClient(self.mongo_uri)
            
            # Test the connection
            try:
                # Ping the database to ensure connection is working
                self.mongo_client.admin.command('ping')
                logger.debug("MongoDB connection successful")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {str(e)}")
                return False
            
            self.db = self.mongo_client[self.db_name]
            self.todos_collection = self.db[self.todos_collection_name]
            
            logger.debug(f"Connected to database '{self.db_name}'")

            # Create logs collection if it doesn't exist
            if self.logs_collection_name not in self.db.list_collection_names():
                logger.info(f"Creating {self.logs_collection_name} collection")
                try:
                    self.db.create_collection(self.logs_collection_name,
                        validator={
                            "$jsonSchema": {
                                "bsonType": "object",
                                "required": ["timestamp", "operation", "todoId"],
                                "properties": {
                                    "timestamp": { "bsonType": "date" },
                                    "operation": { "bsonType": "string" },
                                    "todoId": { "bsonType": "string" },
                                    "description": { "bsonType": "string" },
                                    "todoTitle": { "bsonType": "string" },
                                    "project": { "bsonType": "string" },
                                    "changes": { "bsonType": "array" },
                                    "userAgent": { "bsonType": "string" }
                                }
                            }
                        }
                    )

                    # Create indexes for efficient querying
                    self.db[self.logs_collection_name].create_index([("timestamp", pymongo.DESCENDING)])
                    self.db[self.logs_collection_name].create_index([("operation", pymongo.ASCENDING)])
                    self.db[self.logs_collection_name].create_index([("todoId", pymongo.ASCENDING)])
                    self.db[self.logs_collection_name].create_index([("project", pymongo.ASCENDING)])
                    logger.info(f"Created indexes for {self.logs_collection_name} collection")
                    
                except Exception as e:
                    logger.warning(f"Failed to create collection with validator, creating simple collection: {str(e)}")
                    # Fallback: create collection without validator
                    self.db.create_collection(self.logs_collection_name)
            else:
                logger.debug(f"Collection {self.logs_collection_name} already exists")

            self.logs_collection = self.db[self.logs_collection_name]
            
            # Verify the collection is accessible
            try:
                count = self.logs_collection.count_documents({})
                logger.info(f"Database connections initialized successfully. Found {count} existing log entries.")
            except Exception as e:
                logger.error(f"Failed to access logs collection: {str(e)}")
                return False
                
            return True

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            # Clean up partial initialization
            if hasattr(self, 'mongo_client') and self.mongo_client:
                try:
                    self.mongo_client.close()
                except:
                    pass
                self.mongo_client = None
            self.db = None
            self.todos_collection = None
            self.logs_collection = None
            return False

    def generate_title(self, description: str) -> str:
        """
        Generate a title from the description (matches Node-RED JavaScript logic).
        First 60 chars, truncated at word boundary.
        
        Args:
            description: The full description text
            
        Returns:
            Truncated title string
        """
        if not description or description == 'Unknown':
            return 'Unknown'
        
        # If description is short enough, return as-is
        if len(description) <= 60:
            return description
        
        # Truncate at 60 chars and find the last space to avoid cutting words
        truncated = description[:60]
        last_space = truncated.rfind(' ')
        
        # Only truncate at word if we have reasonable length
        if last_space > 30:
            return truncated[:last_space] + '...'
        
        return truncated + '...'

    async def log_todo_action(self, operation: str, todo_id: str, description: str,
                             project: str, changes: List[Dict] = None, user_agent: str = None) -> bool:
        """
        Log a todo action to the database and notify via MQTT.
        
        Args:
            operation: The operation performed ('create', 'update', 'delete', 'complete')
            todo_id: The ID of the todo
            description: The description of the todo
            project: The project the todo belongs to
            changes: List of changes made (for update operations)
            user_agent: The user agent performing the action
            
        Returns:
            True if logging was successful, False otherwise
        """
        try:
            # Ensure the service is initialized before attempting to log
            if not self.running or self.logs_collection is None:
                logger.debug("TodoLogService not initialized, attempting to start...")
                success = await self.start()
                if not success:
                    logger.warning("Failed to initialize TodoLogService for logging")
                    return False

            # Create log entry
            log_entry = {
                'timestamp': datetime.now(UTC),
                'operation': operation,
                'todoId': todo_id,
                'description': description,
                'todoTitle': self.generate_title(description),  # Add truncated title
                'project': project,
                'changes': changes or [],
                'userAgent': user_agent or 'Unknown'
            }

            # Store in database
            self.logs_collection.insert_one(log_entry)

            # Send MQTT notification if configured
            await self.notify_change(log_entry)

            logger.info(f"Logged {operation} for todo {todo_id}")
            return True

        except Exception as e:
            logger.error(f"Error logging todo action: {str(e)}")
            return False

    async def notify_change(self, log_entry: Dict[str, Any]):
        """
        Notify about a change via MQTT.
        
        Args:
            log_entry: The log entry to notify about
        """
        try:
            # Convert datetime to string for JSON serialization
            log_data = log_entry.copy()
            log_data['timestamp'] = log_data['timestamp'].isoformat()
            
            # Convert ObjectId to string if present
            if '_id' in log_data:
                log_data['_id'] = str(log_data['_id'])

            # Publish to MQTT
            topic = f"todo/log/new_entry"
            message = json.dumps(log_data)

            await mqtt_publish(topic, message)
            logger.debug(f"MQTT notification sent for {log_entry['operation']} on {log_entry['todoId']}")

        except Exception as e:
            logger.error(f"Error sending MQTT notification: {str(e)}")

    async def start(self):
        """
        Start the Todo Log Service.
        """
        # Initialize database connections
        success = await self.initialize_db()
        if not success:
            logger.error("Failed to initialize database, cannot start service")
            self.running = False
            return False

        self.running = True
        logger.info("TodoLogService started successfully")
        return True

    async def stop(self):
        """
        Stop the Todo Log Service.
        """
        # Close the MongoDB connection
        if self.mongo_client:
            self.mongo_client.close()

        logger.info("TodoLogService stopped")
        self.running = False

    async def get_logs(self, filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        Get logs from the database.
        
        Args:
            filter_type: Operation type filter ('all', 'create', 'update', 'delete', 'complete')
            project: Project name to filter by ('all' for all projects)
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Dict with logs data
        """
        # Ensure the service is initialized before attempting to get logs
        if not self.running or self.logs_collection is None:
            logger.debug("TodoLogService not initialized in get_logs, attempting to start...")
            success = await self.start()
            if not success:
                logger.warning("Failed to initialize TodoLogService for getting logs")
                return {
                    'error': 'TodoLogService initialization failed',
                    'logEntries': [],
                    'totalCount': 0,
                    'page': page,
                    'pageSize': page_size,
                    'hasMore': False,
                    'projects': []
                }

        # Build the query
        query = {}

        # Apply operation filter
        if filter_type != 'all':
            query['operation'] = filter_type

        # Apply project filter
        if project != 'all':
            query['project'] = project

        # Calculate skip amount
        skip = (page - 1) * page_size

        try:
            # Get the total count
            total_count = self.logs_collection.count_documents(query)

            # Get the logs
            logs = list(self.logs_collection.find(query)
                       .sort('timestamp', pymongo.DESCENDING)
                       .skip(skip).limit(page_size))

            # Get unique projects for filtering
            projects = self.logs_collection.distinct('project')

            # Convert ObjectId to string and datetime to string for JSON
            for log in logs:
                if '_id' in log:
                    log['_id'] = str(log['_id'])
                if 'timestamp' in log:
                    log['timestamp'] = log['timestamp'].isoformat()

            # Determine if there are more logs
            has_more = total_count > (skip + len(logs))

            return {
                'logEntries': logs,
                'totalCount': total_count,
                'page': page,
                'pageSize': page_size,
                'hasMore': has_more,
                'projects': [p for p in projects if p]  # Filter out empty projects
            }

        except Exception as e:
            logger.error(f"Error getting logs: {str(e)}")
            return {
                'error': str(e),
                'logEntries': [],
                'totalCount': 0,
                'page': page,
                'pageSize': page_size,
                'hasMore': False,
                'projects': []
            }


# Singleton instance
_service_instance = None

def get_service_instance() -> TodoLogService:
    """
    Get the singleton TodoLogService instance.
    
    Returns:
        The TodoLogService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = TodoLogService()
    return _service_instance

async def start_service():
    """
    Start the TodoLogService.
    """
    service = get_service_instance()
    await service.start()
    logger.info("Todo Log Service started")
    return service

async def stop_service():
    """
    Stop the TodoLogService.
    """
    service = get_service_instance()
    await service.stop()

# Direct logging functions for use in tools
async def log_todo_create(todo_id: str, description: str, project: str, user_agent: str = None) -> bool:
    """
    Log a todo creation action.
    """
    service = get_service_instance()
    # Ensure service is initialized
    if not service.running or service.logs_collection is None:
        logger.debug("TodoLogService not initialized in log_todo_create, attempting to start...")
        success = await service.start()
        if not success:
            logger.warning("Failed to initialize TodoLogService for logging todo creation")
            return False
    return await service.log_todo_action('create', todo_id, description, project, None, user_agent)

async def log_todo_update(todo_id: str, description: str, project: str, 
                         changes: List[Dict] = None, user_agent: str = None) -> bool:
    """
    Log a todo update action.
    """
    service = get_service_instance()
    # Ensure service is initialized
    if not service.running or service.logs_collection is None:
        logger.debug("TodoLogService not initialized in log_todo_update, attempting to start...")
        success = await service.start()
        if not success:
            logger.warning("Failed to initialize TodoLogService for logging todo update")
            return False
    return await service.log_todo_action('update', todo_id, description, project, changes, user_agent)

async def log_todo_complete(todo_id: str, description: str, project: str, user_agent: str = None) -> bool:
    """
    Log a todo completion action.
    """
    service = get_service_instance()
    # Ensure service is initialized
    if not service.running or service.logs_collection is None:
        logger.debug("TodoLogService not initialized in log_todo_complete, attempting to start...")
        success = await service.start()
        if not success:
            logger.warning("Failed to initialize TodoLogService for logging todo completion")
            return False
    return await service.log_todo_action('complete', todo_id, description, project, None, user_agent)

async def log_todo_delete(todo_id: str, description: str, project: str, user_agent: str = None) -> bool:
    """
    Log a todo deletion action.
    """
    service = get_service_instance()
    # Ensure service is initialized
    if not service.running or service.logs_collection is None:
        logger.debug("TodoLogService not initialized in log_todo_delete, attempting to start...")
        success = await service.start()
        if not success:
            logger.warning("Failed to initialize TodoLogService for logging todo deletion")
            return False
    return await service.log_todo_action('delete', todo_id, description, project, None, user_agent)
