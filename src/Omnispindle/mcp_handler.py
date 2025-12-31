
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
        if method == "initialize":
            # Return server capabilities for MCP protocol initialization
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "Omnispindle",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": {},
                            "prompts": {},
                            "resources": {}
                        }
                    }
                }
            )
        elif method == "tools/list":
            # Return list of available tools
            tools = [
                {
                    "name": "add_todo",
                    "description": "Create todo. Returns ID and project stats.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Task description"},
                            "project": {"type": "string", "description": "Project name"},
                            "priority": {"type": "string", "description": "Critical|High|Medium|Low"},
                            "target_agent": {"type": "string", "description": "user|AI name"},
                            "notes": {"type": "string", "description": "User-facing notes/context (optional)"},
                            "ticket": {"type": "string", "description": "External ticket reference (optional)"},
                            "metadata": {"type": "object", "description": "{key: value} pairs"}
                        },
                        "required": ["description", "project"]
                    }
                },
                {
                    "name": "query_todos",
                    "description": "Query todos",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "object", "description": "{project: 'name', status: 'pending'|'completed'}"},
                            "limit": {"type": "number"}
                        }
                    }
                },
                {
                    "name": "get_todo",
                    "description": "Get todo by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string"}
                        },
                        "required": ["todo_id"]
                    }
                },
                {
                    "name": "mark_todo_complete",
                    "description": "Complete todo",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string"},
                            "comment": {"type": "string"}
                        },
                        "required": ["todo_id"]
                    }
                },
                {
                    "name": "add_lesson",
                    "description": "Add lesson",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "language": {"type": "string", "description": "python|javascript|rust|etc"},
                            "topic": {"type": "string"},
                            "lesson_learned": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["language", "topic", "lesson_learned"]
                    }
                },
                {
                    "name": "get_lesson",
                    "description": "Get lesson by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "lesson_id": {"type": "string"}
                        },
                        "required": ["lesson_id"]
                    }
                },
                {
                    "name": "update_lesson",
                    "description": "Update lesson",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "lesson_id": {"type": "string"},
                            "updates": {"type": "object"}
                        },
                        "required": ["lesson_id", "updates"]
                    }
                },
                {
                    "name": "delete_lesson",
                    "description": "Delete lesson",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "lesson_id": {"type": "string"}
                        },
                        "required": ["lesson_id"]
                    }
                },
                {
                    "name": "search_lessons",
                    "description": "Text search lessons",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "fields": {"type": "array", "items": {"type": "string"}, "description": "['topic','lesson_learned','tags']"},
                            "limit": {"type": "number"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "grep_lessons",
                    "description": "Pattern match lessons",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "regex pattern"},
                            "limit": {"type": "number"}
                        },
                        "required": ["pattern"]
                    }
                },
                {
                    "name": "inventorium_sessions_list",
                    "description": "List chat sessions",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "limit": {"type": "number", "description": "default 50"}
                        }
                    }
                },
                {
                    "name": "inventorium_sessions_get",
                    "description": "Get session by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"}
                        },
                        "required": ["session_id"]
                    }
                },
                {
                    "name": "inventorium_sessions_create",
                    "description": "Create session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "title": {"type": "string"},
                            "initial_prompt": {"type": "string"},
                            "agentic_tool": {"type": "string", "description": "claude-code|codex|gemini|opencode"}
                        },
                        "required": ["project"]
                    }
                },
                {
                    "name": "inventorium_sessions_spawn",
                    "description": "Spawn child session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "parent_session_id": {"type": "string"},
                            "prompt": {"type": "string"},
                            "todo_id": {"type": "string"},
                            "title": {"type": "string"}
                        },
                        "required": ["parent_session_id", "prompt"]
                    }
                },
                {
                    "name": "inventorium_todos_link_session",
                    "description": "Link todo to session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "string"},
                            "session_id": {"type": "string"}
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
                "add_lesson": tools.add_lesson,
                "get_lesson": tools.get_lesson,
                "update_lesson": tools.update_lesson,
                "delete_lesson": tools.delete_lesson,
                "search_lessons": tools.search_lessons,
                "grep_lessons": tools.grep_lessons,
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
