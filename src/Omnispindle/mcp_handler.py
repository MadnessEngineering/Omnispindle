
import json
import logging
from typing import Dict, Any, Callable, Coroutine

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


async def mcp_handler(request: Request, get_current_user: Callable[[], Coroutine[Any, Any, Any]]) -> JSONResponse:
    """
    Handle MCP JSON-RPC requests over HTTP
    """
    try:
        # Get user from authentication (passed as lambda that returns the user dict)
        # get_current_user is provided by FastAPI dependency; it may be a simple value or coroutine.
        user = get_current_user()
        if asyncio.iscoroutine(user):
            user = await user
        if not user:
            return JSONResponse(
                content={"error": "Unauthorized"},
                status_code=401
            )

        # Parse JSON-RPC request
        try:
            rpc_request = await request.json()
        except json.JSONDecodeError as e:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error", "data": str(e)}
                },
                status_code=400
            )

        # Validate JSON-RPC format
        if not isinstance(rpc_request, dict) or "jsonrpc" not in rpc_request:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_request.get("id") if isinstance(rpc_request, dict) else None,
                    "error": {"code": -32600, "message": "Invalid Request"}
                },
                status_code=400
            )

        request_id = rpc_request.get("id", 1)
        method = rpc_request.get("method")
        params = rpc_request.get("params", {})

        logger.info(f"🔗 MCP Request: {method} from user {user.get('email', 'unknown')}")

        # Handle different MCP methods
        if method == "tools/list":
            # Return list of available tools
            tools = [
                {
                    "name": "add_todo",
                    "description": "Create a new todo item",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Todo description"},
                            "project": {"type": "string", "description": "Project name"},
                            "priority": {"type": "string", "description": "Priority level"}
                        },
                        "required": ["description", "project"]
                    }
                },
                {
                    "name": "query_todos",
                    "description": "Query todos with filters",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "object", "description": "Filter conditions"},
                            "limit": {"type": "number", "description": "Result limit"}
                        }
                    }
                },
                {
                    "name": "get_todo",
                    "description": "Get a specific todo by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string", "description": "Todo ID"}
                        },
                        "required": ["todo_id"]
                    }
                },
                {
                    "name": "mark_todo_complete",
                    "description": "Mark a todo as completed",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string", "description": "Todo ID"},
                            "comment": {"type": "string", "description": "Completion comment"}
                        },
                        "required": ["todo_id"]
                    }
                },
                {
                    "name": "inventorium_sessions_list",
                    "description": "List chat sessions for the authenticated user",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project slug to filter"},
                            "limit": {"type": "number", "description": "Maximum results (default 50)"}
                        }
                    }
                },
                {
                    "name": "inventorium_sessions_get",
                    "description": "Load a specific chat session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Chat session UUID"}
                        },
                        "required": ["session_id"]
                    }
                },
                {
                    "name": "inventorium_sessions_create",
                    "description": "Create a chat session for a project",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project slug"},
                            "title": {"type": "string", "description": "Optional session title"},
                            "initial_prompt": {"type": "string", "description": "Seed prompt"},
                            "agentic_tool": {"type": "string", "description": "claude-code|codex|gemini|opencode"}
                        },
                        "required": ["project"]
                    }
                },
                {
                    "name": "inventorium_sessions_spawn",
                    "description": "Spawn a child session from an existing session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "parent_session_id": {"type": "string", "description": "Parent session UUID"},
                            "prompt": {"type": "string", "description": "Instructions for the child session"},
                            "todo_id": {"type": "string", "description": "Optional todo to link"},
                            "title": {"type": "string", "description": "Optional child session title"}
                        },
                        "required": ["parent_session_id", "prompt"]
                    }
                },
                {
                    "name": "inventorium_todos_link_session",
                    "description": "Link a todo to a chat session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string", "description": "Todo identifier"},
                            "session_id": {"type": "string", "description": "Chat session UUID"}
                        },
                        "required": ["todo_id", "session_id"]
                    }
                }
            ]

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            })

        elif method == "tools/call":
            # Handle tool calls
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {}) or {}

            # Never allow client-provided ctx to collide with server ctx
            if "ctx" in tool_arguments:
                logger.warning("Stripping client-provided ctx from tool arguments to avoid conflicts")
                tool_arguments.pop("ctx", None)

            # Import tools module to access the actual tool functions
            from . import tools
            from .context import Context

            # Create context for the user
            ctx = Context(user=user)

            # Map tool names to actual functions
            tool_functions = {
                "add_todo": tools.add_todo,
                "query_todos": tools.query_todos,
                "get_todo": tools.get_todo,
                "mark_todo_complete": tools.mark_todo_complete,
                "update_todo": tools.update_todo,
                "delete_todo": tools.delete_todo,
                "list_project_todos": tools.list_project_todos,
                "search_todos": tools.search_todos,
                "list_projects": tools.list_projects,
                "inventorium_sessions_list": tools.inventorium_sessions_list,
                "inventorium_sessions_get": tools.inventorium_sessions_get,
                "inventorium_sessions_create": tools.inventorium_sessions_create,
                "inventorium_sessions_spawn": tools.inventorium_sessions_spawn,
                "inventorium_todos_link_session": tools.inventorium_todos_link_session
            }

            if tool_name not in tool_functions:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"}
                })

            try:
                # Call the tool function with context
                tool_func = tool_functions[tool_name]
                result = await tool_func(**tool_arguments, ctx=ctx)

                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
                })

            except Exception as tool_error:
                logger.error(f"Tool execution error: {tool_error}")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": "Internal error", "data": str(tool_error)}
                })

        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

    except Exception as e:
        logger.error(f"MCP handler error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)}
            },
            status_code=500
        ) 
