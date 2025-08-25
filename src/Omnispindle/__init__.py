import asyncio
import inspect
import logging
from typing import Callable, Dict, Any, Optional, Union
import json

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Response, status

from .auth import get_current_user
from .context import Context
from .middleware import ConnectionErrorsMiddleware, NoneTypeResponseMiddleware, EnhancedLoggingMiddleware
from .patches import apply_patches
from .sse_handler import sse_handler
from . import tools

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

        @app.get("/sse")
        async def sse_endpoint(request: Request):
            async def event_generator(req: Request):
                # First, send the tool information as a handshake
                tools_info = {}
                for name, func in self.tools.items():
                    tools_info[name] = {
                        "doc": inspect.getdoc(func),
                        "signature": str(inspect.signature(func)),
                    }
                yield {
                    "event": "tools_info",
                    "data": json.dumps(tools_info)
                }

                # Then, enter the ping loop
                while not await req.is_disconnected():
                    yield {"event": "ping", "data": "ping"}
                    await asyncio.sleep(15)
            return sse_handler.sse_response(request, event_generator)

        @app.get("/sse_authenticated")
        async def sse_authenticated_endpoint(request: Request, user: dict = Depends(get_current_user)):
            user_name = user.get("sub", "unknown_user") # Use .get("sub") to get user ID
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

        @self.tool()
        async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None, ctx: Optional[Context] = None) -> str:
            """
            Adds a new todo item.

            description: The task description.
            project: The project the task belongs to.
            priority: The priority of the task (Low, Medium, High).
            target_agent: The agent the task is for.
            metadata: Optional metadata for the task.
            """
            return await tools.add_todo(description, project, priority, target_agent, metadata, ctx)

        @self.tool()
        async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
            """
            Queries for todo items.

            filter: a dict of mongo query filters
            projection: a dict of mongo query projections
            limit: max number of results
            """
            return await tools.query_todos(filter, projection, limit, ctx)

        @self.tool()
        async def update_todo(todo_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
            """
            Updates a todo item.

            todo_id: The ID of the todo to update.
            updates: A dictionary of fields to update.
            """
            return await tools.update_todo(todo_id, updates, ctx)

        @self.tool()
        async def delete_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
            """
            Deletes a todo item.

            todo_id: The ID of the todo to delete.
            """
            return await tools.delete_todo(todo_id, ctx)

        @self.tool()
        async def get_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
            """
            Gets a single todo item.

            todo_id: The ID of the todo to get.
            """
            return await tools.get_todo(todo_id, ctx)

        @self.tool()
        async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: Optional[Context] = None) -> str:
            """
            Marks a todo as complete.

            todo_id: The ID of the todo to mark as complete.
            comment: An optional comment.
            """
            return await tools.mark_todo_complete(todo_id, comment, ctx)

        @self.tool()
        async def list_todos_by_status(status: str, limit: int = 100, ctx: Optional[Context] = None) -> str:
            """
            Lists todos by status.

            status: The status to filter by (e.g., "pending", "completed").
            limit: The maximum number of todos to return.
            """
            return await tools.list_todos_by_status(status, limit, ctx)

        @self.tool()
        async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None, ctx: Optional[Context] = None) -> str:
            """
            Adds a new lesson to the knowledge base.

            language: The programming language or technology.
            topic: A brief summary of the lesson.
            lesson_learned: The full content of the lesson.
            tags: Optional list of tags.
            """
            return await tools.add_lesson(language, topic, lesson_learned, tags, ctx)

        @self.tool()
        async def get_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
            """
            Gets a single lesson.

            lesson_id: The ID of the lesson to get.
            """
            return await tools.get_lesson(lesson_id, ctx)

        @self.tool()
        async def update_lesson(lesson_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
            """
            Updates a lesson.

            lesson_id: The ID of the lesson to update.
            updates: A dictionary of fields to update.
            """
            return await tools.update_lesson(lesson_id, updates, ctx)

        @self.tool()
        async def delete_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
            """
            Deletes a lesson.

            lesson_id: The ID of the lesson to delete.
            """
            return await tools.delete_lesson(lesson_id, ctx)

        @self.tool()
        async def search_todos(query: str, fields: Optional[list] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
            """
            Searches for todos.

            query: The search query.
            fields: Optional list of fields to search.
            limit: The maximum number of results to return.
            """
            return await tools.search_todos(query, fields, limit, ctx)

        @self.tool()
        async def grep_lessons(pattern: str, limit: int = 20, ctx: Optional[Context] = None) -> str:
            """
            Searches lessons with a regex pattern.

            pattern: The regex pattern to search for.
            limit: The maximum number of results to return.
            """
            return await tools.grep_lessons(pattern, limit, ctx)

        @self.tool()
        async def list_project_todos(project: str, limit: int = 5, ctx: Optional[Context] = None) -> str:
            """
            Lists recent todos for a project.

            project: The project to list todos for.
            limit: The maximum number of todos to return.
            """
            return await tools.list_project_todos(project, limit, ctx)

        @self.tool()
        async def query_todo_logs(filter_type: str = 'all', project: str = 'all', page: int = 1, page_size: int = 20, ctx: Optional[Context] = None) -> str:
            """
            Queries todo logs.

            filter_type: The type of filter to apply.
            project: The project to filter by.
            page: The page number to return.
            page_size: The number of results per page.
            """
            return await tools.query_todo_logs(filter_type, project, page, page_size, ctx)

        @self.tool()
        async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive", ctx: Optional[Context] = None) -> str:
            """
            Lists all projects.

            include_details: Whether to include detailed project information.
            madness_root: The root directory of the madness interactive project.
            """
            return await tools.list_projects(include_details, madness_root, ctx)

        @self.tool()
        async def explain(topic: str, brief: bool = False, ctx: Optional[Context] = None) -> str:
            """
            Explains a topic.

            topic: The topic to explain.
            brief: Whether to return a brief explanation.
            """
            return await tools.explain_tool(topic, brief, ctx)

        @self.tool()
        async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Optional[Context] = None) -> str:
            """
            Adds an explanation to the knowledge base.

            topic: The topic of the explanation.
            content: The content of the explanation.
            kind: The kind of explanation.
            author: The author of the explanation.
            """
            return await tools.add_explanation(topic, content, kind, author, ctx)

        @self.tool()
        async def list_lessons(limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
            """
            Lists all lessons.

            limit: The maximum number of lessons to return.
            brief: Whether to return a brief listing.
            """
            return await tools.list_lessons(limit, brief, ctx)

        @self.tool()
        async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
            """
            Searches for lessons.

            query: The search query.
            fields: Optional list of fields to search.
            limit: The maximum number of results to return.
            brief: Whether to return a brief listing.
            """
            return await tools.search_lessons(query, fields, limit, brief, ctx)

        @self.tool()
        async def point_out_obvious(observation: str, sarcasm_level: int = 5, ctx: Optional[Context] = None) -> str:
            """
            Points out something obvious to the human user with humor.

            observation: The obvious thing to point out.
            sarcasm_level: Scale from 1-10 (1=gentle, 10=maximum sass).
            """
            return await tools.point_out_obvious(observation, sarcasm_level, ctx)

        @self.tool()
        async def bring_your_own(tool_name: str, code: str, runtime: str = "python", 
                                timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                                persist: bool = False, ctx: Optional[Context] = None) -> str:
            """
            Temporarily hijack the MCP server to run custom tool code.

            tool_name: Name for the temporary tool.
            code: The code to execute (must define a main function).
            runtime: Runtime environment (python, javascript, bash).
            timeout: Maximum execution time in seconds.
            args: Arguments to pass to the custom tool.
            persist: Whether to save this tool for future use.
            """
            return await tools.bring_your_own(tool_name, code, runtime, timeout, args, persist, ctx)

        tools_to_register = []
        for tool_func in tools_to_register:
            self.tool(name=tool_func.__name__)(tool_func)

# --- Server Instantiation ---
server = Omnispindle()
app = asyncio.run(server.run_server())
