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
from .tools import (
    add_lesson, add_todo, delete_lesson, delete_todo, get_lesson, get_todo,
    grep_lessons, list_projects, mark_todo_complete, query_todos, query_todo_logs,
    update_lesson, update_todo, list_project_todos,
    explain_tool as _explain_tool,
    add_explanation as _add_explanation,
    list_lessons as list_lessons_tool,
    search_lessons as search_lessons_tool
)
from .mqtt import mqtt_publish, mqtt_get
from .todo_log_service import get_service_instance as get_log_service

# --- Initializations ---
apply_patches()
load_dotenv()

# --- Centralized Tool Registry ---
TOOL_REGISTRY = {
    "add_todo": add_todo,
    "query_todos": query_todos,
    "update_todo": update_todo,
    "delete_todo": delete_todo,
    "get_todo": get_todo,
    "mark_todo_complete": mark_todo_complete,
    "add_lesson": add_lesson,
    "get_lesson": get_lesson,
    "update_lesson": update_lesson,
    "delete_lesson": delete_lesson,
    "grep_lessons": grep_lessons,
    "list_lessons": list_lessons_tool,
    "search_lessons": search_lessons_tool,
    "list_project_todos": list_project_todos,
    "query_todo_logs": query_todo_logs,
    "list_projects": list_projects,
    "explain": _explain_tool,
    "add_explanation": _add_explanation,
}

# --- Server Entry Point ---
async def run_server() -> Callable:
    """
    Run the FastMCP server.
    This function initializes and starts the FastMCP server, ensuring all
    tools are properly registered before starting.
    """
    if server:
        logger.info("Registering tools with the server...")
        server.register_tools(TOOL_REGISTRY)
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
