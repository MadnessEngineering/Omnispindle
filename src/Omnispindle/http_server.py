#!/usr/bin/env python3.11
"""
FastMCP HTTP Server for Omnispindle with user-scoped databases.

This server uses the recommended FastMCP HTTP transport for remote deployments.
Run with: fastmcp run src/Omnispindle/http_server.py

Compatibility note:
- `fastmcp run ...` imports this module and serves the FastMCP `mcp` instance.
- `python -m src.Omnispindle.http_server` boots the legacy FastAPI app (`/api/mcp`)
  to preserve existing PM2 and Inventorium endpoint contracts.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, Union, List

from fastmcp import FastMCP, Context as MCPContext
# get_current_starlette_request removed in fastmcp 3.x — use global header capture instead
def get_current_starlette_request():
    return None
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
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

# Import shared loadout definitions
from src.Omnispindle.tool_loadouts import get_loadout

# Global variable to store current request headers (not ideal but might work)
_current_request_headers = {}

class HeaderCaptureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _current_request_headers
        # Capture headers from the request
        _current_request_headers = dict(request.headers)
        logger.info(f"Middleware captured headers: {list(_current_request_headers.keys())}")
        
        response = await call_next(request)
        return response

# Create the FastMCP instance that fastmcp run will use
mcp = FastMCP("Omnispindle 🌪️")

# Add middleware to capture headers (if FastMCP supports it)
if hasattr(mcp, 'app') and hasattr(mcp.app, 'add_middleware'):
    mcp.app.add_middleware(HeaderCaptureMiddleware)
    logger.info("Added HeaderCaptureMiddleware to FastMCP app")
else:
    logger.warning("FastMCP doesn't support app.add_middleware - using fallback header capture")


async def get_authenticated_context_from_mcp(mcp_ctx: MCPContext, user_ctx: Optional[Dict[str, Any]] = None) -> Context:
    """
    Extract and verify Auth0 token from MCP context.
    Returns authenticated user context or raises an error.
    """
    # Fast path: backend already verified user, use pre-resolved context dict
    if user_ctx and isinstance(user_ctx, dict):
        user_data = user_ctx.get('user', user_ctx)
        if user_data and user_data.get('sub'):
            logger.info(f"Using pre-resolved user context from backend: {user_data.get('sub')}")
            return Context(user=user_data)

    token = None
    
    # Debug: Log what MCP context contains
    logger.info(f"MCP Context received: {mcp_ctx}")
    if mcp_ctx:
        logger.info(f"MCP Context type: {type(mcp_ctx)}")
        logger.info(f"MCP Context attributes: {dir(mcp_ctx)}")
    
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
    
    # Try other potential MCP context attributes
    if not token and mcp_ctx:
        for attr_name in ['request', 'http_headers', 'context', 'session']:
            if hasattr(mcp_ctx, attr_name):
                attr = getattr(mcp_ctx, attr_name)
                logger.info(f"MCP Context has {attr_name}: {attr}")
                if hasattr(attr, 'headers'):
                    headers = attr.headers
                    logger.info(f"Found headers in {attr_name}: {list(headers.keys()) if headers else 'None'}")
                    if headers:
                        auth_header = headers.get("authorization") or headers.get("Authorization")
                        if auth_header and auth_header.startswith("Bearer "):
                            token = auth_header[7:]
                            logger.info(f"Token extracted from {attr_name} (length: {len(token)})")
                            break
    
    # Fallback to get_current_starlette_request
    if not token:
        try:
            starlette_req = get_current_starlette_request()
            request_headers = dict(starlette_req.headers) if starlette_req else {}
            logger.info(f"Fallback headers from starlette request: {list(request_headers.keys()) if request_headers else 'None'}")
            if request_headers:
                auth_header = request_headers.get("authorization") or request_headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    logger.info(f"Token extracted from starlette request (length: {len(token)})")
        except Exception as e:
            logger.warning(f"Could not get HTTP headers from FastMCP context: {e}")
    
    # Final fallback: check global headers variable
    if not token and _current_request_headers:
        logger.info(f"Trying global headers: {list(_current_request_headers.keys())}")
        auth_header = _current_request_headers.get("authorization") or _current_request_headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            logger.info(f"Token extracted from global headers (length: {len(token)})")

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
            starlette_req = get_current_starlette_request()
            request_headers = dict(starlette_req.headers) if starlette_req else {}
            logger.info(f"Retrieved headers from starlette request: {list(request_headers.keys()) if request_headers else 'None'}")
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


# Get tool loadout from environment (remote mode - filters local-only tools)
loadout_name = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full")
selected_tools = get_loadout(loadout_name, mode="remote")
logger.info(f"Loading '{loadout_name}' loadout (remote mode, {len(selected_tools)} tools): {selected_tools}")

# Register specific tools manually for HTTP transport compatibility
if "add_todo" in selected_tools:
    @mcp.tool()
    async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", notes: str = "", ticket: str = "", metadata: Optional[Dict[str, Any]] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Create task with priority/agent. Returns created todo. Use for new work tracking."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.add_todo(description, project, priority, target_agent, notes, ticket, metadata, auth_ctx)

if "query_todos" in selected_tools:
    @mcp.tool()
    async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100, offset: int = 0, exclude_completed: bool = True, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Search tasks via filter. Default excludes completed. Returns list. Use for bulk retrieval."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.query_todos(filter, projection, limit, offset, exclude_completed, auth_ctx)

if "get_todo" in selected_tools:
    @mcp.tool()
    async def get_todo(todo_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Retrieve single task by ID. Returns full todo object."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.get_todo(todo_id, auth_ctx)

if "complete_todo" in selected_tools:
    @mcp.tool()
    async def complete_todo(todo_id: str, comment: Optional[str] = None, files: Optional[List[str]] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Set status=completed. Optional closing comment and changed file list. Returns updated todo."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.complete_todo(todo_id, comment, files, auth_ctx)

if "update_todo" in selected_tools:
    @mcp.tool()
    async def update_todo(todo_id: str, updates: Dict[str, Any], user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Modify existing task fields. Returns updated todo object."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.update_todo(todo_id, updates, auth_ctx)

if "list_todos_by_status" in selected_tools:
    @mcp.tool()
    async def list_todos_by_status(status: str, limit: int = 100, offset: int = 0, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch tasks by status string. Returns paginated list."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.list_todos_by_status(status, limit, offset, auth_ctx)

if "list_project_todos" in selected_tools:
    @mcp.tool()
    async def list_project_todos(project: str, limit: int = 5, offset: int = 0, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch latest project tasks. Returns paginated list. Quick project filter."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.list_project_todos(project, limit, offset, auth_ctx)

# ADDED: Missing CRUD tools for remote parity
if "delete_todo" in selected_tools:
    @mcp.tool()
    async def delete_todo(todo_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Permanently remove task by ID. Returns success status."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.delete_todo(todo_id, auth_ctx)

if "search_todos" in selected_tools:
    @mcp.tool()
    async def search_todos(query: str, limit: int = 100, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Text search task content. Returns matching list. Use when ID unknown."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.search_todos(query, limit, auth_ctx)

# ADDED: Lesson management tools
if "add_lesson" in selected_tools:
    @mcp.tool()
    async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Store learned experience/pitfall. Returns lesson object. Use for knowledge persistence."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.add_lesson(language, topic, lesson_learned, tags, auth_ctx)

if "get_lesson" in selected_tools:
    @mcp.tool()
    async def get_lesson(lesson_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Retrieve specific lesson by ID. Returns full lesson object."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.get_lesson(lesson_id, auth_ctx)

if "update_lesson" in selected_tools:
    @mcp.tool()
    async def update_lesson(lesson_id: str, updates: Dict[str, Any], user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Modify stored lesson fields. Returns updated lesson."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.update_lesson(lesson_id, updates, auth_ctx)

if "delete_lesson" in selected_tools:
    @mcp.tool()
    async def delete_lesson(lesson_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Permanently remove lesson by ID. Returns success status."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.delete_lesson(lesson_id, auth_ctx)

if "search_lessons" in selected_tools:
    @mcp.tool()
    async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 50, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Keyword search topic/content/tags. Returns matching list. Use find_relevant for semantic search."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.search_lessons(query, fields, limit, auth_ctx)

if "grep_lessons" in selected_tools:
    @mcp.tool()
    async def grep_lessons(pattern: str, limit: int = 50, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Regex match topic/content only. No tags. Use search_lessons for tag coverage."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.grep_lessons(pattern, limit, auth_ctx)

if "list_lessons" in selected_tools:
    @mcp.tool()
    async def list_lessons(limit: int = 50, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch all lessons paginated. Returns list. Use for broad browsing."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.list_lessons(limit, auth_ctx)

# Admin/System tools
if "query_todo_logs" in selected_tools:
    @mcp.tool()
    async def query_todo_logs(filter_type: str = "all", project: str = "all", page: int = 1, page_size: int = 20, unified: bool = False, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Retrieve task audit trails. Returns paginated logs. Use for debugging state changes."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.query_todo_logs(filter_type, project, page, page_size, unified, auth_ctx)

if "explain" in selected_tools:
    @mcp.tool()
    async def explain(topic: str, brief: bool = False, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch topic explanation from knowledge base. Returns text. Use for conceptual lookups."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.explain_tool(topic, brief, auth_ctx)

if "add_explanation" in selected_tools:
    @mcp.tool()
    async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Insert new concept into knowledge base. Returns created object."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.add_explanation(topic, content, kind, author, auth_ctx)

if "point_out_obvious" in selected_tools:
    @mcp.tool()
    async def point_out_obvious(observation: str, sarcasm_level: int = 5, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Snarky observation generator. Returns formatted text. Adjustable sass level."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.point_out_obvious(observation, sarcasm_level, auth_ctx)

# Session management tools
if "inventorium_sessions_list" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_list(project: Optional[str] = None, limit: int = 50, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """List chat sessions by project. Returns list. Use for context navigation."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_list(project, limit, auth_ctx)

if "inventorium_sessions_get" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_get(session_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Retrieve full session history by ID. Returns messages and metadata."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_get(session_id, auth_ctx)

if "inventorium_sessions_create" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_create(project: str, title: Optional[str] = None, initial_prompt: Optional[str] = None, agentic_tool: str = "claude-code", user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Initialize new project chat. Returns session object. Use to start fresh work."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_create(project, title, initial_prompt, agentic_tool, auth_ctx)

if "inventorium_sessions_spawn" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_spawn(parent_session_id: str, prompt: str, todo_id: Optional[str] = None, title: Optional[str] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Create sub-session from parent. Links to todo. Returns new session."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_spawn(parent_session_id, prompt, todo_id, title, auth_ctx)

if "inventorium_sessions_fork" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_fork(session_id: str, title: Optional[str] = None, include_messages: bool = True, inherit_todos: bool = True, initial_status: Optional[str] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Branch existing session. Returns new session. Use to explore alternatives."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_fork(session_id, title, include_messages, inherit_todos, initial_status, auth_ctx)

if "inventorium_sessions_genealogy" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_genealogy(session_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch session lineage. Returns parent/child IDs. Use to trace context history."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_genealogy(session_id, auth_ctx)

if "inventorium_sessions_tree" in selected_tools:
    @mcp.tool()
    async def inventorium_sessions_tree(project: Optional[str] = None, limit: int = 200, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Fetch full project session hierarchy. Returns tree. Use for global overview."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_sessions_tree(project, limit, auth_ctx)

if "inventorium_todos_link_session" in selected_tools:
    @mcp.tool()
    async def inventorium_todos_link_session(todo_id: str, session_id: str, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Associate task with chat ID. Returns status. Use for context grouping."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.inventorium_todos_link_session(todo_id, session_id, auth_ctx)

# RAG / Context tools
if "get_context_bundle" in selected_tools:
    @mcp.tool()
    async def get_context_bundle(project: Optional[str] = None, keywords: Optional[List[str]] = None, include_completed: bool = False, since: Optional[int] = None, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Bulk fetch recent tasks/lessons/sessions. Returns slim summaries. Use for session initialization."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.get_context_bundle(project=project, keywords=keywords, include_completed=include_completed, since=since, ctx=auth_ctx)

if "find_relevant" in selected_tools:
    @mcp.tool()
    async def find_relevant(query: str, types: Optional[List[str]] = None, limit: int = 5, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Semantic search across tasks and lessons. Embeddings when available, regex fallback. Use for complex discovery."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.find_relevant(query=query, types=types, limit=limit, ctx=auth_ctx)

if "preflight_rag" in selected_tools:
    @mcp.tool()
    async def preflight_rag(intent: str, project: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 5, user_ctx: Optional[Dict[str, Any]] = None, ctx: MCPContext = None):
        """Scan lessons for past work/pitfalls before starting. Returns insights. Always run before new tasks."""
        auth_ctx = await get_authenticated_context_from_mcp(ctx, user_ctx)
        return await tools.preflight_rag(intent=intent, project=project, tags=tags, limit=limit, ctx=auth_ctx)

# Log all registered tools
logger.info(f"Registered {len([t for t in selected_tools])} tools for HTTP transport (remote mode)")

# The mcp instance is now ready for fastmcp run command


if __name__ == "__main__":
    # Keep long-standing operator workflow working:
    # `python -m src.Omnispindle.http_server` should start the HTTP MCP endpoint
    # expected by Inventorium (`/api/mcp`), even as we retain FastMCP import mode.
    from src.Omnispindle.__main__ import run_web_server

    run_web_server()
