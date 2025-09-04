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

from src.Omnispindle.context import Context
from src.Omnispindle.patches import apply_patches
from src.Omnispindle.auth_utils import verify_auth0_token
from src.Omnispindle.auth_flow import ensure_authenticated, run_async_in_thread
from src.Omnispindle import tools

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

# Register specific tools manually for HTTP transport compatibility
if "add_todo" in selected_tools:
    @mcp.tool()
    async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None):
        """Creates a task in the specified project with the given priority and target agent."""
        ctx = Context(user=None)
        return await tools.add_todo(description, project, priority, target_agent, metadata, ctx)

if "query_todos" in selected_tools:
    @mcp.tool()
    async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100):
        """Query todos with flexible filtering options from user's database."""
        ctx = Context(user=None)
        return await tools.query_todos(filter, projection, limit, ctx)

if "get_todo" in selected_tools:
    @mcp.tool()
    async def get_todo(todo_id: str):
        """Get a specific todo item by its ID."""
        ctx = Context(user=None)
        return await tools.get_todo(todo_id, ctx)

if "mark_todo_complete" in selected_tools:
    @mcp.tool()
    async def mark_todo_complete(todo_id: str, comment: Optional[str] = None):
        """Mark a todo as completed."""
        ctx = Context(user=None)
        return await tools.mark_todo_complete(todo_id, comment, ctx)

logger.info(f"Registered {len([t for t in selected_tools if t in ['add_todo', 'query_todos', 'get_todo', 'mark_todo_complete']])} tools for HTTP transport")

# The mcp instance is now ready for fastmcp run command