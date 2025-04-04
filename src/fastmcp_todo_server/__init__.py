import json
import os
import shutil
import subprocess
from typing import Callable, Optional

from dotenv import load_dotenv
# Import FastMCP
from fastmcp import Context
# Import the Omnispindle class from the server module
from server import Omnispindle
from tools import add_lesson
# Import the tool functions from the tools module
from tools import add_todo
from tools import delete_lesson
from tools import delete_todo
from tools import get_lesson
from tools import get_todo
from tools import list_lessons
from tools import list_todos_by_status
from tools import mark_todo_complete
from tools import mqtt_publish
from tools import query_todos
from tools import search_lessons
from tools import search_todos
from tools import update_lesson
from tools import update_todo
from pymongo import MongoClient
# Import the AI assistant functions
from ai_assistant import get_todo_suggestions
from ai_assistant import get_specific_suggestions
# Import the scheduler functions
from scheduler import suggest_deadline
from scheduler import suggest_time_slot
from scheduler import generate_daily_schedule
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
async def add_todo_tool(description: str, project: str, priority: str = "initial", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    result = await add_todo(description, project, priority, target_agent, metadata, ctx)
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


@register_tool_once
async def get_todo_suggestions_tool() -> str:
    """
    Get AI-powered suggestions for todos based on pattern analysis.
    
    This tool analyzes completed todos to identify patterns and makes suggestions for:
    1. Task automation opportunities
    2. Priority recommendations for pending todos
    3. Insights about task patterns
    
    Returns:
        A JSON string containing suggestions and analysis results
    """
    return await get_todo_suggestions()


@register_tool_once
async def get_specific_todo_suggestions_tool(todo_id: str) -> str:
    """
    Get AI-powered suggestions for a specific todo.
    
    This tool analyzes a specific todo and compares it with completed todos to provide:
    1. Priority recommendations based on similar completed todos
    2. Estimated completion time based on similar tasks
    3. List of similar completed todos for reference
    
    Args:
        todo_id: ID of the todo to get suggestions for
        
    Returns:
        A JSON string containing suggestions specific to the todo
    """
    return await get_specific_suggestions(todo_id)


@register_tool_once
async def suggest_deadline_tool(todo_id: str) -> str:
    """
    Suggest an optimal deadline for a specific todo based on priority and content analysis.
    
    This tool analyzes a todo's priority and description to suggest a reasonable deadline:
    1. High priority tasks get shorter deadlines
    2. Keywords like "urgent" or "tomorrow" influence the suggestion
    3. The deadline always falls on a working day
    
    Args:
        todo_id: ID of the todo to suggest a deadline for
        
    Returns:
        A JSON string containing the deadline suggestion with reasoning
    """
    return await suggest_deadline(todo_id)


@register_tool_once
async def suggest_time_slot_tool(todo_id: str, date: Optional[str] = None) -> str:
    """
    Suggest an optimal time slot for completing a specific todo.
    
    This tool analyzes completed todos to find patterns in when similar tasks 
    are typically completed, then suggests an optimal time slot:
    1. Based on historical completion patterns for similar tasks
    2. Considering the priority of the task (high priority = morning slots)
    3. Using appropriate duration based on task priority
    
    Args:
        todo_id: ID of the todo to schedule
        date: Optional specific date in YYYY-MM-DD format
        
    Returns:
        A JSON string containing the time slot suggestion with reasoning
    """
    return await suggest_time_slot(todo_id, date)


@register_tool_once
async def generate_daily_schedule_tool(date: Optional[str] = None) -> str:
    """
    Generate an optimized daily schedule based on pending todos.
    
    This tool creates a complete daily schedule by:
    1. Prioritizing tasks based on their importance
    2. Allocating appropriate time slots with breaks between tasks
    3. Ensuring the schedule respects working hours
    4. Limiting the number of tasks to a reasonable amount per day
    
    Args:
        date: Optional specific date in YYYY-MM-DD format (defaults to tomorrow)
        
    Returns:
        A JSON string containing the complete suggested schedule
    """
    return await generate_daily_schedule(date)


# Add Node-RED dashboard tools
server.register_tool(deploy_nodered_flow, name="deploy_nodered_dashboard_tool", description="Deploy a Node-RED dashboard for the todo application")
server.register_tool(publish_to_dashboard, name="publish_to_dashboard_tool", description="Publish data to the Node-RED dashboard")


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
