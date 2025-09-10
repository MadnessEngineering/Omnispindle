import asyncio
import inspect
import logging
import os
from typing import Callable, Dict, Any, Optional, Union, List
import json

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Response, status

from .auth import get_current_user
from .context import Context
from .middleware import ConnectionErrorsMiddleware, NoneTypeResponseMiddleware, EnhancedLoggingMiddleware
from .patches import apply_patches
from . import tools
from . import hybrid_tools
from .hybrid_tools import OmnispindleMode
from .documentation_manager import get_tool_doc

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

        @app.post("/tools/{tool_name}", tags=["tools"])
        async def run_tool(tool_name: str, request: Request, user: dict = Depends(get_current_user)):
            try:
                params = await request.json()
            except Exception:
                params = {}

            ctx = Context(user=user)
            result = await self.dispatch_tool(tool_name, params, ctx)
            return {"result": str(result) if not isinstance(result, (dict, list, str, int, float, bool, type(None))) else result}


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

        # Tool registry - uses loadout-aware documentation
        tool_registry = {
            "add_todo": (tools_module.add_todo, get_tool_doc("add_todo")),
            "query_todos": (tools_module.query_todos, get_tool_doc("query_todos")),
            "update_todo": (tools_module.update_todo, get_tool_doc("update_todo")),
            "delete_todo": (tools_module.delete_todo, get_tool_doc("delete_todo")),
            "get_todo": (tools_module.get_todo, get_tool_doc("get_todo")),
            "mark_todo_complete": (tools_module.mark_todo_complete, get_tool_doc("mark_todo_complete")),
            "list_todos_by_status": (tools_module.list_todos_by_status, get_tool_doc("list_todos_by_status")),
            "search_todos": (tools_module.search_todos, get_tool_doc("search_todos")),
            "list_project_todos": (tools_module.list_project_todos, get_tool_doc("list_project_todos")),
            "add_lesson": (tools_module.add_lesson, get_tool_doc("add_lesson")),
            "get_lesson": (tools_module.get_lesson, get_tool_doc("get_lesson")),
            "update_lesson": (tools_module.update_lesson, get_tool_doc("update_lesson")),
            "delete_lesson": (tools_module.delete_lesson, get_tool_doc("delete_lesson")),
            "search_lessons": (tools_module.search_lessons, get_tool_doc("search_lessons")),
            "grep_lessons": (tools_module.grep_lessons, get_tool_doc("grep_lessons")),
            "list_lessons": (tools_module.list_lessons, get_tool_doc("list_lessons")),
            "query_todo_logs": (tools_module.query_todo_logs, get_tool_doc("query_todo_logs")),
            "list_projects": (tools_module.list_projects, get_tool_doc("list_projects")),
            "explain": (tools_module.explain_tool, get_tool_doc("explain")),
            "add_explanation": (tools_module.add_explanation, get_tool_doc("add_explanation")),
            "point_out_obvious": (tools_module.point_out_obvious, get_tool_doc("point_out_obvious")),
            "bring_your_own": (tools_module.bring_your_own, get_tool_doc("bring_your_own")),
            # Hybrid-specific tools
            "get_hybrid_status": (hybrid_tools.get_hybrid_status, "Get current hybrid mode status and performance statistics."),
            "test_api_connectivity": (hybrid_tools.test_api_connectivity, "Test API connectivity and response times.")
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
