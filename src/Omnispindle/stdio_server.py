#!/usr/bin/env python3
"""
Stdio-based MCP server for Omnispindle using FastMCP.

This module provides a standard input/output transport layer for the MCP protocol,
allowing the Omnispindle tools to be used by Claude Desktop and other MCP clients
that expect stdio communication.

Usage:
    python -m src.Omnispindle.stdio_server
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional

from fastmcp import FastMCP
from .context import Context
from . import tools

# Configure logging to stderr so it doesn't interfere with stdio protocol
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tool loadout configurations - same as FastAPI server
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


def _create_context() -> Context:
    """Create a context object with REQUIRED environment-based user information."""
    # Check for API key first, then fall back to email/user_id
    api_key = os.getenv("MCP_API_KEY")
    user_email = os.getenv("MCP_USER_EMAIL")
    user_id = os.getenv("MCP_USER_ID") 
    
    if api_key:
        # Use API key authentication - we'll trust the API key format validation
        # This allows using API keys from the Inventorium dashboard
        logger.info(f"🔐 Using API key authentication: {api_key[:12]}...")
        user = {
            "email": "api-key-user",  # Placeholder - real validation would happen server-side
            "sub": api_key[:16],  # Use key prefix as identifier
            "auth_method": "api_key"
        }
        return Context(user=user)
    
    if not user_email and not user_id:
        logger.error("❌ Authentication required for STDIO MCP server")
        logger.error("💡 Setup authentication with: python -m src.Omnispindle auth --setup")
        logger.error("🔑 Or manually set: MCP_USER_EMAIL, MCP_USER_ID, or MCP_API_KEY environment variables")
        raise ValueError(
            "Authentication required: MCP_USER_EMAIL, MCP_USER_ID, or MCP_API_KEY must be set. "
            "Run 'python -m src.Omnispindle auth --setup' to configure authentication."
        )
    
    user = {
        "email": user_email,
        "sub": user_id or user_email,  # Use email as fallback ID
        "auth_method": "environment"
    }
    logger.info(f"🔐 Authenticated user: {user_email or user_id}")
    
    return Context(user=user)


class OmniSpindleStdioServer:
    """Stdio-based MCP server for Omnispindle tools using FastMCP."""
    
    def __init__(self):
        self.server = FastMCP(name="omnispindle")
        self._register_tools()
        logger.info("OmniSpindleStdioServer initialized with FastMCP")
    
    def _register_tools(self):
        """Register tools based on OMNISPINDLE_TOOL_LOADOUT env var."""
        
        loadout = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full").lower()
        if loadout not in TOOL_LOADOUTS:
            logger.warning(f"Unknown loadout '{loadout}', using 'full'")
            loadout = "full"
        
        enabled = TOOL_LOADOUTS[loadout]
        logger.info(f"Loading '{loadout}' loadout: {enabled}")

        # Tool registry with streamlined docstrings for MCP
        tool_registry = {
            "add_todo": {
                "func": tools.add_todo,
                "doc": "Creates a task in the specified project with the given priority and target agent. Returns a compact representation of the created todo with an ID for reference.",
                "params": {"description": str, "project": str, "priority": str, "target_agent": str, "metadata": Optional[Dict[str, Any]]}
            },
            "query_todos": {
                "func": tools.query_todos,
                "doc": "Query todos with flexible filtering options. Searches the todo database using MongoDB-style query filters and projections.",
                "params": {"filter": Optional[Dict[str, Any]], "projection": Optional[Dict[str, Any]], "limit": int, "ctx": Optional[str]}
            },
            "update_todo": {
                "func": tools.update_todo,
                "doc": "Update a todo with the provided changes. Common fields to update: description, priority, status, metadata.",
                "params": {"todo_id": str, "updates": dict}
            },
            "delete_todo": {
                "func": tools.delete_todo,
                "doc": "Delete a todo by its ID.",
                "params": {"todo_id": str}
            },
            "get_todo": {
                "func": tools.get_todo,
                "doc": "Get a specific todo by ID.",
                "params": {"todo_id": str}
            },
            "mark_todo_complete": {
                "func": tools.mark_todo_complete,
                "doc": "Mark a todo as completed. Calculates the duration from creation to completion.",
                "params": {"todo_id": str, "comment": Optional[str]}
            },
            "list_todos_by_status": {
                "func": tools.list_todos_by_status,
                "doc": "List todos filtered by status ('initial', 'pending', 'completed'). Results are formatted for efficiency with truncated descriptions.",
                "params": {"status": str, "limit": int}
            },
            "search_todos": {
                "func": tools.search_todos,
                "doc": "Search todos with text search capabilities across specified fields. Special format: \"project:ProjectName\" to search by project.",
                "params": {"query": str, "fields": Optional[list], "limit": int, "ctx": Optional[str]}
            },
            "list_project_todos": {
                "func": tools.list_project_todos,
                "doc": "List recent active todos for a specific project.",
                "params": {"project": str, "limit": int}
            },
            "add_lesson": {
                "func": tools.add_lesson,
                "doc": "Add a new lesson learned to the knowledge base.",
                "params": {"language": str, "topic": str, "lesson_learned": str, "tags": Optional[list]}
            },
            "get_lesson": {
                "func": tools.get_lesson,
                "doc": "Get a specific lesson by ID.",
                "params": {"lesson_id": str}
            },
            "update_lesson": {
                "func": tools.update_lesson,
                "doc": "Update an existing lesson by ID.",
                "params": {"lesson_id": str, "updates": dict}
            },
            "delete_lesson": {
                "func": tools.delete_lesson,
                "doc": "Delete a lesson by ID.",
                "params": {"lesson_id": str}
            },
            "search_lessons": {
                "func": tools.search_lessons,
                "doc": "Search lessons with text search capabilities.",
                "params": {"query": str, "fields": Optional[list], "limit": int}
            },
            "grep_lessons": {
                "func": tools.grep_lessons,
                "doc": "Search lessons with grep-style pattern matching across topic and content.",
                "params": {"pattern": str, "limit": int}
            },
            "list_lessons": {
                "func": tools.list_lessons,
                "doc": "List all lessons, sorted by creation date.",
                "params": {"limit": int}
            },
            "query_todo_logs": {
                "func": tools.query_todo_logs,
                "doc": "Query todo logs with filtering options.",
                "params": {"filter_type": str, "project": str, "page": int, "page_size": int}
            },
            "list_projects": {
                "func": tools.list_projects,
                "doc": "List all valid projects from the centralized project management system. `include_details`: False (names only), True (full metadata), \"filemanager\" (for UI).",
                "params": {"include_details": bool, "madness_root": str}
            },
            "explain": {
                "func": tools.explain_tool,
                "doc": "Provides a detailed explanation for a project or concept. For projects, it dynamically generates a summary with recent activity.",
                "params": {"topic": str}
            },
            "add_explanation": {
                "func": tools.add_explanation,
                "doc": "Add a new static explanation to the knowledge base.",
                "params": {"topic": str, "content": str, "kind": str, "author": str}
            },
            "point_out_obvious": {
                "func": tools.point_out_obvious,
                "doc": "Points out something obvious to the human user with humor.",
                "params": {"observation": str, "sarcasm_level": int}
            },
            "bring_your_own": {
                "func": tools.bring_your_own,
                "doc": "Temporarily hijack the MCP server to run custom tool code.",
                "params": {"tool_name": str, "code": str, "runtime": str, "timeout": int, "args": Optional[Dict[str, Any]], "persist": bool}
            }
        }

        # Register enabled tools dynamically
        for tool_name in enabled:
            if tool_name in tool_registry:
                tool_info = tool_registry[tool_name]
                
                # Create dynamic tool function with proper signature
                def make_tool(name, func, docstring):
                    def create_wrapper():
                        if name == "add_todo":
                            @self.server.tool()
                            async def add_todo(description: str, project: str, priority: str = "Medium", 
                                              target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None) -> str:
                                ctx = _create_context()
                                return await func(description, project, priority, target_agent, metadata, ctx=ctx)
                            add_todo.__doc__ = docstring
                            return add_todo
                        
                        elif name == "query_todos":
                            @self.server.tool()
                            async def query_todos(filter: Optional[Dict[str, Any]] = None, 
                                                 projection: Optional[Dict[str, Any]] = None, 
                                                 limit: int = 100, ctx: Optional[str] = None) -> str:
                                context = _create_context()
                                return await func(filter, projection, limit, ctx=context)
                            query_todos.__doc__ = docstring
                            return query_todos
                        
                        elif name == "update_todo":
                            @self.server.tool()
                            async def update_todo(todo_id: str, updates: dict) -> str:
                                ctx = _create_context()
                                return await func(todo_id, updates, ctx=ctx)
                            update_todo.__doc__ = docstring
                            return update_todo
                        
                        elif name == "delete_todo":
                            @self.server.tool()
                            async def delete_todo(todo_id: str) -> str:
                                ctx = _create_context()
                                return await func(todo_id, ctx=ctx)
                            delete_todo.__doc__ = docstring
                            return delete_todo
                        
                        elif name == "get_todo":
                            @self.server.tool()
                            async def get_todo(todo_id: str) -> str:
                                ctx = _create_context()
                                return await func(todo_id, ctx=ctx)
                            get_todo.__doc__ = docstring
                            return get_todo
                        
                        elif name == "mark_todo_complete":
                            @self.server.tool()
                            async def mark_todo_complete(todo_id: str, comment: Optional[str] = None) -> str:
                                ctx = _create_context()
                                return await func(todo_id, comment, ctx=ctx)
                            mark_todo_complete.__doc__ = docstring
                            return mark_todo_complete
                        
                        elif name == "list_todos_by_status":
                            @self.server.tool()
                            async def list_todos_by_status(status: str, limit: int = 100) -> str:
                                ctx = _create_context()
                                return await func(status, limit, ctx=ctx)
                            list_todos_by_status.__doc__ = docstring
                            return list_todos_by_status
                        
                        elif name == "search_todos":
                            @self.server.tool()
                            async def search_todos(query: str, fields: Optional[list] = None, 
                                                   limit: int = 100, ctx: Optional[str] = None) -> str:
                                context = _create_context()
                                return await func(query, fields, limit, ctx=context)
                            search_todos.__doc__ = docstring
                            return search_todos
                        
                        elif name == "list_project_todos":
                            @self.server.tool()
                            async def list_project_todos(project: str, limit: int = 5) -> str:
                                ctx = _create_context()
                                return await func(project, limit, ctx=ctx)
                            list_project_todos.__doc__ = docstring
                            return list_project_todos
                        
                        elif name == "add_lesson":
                            @self.server.tool()
                            async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None) -> str:
                                ctx = _create_context()
                                return await func(language, topic, lesson_learned, tags, ctx=ctx)
                            add_lesson.__doc__ = docstring
                            return add_lesson
                        
                        elif name == "get_lesson":
                            @self.server.tool()
                            async def get_lesson(lesson_id: str) -> str:
                                ctx = _create_context()
                                return await func(lesson_id, ctx=ctx)
                            get_lesson.__doc__ = docstring
                            return get_lesson
                        
                        elif name == "update_lesson":
                            @self.server.tool()
                            async def update_lesson(lesson_id: str, updates: dict) -> str:
                                ctx = _create_context()
                                return await func(lesson_id, updates, ctx=ctx)
                            update_lesson.__doc__ = docstring
                            return update_lesson
                        
                        elif name == "delete_lesson":
                            @self.server.tool()
                            async def delete_lesson(lesson_id: str) -> str:
                                ctx = _create_context()
                                return await func(lesson_id, ctx=ctx)
                            delete_lesson.__doc__ = docstring
                            return delete_lesson
                        
                        elif name == "search_lessons":
                            @self.server.tool()
                            async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 100) -> str:
                                ctx = _create_context()
                                return await func(query, fields, limit, ctx=ctx)
                            search_lessons.__doc__ = docstring
                            return search_lessons
                        
                        elif name == "grep_lessons":
                            @self.server.tool()
                            async def grep_lessons(pattern: str, limit: int = 20) -> str:
                                ctx = _create_context()
                                return await func(pattern, limit, ctx=ctx)
                            grep_lessons.__doc__ = docstring
                            return grep_lessons
                        
                        elif name == "list_lessons":
                            @self.server.tool()
                            async def list_lessons(limit: int = 100) -> str:
                                ctx = _create_context()
                                return await func(limit, ctx=ctx)
                            list_lessons.__doc__ = docstring
                            return list_lessons
                        
                        elif name == "query_todo_logs":
                            @self.server.tool()
                            async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                                                     page: int = 1, page_size: int = 20) -> str:
                                ctx = _create_context()
                                return await func(filter_type, project, page, page_size, ctx=ctx)
                            query_todo_logs.__doc__ = docstring
                            return query_todo_logs
                        
                        elif name == "list_projects":
                            @self.server.tool()
                            async def list_projects(include_details: bool = False, 
                                                   madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
                                ctx = _create_context()
                                return await func(include_details, madness_root, ctx=ctx)
                            list_projects.__doc__ = docstring
                            return list_projects
                        
                        elif name == "explain":
                            @self.server.tool()
                            async def explain(topic: str) -> str:
                                ctx = _create_context()
                                return await func(topic, ctx=ctx)
                            explain.__doc__ = docstring
                            return explain
                        
                        elif name == "add_explanation":
                            @self.server.tool()
                            async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system") -> str:
                                ctx = _create_context()
                                return await func(topic, content, kind, author, ctx=ctx)
                            add_explanation.__doc__ = docstring
                            return add_explanation
                        
                        elif name == "point_out_obvious":
                            @self.server.tool()
                            async def point_out_obvious(observation: str, sarcasm_level: int = 5) -> str:
                                ctx = _create_context()
                                return await func(observation, sarcasm_level, ctx=ctx)
                            point_out_obvious.__doc__ = docstring
                            return point_out_obvious
                        
                        elif name == "bring_your_own":
                            @self.server.tool()
                            async def bring_your_own(tool_name: str, code: str, runtime: str = "python",
                                                    timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                                                    persist: bool = False) -> str:
                                ctx = _create_context()
                                return await func(tool_name, code, runtime, timeout, args, persist, ctx=ctx)
                            bring_your_own.__doc__ = docstring
                            return bring_your_own
                    
                    return create_wrapper()
                
                make_tool(tool_name, tool_info["func"], tool_info["doc"])
    
    async def run(self):
        """Run the stdio server."""
        logger.info("Starting Omnispindle stdio MCP server with FastMCP")
        await self.server.run_stdio_async()


async def main():
    """Main entry point for stdio server."""
    server = OmniSpindleStdioServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
