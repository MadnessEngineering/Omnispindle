from fastmcp import FastMCP, Context
from pymongo import MongoClient
from datetime import datetime, UTC
import uuid
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

class TodoServer:
    def __init__(self):
        self.mongo_client = MongoClient(MONGODB_URI)
        self.db = self.mongo_client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]
        self.server = FastMCP("todo_server")

        @self.server.tool()
        async def add_todo(description: str, priority: str = "medium", target_agent: str = "user", ctx: Context = None) -> str:
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

                # Only try to use context if it's available and has a request context
                if ctx is not None:
                    try:
                        ctx.info(f"Added todo: {description}")
                    except ValueError:
                        # Context not available, ignore logging
                        pass

                return json.dumps({"status": "success", "todo_id": todo["id"]})
            except Exception as e:
                # Only try to use context if it's available and has a request context
                if ctx is not None:
                    try:
                        ctx.error(f"Failed to add todo: {str(e)}")
                    except ValueError:
                        # Context not available, ignore logging
                        pass
                return json.dumps({"status": "error", "message": str(e)})

    def run(self):
        self.server.run()

def main():
    server = TodoServer()
    server.run()
