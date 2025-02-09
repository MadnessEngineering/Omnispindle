from fastmcp import FastMCPServer, FastMCPHandler
from pymongo import MongoClient
from datetime import datetime
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

class TodoHandler(FastMCPHandler):
    def __init__(self):
        super().__init__()
        self.mongo_client = MongoClient(MONGODB_URI)
        self.db = self.mongo_client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]

    async def on_message(self, message):
        try:
            # Parse the message
            todo_data = json.loads(message)
            
            # Create todo document
            todo = {
                "id": str(uuid.uuid4()),
                "description": todo_data.get("description"),
                "priority": todo_data.get("priority", "medium"),
                "source_agent": todo_data.get("source_agent", "mcp_server"),
                "target_agent": todo_data.get("target_agent", "user"),
                "status": "pending",
                "created_at": int(datetime.utcnow().timestamp()),
                "completed_at": None
            }
            
            # Insert into MongoDB
            self.collection.insert_one(todo)
            
            return {"status": "success", "todo_id": todo["id"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def main():
    # Create and start the FastMCP server
    server = FastMCPServer(TodoHandler)
    server.run()
