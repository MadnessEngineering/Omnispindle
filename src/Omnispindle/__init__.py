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

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*ServerErrorMiddleware.*")

from dotenv import load_dotenv
from fastmcp import Context

# --- Local Imports ---
from .patches import apply_patches
from .server import server
# Import the implementation functions from tools.py
from .tools import (
    add_lesson as _add_lesson,
    add_todo as _add_todo,
    delete_lesson as _delete_lesson,
    delete_todo as _delete_todo,
    get_lesson as _get_lesson,
    get_todo as _get_todo,
    grep_lessons as _grep_lessons,
    list_projects as _list_projects,
    list_todos_by_status as _list_todos_by_status,
    mark_todo_complete as _mark_todo_complete,
    query_todos as _query_todos,
    query_todo_logs as _query_todo_logs,
    search_todos as _search_todos,
    update_lesson as _update_lesson,
    update_todo as _update_todo,
    list_project_todos as _list_project_todos,
    explain_tool as _explain_tool,
    add_explanation as _add_explanation,
    list_lessons as _list_lessons,
    search_lessons as _search_lessons
)
from .mqtt import mqtt_publish, mqtt_get
from .todo_log_service import get_service_instance as get_log_service

# --- Initializations ---
apply_patches()
load_dotenv()

# --- Agent-Facing Tool Definitions ---
# These wrappers provide the clean API and docstrings for the AI agents.

async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """
    Creates a task in the specified project with the given priority and target agent. 
    Returns a compact representation of the created todo with an ID for reference.
    This is the main driver for the todo system. These tools are collectively known as the Omnispindle.
    It spins the weave between our Madness Interactive projects and acts as Power Armor for our Agent Swarmonomicon. 
    """
    return await _add_todo(description, project, priority, target_agent, metadata, ctx)

async def query_todos(filter: dict = None, projection: dict = None, limit: int = 100, ctx=None) -> str:
    """
    Query todos with flexible filtering options.
    Searches the todo database using MongoDB-style query filters and projections.
    """
    return await _query_todos(filter, projection, limit, ctx)

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update a todo with the provided changes.
    Common fields to update: description, priority, status, metadata.
    """
    return await _update_todo(todo_id, updates, ctx)

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """Delete a todo by its ID."""
    return await _delete_todo(todo_id, ctx)

async def get_todo(todo_id: str) -> str:
    """Get a specific todo by ID."""
    return await _get_todo(todo_id)

async def mark_todo_complete(todo_id: str, comment: str = None, ctx: Context = None) -> str:
    """
    Mark a todo as completed.
    Calculates the duration from creation to completion.
    """
    return await _mark_todo_complete(todo_id, comment, ctx)

async def list_todos_by_status(status: str, limit: int = 100) -> str:
    """
    List todos filtered by status ('initial', 'pending', 'completed').
    Results are formatted for efficiency with truncated descriptions.
    """
    return await _list_todos_by_status(status, limit)

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    """
    Add a new lesson learned to the knowledge base.
    """
    return await _add_lesson(language, topic, lesson_learned, tags, ctx)

async def get_lesson(lesson_id: str) -> str:
    """Get a specific lesson by ID."""
    return await _get_lesson(lesson_id)

async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing lesson by ID."""
    return await _update_lesson(lesson_id, updates, ctx)

async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
    """Delete a lesson by ID."""
    return await _delete_lesson(lesson_id, ctx)

async def search_todos(query: str, fields: list = None, limit: int = 100, ctx=None) -> str:
    """
    Search todos with text search capabilities across specified fields.
    Special format: "project:ProjectName" to search by project.
    """
    return await _search_todos(query, fields, limit, ctx)

async def grep_lessons(pattern: str, limit: int = 20) -> str:
    """Search lessons with grep-style pattern matching across topic and content."""
    return await _grep_lessons(pattern, limit)

async def list_project_todos(project: str, limit: int = 5) -> str:
    """List recent active todos for a specific project."""
    return await _list_project_todos(project, limit)

async def query_todo_logs(filter_type: str = 'all', project: str = 'all', page: int = 1, page_size: int = 20, ctx: Context = None) -> str:
    """Query todo logs with filtering options."""
    return await _query_todo_logs(filter_type, project, page, page_size, ctx)

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
    """
    List all valid projects from the centralized project management system.
    `include_details`: False (names only), True (full metadata), "filemanager" (for UI).
    """
    return await _list_projects(include_details, madness_root)

async def explain(topic: str, ctx: Context = None) -> str:
    """
    Provides a detailed explanation for a project or concept.
    For projects, it dynamically generates a summary with recent activity.
    """
    return await _explain_tool(topic, ctx)

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Context = None) -> str:
    """Add a new static explanation to the knowledge base."""
    return await _add_explanation(topic, content, kind, author, ctx)

async def list_lessons(limit: int = 100, ctx: Context = None) -> str:
    """List all lessons, sorted by creation date."""
    return await _list_lessons(limit, ctx)

async def search_lessons(query: str, fields: list = None, limit: int = 100, ctx: Context = None) -> str:
    """Search lessons with text search capabilities."""
    return await _search_lessons(query, fields, limit, ctx)

# TODO: a3a81511-5766-41c6-be04-c3ddca06b424
# async def mad_tinker_mode(ctx: Context = None) -> str:
#     """Receive a prompt to instill the mad mind of an unheinged Tinker in our workflow.
#     This will enable additional tooling and options for invention! Embrace the madness!"""
#     return await _mad_tinker_mode(ctx)

# --- Server Entry Point ---
# This list explicitly defines which functions are registered as tools.
TOOLS_TO_REGISTER = [
    add_todo, query_todos, update_todo, delete_todo, get_todo, mark_todo_complete,
    list_todos_by_status, add_lesson, get_lesson, update_lesson, delete_lesson,
    search_todos, grep_lessons, list_project_todos, query_todo_logs, list_projects,
    explain, add_explanation, list_lessons, search_lessons
]

async def run_server() -> Callable:
    """
    Run the FastMCP server.
    This function initializes and starts the FastMCP server, ensuring all
    tools are properly registered before starting.
    """
    if server:
        logger.info(f"Registering {len(TOOLS_TO_REGISTER)} tools with the server...")
        for tool_func in TOOLS_TO_REGISTER:
            server.register_tool(tool_func)
        logger.info("All tools registered.")
    else:
        logger.critical("Server instance is None. Cannot register tools or run.")
        return None

    # Set up improved exception handling for connection-related errors
    original_excepthook = sys.excepthook

    def global_excepthook(exctype, value, traceback):
        if exctype in (asyncio.exceptions.CancelledError, anyio.WouldBlock,
                      ConnectionResetError, ConnectionAbortedError):
            logging.debug(f"Suppressed common connection error: {exctype.__name__}: {value}")
            return
        if exctype is RuntimeError and str(value) == "No response returned.":
            logging.debug("Suppressed 'No response returned' error from disconnected client")
            return
        if exctype is TypeError and "'NoneType' object is not callable" in str(value):
            logging.debug(f"Suppressed NoneType error: {str(value)}")
            return
        original_excepthook(exctype, value, traceback)

    sys.excepthook = global_excepthook

    logger.info("Calling server.run_server() to start the FastMCP server")
    result = await server.run_server()
    logger.info("server.run_server() completed successfully")

    return result

# --- Automatic Service Initialization ---
async def _init_todo_log_service():
    """Initialize the TodoLogService."""
    log_service = get_log_service()
    try:
        await log_service.start()
        logger.info("TodoLogService started successfully.")
    except Exception as e:
        logger.error(f"Failed to start TodoLogService: {str(e)}")

try:
    asyncio.get_running_loop().create_task(_init_todo_log_service())
except RuntimeError: # 'asyncio.get_running_loop()' when no loop is running
    # This happens when the module is imported in a non-async context.
    # The main application entry point (__main__.py) will start the loop.
    pass
except Exception as e:
    logger.error(f"Failed to schedule TodoLogService initialization: {str(e)}")
