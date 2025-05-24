"""
Todo Log Change Stream Service

This module provides a standalone service that:
1. Monitors MongoDB change streams for todo item changes
2. Logs all changes (create, update, delete, complete) to a separate todo_logs collection
3. Provides an API for querying the log data
4. Can run independently from Node-RED

This approach separates concerns:
- This service focuses exclusively on monitoring and recording todo changes
- Node-RED only needs to query and display the logs
"""

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Union

import pymongo
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError
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
    A standalone service for monitoring MongoDB change streams and logging todo changes.
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
        self.change_stream = None

        # For tracking the service state
        self.running = False
        self.watch_thread = None
        self._stop_event = threading.Event()

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
                                "fullDocument": { "bsonType": "object" }
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

    def process_change_event(self, change_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a change event into a log entry.
        
        Args:
            change_event: The MongoDB change event document
            
        Returns:
            A log entry dict or None if it should be skipped
        """
        # Skip if not a real operation we care about
        if not change_event.get('operationType') or \
           change_event['operationType'] not in ['insert', 'update', 'delete', 'replace']:
            return None
        
        timestamp = datetime.now(UTC)
        operation = ''
        todo_id = ''
        todo_title = ''
        project = ''
        changes = []
        full_document = None
        
        # Process based on operation type
        op_type = change_event['operationType']
        
        if op_type in ['insert', 'replace']:
            operation = 'create'
            # Get document data
            doc = change_event.get('fullDocument', {})
            todo_id = str(doc.get('_id', ''))
            todo_title = doc.get('description', 'Untitled Todo')
            project = doc.get('project', 'No Project')
            full_document = doc
        
        elif op_type == 'update':
            # Check if this is a completion
            doc = change_event.get('fullDocument', {})
            
            # Determine operation type
            if doc.get('status') == 'completed':
                operation = 'complete'
            else:
                operation = 'update'
            
            # Get the document ID
            todo_id = str(change_event.get('documentKey', {}).get('_id', ''))
            
            todo_title = doc.get('description', 'Untitled Todo')
            project = doc.get('project', 'No Project')
            full_document = doc
            
            # Extract changes
            if 'updateDescription' in change_event and 'updatedFields' in change_event['updateDescription']:
                updated_fields = change_event['updateDescription']['updatedFields']
                
                # Convert to array of changes
                changes = [
                    {
                        'field': field,
                        'oldValue': None,  # We don't have the previous value in the change stream
                        'newValue': value
                    }
                    for field, value in updated_fields.items()
                ]
        
        elif op_type == 'delete':
            operation = 'delete'
            # For delete, use the document key
            todo_id = str(change_event.get('documentKey', {}).get('_id', ''))
        
        # Construct log entry
        return {
            'timestamp': timestamp,
            'operation': operation,
            'todoId': todo_id,
            'todoTitle': todo_title,
            'project': project,
            'changes': changes,
            'fullDocument': full_document
        }

    def watch_changes_thread(self):
        """
        Thread function that watches for MongoDB changes.
        """
        logger.info("Starting MongoDB change stream watcher thread")

        # Setup options for the change stream
        pipeline = [
            {'$match': {
                'operationType': {'$in': ['insert', 'update', 'delete', 'replace']}
            }}
        ]

        try:
            # Create the change stream
            with self.todos_collection.watch(pipeline) as stream:
                logger.info("Change stream established successfully")

                # Process changes as they come in
                while not self._stop_event.is_set():
                    try:
                        # Use next_document with a timeout to allow checking the stop event
                        change = stream.try_next()

                        if change is not None:
                            # Process the change
                            log_entry = self.process_change_event(change)

                            if log_entry:
                                # Store the log entry
                                self.logs_collection.insert_one(log_entry)
                                logger.debug(f"Logged {log_entry['operation']} for todo {log_entry['todoId']}")

                                # Notify via MQTT
                                asyncio.run(self.notify_change(log_entry))

                        # Small sleep to prevent CPU spinning
                        time.sleep(0.1)

                    except pymongo.errors.PyMongoError as e:
                        if not self._stop_event.is_set():
                            logger.error(f"Error processing change: {str(e)}")
                            # Continue watching after a short delay
                            time.sleep(1)

                logger.info("Change stream watcher thread stopping")

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Error in change stream: {str(e)}")

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

            # Remove the full document to reduce message size
            if 'fullDocument' in log_data:
                del log_data['fullDocument']

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
        if self.running:
            logger.warning("TodoLogService is already running")
            return

        # Initialize database connections
        success = await self.initialize_db()
        if not success:
            logger.error("Failed to initialize database, cannot start service")
            return

        # Clear the stop event
        self._stop_event.clear()

        # Start the change stream watcher thread
        self.watch_thread = threading.Thread(target=self.watch_changes_thread)
        self.watch_thread.daemon = True
        self.watch_thread.start()

        self.running = True
        logger.info("TodoLogService started successfully")

    async def stop(self):
        """
        Stop the Todo Log Service.
        """
        if not self.running:
            logger.warning("TodoLogService is not running")
            return

        # Signal the thread to stop
        self._stop_event.set()

        # Wait for the thread to finish
        if self.watch_thread:
            self.watch_thread.join(timeout=5.0)

        # Close the MongoDB connection
        if self.mongo_client:
            self.mongo_client.close()

        self.running = False
        logger.info("TodoLogService stopped")

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
    Start the TodoLogService as a standalone service.
    """
    service = get_service_instance()
    await service.start()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(stop_service()))

    logger.info("Todo Log Service is running. Press Ctrl+C to stop.")

    # Keep the service running
    try:
        while service.running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

    logger.info("Todo Log Service shutting down")

async def stop_service():
    """
    Stop the TodoLogService.
    """
    service = get_service_instance()
    await service.stop()

# Main entry point for running as a standalone script
if __name__ == "__main__":
    asyncio.run(start_service())
