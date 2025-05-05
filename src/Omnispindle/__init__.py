import json
import os
import shutil
import subprocess
import logging
import sys
import asyncio
import anyio
import threading
import traceback
from typing import Callable, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# logging.getLogger('pymongo').setLevel(logging.WARNING)
# logging.getLogger('asyncio').setLevel(logging.WARNING)
# logging.getLogger('uvicorn').setLevel(logging.INFO)
# logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
# logging.getLogger('uvicorn.error').setLevel(logging.INFO)
# logging.getLogger('uvicorn.protocols').setLevel(logging.WARNING)

# Detect if this module has already been initialized
if globals().get('_MODULE_INITIALIZED', False):
    logger.warning("WARNING: Omnispindle/__init__.py is being loaded AGAIN!")
    _REINITIALIZATION_COUNT = globals().get('_REINITIALIZATION_COUNT', 0) + 1
    logger.warning(f"Reinitialization count: {_REINITIALIZATION_COUNT}")
    logger.warning(f"Stack trace:\n{''.join(traceback.format_stack())}")
    globals()['_REINITIALIZATION_COUNT'] = _REINITIALIZATION_COUNT
else:
    logger.info("First time initializing Omnispindle/__init__.py module")
    _MODULE_INITIALIZED = True
    _REINITIALIZATION_COUNT = 0
    globals()['_MODULE_INITIALIZED'] = True
    globals()['_REINITIALIZATION_COUNT'] = 0

from dotenv import load_dotenv
# Import FastMCP
from fastmcp import Context
# Apply patches before importing any Starlette-dependent code
from .patches import apply_patches
apply_patches()

# Import the Omnispindle class from the server module
logger.debug("About to import server module")
from .server import Omnispindle, server as existing_server
logger.debug("Server module imported successfully")

# Ensure we only have one instance
logger.debug(f"Existing server: {existing_server}, thread: {threading.current_thread().name}")
server = existing_server
logger.debug("Server instance assigned")

# Additional safety check - add a lock to make sure run_server is only called once
_run_server_lock = threading.Lock()
_run_server_called = False
_run_server_result = None

# Track where run_server is called from
_run_server_callsites = []

# Import the tool functions from the tools module
from .tools import add_lesson
from .tools import add_todo
from .tools import delete_lesson
from .tools import delete_todo
from .tools import get_lesson
from .tools import get_todo
from .tools import list_lessons
from .tools import list_todos_by_status
from .tools import mark_todo_complete
from .tools import query_todos
from .tools import search_lessons
from .tools import search_todos
from .tools import update_lesson
from .tools import update_todo
from .mqtt import mqtt_publish
from .mqtt import mqtt_get
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
    """    
    project: [ Madness_interactive, Omnispindle, Swarmonomicon, todomill_projectorium, RegressionTestKit, Dirname, Repo_name ]
    priority: "Low"|"Medium"|"High" (default: Medium)
    metadata: { "ticket": "ticket number", "tags": ["tag1", "tag2"], "notes": "notes" }
    → Returns: {todo_id, truncated_description, project}
    """
    # Create TODO about these comments with mcp tools to test this
    # normalize_project_name(project)
    # Check with regex if can match the full name from the list of projects
    # If not, try to use local AI models to infer the project name from existing list
    # If still not found, return error to the mcp call with a full list
    try:
        result = await add_todo(description, project, priority, target_agent, metadata, ctx)

        # Enhance the result with minimal but effective AI agent hints
        try:
            data = json.loads(result)
            if data.get("success") and "data" in data:
                todo_data = data["data"]
                todo_id = todo_data.get("todo_id")
                todo_truncated_desc = todo_data.get("description")
                todo_project = todo_data.get("project")

                data["data"] = {
                    "todo_id": todo_id,
                    "description": todo_truncated_desc,
                    "project": todo_project,
                }
                return json.dumps(data)
        except Exception as e:
            print(f"Error enhancing add_todo response: {str(e)}")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise


@register_tool_once
async def query_todos_tool(filter: dict = None, projection: dict = None, limit: int = 100) -> str:
    """
    Query todos with filters.
    
    filter: MongoDB query dict (e.g. {"status": "pending"})
    projection: Fields to include/exclude
    limit: Max results (default: 100)
    
    → Returns: {count, items[{id, description, project, status, priority}]}
    """
    result = await query_todos(filter, projection, limit)
    return json.dumps(result, default=str)


@register_tool_once
async def update_todo_tool(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update todo.
    
    todo_id: ID of todo to update
    updates: Fields to change {field: new_value}
    
    → Returns: {success, message}
    """
    return await update_todo(todo_id, updates, ctx)


@register_tool_once
async def mqtt_publish_tool(topic: str, message: str, ctx: Context = None, retain: bool = False) -> str:
    """
    Publish MQTT message.
    
    topic: Topic path to publish to
    message: Content to send
    retain: Keep for new subscribers (default: false)
    
    → Returns: {success, message?}
    """
    return await mqtt_publish(topic, message, ctx, retain)


@register_tool_once
async def mqtt_get_tool(topic: str) -> str:
    """
    Get latest MQTT message.
    
    topic: Topic to retrieve from
    
    → Returns: {success, data (or message if error)}
    """
    result = await mqtt_get(topic)
    return json.dumps({
        "success": result is not None,
        "data": result,
        "message": None if result is not None else "Failed to get MQTT message"
    })


@register_tool_once
async def delete_todo_tool(todo_id: str, ctx: Context = None) -> str:
    """
    Delete todo.
    
    todo_id: ID of todo to remove
    
    → Returns: {success, message}
    """
    return await delete_todo(todo_id, ctx)


@register_tool_once
async def get_todo_tool(todo_id: str) -> str:
    """
    Get todo details.
    
    todo_id: ID of todo to retrieve
    
    → Returns: {id, description, project, status, priority, target, created, [completed, duration]}
    """
    result = await get_todo(todo_id)

    # Optimize the result with focused AI agent hints
    try:
        data = json.loads(result)
        if data.get("success") and "data" in data:
            todo_data = data["data"]

            # Add compact AI hints
            status = todo_data.get("status", "unknown")
            ticket = todo_data.get("ticket", "unknown")
            priority = todo_data.get("priority", "unknown")

            todo_data["ai_hints"] = {
                "status": status,
                "templates": [
                    f"{priority} task in {todo_data.get('project')}",
                    f"Task is {status}"
                ]
            }

            # Only add next actions if task is actionable
            if status in ["initial", "pending"]:
                todo_data["next"] = ["update_todo_tool", "mark_todo_complete_tool", "delete_todo_tool"]
            elif status == "completed":
                todo_data["next"] = ["get_todo_tool", "update_todo_tool", "delete_todo_tool"]

            data["data"] = todo_data
            result = json.dumps(data)
    except Exception as e:
        print(f"Error optimizing get_todo response: {str(e)}")

    return result


@register_tool_once
async def mark_todo_complete_tool(todo_id: str, ctx: Context = None) -> str:
    """
    Complete todo.
    
    todo_id: ID of todo to mark completed
    
    → Returns: {todo_id, completed_at}
    """
    return await mark_todo_complete(todo_id, ctx)


@register_tool_once
async def list_todos_by_status_tool(status: str, limit: int = 100) -> str:
    """
    List todos by status.
    
    status: Filter value ("initial"|"pending"|"completed"|"review")
    limit: Max results (default: 100)
    
    → Returns: {count, status, items[{id, desc, project}], projects?}
    """
    return await list_todos_by_status(status, limit)


@register_tool_once
async def add_lesson_tool(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    """
    Create lesson.
    
    language: Technology or language name
    topic: Brief title/subject
    lesson_learned: Full lesson content
    tags: Optional categorization tags
    
    → Returns: {lesson_id, topic}
    """
    return await add_lesson(language, topic, lesson_learned, tags, ctx)


@register_tool_once
async def get_lesson_tool(lesson_id: str) -> str:
    """
    Get lesson details.
    
    lesson_id: ID of lesson to retrieve
    
    → Returns: {id, language, topic, lesson_learned, tags, created}
    """
    return await get_lesson(lesson_id)


@register_tool_once
async def update_lesson_tool(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update lesson.
    
    lesson_id: ID of lesson to update
    updates: Fields to change {field: new_value}
    
    → Returns: {success, message}
    """
    return await update_lesson(lesson_id, updates, ctx)


@register_tool_once
async def delete_lesson_tool(lesson_id: str, ctx: Context = None) -> str:
    """
    Delete lesson.
    
    lesson_id: ID of lesson to remove
    
    → Returns: {success, message}
    """
    return await delete_lesson(lesson_id, ctx)


@register_tool_once
async def list_lessons_tool(limit: int = 100) -> str:
    """
    List all lessons.
    
    limit: Max results (default: 100)
    
    → Returns: {count, items[{id, language, topic, tags, preview}]}
    """
    return await list_lessons(limit)


@register_tool_once
async def search_todos_tool(query: str, fields: list = None, limit: int = 100) -> str:
    """
    Search todos by text.
    
    query: Text to search for
    fields: Fields to search in (default: ["description"])
    limit: Max results (default: 100)
    
    → Returns: {count, query, matches[{id, description, project, status}]}
    """
    return await search_todos(query, fields, limit)


@register_tool_once
async def search_lessons_tool(query: str, fields: list = None, limit: int = 100) -> str:
    """
    Search lessons by text.
    
    query: Text to search for
    fields: Fields to search in (default: ["topic", "lesson_learned"])
    limit: Max results (default: 100)
    
    → Returns: {count, query, matches[{id, language, topic, preview, tags}]}
    """
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
    global _run_server_called, _run_server_result, _run_server_callsites

    # Get current call location for debugging
    current_stack = ''.join(traceback.format_stack()[-5:])
    current_thread = threading.current_thread().name
    logger.debug(f"run_server called from thread {current_thread}")

    # Track this call site
    _run_server_callsites.append((current_thread, current_stack))

    # Thread-safe check if we've already called this
    with _run_server_lock:
        if _run_server_called:
            logger.warning(f"run_server was already called! Returning previous result.")
            if _run_server_callsites and len(_run_server_callsites) > 1:
                logger.warning(f"First call was from: {_run_server_callsites[0][0]}")
                logger.warning(f"First call stack:\n{_run_server_callsites[0][1]}")
            return _run_server_result

        # We're the first one here
        _run_server_called = True

    # Set up improved exception handling for connection-related errors
    original_excepthook = sys.excepthook

    def global_excepthook(exctype, value, traceback):
        # Handle connection errors more gracefully
        if exctype in (asyncio.exceptions.CancelledError, anyio.WouldBlock,
                      ConnectionResetError, ConnectionAbortedError):
            # Log but don't show full traceback for these common connection errors
            logging.debug(f"Suppressed common connection error: {exctype.__name__}: {value}")
            return
        # Handle "No response returned" RuntimeError
        if exctype is RuntimeError and str(value) == "No response returned.":
            logging.debug("Suppressed 'No response returned' error from disconnected client")
            return
        # Handle NoneType errors specifically
        if exctype is TypeError and "'NoneType' object is not callable" in str(value):
            logging.debug(f"Suppressed NoneType error: {str(value)}")
            return
        # For all other errors, use the original exception handler
        original_excepthook(exctype, value, traceback)

    # Install the global exception handler
    sys.excepthook = global_excepthook

    # Register all the tools with the server
    logger.info("Calling server.run_server() to start the FastMCP server")
    result = await server.run_server()
    logger.info("server.run_server() completed successfully")

    # Store the result for reuse
    _run_server_result = result

    return result
