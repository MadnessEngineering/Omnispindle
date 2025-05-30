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
            # Create MongoDB connection
            self.mongo_client = MongoClient(self.mongo_uri)
            self.db = self.mongo_client[self.db_name]
            self.todos_collection = self.db[self.todos_collection_name]

            # Create logs collection if it doesn't exist
            if self.logs_collection_name not in self.db.list_collection_names():
                logger.info(f"Creating {self.logs_collection_name} collection")
                self.db.create_collection(self.logs_collection_name,
                    validator={
                        "$jsonSchema": {
                            "bsonType": "object",
                            "required": ["timestamp", "operation", "todoId"],
                            "properties": {
                                "timestamp": { "bsonType": "date" },
                                "operation": { "bsonType": "string" },
                                "todoId": { "bsonType": "string" },
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

            self.logs_collection = self.db[self.logs_collection_name]
            logger.info("Database connections initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            return False

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
            # Create log entry
            log_entry = {
                'timestamp': datetime.now(UTC),
                'operation': operation,
                'todoId': todo_id,
                'description': description,
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
                'logEntries': []
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
    return await service.log_todo_action('create', todo_id, description, project, None, user_agent)

async def log_todo_update(todo_id: str, description: str, project: str, 
                         changes: List[Dict] = None, user_agent: str = None) -> bool:
    """
    Log a todo update action.
    """
    service = get_service_instance()
    return await service.log_todo_action('update', todo_id, description, project, changes, user_agent)

async def log_todo_complete(todo_id: str, description: str, project: str, user_agent: str = None) -> bool:
    """
    Log a todo completion action.
    """
    service = get_service_instance()
    return await service.log_todo_action('complete', todo_id, description, project, None, user_agent)

async def log_todo_delete(todo_id: str, description: str, project: str, user_agent: str = None) -> bool:
    """
    Log a todo deletion action.
    """
    service = get_service_instance()
    return await service.log_todo_action('delete', todo_id, description, project, None, user_agent)
