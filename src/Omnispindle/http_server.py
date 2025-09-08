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

from fastmcp import FastMCP, Context as MCPContext
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


async def get_authenticated_context_from_mcp(mcp_ctx: MCPContext) -> Context:
    """
    Extract and verify Auth0 token from MCP context.
    Returns authenticated user context or raises an error.
    """
    token = None
    
    # Try to get headers from MCP context
    if mcp_ctx and hasattr(mcp_ctx, 'headers'):
        headers = mcp_ctx.headers
        logger.info(f"MCP Context headers: {list(headers.keys()) if headers else 'None'}")
        if headers:
            auth_header = headers.get("authorization") or headers.get("Authorization")
            logger.info(f"Authorization header found in MCP context: {'Yes' if auth_header else 'No'}")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                logger.info(f"Token extracted from MCP context (length: {len(token)})")
    
    # Fallback to get_http_headers
    if not token:
        try:
            request_headers = get_http_headers()
            logger.info(f"Fallback headers from get_http_headers: {list(request_headers.keys()) if request_headers else 'None'}")
            if request_headers:
                auth_header = request_headers.get("authorization") or request_headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    logger.info(f"Token extracted from get_http_headers (length: {len(token)})")
        except Exception as e:
            logger.warning(f"Could not get HTTP headers from FastMCP context: {e}")

    if not token:
        auth_url = f"https://{AUTH_CONFIG.domain}/authorize?client_id={AUTH_CONFIG.client_id}&audience={AUTH_CONFIG.audience}&response_type=token&redirect_uri=http://localhost:8765/callback"
        raise ValueError(
            f"Authentication required. No Authorization header found in request.\n"
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
            logger.info(f"Retrieved headers from FastMCP context: {list(request_headers.keys()) if request_headers else 'None'}")
        except Exception as e:
            logger.warning(f"Could not get HTTP headers from FastMCP context: {e}")
            request_headers = {}
    
    if request_headers:
        auth_header = request_headers.get("authorization") or request_headers.get("Authorization")
        logger.info(f"Authorization header found: {'Yes' if auth_header else 'No'}")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            logger.info(f"Token extracted successfully (length: {len(token)})")
        elif auth_header:
            logger.warning(f"Authorization header present but doesn't start with 'Bearer ': {auth_header[:20]}...")

    if not token:
        auth_url = f"https://{AUTH_CONFIG.domain}/authorize?client_id={AUTH_CONFIG.client_id}&audience={AUTH_CONFIG.audience}&response_type=token&redirect_uri=http://localhost:8765/callback"
        raise ValueError(
            f"Authentication required. No Authorization header found in request.\n"
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
    async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Creates a task in the specified project with the given priority and target agent."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.add_todo(description, project, priority, target_agent, metadata, auth_ctx)

if "query_todos" in selected_tools:
    @mcp.tool()
    async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100, ctx: MCPContext = None):
        """Query todos with flexible filtering options from user's database."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.query_todos(filter, projection, limit, auth_ctx)

if "get_todo" in selected_tools:
    @mcp.tool()
    async def get_todo(todo_id: str, ctx: MCPContext = None):
        """Get a specific todo item by its ID."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.get_todo(todo_id, auth_ctx)

if "mark_todo_complete" in selected_tools:
    @mcp.tool()
    async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: MCPContext = None):
        """Mark a todo as completed."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.mark_todo_complete(todo_id, comment, auth_ctx)

if "update_todo" in selected_tools:
    @mcp.tool()
    async def update_todo(todo_id: str, updates: Dict[str, Any], ctx: MCPContext = None):
        """Update an existing todo with the provided changes."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.update_todo(todo_id, updates, auth_ctx)

if "list_todos_by_status" in selected_tools:
    @mcp.tool()
    async def list_todos_by_status(status: str, limit: int = 100, ctx: MCPContext = None):
        """List todos filtered by status."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.list_todos_by_status(status, limit, auth_ctx)

if "list_project_todos" in selected_tools:
    @mcp.tool()
    async def list_project_todos(project: str, limit: int = 5, ctx: MCPContext = None):
        """List recent todos for a specific project."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx)
        return await tools.list_project_todos(project, limit, auth_ctx)

# Count all registered tools
registered_tools = [t for t in selected_tools if t in ['add_todo', 'query_todos', 'get_todo', 'mark_todo_complete', 'update_todo', 'list_todos_by_status', 'list_project_todos']]
logger.info(f"Registered {len(registered_tools)} tools for HTTP transport: {registered_tools}")

# The mcp instance is now ready for fastmcp run command
