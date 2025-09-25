
import asyncio
import json
import logging
from typing import Dict, Any, Callable, Coroutine

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


async def mcp_handler(request: Request, get_current_user: Callable[[], Coroutine[Any, Any, Any]]) -> JSONResponse:
    """
    Handle MCP JSON-RPC requests over HTTP
    """
    try:
        # Get user from authentication (passed as lambda that returns the user dict)
        user = get_current_user()
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
            tool_arguments = params.get("arguments", {})

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
                "list_projects": tools.list_projects
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
