from fastmcp import FastMCP
import asyncio
import logging
import json
import sys
import os
from typing import Optional

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable debug logging for FastMCP
logging.getLogger('fastmcp').setLevel(logging.DEBUG)
logging.getLogger('mcp').setLevel(logging.DEBUG)

class TodoClient:
    def __init__(self, host: str = "localhost", port: int = 1883):
        self.host = host
        self.port = port
        self.client: Optional[FastMCP] = None

    async def connect(self) -> bool:
        """Connect to the FastMCP server"""
        try:
            logger.debug(f"Connecting to FastMCP server at {self.host}:{self.port}")
            self.client = FastMCP(
                "todo_test_client",
                mqtt_host=self.host,
                mqtt_port=self.port
            )
            logger.debug("FastMCP client created")

            # Wait for connection
            await asyncio.sleep(2)
            logger.debug("Connection wait complete")

            return True
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}", exc_info=True)
            return False

    async def add_todo(self, description: str, project: str, priority: str = "high", target_agent: str = "test_client", metadata: dict = None) -> dict:
        """Add a new todo item"""
        if not self.client:
            raise RuntimeError("Client not connected")

        try:
            args = {
                "description": description,
                "project": project,
                "priority": priority,
                "target_agent": target_agent
            }
            
            # Add metadata if provided
            if metadata:
                args["metadata"] = metadata
                
            logger.debug(f"Adding todo with args: {args}")

            result = await self.client.call_tool("add_todo", args)
            logger.debug(f"Add todo result: {result}")

            return json.loads(result)
        except Exception as e:
            logger.error(f"Failed to add todo: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def query_todos(self, filter: dict = None, projection: dict = None, limit: int = 5) -> dict:
        """Query todo items"""
        if not self.client:
            raise RuntimeError("Client not connected")

        try:
            args = {
                "filter": filter or {},
                "projection": projection,
                "limit": limit
            }
            logger.debug(f"Querying todos with args: {args}")

            result = await self.client.call_tool("query_todos", args)
            logger.debug(f"Query result: {result}")

            return json.loads(result)
        except Exception as e:
            logger.error(f"Failed to query todos: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

async def run_tests():
    """Run the test suite"""
    client = TodoClient()

    # Connect to server
    logger.info("Connecting to server...")
    if not await client.connect():
        logger.error("Failed to connect to server")
        return 1

    try:
        # Test 1: Add a todo
        logger.info("\nTest 1: Adding todo")
        result = await client.add_todo(
            description="Test todo from client",
            project="test_project",
            priority="high",
            target_agent="test_client"
        )

        if result.get("status") != "success":
            logger.error(f"Failed to add todo: {result.get('message', 'Unknown error')}")
            return 1

        todo_id = result["todo_id"]
        logger.info(f"Successfully added todo with ID: {todo_id}")

        # Test 2: Query todos
        logger.info("\nTest 2: Querying todos")
        result = await client.query_todos(
            filter={"priority": "high"},
            projection={"description": 1, "priority": 1, "status": 1}
        )

        if result.get("status") != "success":
            logger.error(f"Failed to query todos: {result.get('message', 'Unknown error')}")
            return 1

        todos = result["todos"]
        logger.info(f"Found {len(todos)} todos:")
        for todo in todos:
            logger.info(f"  - {todo}")

        return 0

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        return 1

def main():
    """Main entry point"""
    logger.info("Starting FastMCP Todo Client Tests")
    return asyncio.run(run_tests())

if __name__ == "__main__":
    sys.exit(main())
