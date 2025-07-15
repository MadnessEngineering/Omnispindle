import asyncio
import inspect
import logging
from typing import Callable, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Response, status

from .auth import get_current_user, Settings, CurrentUser
from .context import Context
from .middleware import ConnectionErrorsMiddleware, NoneTypeResponseMiddleware, EnhancedLoggingMiddleware
from .patches import apply_patches
from .sse_handler import sse_handler
from .tools import (
    add_todo,
    query_todos,
    update_todo,
    delete_todo,
    get_todo,
    mark_todo_complete,
    list_todos_by_status,
    add_lesson,
    get_lesson,
    update_lesson,
    delete_lesson,
    search_todos,
    grep_lessons,
    list_project_todos,
    query_todo_logs,
    list_projects,
    explain_tool as explain,
    add_explanation,
    list_lessons,
    search_lessons,
)

# --- Initializations ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
apply_patches()
load_dotenv()


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

        @app.get("/tools", tags=["tools"])
        async def list_tools():
            """
            Returns a list of available tools, their documentation, and authentication info.
            """
            auth_config = Settings()
            tools_info = {}
            for name, func in self.tools.items():
                tools_info[name] = {
                    "doc": inspect.getdoc(func),
                    "signature": str(inspect.signature(func)),
                }
            
            auth_info = {
                "enabled": auth_config.enabled,
                "testing": auth_config.testing,
                "instructions": "Clients can authenticate via a 'ss_tok' cookie or an 'Authorization: Bearer <token>' header. For testing environments, a token of 'let-me-in' is accepted."
            }

            return {"tools": tools_info, "auth_info": auth_info}

        @app.get("/auth/testing-login", tags=["auth"], include_in_schema=False)
        async def testing_login(response: Response):
            auth_config = Settings()
            if not auth_config.testing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not available.")
            response.set_cookie(key="ss-tok", value="let-me-in", httponly=True, samesite="strict", secure=True)
            return {"message": "Test cookie set."}

        @app.get("/auth/logout", tags=["auth"])
        async def logout(response: Response):
            response.delete_cookie(key="ss-tok", httponly=True, samesite="strict", secure=True)
            return {"message": "Successfully logged out."}

        @app.post("/tools/{tool_name}", tags=["tools"])
        async def run_tool(tool_name: str, request: Request, user: CurrentUser = Depends(get_current_user)):
            try:
                params = await request.json()
            except Exception:
                params = {}

            ctx = Context(user=user)
            result = await self.dispatch_tool(tool_name, params, ctx)
            return {"result": str(result) if not isinstance(result, (dict, list, str, int, float, bool, type(None))) else result}

        @app.get("/sse")
        async def sse_endpoint(request: Request):
            async def event_generator(req: Request):
                while not await req.is_disconnected():
                    yield {"event": "ping", "data": "ping"}
                    await asyncio.sleep(15)
            return sse_handler.sse_response(request, event_generator)

        @app.get("/sse_authenticated")
        async def sse_authenticated_endpoint(request: Request, user: CurrentUser = Depends(get_current_user)):
            user_name = user.name
            logger.info(f"User {user_name} connected to authenticated SSE stream.")
            async def user_specific_generator(req: Request):
                while not await req.is_disconnected():
                    yield {"event": "user_ping", "data": f"ping for {user_name}"}
                    await asyncio.sleep(15)
            return sse_handler.sse_response(request, user_specific_generator)

        @app.get("/")
        def read_root():
            return {"message": "Omnispindle is running."}

        self._register_default_tools()
        return app

    def _register_default_tools(self):
        """Registers all the functions from tools.py."""
        tools_to_register = [
            add_todo, query_todos, update_todo, delete_todo, get_todo, mark_todo_complete,
            list_todos_by_status, add_lesson, get_lesson, update_lesson, delete_lesson,
            search_todos, grep_lessons, list_project_todos, query_todo_logs, list_projects,
            explain, add_explanation, list_lessons, search_lessons
        ]
        for tool_func in tools_to_register:
            self.tool(name=tool_func.__name__)(tool_func)

# --- Server Instantiation ---
server = Omnispindle()
app = asyncio.run(server.run_server())
