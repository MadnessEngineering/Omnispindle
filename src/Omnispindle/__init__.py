import json
import os
import shutil
import subprocess
from typing import Callable, Optional

from dotenv import load_dotenv
# Import FastMCP
from fastmcp import Context
# Import the Omnispindle class from the server module
from .server import Omnispindle
from .tools import add_lesson
# Import the tool functions from the tools module
from .tools import add_todo
from .tools import delete_lesson
from .tools import delete_todo
from .tools import get_lesson
from .tools import get_todo
from .tools import list_lessons
from .tools import list_todos_by_status
from .tools import mark_todo_complete
from .utils import mqtt_publish
from .utils import mqtt_get
from .tools import query_todos
from .tools import search_lessons
from .tools import search_todos
from .tools import update_lesson
from .tools import update_todo
from pymongo import MongoClient

# Import the AI assistant functions (WIP)
# from .ai_assistant import get_todo_suggestions
# from .ai_assistant import get_specific_suggestions
# Import the scheduler functions
# from .scheduler import suggest_deadline
# from .scheduler import suggest_time_slot
# from .scheduler import generate_daily_schedule
# from tools import deploy_nodered_flow, publish_to_dashboard

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "todo_app")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# MQTT configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60

# Create MongoDB connection at module level
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
lessons_collection = db["lessons_learned"]
server = Omnispindle()
MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None


def publish_mqtt_status(topic, message, retain=False):
    """
    Publish MQTT message using mosquitto_pub command line tool
    Falls back to logging if mosquitto_pub is not available
    
    Args:
        topic: MQTT topic to publish to
        message: Message to publish (will be converted to string)
        retain: Whether to set the retain flag
    """
    if not MOSQUITTO_PUB_AVAILABLE:
        print(f"MQTT publishing not available - would publish {message} to {topic} (retain={retain})")
        return False

    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False


# Modify tool registration to prevent duplicates
def register_tool_once(tool_func):
    """
    Decorator to register a tool only if it hasn't been registered before
    """
    try:
        # Use the Omnispindle's register_tool method which handles duplicates
        return server.register_tool(tool_func)
    except Exception as e:
        print(f"Failed to register tool {tool_func.__name__}: {str(e)}")
        return tool_func


@register_tool_once
async def add_todo_tool(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    try:
        result = await add_todo(description, project, priority, target_agent, metadata, ctx)
        
        # Enhance the result with minimal but effective AI agent hints
        try:
            data = json.loads(result)
            if data.get("success") and "data" in data:
                todo_data = data["data"]
                todo_id = todo_data.get("todo_id")
                
                # Add simplified agent hints directly in the data object
                todo_data["ai_hints"] = {
                    "summary": f"Created {priority} task in {project}",
                    "context": {
                        "next": f"get_todo({todo_id}), mark_complete({todo_id})",
                        "templates": [
                            f"Task added to {project}",
                            f"Created new task in {project}"
                        ]
                    }
                }
                data["data"] = todo_data
                result = json.dumps(data)
        except Exception as e:
            print(f"Error enhancing add_todo response: {str(e)}")
        
        return result
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise


@register_tool_once
async def query_todos_tool(filter: dict = None, projection: dict = None, limit: int = 100) -> str:
    result = await query_todos(filter, projection, limit)
    return json.dumps(result, default=str)


@register_tool_once
async def update_todo_tool(todo_id: str, updates: dict, ctx: Context = None) -> str:
    return await update_todo(todo_id, updates, ctx)


@register_tool_once
async def mqtt_publish_tool(topic: str, message: str, ctx: Context = None, retain: bool = False) -> str:
    return await mqtt_publish(topic, message, ctx, retain)


@register_tool_once
async def mqtt_get_tool(topic: str) -> str:
    result = await mqtt_get(topic)
    return json.dumps({
        "success": result is not None,
        "data": result,
        "message": None if result is not None else "Failed to get MQTT message"
    })


@register_tool_once
async def delete_todo_tool(todo_id: str, ctx: Context = None) -> str:
    return await delete_todo(todo_id, ctx)


@register_tool_once
async def get_todo_tool(todo_id: str) -> str:
    """
    Get information about a specific todo by ID.
    
    Returns:
        A JSON string containing todo information with minimal but effective AI context
    """
    result = await get_todo(todo_id)
    
    # Optimize the result with focused AI agent hints
    try:
        data = json.loads(result)
        if data.get("success") and "data" in data:
            todo_data = data["data"]
            
            # Add compact AI hints
            status = todo_data.get("status", "unknown")
            priority = todo_data.get("priority", "unknown")
            
            # Use a concise hint format
            todo_data["ai_hints"] = {
                "status": status,
                "templates": [
                    f"{priority} task in {todo_data.get('project')}",
                    f"Task is {status}"
                ]
            }
            
            # Only add next actions if task is actionable
            if status in ["initial", "pending"]:
                todo_data["next"] = ["update", "complete", "delete"]
            
            data["data"] = todo_data
            result = json.dumps(data)
    except Exception as e:
        print(f"Error optimizing get_todo response: {str(e)}")
    
    return result


@register_tool_once
async def mark_todo_complete_tool(todo_id: str, ctx: Context = None) -> str:
    return await mark_todo_complete(todo_id, ctx)


@register_tool_once
async def list_todos_by_status_tool(status: str, limit: int = 100) -> str:
    return await list_todos_by_status(status, limit)


@register_tool_once
async def add_lesson_tool(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    return await add_lesson(language, topic, lesson_learned, tags, ctx)


@register_tool_once
async def get_lesson_tool(lesson_id: str) -> str:
    return await get_lesson(lesson_id)


@register_tool_once
async def update_lesson_tool(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    return await update_lesson(lesson_id, updates, ctx)


@register_tool_once
async def delete_lesson_tool(lesson_id: str, ctx: Context = None) -> str:
    return await delete_lesson(lesson_id, ctx)


@register_tool_once
async def list_lessons_tool(limit: int = 100) -> str:
    return await list_lessons(limit)


@register_tool_once
async def search_todos_tool(query: str, fields: list = None, limit: int = 100) -> str:
    """Search todos with text search capabilities"""
    return await search_todos(query, fields, limit)


@register_tool_once
async def search_lessons_tool(query: str, fields: list = None, limit: int = 100) -> str:
    """Search lessons with text search capabilities"""
    return await search_lessons(query, fields, limit)


async def run_server() -> Callable:
    """
    Run the FastMCP server.
    
    This function initializes and starts the FastMCP server by calling the run_server method
    on the Omnispindle instance. It handles server setup and ensures that all tools are
    properly registered before starting.
    
    Returns:
        Callable: An ASGI application that can handle HTTP, WebSocket, and lifespan requests.
        If the underlying run_sse_async() method returns None, a fallback ASGI application
        will be returned that properly handles requests with appropriate error responses.
    """
    # Register all the tools with the server
    return await server.run_server(publish_mqtt_status)
