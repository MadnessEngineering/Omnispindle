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


class OmniSpindleStdioServer:
    """Stdio-based MCP server for Omnispindle tools using FastMCP."""
    
    def __init__(self):
        self.server = FastMCP(name="omnispindle")
        self._register_tools()
        logger.info("OmniSpindleStdioServer initialized with FastMCP")
    
    def _register_tools(self):
        """Register all tools with the FastMCP server."""
        
        @self.server.tool()
        async def add_todo(description: str, project: str, priority: str = "Medium", 
                          target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None) -> str:
            """
            Creates a task in the specified project with the given priority and target agent.
            
            Args:
                description: The task description
                project: The project the task belongs to
                priority: The priority of the task (Low, Medium, High)
                target_agent: The agent the task is for
                metadata: Optional metadata for the task
            """
            ctx = Context(user=None)  # No user auth in stdio mode
            return await tools.add_todo(description, project, priority, target_agent, metadata, ctx)

        @self.server.tool()
        async def query_todos(filter: Optional[Dict[str, Any]] = None, 
                             projection: Optional[Dict[str, Any]] = None, limit: int = 100) -> str:
            """
            Query todos with flexible filtering options.
            
            Args:
                filter: MongoDB query filters
                projection: MongoDB query projections
                limit: Maximum number of results
            """
            ctx = Context(user=None)
            return await tools.query_todos(filter, projection, limit, ctx)

        @self.server.tool()
        async def update_todo(todo_id: str, updates: dict) -> str:
            """
            Update a todo with the provided changes.
            
            Args:
                todo_id: The ID of the todo to update
                updates: Dictionary of fields to update
            """
            ctx = Context(user=None)
            return await tools.update_todo(todo_id, updates, ctx)

        @self.server.tool()
        async def delete_todo(todo_id: str) -> str:
            """
            Delete a todo item by its ID.
            
            Args:
                todo_id: The ID of the todo to delete
            """
            ctx = Context(user=None)
            return await tools.delete_todo(todo_id, ctx)

        @self.server.tool()
        async def get_todo(todo_id: str) -> str:
            """
            Get a specific todo item by its ID.
            
            Args:
                todo_id: The ID of the todo to get
            """
            ctx = Context(user=None)
            return await tools.get_todo(todo_id, ctx)

        @self.server.tool()
        async def mark_todo_complete(todo_id: str, comment: Optional[str] = None) -> str:
            """
            Mark a todo as completed.
            
            Args:
                todo_id: The ID of the todo to mark as complete
                comment: Optional completion comment
            """
            ctx = Context(user=None)
            return await tools.mark_todo_complete(todo_id, comment, ctx)

        @self.server.tool()
        async def list_todos_by_status(status: str, limit: int = 100) -> str:
            """
            List todos filtered by their status.
            
            Args:
                status: The status to filter by (pending, completed, initial)
                limit: Maximum number of todos to return
            """
            ctx = Context(user=None)
            return await tools.list_todos_by_status(status, limit, ctx)

        @self.server.tool()
        async def search_todos(query: str, fields: Optional[list] = None, limit: int = 100) -> str:
            """
            Search todos with text search capabilities.
            
            Args:
                query: The search query
                fields: Fields to search
                limit: Maximum number of results
            """
            ctx = Context(user=None)
            return await tools.search_todos(query, fields, limit, ctx)

        @self.server.tool()
        async def list_project_todos(project: str, limit: int = 5) -> str:
            """
            List recent active todos for a specific project.
            
            Args:
                project: The project to list todos for
                limit: Maximum number of todos to return
            """
            ctx = Context(user=None)
            return await tools.list_project_todos(project, limit, ctx)

        @self.server.tool()
        async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None) -> str:
            """
            Add a new lesson to the knowledge base.
            
            Args:
                language: The programming language or technology
                topic: A brief summary of the lesson
                lesson_learned: The full content of the lesson
                tags: Optional list of tags
            """
            ctx = Context(user=None)
            return await tools.add_lesson(language, topic, lesson_learned, tags, ctx)

        @self.server.tool()
        async def get_lesson(lesson_id: str) -> str:
            """
            Get a specific lesson by its ID.
            
            Args:
                lesson_id: The ID of the lesson to get
            """
            ctx = Context(user=None)
            return await tools.get_lesson(lesson_id, ctx)

        @self.server.tool()
        async def update_lesson(lesson_id: str, updates: dict) -> str:
            """
            Update an existing lesson.
            
            Args:
                lesson_id: The ID of the lesson to update
                updates: Dictionary of fields to update
            """
            ctx = Context(user=None)
            return await tools.update_lesson(lesson_id, updates, ctx)

        @self.server.tool()
        async def delete_lesson(lesson_id: str) -> str:
            """
            Delete a lesson by its ID.
            
            Args:
                lesson_id: The ID of the lesson to delete
            """
            ctx = Context(user=None)
            return await tools.delete_lesson(lesson_id, ctx)

        @self.server.tool()
        async def search_lessons(query: str, fields: Optional[list] = None, 
                                limit: int = 100, brief: bool = False) -> str:
            """
            Search lessons with text search capabilities.
            
            Args:
                query: The search query
                fields: Fields to search
                limit: Maximum number of results
                brief: Whether to return brief results
            """
            ctx = Context(user=None)
            return await tools.search_lessons(query, fields, limit, brief, ctx)

        @self.server.tool()
        async def grep_lessons(pattern: str, limit: int = 20) -> str:
            """
            Search lessons with grep-style pattern matching.
            
            Args:
                pattern: The regex pattern to search for
                limit: Maximum number of results
            """
            ctx = Context(user=None)
            return await tools.grep_lessons(pattern, limit, ctx)

        @self.server.tool()
        async def list_lessons(limit: int = 100, brief: bool = False) -> str:
            """
            List all lessons, sorted by creation date.
            
            Args:
                limit: Maximum number of lessons to return
                brief: Whether to return brief results
            """
            ctx = Context(user=None)
            return await tools.list_lessons(limit, brief, ctx)

        @self.server.tool()
        async def list_projects(include_details: bool = False, 
                               madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
            """
            List all valid projects.
            
            Args:
                include_details: Whether to include detailed project information
                madness_root: The root directory of the madness interactive project
            """
            ctx = Context(user=None)
            return await tools.list_projects(include_details, madness_root, ctx)

        @self.server.tool()
        async def explain(topic: str, brief: bool = False) -> str:
            """
            Provides a detailed explanation for a project or concept.
            
            Args:
                topic: The topic to explain
                brief: Whether to return a brief explanation
            """
            ctx = Context(user=None)
            return await tools.explain_tool(topic, brief, ctx)

        @self.server.tool()
        async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system") -> str:
            """
            Add an explanation to the knowledge base.
            
            Args:
                topic: The topic of the explanation
                content: The content of the explanation
                kind: The kind of explanation
                author: The author of the explanation
            """
            ctx = Context(user=None)
            return await tools.add_explanation(topic, content, kind, author, ctx)

        @self.server.tool()
        async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                                 page: int = 1, page_size: int = 20) -> str:
            """
            Query the todo logs with filtering and pagination.
            
            Args:
                filter_type: The type of filter to apply
                project: The project to filter by
                page: The page number to return
                page_size: The number of results per page
            """
            ctx = Context(user=None)
            return await tools.query_todo_logs(filter_type, project, page, page_size, ctx)
        
        @self.server.tool()
        async def point_out_obvious(observation: str, sarcasm_level: int = 5) -> str:
            """
            Points out something obvious to the human user with varying levels of humor.
            Perfect for when the AI needs to highlight the blindingly obvious.
            
            Args:
                observation: The obvious thing to point out
                sarcasm_level: Scale from 1-10 (1=gentle reminder, 10=maximum sass)
            
            Returns:
                A response highlighting the obvious with appropriate commentary
            """
            ctx = Context(user=None)
            return await tools.point_out_obvious(observation, sarcasm_level, ctx)
        
        @self.server.tool()
        async def bring_your_own(tool_name: str, code: str, runtime: str = "python",
                                timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                                persist: bool = False) -> str:
            """
            Temporarily hijack the MCP server to run custom tool code.
            This allows models to define and execute their own tools on the fly.
            
            Args:
                tool_name: Name for the temporary tool
                code: The code to execute (must define a 'main' function)
                runtime: Runtime environment (python, javascript, bash)
                timeout: Maximum execution time in seconds
                args: Arguments to pass to the custom tool
                persist: Whether to save this tool for future use
            
            Returns:
                The result of executing the custom tool
            
            Security Note: This is intentionally powerful. Use with caution.
            """
            ctx = Context(user=None)
            return await tools.bring_your_own(tool_name, code, runtime, timeout, args, persist, ctx)
    
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
