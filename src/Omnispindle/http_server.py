#!/usr/bin/env python3.11
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
from fastmcp.server.dependencies import get_http_headers
from dotenv import load_dotenv

from src.Omnispindle.context import Context
from src.Omnispindle.patches import apply_patches
from src.Omnispindle.auth_utils import verify_auth0_token, AUTH_CONFIG
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
        "explain", "add_explanation", "point_out_obvious"
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


async def get_authenticated_context(request_headers: Optional[Dict[str, str]] = None) -> Context:
    """
    Extract and verify Auth0 token from HTTP request context.
    Returns authenticated user context or raises an error.
    """
    token = None
    
    # First try to get token from FastMCP request headers
    if not request_headers:
        try:
            request_headers = get_http_headers()
        except Exception as e:
            logger.debug(f"Could not get HTTP headers from FastMCP context: {e}")
            request_headers = {}
    
    if request_headers:
        auth_header = request_headers.get("authorization") or request_headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Fall back to environment variables (for testing/development)
    if not token:
        token = os.getenv("OMNISPINDLE_AUTH0_TOKEN") or os.getenv("AUTH0_TOKEN")

    if not token:
        # In production, this would extract from Authorization: Bearer <token> header
        auth_url = f"https://{AUTH_CONFIG.domain}/authorize?client_id={AUTH_CONFIG.client_id}&audience={AUTH_CONFIG.audience}&response_type=token&redirect_uri=http://localhost:8765/callback"
        raise ValueError(
            f"Authentication required. No valid Auth0 token found.\n"
            f"Please obtain a token by visiting: {auth_url}\n"
            f"Then include it in the Authorization header: 'Bearer <your-token>'"
        )

    # Verify the token
    user_payload = await verify_auth0_token(token)
    if not user_payload:
        raise ValueError("Invalid or expired Auth0 token. Please re-authenticate.")

    user_payload["auth_method"] = "auth0"
    logger.info(f"HTTP request authenticated via Auth0: {user_payload.get('sub')}")
    return Context(user=user_payload)


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
        ctx = await get_authenticated_context()
        return await tools.add_todo(description, project, priority, target_agent, metadata, ctx)

if "query_todos" in selected_tools:
    @mcp.tool()
    async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100):
        """Query todos with flexible filtering options from user's database."""
        ctx = await get_authenticated_context()
        return await tools.query_todos(filter, projection, limit, ctx)

if "get_todo" in selected_tools:
    @mcp.tool()
    async def get_todo(todo_id: str):
        """Get a specific todo item by its ID."""
        ctx = await get_authenticated_context()
        return await tools.get_todo(todo_id, ctx)

if "mark_todo_complete" in selected_tools:
    @mcp.tool()
    async def mark_todo_complete(todo_id: str, comment: Optional[str] = None):
        """Mark a todo as completed."""
        ctx = await get_authenticated_context()
        return await tools.mark_todo_complete(todo_id, comment, ctx)

if "update_todo" in selected_tools:
    @mcp.tool()
    async def update_todo(todo_id: str, updates: Dict[str, Any]):
        """Update an existing todo with the provided changes."""
        ctx = await get_authenticated_context()
        return await tools.update_todo(todo_id, updates, ctx)

if "list_todos_by_status" in selected_tools:
    @mcp.tool()
    async def list_todos_by_status(status: str, limit: int = 100):
        """List todos filtered by status."""
        ctx = await get_authenticated_context()
        return await tools.list_todos_by_status(status, limit, ctx)

if "list_project_todos" in selected_tools:
    @mcp.tool()
    async def list_project_todos(project: str, limit: int = 5):
        """List recent todos for a specific project."""
        ctx = await get_authenticated_context()
        return await tools.list_project_todos(project, limit, ctx)

# Count all registered tools
registered_tools = [t for t in selected_tools if t in ['add_todo', 'query_todos', 'get_todo', 'mark_todo_complete', 'update_todo', 'list_todos_by_status', 'list_project_todos']]
logger.info(f"Registered {len(registered_tools)} tools for HTTP transport: {registered_tools}")

# The mcp instance is now ready for fastmcp run command
