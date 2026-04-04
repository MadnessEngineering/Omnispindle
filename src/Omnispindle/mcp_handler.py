
import json
import logging
import os
from typing import Dict, Any, Callable, Coroutine

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from .tool_loadouts import get_loadout

logger = logging.getLogger(__name__)


# Centralized tool schemas - single source of truth for all MCP tools
TOOL_SCHEMAS = {
    "add_todo": {
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
    "query_todos": {
        "name": "query_todos",
        "description": "Query todos with pagination. Excludes completed items by default. Use 'since' for change detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "object", "description": "{project: 'name', status: 'pending'|'completed'}"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"},
                "exclude_completed": {"type": "boolean", "description": "Exclude completed items (default: true)"},
                "since": {"type": "number", "description": "Unix timestamp — only return items modified after this time"}
            }
        }
    },
    "update_todo": {
        "name": "update_todo",
        "description": "Update todo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string"},
                "updates": {"type": "object"}
            },
            "required": ["todo_id", "updates"]
        }
    },
    "delete_todo": {
        "name": "delete_todo",
        "description": "Delete todo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string"}
            },
            "required": ["todo_id"]
        }
    },
    "get_todo": {
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
    "mark_todo_complete": {
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
    "list_todos_by_status": {
        "name": "list_todos_by_status",
        "description": "Quick status filter. Returns todos matching a single status with pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "pending|completed|initial|blocked|in_progress"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"}
            },
            "required": ["status"]
        }
    },
    "search_todos": {
        "name": "search_todos",
        "description": "Text search todos by keyword. Shorthand for query_todos with tokenized regex on description+project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "number"}
            },
            "required": ["query"]
        }
    },
    "list_project_todos": {
        "name": "list_project_todos",
        "description": "Quick project filter. Returns recent pending todos for one project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "limit": {"type": "number", "description": "Max results (default: 5)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"}
            },
            "required": ["project"]
        }
    },
    "add_lesson": {
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
    "get_lesson": {
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
    "update_lesson": {
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
    "delete_lesson": {
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
    "search_lessons": {
        "name": "search_lessons",
        "description": "Text search across lesson topic, content, and tags. For broader semantic search, use find_relevant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "fields": {"type": "array"},
                "limit": {"type": "number"}
            },
            "required": ["query"]
        }
    },
    "grep_lessons": {
        "name": "grep_lessons",
        "description": "Pattern match on lesson topic and content only (no tags). Use search_lessons for broader search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "limit": {"type": "number"}
            },
            "required": ["pattern"]
        }
    },
    "list_lessons": {
        "name": "list_lessons",
        "description": "List all lessons",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number"}
            }
        }
    },
    "query_todo_logs": {
        "name": "query_todo_logs",
        "description": "Query todo audit logs with filtering and pagination",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter_type": {"type": "string", "description": "Log type filter: all|create|update|delete|complete (default: all)"},
                "project": {"type": "string", "description": "Project filter (default: all)"},
                "page": {"type": "number", "description": "Page number (default: 1)"},
                "page_size": {"type": "number", "description": "Results per page (default: 20)"},
                "unified": {"type": "boolean", "description": "Query both personal and shared databases (default: false)"}
            }
        }
    },
    "list_projects": {
        "name": "list_projects",
        "description": "List available projects",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_details": {"type": "boolean", "description": "Include project metadata (default: false)"},
                "madness_root": {"type": "string", "description": "Root directory path (default: lab root)"}
            }
        }
    },
    "explain": {
        "name": "explain",
        "description": "Get explanation for topic",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"}
            },
            "required": ["topic"]
        }
    },
    "add_explanation": {
        "name": "add_explanation",
        "description": "Add explanation to the knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to explain"},
                "content": {"type": "string", "description": "Explanation content"},
                "kind": {"type": "string", "description": "Type: concept|pattern|gotcha|reference (default: concept)"},
                "author": {"type": "string", "description": "Author attribution (default: system)"}
            },
            "required": ["topic", "content"]
        }
    },
    "point_out_obvious": {
        "name": "point_out_obvious",
        "description": "Point out something obvious with varying levels of humor",
        "inputSchema": {
            "type": "object",
            "properties": {
                "observation": {"type": "string", "description": "The obvious thing to point out"},
                "sarcasm_level": {"type": "number", "description": "Scale from 1-10 (1=gentle, 10=maximum sass, default: 5)"}
            },
            "required": ["observation"]
        }
    },
    "inventorium_sessions_list": {
        "name": "inventorium_sessions_list",
        "description": "List chat sessions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number"},
                "project": {"type": "string"}
            }
        }
    },
    "inventorium_sessions_get": {
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
    "inventorium_sessions_create": {
        "name": "inventorium_sessions_create",
        "description": "Create session",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "title": {"type": "string"},
                "agentic_tool": {"type": "string"},
                "initial_prompt": {"type": "string"}
            },
            "required": ["project"]
        }
    },
    "inventorium_sessions_spawn": {
        "name": "inventorium_sessions_spawn",
        "description": "Spawn child session",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_session_id": {"type": "string"},
                "prompt": {"type": "string"},
                "title": {"type": "string"},
                "todo_id": {"type": "string"}
            },
            "required": ["parent_session_id", "prompt"]
        }
    },
    "inventorium_sessions_fork": {
        "name": "inventorium_sessions_fork",
        "description": "Fork an existing session into a new branch",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to fork from"},
                "title": {"type": "string", "description": "Title for the forked session"},
                "include_messages": {"type": "boolean", "description": "Copy message history to fork (default: true)"},
                "inherit_todos": {"type": "boolean", "description": "Link parent todos to fork (default: true)"},
                "initial_status": {"type": "string", "description": "Status for forked session (default: server decides)"}
            },
            "required": ["session_id"]
        }
    },
    "inventorium_sessions_genealogy": {
        "name": "inventorium_sessions_genealogy",
        "description": "Get session genealogy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"}
            },
            "required": ["session_id"]
        }
    },
    "inventorium_sessions_tree": {
        "name": "inventorium_sessions_tree",
        "description": "Get full session tree for a project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name filter (optional)"},
                "limit": {"type": "number", "description": "Max sessions to return (default: 200)"}
            }
        }
    },
    "inventorium_todos_link_session": {
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
    },
    "get_context_bundle": {
        "name": "get_context_bundle",
        "description": "Session startup bundle. Returns slim todo/lesson/session summaries in one call. Use at conversation start. Use 'since' for change detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name (optional)"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "Keywords to search across todos and lessons (optional)"},
                "include_completed": {"type": "boolean", "description": "Include recent completed todos (default: false)"},
                "since": {"type": "number", "description": "Unix timestamp — adds changed_todos section with items modified after this time"}
            }
        }
    },
    "find_relevant": {
        "name": "find_relevant",
        "description": "Semantic search across todos AND lessons. Use for ad-hoc 'find related items' queries mid-task. Uses embeddings when available, regex fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "types": {"type": "array", "items": {"type": "string"}, "description": "Types to search: ['todos', 'lessons'] (default: both)"},
                "limit": {"type": "number", "description": "Max results per type (default: 5)"}
            },
            "required": ["query"]
        }
    },
    "preflight_rag": {
        "name": "preflight_rag",
        "description": "Pre-task lessons check. Searches lessons only, classifies into solutions vs pitfalls. Use before starting work on a task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "What the agent is about to do (natural language)"},
                "project": {"type": "string", "description": "Project scope to prioritise project-specific lessons"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to narrow the search (e.g. ['deployment', 'auth'])"},
                "limit": {"type": "number", "description": "Max lessons to return (default: 5)"}
            },
            "required": ["intent"]
        }
    }
}


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
            # Get tools dynamically based on loadout (remote mode - filters local-only tools)
            loadout = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full")
            enabled_tools = get_loadout(loadout, mode="remote")

            logger.info(f"🔧 MCP tools/list: Loading '{loadout}' loadout (remote mode, {len(enabled_tools)} tools)")

            # Build tools list dynamically from TOOL_SCHEMAS
            tools = [
                TOOL_SCHEMAS[tool_name]
                for tool_name in enabled_tools
                if tool_name in TOOL_SCHEMAS
            ]

            logger.info(f"✅ Generated {len(tools)} tool schemas for remote client")

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

            # Map tool names to actual functions (complete list)
            tool_functions = {
                # Todo tools
                "add_todo": tools.add_todo,
                "query_todos": tools.query_todos,
                "update_todo": tools.update_todo,
                "delete_todo": tools.delete_todo,
                "get_todo": tools.get_todo,
                "mark_todo_complete": tools.mark_todo_complete,
                "list_todos_by_status": tools.list_todos_by_status,
                "search_todos": tools.search_todos,
                "list_project_todos": tools.list_project_todos,
                # Lesson tools
                "add_lesson": tools.add_lesson,
                "get_lesson": tools.get_lesson,
                "update_lesson": tools.update_lesson,
                "delete_lesson": tools.delete_lesson,
                "search_lessons": tools.search_lessons,
                "grep_lessons": tools.grep_lessons,
                "list_lessons": tools.list_lessons,
                # Admin/system tools
                "query_todo_logs": tools.query_todo_logs,
                "list_projects": tools.list_projects,
                "explain": tools.explain_tool,
                "add_explanation": tools.add_explanation,
                "point_out_obvious": tools.point_out_obvious,
                # Inventorium session tools
                "inventorium_sessions_list": tools.inventorium_sessions_list,
                "inventorium_sessions_get": tools.inventorium_sessions_get,
                "inventorium_sessions_create": tools.inventorium_sessions_create,
                "inventorium_sessions_spawn": tools.inventorium_sessions_spawn,
                "inventorium_sessions_fork": tools.inventorium_sessions_fork,
                "inventorium_sessions_genealogy": tools.inventorium_sessions_genealogy,
                "inventorium_sessions_tree": tools.inventorium_sessions_tree,
                "inventorium_todos_link_session": tools.inventorium_todos_link_session,
                # Context bundle (Tier 1 RAG)
                "get_context_bundle": tools.get_context_bundle,
                # Semantic search (Tier 2 RAG)
                "find_relevant": tools.find_relevant,
                # Preflight RAG (Pre-processing lessons lookup)
                "preflight_rag": tools.preflight_rag
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
