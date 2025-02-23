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

class TodoServer:
    def __init__(self):
        logger.debug("Initializing TodoServer")

        # Initialize MongoDB
        logger.debug(f"Connecting to MongoDB at {MONGODB_URI}")
        self.mongo_client = MongoClient(MONGODB_URI)
        self.db = self.mongo_client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]
        logger.debug("MongoDB connection established")

        # Initialize FastMCP server
        logger.debug("Creating FastMCP server instance")
        self.server = FastMCP(
            "todo_list",
        )
        logger.debug("FastMCP server instance created")

        # Register tools
        logger.debug("Registering tools")
        self.register_tools()
        logger.debug("Tools registered")

    def register_tools(self):
        """Register all tools with the server"""
        logger.debug("Registering add_todo tool")
        @self.server.tool("add_todo")
        async def add_todo(description: str, priority: str = "medium", target_agent: str = "user", ctx: Context = None) -> str:
            logger.debug(f"add_todo called with description={description}, priority={priority}, target_agent={target_agent}")
            try:
                # Create todo document
                todo = {
                    "id": str(uuid.uuid4()),
                    "description": description,
                    "priority": priority,
                    "source_agent": "mcp_server",
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

    async def run_async(self):
        """Run the server asynchronously"""
        logger.info("Starting TodoServer")
        try:
            # Run the FastMCP server
            logger.debug("Starting FastMCP server")
            await self.server.run_stdio_async()
        except Exception as e:
            logger.error(f"Error running server: {str(e)}", exc_info=True)
            raise

    def run(self):
        """Run the server synchronously"""
        logger.info("Starting server synchronously")
        asyncio.run(self.run_async())

def main():
    logger.info("Starting FastMCP Todo Server")
    server = TodoServer()
    logger.info("Server initialized, starting run")
    server.run()

if __name__ == "__main__":
    main()
