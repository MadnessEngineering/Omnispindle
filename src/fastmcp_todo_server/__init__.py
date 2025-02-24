from fastmcp import FastMCP, Context
from pymongo import MongoClient
from datetime import datetime, UTC
import uuid
import os
from dotenv import load_dotenv
import json
import logging
import asyncio
import signal
import sys
import paho.mqtt.client as mqtt

# Configure logging - set to DEBUG level for maximum visibility
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable debug logging for FastMCP
logging.getLogger('fastmcp').setLevel(logging.DEBUG)
logging.getLogger('mcp').setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# MQTT configuration
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 3003
MQTT_KEEPALIVE = 60

class TodoServer:
    def __init__(self):
        logger.debug("Initializing TodoServer")

        logger.debug(f"Connecting to MongoDB at {MONGODB_URI}")
        self.mongo_client = MongoClient(MONGODB_URI)
        self.db = self.mongo_client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]
        logger.debug("MongoDB connection established")

        # Lessons Learned configuration
        self.lessons_collection = self.db["lessons_learned"]

        logger.debug("Creating FastMCP server instance")
        self.server = FastMCP("todo_server")
        logger.debug("FastMCP server instance created")

        logger.debug("Registering tools")
        self.register_tools()
        logger.debug("Tools registered")

    def register_tools(self):
        """Register all tools with the server"""
        logger.debug("Registering add_todo tool")
        @self.server.tool("add_todo")
        async def add_todo(description: str, priority: str = "inital", target_agent: str = "user", ctx: Context = None) -> str:
            logger.debug(f"add_todo called with description={description}, priority={priority}, target_agent={target_agent}")
            try:
                # Create todo document
                todo = {
                    "id": str(uuid.uuid4()),
                    "description": description,
                    "priority": priority,
                    "source_agent": "fastmcp",
                    "target_agent": target_agent,
                    "status": "pending",
                    "created_at": int(datetime.now(UTC).timestamp()),
                    "completed_at": None
                }

                # Insert into MongoDB
                self.collection.insert_one(todo)
                logger.debug(f"Successfully inserted todo: {todo['id']}")

                # Log with context if available
                if ctx is not None:
                    try:
                        ctx.info(f"Added todo: {description}")
                    except ValueError:
                        logger.debug("Context not available for logging")

                response = {"status": "success", "todo_id": todo["id"]}
                logger.debug(f"Returning response: {response}")
                return json.dumps(response)
            except Exception as e:
                logger.error(f"Error adding todo: {str(e)}", exc_info=True)
                if ctx is not None:
                    try:
                        ctx.error(f"Failed to add todo: {str(e)}")
                    except ValueError:
                        logger.debug("Context not available for error logging")
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering query_todos tool")
        @self.server.tool("query_todos")
        async def query_todos(filter: dict = None, projection: dict = None, limit: int = 100) -> str:
            """Query todos with optional filtering and projection"""
            logger.debug(f"query_todos called with filter={filter}, projection={projection}, limit={limit}")
            try:
                cursor = self.collection.find(
                    filter or {},
                    projection=projection,
                    limit=limit
                )
                results = list(cursor)

                return json.dumps({
                    "status": "success",
                    "todos": results
                }, default=str)
            except Exception as e:
                logger.error(f"Error querying todos: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        @self.server.tool("update_todo")
        async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
            """Update an existing todo by ID"""
            logger.debug(f"update_todo called with todo_id={todo_id}, updates={updates}")
            try:
                result = self.collection.update_one({"id": todo_id}, {"$set": updates})
                if result.modified_count == 0:
                    return json.dumps({"status": "error", "message": "Todo not found"})

                if ctx is not None:
                    try:
                        ctx.info(f"Updated todo {todo_id}")
                    except ValueError:
                        logger.debug("Context not available for logging")

                return json.dumps({"status": "success"})
            except Exception as e:
                logger.error(f"Error updating todo: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        @self.server.tool("mqtt_publish")
        async def mqtt_publish(topic: str, message: str, ctx: Context = None) -> str:
            """Publish a message to the specified MQTT topic"""
            logger.debug(f"mqtt_publish called with topic={topic}, message={message}")
            try:
                mqtt_client = mqtt.Client()
                mqtt_client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)

                result = mqtt_client.publish(topic, message)
                result.wait_for_publish()

                mqtt_client.disconnect()

                if result.is_published():
                    if ctx is not None:
                        try:
                            ctx.info(f"Published message to topic {topic}")
                        except ValueError:
                            logger.debug("Context not available for logging")

                    return json.dumps({"status": "success"})
                else:
                    return json.dumps({"status": "error", "message": "Message not published"})
            except Exception as e:
                logger.error(f"Error publishing MQTT message: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering delete_todo tool")
        @self.server.tool("delete_todo")
        async def delete_todo(todo_id: str, ctx: Context = None) -> str:
            """Delete a todo by ID"""
            logger.debug(f"delete_todo called with todo_id={todo_id}")
            try:
                result = self.collection.delete_one({"id": todo_id})
                if result.deleted_count == 0:
                    return json.dumps({"status": "error", "message": "Todo not found"})

                if ctx is not None:
                    try:
                        ctx.info(f"Deleted todo {todo_id}")
                    except ValueError:
                        logger.debug("Context not available for logging")

                return json.dumps({"status": "success"})
            except Exception as e:
                logger.error(f"Error deleting todo: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering get_todo tool")
        @self.server.tool("get_todo")
        async def get_todo(todo_id: str) -> str:
            """Get a specific todo by ID"""
            logger.debug(f"get_todo called with todo_id={todo_id}")
            try:
                todo = self.collection.find_one({"id": todo_id})
                if todo is None:
                    return json.dumps({"status": "error", "message": "Todo not found"})

                return json.dumps({"status": "success", "todo": todo}, default=str)
            except Exception as e:
                logger.error(f"Error getting todo: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering mark_todo_complete tool")
        @self.server.tool("mark_todo_complete")
        async def mark_todo_complete(todo_id: str, ctx: Context = None) -> str:
            """Mark a todo as completed"""
            logger.debug(f"mark_todo_complete called with todo_id={todo_id}")
            try:
                result = self.collection.update_one(
                    {"id": todo_id},
                    {"$set": {"status": "completed", "completed_at": int(datetime.now(UTC).timestamp())}}
                )
                if result.modified_count == 0:
                    return json.dumps({"status": "error", "message": "Todo not found"})

                if ctx is not None:
                    try:
                        ctx.info(f"Marked todo {todo_id} as completed")
                    except ValueError:
                        logger.debug("Context not available for logging")

                return json.dumps({"status": "success"})
            except Exception as e:
                logger.error(f"Error marking todo as completed: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering list_todos_by_status tool")
        @self.server.tool("list_todos_by_status")
        async def list_todos_by_status(status: str, limit: int = 100) -> str:
            """List todos by their status"""
            logger.debug(f"list_todos_by_status called with status={status}, limit={limit}")
            try:
                cursor = self.collection.find(
                    {"status": status},
                    limit=limit
                )
                results = list(cursor)

                return json.dumps({
                    "status": "success",
                    "todos": results
                }, default=str)
            except Exception as e:
                logger.error(f"Error listing todos by status: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering add_lesson tool")
        @self.server.tool("add_lesson")
        async def add_lesson(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
            """Add a lesson learned"""
            logger.debug(f"add_lesson called with language={language}, topic={topic}, lesson_learned={lesson_learned}, tags={tags}")
            try:
                lesson = {
                    "id": str(uuid.uuid4()),
                    "language": language,
                    "topic": topic,
                    "lesson_learned": lesson_learned,
                    "tags": tags or [],
                    "created_at": int(datetime.now(UTC).timestamp())
                }

                # Insert into MongoDB
                self.lessons_collection.insert_one(lesson)
                logger.debug(f"Successfully inserted lesson: {lesson['id']}")

                response = {"status": "success", "lesson_id": lesson["id"]}
                logger.debug(f"Returning response: {response}")
                return json.dumps(response)
            except Exception as e:
                logger.error(f"Error adding lesson: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering get_lesson tool")
        @self.server.tool("get_lesson")
        async def get_lesson(lesson_id: str) -> str:
            """Get a specific lesson by ID"""
            logger.debug(f"get_lesson called with lesson_id={lesson_id}")
            try:
                lesson = self.lessons_collection.find_one({"id": lesson_id})
                if lesson is None:
                    return json.dumps({"status": "error", "message": "Lesson not found"})

                return json.dumps({"status": "success", "lesson": lesson}, default=str)
            except Exception as e:
                logger.error(f"Error getting lesson: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering update_lesson tool")
        @self.server.tool("update_lesson")
        async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
            """Update an existing lesson by ID"""
            logger.debug(f"update_lesson called with lesson_id={lesson_id}, updates={updates}")
            try:
                result = self.lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
                if result.modified_count == 0:
                    return json.dumps({"status": "error", "message": "Lesson not found"})

                return json.dumps({"status": "success"})
            except Exception as e:
                logger.error(f"Error updating lesson: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering delete_lesson tool")
        @self.server.tool("delete_lesson")
        async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
            """Delete a lesson by ID"""
            logger.debug(f"delete_lesson called with lesson_id={lesson_id}")
            try:
                result = self.lessons_collection.delete_one({"id": lesson_id})
                if result.deleted_count == 0:
                    return json.dumps({"status": "error", "message": "Lesson not found"})

                return json.dumps({"status": "success"})
            except Exception as e:
                logger.error(f"Error deleting lesson: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

        logger.debug("Registering list_lessons tool")
        @self.server.tool("list_lessons")
        async def list_lessons(limit: int = 100) -> str:
            """List all lessons learned"""
            logger.debug(f"list_lessons called with limit={limit}")
            try:
                cursor = self.lessons_collection.find(limit=limit)
                results = list(cursor)

                return json.dumps({
                    "status": "success",
                    "lessons": results
                }, default=str)
            except Exception as e:
                logger.error(f"Error listing lessons: {str(e)}", exc_info=True)
                return json.dumps({"status": "error", "message": str(e)})

    async def run_async(self):
        """Run the server asynchronously"""
        logger.info("Starting TodoServer")
        try:
            logger.debug("Starting FastMCP server")
            await self.server.run_stdio_async()
        except Exception as e:
            logger.error(f"Error running server: {str(e)}", exc_info=True)
            raise

    def run(self):
        """Run the server synchronously"""
        logger.info("Starting server synchronously")
        asyncio.run(self.run_async())


# if __name__ == "__main__":
logger.info("Starting FastMCP Todo Server")
server = TodoServer()
logger.info("Server initialized, starting run")
server.run()
