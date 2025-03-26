import json
import os
import shutil
import subprocess

from dotenv import load_dotenv
# Import FastMCP
from fastmcp import Context
# Import the Omnispindle class from the server module
from fastmcp_todo_server.server import server
from fastmcp_todo_server.tools import add_lesson
# Import the tool functions from the tools module
from fastmcp_todo_server.tools import add_todo
from fastmcp_todo_server.tools import delete_lesson
from fastmcp_todo_server.tools import delete_todo
from fastmcp_todo_server.tools import get_lesson
from fastmcp_todo_server.tools import get_todo
from fastmcp_todo_server.tools import list_lessons
from fastmcp_todo_server.tools import list_todos_by_status
from fastmcp_todo_server.tools import mark_todo_complete
from fastmcp_todo_server.tools import mqtt_publish
from fastmcp_todo_server.tools import query_todos
from fastmcp_todo_server.tools import search_lessons
from fastmcp_todo_server.tools import search_todos
from fastmcp_todo_server.tools import update_lesson
from fastmcp_todo_server.tools import update_todo
from pymongo import MongoClient

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
        # Use the server's register_tool method which handles duplicates
        return server.register_tool(tool_func)
    except Exception as e:
        print(f"Failed to register tool {tool_func.__name__}: {str(e)}")
        return tool_func


@register_tool_once
async def add_todo_tool(description: str, priority: str = "initial", target_agent: str = "user", ctx: Context = None) -> str:
    result = await add_todo(description, priority, target_agent, ctx)
    return json.dumps(result)


@register_tool_once
async def query_todos_tool(filter: dict = None, projection: dict = None, limit: int = 100) -> str:
    result = await query_todos(filter, projection, limit)
    return json.dumps(result, default=str)


@register_tool_once
async def update_todo_tool(todo_id: str, updates: dict, ctx: Context = None) -> str:
    return await update_todo(todo_id, updates, ctx)


@register_tool_once
async def mqtt_publish_tool(topic: str, message: str, ctx: Context = None) -> str:
    return await mqtt_publish(topic, message, ctx)


@register_tool_once
async def delete_todo_tool(todo_id: str, ctx: Context = None) -> str:
    return await delete_todo(todo_id, ctx)


@register_tool_once
async def get_todo_tool(todo_id: str) -> str:
    return await get_todo(todo_id)


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


async def run_server():
    """Run the FastMCP server"""
    # Register all the tools with the server
    await server.run_server(publish_mqtt_status)
