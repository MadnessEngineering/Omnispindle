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
from typing import Callable, Optional, Union
import warnings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# logging.getLogger('pymongo').setLevel(logging.WARNING)
# logging.getLogger('asyncio').setLevel(logging.WARNING)
# logging.getLogger('uvicorn').setLevel(logging.INFO)
# logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
# logging.getLogger('uvicorn.error').setLevel(logging.INFO)
# logging.getLogger('uvicorn.protocols').setLevel(logging.WARNING)

# Filter out specific RuntimeWarnings about unawaited coroutines - moved after logging setup
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*send_log_message.*was never awaited.*")

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
from .tools import list_projects
from .tools import list_todos_by_status
from .tools import mark_todo_complete
from .tools import query_todos
from .tools import query_todo_logs
from .tools import search_lessons
from .tools import search_todos
from .tools import update_lesson
from .tools import update_todo
from .tools import list_project_todos
from .mqtt import mqtt_publish
from .mqtt import mqtt_get
from pymongo import MongoClient

# Import the TodoLogService for initialization
from .todo_log_service import get_service_instance as get_log_service

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
    project: [ Madness_interactive, Omnispindle, Swarmonomicon, todomill_projectorium, RegressionTestKit, etc ]
    priority: "Low"|"Medium"|"High" (default: Medium)
    metadata: { "ticket": "ticket number", "tags": ["tag1", "tag2"], "notes": "notes" }
    → Returns: {success, todo_id, message}
    """
    # Project name will be validated and normalized in tools.py
    # This includes:
    # 1. Conversion to lowercase for consistent storage
    # 2. Validation against known project list
    # 3. Partial matching for typos/case differences
    # 4. Fallback to madness_interactive if no match found
    try:
        result = await add_todo(description, project, priority, target_agent, metadata, ctx)

        # Simplify the response to just return the todo_id and success message
        try:
            data = json.loads(result)
            if data.get("success") and "data" in data:
                todo_id = data["data"].get("todo_id")
                return json.dumps({
                    "success": True,
                    "todo_id": todo_id,
                    "message": "Todo created successfully"
                })
        except Exception as e:
            print(f"Error simplifying add_todo response: {str(e)}")

        # Fallback to original result if parsing fails
        return result

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise


@register_tool_once
async def query_todos_tool(query_or_filter=None, fields_or_projection=None, limit: int = 100, ctx: Context = None) -> str:
    """
    Query or search todos with flexible options.
    
    query_or_filter: Can be either:
                    - MongoDB query dict (e.g. {"status": "pending"})
                    - Text string to search for when fields_or_projection is a list
                      Special formats:
                      - Use "project:ProjectName" to search for todos in specific project
    fields_or_projection: Can be either:
                    - MongoDB projection dict for filtering fields to return
                    - List of fields to search in when query_or_filter is a text string
                      Special values supported:
                      - "all" to search all text fields
    limit: Max results (default: 100)
    
    → Returns: {count, items[...]} when filtering or {count, query, matches[...]} when searching
    """
    # Determine if this is a search or query operation based on parameter types
    if isinstance(query_or_filter, str):
        # This is a search operation with a text query
        return await search_todos(query_or_filter, fields_or_projection, limit, ctx)
    else:
        # This is a filter operation with a MongoDB filter
        result = await query_todos(query_or_filter, fields_or_projection, limit, ctx)
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


# @register_tool_once
# async def mqtt_publish_tool(topic: str, message: str, ctx: Context = None, retain: bool = False) -> str:
#     """
#     Publish MQTT message.

#     topic: Topic path to publish to
#     message: Content to send
#     retain: Keep for new subscribers (default: false)

#     → Returns: {success, message?}
#     """
#     return await mqtt_publish(topic, message, ctx, retain)


# @register_tool_once
# async def mqtt_get_tool(topic: str) -> str:
#     """
#     Get latest MQTT message.

#     topic: Topic to retrieve from

#     → Returns: {success, data (or message if error)}
#     """
#     result = await mqtt_get(topic)
#     return json.dumps({
#         "success": result is not None,
#         "data": result,
#         "message": None if result is not None else "Failed to get MQTT message"
#     })


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
    
    → Returns: {id, description, project, status, enhanced_description, priority, target, metadata} or {id, description, project, status, completed, duration, completion_comment}
    """
    result = await get_todo(todo_id)

    # The underlying get_todo function now returns optimized fields based on status
    # For active todos: id, description, project, status, enhanced_description, priority, target, metadata
    # For completed todos: id, description, project, status, completed, duration, completion_comment

    return result


@register_tool_once
async def mark_todo_complete_tool(todo_id: str, comment: str = None, ctx: Context = None) -> str:
    """
    Complete todo.
    
    Marks a todo as completed and records completion time. Optionally accepts 
    a completion comment to document the solution or outcome.
    
    todo_id: ID of todo to mark completed, str
    comment: Str = None
    
    → Returns: {todo_id, completed_at, duration}
    """
    return await mark_todo_complete(todo_id, comment, ctx)


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
async def search_lessons_tool(query: str, fields: list = None, limit: int = 100) -> str:
    """
    Search lessons by text.

    query: Text to search for
    fields: Fields to search in (default: ["topic", "lesson_learned"])
    limit: Max results (default: 100)

    → Returns: {count, query, matches[{id, language, topic, preview, tags}]}
    """
    return await search_lessons(query, fields, limit)


@register_tool_once
async def list_project_todos_tool(project: str, limit: int = 5) -> str:
    """
    List recent todos by project.
    
    Returns active (non-completed) todos for a specific project, sorted by creation date 
    with newest first. Completed todos are automatically excluded to keep the view 
    focused on actionable work items.
    
    project: Project name to filter by
    limit: Max results (default: 5)
    
    → Returns: {count, project, items[{id, description, status, created_at}]}
    """
    return await list_project_todos(project, limit)


@register_tool_once
async def query_todo_logs_tool(filter_type: str = 'all', project: str = 'all', page: int = 1, page_size: int = 20, ctx: Context = None) -> str:
    """
    Query todo logs with filtering options.
    
    filter_type: Operation type filter ('all', 'create', 'update', 'delete', 'complete')
    project: Project name to filter by ('all' for all projects)
    page: Page number (1-based)
    page_size: Number of items per page (default: 20)
    
    → Returns: {logEntries, totalCount, page, pageSize, hasMore, projects}
    """
    return await query_todo_logs(filter_type, project, page, page_size, ctx)


@register_tool_once
async def list_projects_tool(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
    """
    List all valid projects from the centralized project management system.
    
    include_details: False for project names only, True for detailed metadata, "filemanager" for FileManager format
    
    → Returns: {count, projects, cached}
    """
    return await list_projects(include_details, madness_root)


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

# Automatically start the TodoLogService when the module is imported
async def _init_todo_log_service():
    """Initialize the TodoLogService."""
    log_service = get_log_service()
    try:
        await log_service.start()
        logger.info("TodoLogService started at module initialization")
    except Exception as e:
        logger.error(f"Failed to start TodoLogService: {str(e)}")

# Schedule the initialization
loop = asyncio.get_event_loop()
try:
    loop.create_task(_init_todo_log_service())
except Exception as e:
    logger.error(f"Failed to schedule TodoLogService initialization: {str(e)}")
