#!/usr/bin/env python3
"""
FastMCP HTTP Server for Omnispindle with user-scoped databases.

This server uses the recommended FastMCP HTTP transport for remote deployments.
Run with: fastmcp run src/Omnispindle/http_server.py
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, Union, List

from fastmcp import FastMCP
from dotenv import load_dotenv

from .context import Context
from .patches import apply_patches
from .auth_utils import verify_auth0_token
from .auth_flow import ensure_authenticated, run_async_in_thread
from . import tools

# Initialize
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
apply_patches()
load_dotenv()

# Tool loadout configurations
TOOL_LOADOUTS = {
    "full": [
        "add_todo", "query_todos", "update_todo", "delete_todo", "get_todo",
        "mark_todo_complete", "list_todos_by_status", "search_todos", "list_project_todos",
        "add_lesson", "get_lesson", "update_lesson", "delete_lesson", "search_lessons",
        "grep_lessons", "list_lessons", "query_todo_logs", "list_projects",
        "explain", "add_explanation", "point_out_obvious", "bring_your_own"
    ],
    "basic": [
        "add_todo", "query_todos", "update_todo", "get_todo", "mark_todo_complete",
        "list_todos_by_status", "list_project_todos"
    ],
    "minimal": [
        "add_todo", "query_todos", "get_todo", "mark_todo_complete"
    ],
    "lessons": [
        "add_lesson", "get_lesson", "update_lesson", "delete_lesson", "search_lessons",
        "grep_lessons", "list_lessons"
    ],
    "admin": [
        "query_todos", "update_todo", "delete_todo", "query_todo_logs", 
        "list_projects", "explain", "add_explanation"
    ]
}

# Create the FastMCP instance that fastmcp run will use
mcp = FastMCP("Omnispindle 🌪️")


# Get tool loadout from environment
loadout_name = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full")
if loadout_name not in TOOL_LOADOUTS:
    logger.warning(f"Unknown loadout '{loadout_name}', using 'full'")
    loadout_name = "full"

selected_tools = TOOL_LOADOUTS[loadout_name]
logger.info(f"Loading '{loadout_name}' loadout: {selected_tools}")

# Register tools based on loadout
for tool_name in selected_tools:
    if hasattr(tools, tool_name):
        func = getattr(tools, tool_name)
        docstring = func.__doc__ or f"Tool: {tool_name}"
        
        # Create wrapper that adds HTTP context with Auth0 authentication
        def create_wrapper(original_func, name):
            @mcp.tool(name=name)
            async def wrapper(*args, **kwargs):
                # TODO: Extract auth from request headers in production
                # For now, use anonymous context
                ctx = Context(user=None)
                return await original_func(*args, **kwargs, ctx=ctx)
            
            wrapper.__doc__ = docstring
            return wrapper
        
        create_wrapper(func, tool_name)
        logger.info(f"Tool '{tool_name}' registered for HTTP transport.")

# The mcp instance is now ready for fastmcp run command