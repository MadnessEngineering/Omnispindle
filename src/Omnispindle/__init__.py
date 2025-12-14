import asyncio
import inspect
import logging
import os
from typing import Callable, Dict, Any, Optional, Union, List
import json

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Response, status

# from .auth import get_current_user  # Removed - not used in current MCP servers
from .context import Context
from .middleware import ConnectionErrorsMiddleware, NoneTypeResponseMiddleware, EnhancedLoggingMiddleware
from .patches import apply_patches
from . import tools
from . import hybrid_tools
from .hybrid_tools import OmnispindleMode

# --- Initializations ---
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
    ],
    "hybrid_test": [
        "add_todo", "query_todos", "get_todo", "mark_todo_complete",
        "get_hybrid_status", "test_api_connectivity"
    ]
}


class Omnispindle:
    """Main Omnispindle server class for FastAPI."""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        logger.info("Omnispindle server class initialized.")

    def tool(self, name: Optional[str] = None) -> Callable:
        """A decorator to register a function as a tool."""
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            logger.info(f"Tool '{tool_name}' registered.")
            return func
        return decorator

    async def dispatch_tool(self, tool_name: str, params: Dict[str, Any], ctx: Context) -> Any:
        """Finds and executes the tool with the given name."""
        if tool_name not in self.tools:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found.")

        tool_func = self.tools[tool_name]

        # Add ctx to the params if the tool's signature includes it.
        sig = inspect.signature(tool_func)
        if 'ctx' in sig.parameters:
            params['ctx'] = ctx

        return await tool_func(**params)

    async def run_server(self) -> FastAPI:
        """Creates and configures the FastAPI application."""
        app = FastAPI(
            title="Omnispindle",
            description="A FastAPI server for managing todos and other tasks, with AI agent integration.",
            version="0.1.0",
        )

        app.add_middleware(ConnectionErrorsMiddleware)
        app.add_middleware(NoneTypeResponseMiddleware)
        app.add_middleware(EnhancedLoggingMiddleware, logger=logger)

        @app.get("/auth/logout", tags=["auth"])
        async def logout(response: Response):
            response.delete_cookie(key="ss-tok", httponly=True, samesite="strict", secure=True)
            return {"message": "Successfully logged out."}

        # @app.post("/tools/{tool_name}", tags=["tools"])  # Commented out - uses removed get_current_user
        # async def run_tool(tool_name: str, request: Request, user: dict = Depends(get_current_user)):
        #     try:
        #         params = await request.json()
        #     except Exception:
        #         params = {}
        #
        #     ctx = Context(user=user)
        #     result = await self.dispatch_tool(tool_name, params, ctx)
        #     return {"result": str(result) if not isinstance(result, (dict, list, str, int, float, bool, type(None))) else result}


        @app.get("/")
        def read_root():
            return {"message": "Omnispindle is running."}

        self._register_default_tools()
        return app

    def _register_default_tools(self):
        """Registers tools based on OMNISPINDLE_TOOL_LOADOUT and OMNISPINDLE_MODE env vars."""

        loadout = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full").lower()
        if loadout not in TOOL_LOADOUTS:
            logger.warning(f"Unknown loadout '{loadout}', using 'full'")
            loadout = "full"

        # Determine which tools module to use based on mode
        mode = os.getenv("OMNISPINDLE_MODE", "hybrid").lower()
        if mode in ["hybrid", "api", "auto"]:
            tools_module = hybrid_tools
            logger.info(f"Using hybrid/API tools module in '{mode}' mode")
        else:
            tools_module = tools
            logger.info(f"Using local tools module in '{mode}' mode")

        enabled = TOOL_LOADOUTS[loadout]
        logger.info(f"Loading '{loadout}' loadout: {enabled}")

        # Tool registry - keeps AI docstrings minimal
        tool_registry = {
            "add_todo": (tools.add_todo, "Creates a task in the specified project with the given priority and target agent. Returns a compact representation of the created todo with an ID for reference."),
            "query_todos": (tools.query_todos, "Query todos with flexible filtering options. Searches the todo database using MongoDB-style query filters and projections."),
            "update_todo": (tools.update_todo, "Update a todo with the provided changes. Common fields to update: description, priority, status, metadata."),
            "delete_todo": (tools.delete_todo, "Delete a todo by its ID."),
            "get_todo": (tools.get_todo, "Get a specific todo by ID."),
            "mark_todo_complete": (tools.mark_todo_complete, "Mark a todo as completed. Calculates the duration from creation to completion."),
            "list_todos_by_status": (tools.list_todos_by_status, "List todos filtered by status ('initial', 'pending', 'completed'). Results are formatted for efficiency with truncated descriptions."),
            "search_todos": (tools.search_todos, "Search todos with text search capabilities across specified fields. Special format: \"project:ProjectName\" to search by project."),
            "list_project_todos": (tools.list_project_todos, "List recent active todos for a specific project."),
            "add_lesson": (tools.add_lesson, "Add a new lesson learned to the knowledge base."),
            "get_lesson": (tools.get_lesson, "Get a specific lesson by ID."),
            "update_lesson": (tools.update_lesson, "Update an existing lesson by ID."),
            "delete_lesson": (tools.delete_lesson, "Delete a lesson by ID."),
            "search_lessons": (tools.search_lessons, "Search lessons with text search capabilities."),
            "grep_lessons": (tools.grep_lessons, "Search lessons with grep-style pattern matching across topic and content."),
            "list_lessons": (tools.list_lessons, "List all lessons, sorted by creation date."),
            "query_todo_logs": (tools.query_todo_logs, "Query todo logs with filtering options."),
            "list_projects": (tools.list_projects, "List all valid projects from the centralized project management system. `include_details`: False (names only), True (full metadata), \"filemanager\" (for UI)."),
            "explain": (tools.explain_tool, "Provides a detailed explanation for a project or concept. For projects, it dynamically generates a summary with recent activity."),
            "add_explanation": (tools.add_explanation, "Add a new static explanation to the knowledge base."),
            "point_out_obvious": (tools.point_out_obvious, "Points out something obvious to the human user with humor."),
            "bring_your_own": (tools.bring_your_own, "Temporarily hijack the MCP server to run custom tool code.")
        }

        # Register enabled tools
        for tool_name in enabled:
            if tool_name in tool_registry:
                func, doc = tool_registry[tool_name]

                # Create closure to capture func properly
                def make_wrapper(f, docstring):
                    async def wrapper(*args, ctx: Optional[Context] = None, **kwargs):
                        return await f(*args, ctx=ctx, **kwargs)
                    wrapper.__doc__ = docstring
                    return wrapper

                self.tool(tool_name)(make_wrapper(func, doc))

# --- Server Instantiation ---
server = Omnispindle()
app = asyncio.run(server.run_server())
