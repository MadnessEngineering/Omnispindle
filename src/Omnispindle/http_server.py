#!/usr/bin/env python3
"""
FastMCP HTTP Server for Omnispindle with user-scoped databases.

This server uses the recommended FastMCP HTTP transport for remote deployments.
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


def _create_context_http(auth_header: Optional[str] = None) -> Context:
    """Create a context object for HTTP requests with authentication."""
    user_payload = {}
    
    # Try to extract and verify Auth0 token from Authorization header
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        try:
            # Verify the token synchronously for HTTP requests
            async def verify_token_async():
                nonlocal user_payload
                payload = await verify_auth0_token(token)
                if payload:
                    user_payload.update(payload)
            
            run_async_in_thread(verify_token_async())
            
            if user_payload:
                user_payload["auth_method"] = "auth0"
                logger.info(f"HTTP request authenticated via Auth0: {user_payload.get('sub')}")
                return Context(user=user_payload)
        except Exception as e:
            logger.error(f"Auth0 token verification failed for HTTP request: {e}")
    
    # For HTTP server, we can't trigger browser auth like stdio server
    # Return anonymous context - tools will handle this appropriately
    logger.warning("HTTP request without valid authentication - using anonymous context")
    return Context(user=None)


class OmnispindleHTTPServer:
    """Omnispindle server using FastMCP HTTP transport."""
    
    def __init__(self):
        self.mcp = FastMCP("Omnispindle 🌪️")
        logger.info("Omnispindle HTTP server initialized with FastMCP")
        
        # Get tool loadout from environment
        loadout_name = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full")
        if loadout_name not in TOOL_LOADOUTS:
            logger.warning(f"Unknown loadout '{loadout_name}', using 'full'")
            loadout_name = "full"
        
        selected_tools = TOOL_LOADOUTS[loadout_name]
        logger.info(f"Loading '{loadout_name}' loadout: {selected_tools}")
        
        # Register tools based on loadout
        self._register_tools(selected_tools)
    
    def _register_tools(self, tool_names: List[str]):
        """Register tools from the tools module based on the loadout."""
        
        for tool_name in tool_names:
            if hasattr(tools, tool_name):
                func = getattr(tools, tool_name)
                docstring = func.__doc__ or f"Tool: {tool_name}"
                
                # Create wrapper that adds HTTP context
                def create_wrapper(original_func, name):
                    @self.mcp.tool(name=name)
                    async def wrapper(*args, **kwargs):
                        # For HTTP server, create anonymous context
                        # In production, you'd extract auth from request headers
                        ctx = Context(user=None)  # Anonymous for now
                        return await original_func(*args, **kwargs, ctx=ctx)
                    
                    wrapper.__doc__ = docstring
                    return wrapper
                
                create_wrapper(func, tool_name)
                logger.info(f"Tool '{tool_name}' registered for HTTP transport.")
    
    def run(self, host: str = "0.0.0.0", port: int = 8000, path: str = "/mcp"):
        """Run the HTTP server."""
        logger.info(f"Starting Omnispindle HTTP server on {host}:{port}{path}")
        # Use the correct FastMCP HTTP parameters
        self.mcp.run(transport="http", host=host, port=port)


def main():
    """Main entry point for the HTTP server."""
    server = OmnispindleHTTPServer()
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    path = os.getenv("MCP_PATH", "/mcp")
    
    server.run(host=host, port=port, path=path)


if __name__ == "__main__":
    main()