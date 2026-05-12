
import json
import logging
import os
from typing import Dict, Any, Callable, Coroutine

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from .tool_loadouts import get_loadout, filter_by_tier
from .tool_metadata import is_pro_tool

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
        "description": "Query todos with pagination. Excludes completed items by default. Use 'since' for change detection. Use 'graph_root' to return a dependency subgraph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "object", "description": "{project: 'name', status: 'pending'|'completed'}"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"},
                "exclude_completed": {"type": "boolean", "description": "Exclude completed items (default: true)"},
                "since": {"type": "number", "description": "Unix timestamp — only return items modified after this time"},
                "projection": {"type": "object", "description": "{field: 1} to include, {field: 0} to exclude"},
                "graph_root": {"type": "string", "description": "Todo ID or short prefix — returns dependency subgraph: {root, nodes, edges} traversing metadata.blockers up to 2 hops in both directions"}
            }
        }
    },
    "update_todo": {
        "name": "update_todo",
        "description": "Modify task fields in-place. Pass only changed fields. Returns updated object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Todo UUID"},
                "updates": {"type": "object", "description": "{field: new_value} — metadata is MERGED not replaced"}
            },
            "required": ["todo_id", "updates"]
        }
    },
    "delete_todo": {
        "name": "delete_todo",
        "description": "Permanently remove task by ID. Irreversible.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Todo UUID to delete"}
            },
            "required": ["todo_id"]
        }
    },
    "get_todo": {
        "name": "get_todo",
        "description": "Retrieve single task by UUID. Returns full object including metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Todo UUID"}
            },
            "required": ["todo_id"]
        }
    },
    "complete_todo": {
        "name": "complete_todo",
        "description": "Set status=review (staged for review). Optional closing comment. Prefer over update_todo for completions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Todo UUID"},
                "comment": {"type": "string", "description": "What was accomplished — omitting loses completion context permanently"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "File paths changed during this work. Feeds SwarmDesk connected buildings. Example: [\"src/components/TodoTab.jsx\"]"}
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
                "status": {"type": "string", "description": "pending|completed|initial|blocked|in_progress|review"},
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
                "query": {"type": "string", "description": "Search text. Tokenized regex across description+project."},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "fields": {"type": "array", "description": "Fields to search (default: description, project)"}
            },
            "required": ["query"]
        }
    },
    "list_project_todos": {
        "name": "list_project_todos",
        "description": "Quick project filter. Returns recent pending and in_progress todos for one project.",
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
        "description": "Persist a lesson/pitfall for future recall. Tag well — drives preflight_rag relevance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "python|javascript|rust|etc"},
                "topic": {"type": "string", "description": "Topic/category"},
                "lesson_learned": {"type": "string", "description": "Lesson content"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Categorization tags"}
            },
            "required": ["language", "topic", "lesson_learned"]
        }
    },
    "get_lesson": {
        "name": "get_lesson",
        "description": "Retrieve single lesson by UUID. Returns full content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson UUID"}
            },
            "required": ["lesson_id"]
        }
    },
    "update_lesson": {
        "name": "update_lesson",
        "description": "Modify stored lesson fields. Use to correct or expand existing entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson UUID"},
                "updates": {"type": "object", "description": "{field: new_value}"}
            },
            "required": ["lesson_id", "updates"]
        }
    },
    "delete_lesson": {
        "name": "delete_lesson",
        "description": "Permanently remove lesson by ID. Irreversible.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson UUID to delete"}
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
                "query": {"type": "string", "description": "Search text"},
                "fields": {"type": "array", "description": "Fields to search (default: topic, lesson_learned, tags)"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "brief": {"type": "boolean", "description": "Return compact results (default: false)"}
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
                "pattern": {"type": "string", "description": "Regex pattern"},
                "limit": {"type": "number", "description": "Max results (default: 20)"}
            },
            "required": ["pattern"]
        }
    },
    "list_lessons": {
        "name": "list_lessons",
        "description": "Fetch all lessons paginated. Broad browse — use search_lessons or grep_lessons for targeted lookup.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "brief": {"type": "boolean", "description": "Return compact results (default: false)"}
            }
        }
    },
    "query_todo_logs": {
        "name": "query_todo_logs",
        "description": "Retrieve task audit trails. Filter by type/project. Use for debugging state changes or history.",
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
        "description": "Enumerate known projects. Returns names and optional metadata.",
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
        "description": "Fetch concept explanation from knowledge base. Returns text. Use for conceptual lookups.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Project or concept name"},
                "brief": {"type": "boolean", "description": "Return compact summary (default: false)"}
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
        "description": "List chat sessions, optionally by project. Use for context navigation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Max results (default: 50)"},
                "project": {"type": "string", "description": "Project name filter (optional)"}
            }
        }
    },
    "inventorium_sessions_get": {
        "name": "inventorium_sessions_get",
        "description": "Retrieve full session history by ID. Returns messages and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"}
            },
            "required": ["session_id"]
        }
    },
    "inventorium_sessions_create": {
        "name": "inventorium_sessions_create",
        "description": "Initialize new chat session for a project. Returns session object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "title": {"type": "string", "description": "Session title (optional)"},
                "agentic_tool": {"type": "string", "description": "Agent tool name (default: claude-code)"},
                "initial_prompt": {"type": "string", "description": "First message to seed session (optional)"}
            },
            "required": ["project"]
        }
    },
    "inventorium_sessions_spawn": {
        "name": "inventorium_sessions_spawn",
        "description": "Create sub-session branching from parent. Links to a todo. Returns new session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent_session_id": {"type": "string", "description": "Parent session UUID"},
                "prompt": {"type": "string", "description": "Initial prompt for child session"},
                "title": {"type": "string", "description": "Child session title (optional)"},
                "todo_id": {"type": "string", "description": "Todo UUID to link (optional)"}
            },
            "required": ["parent_session_id", "prompt"]
        }
    },
    "inventorium_sessions_fork": {
        "name": "inventorium_sessions_fork",
        "description": "Clone session into new branch. Returns new session. Use to explore alternatives without losing original.",
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
        "description": "Fetch session parent/child chain. Use to trace context history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"}
            },
            "required": ["session_id"]
        }
    },
    "inventorium_sessions_tree": {
        "name": "inventorium_sessions_tree",
        "description": "Fetch complete session hierarchy for a project. Use for global context overview.",
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
        "description": "Associate task UUID with chat session ID. Use for context grouping.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Todo UUID"},
                "session_id": {"type": "string", "description": "Session UUID"}
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
    },
    "write_agent_journal": {
        "name": "write_agent_journal",
        "description": "Append a timestamped entry to an agent's persistent journal. Use to leave working notes, session context, or status updates visible in SwarmDesk's 3D world. Other agents can read your journal for cross-agent awareness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Agent identifier (e.g. 'claude', 'gemini', 'user')"},
                "content": {"type": "string", "description": "Journal entry text (max 500 chars)"},
                "entry_type": {"type": "string", "description": "Entry category: note|annotation|session_start|session_end (default: note)"}
            },
            "required": ["agent_name", "content"]
        }
    },
    "read_agent_journal": {
        "name": "read_agent_journal",
        "description": "Read recent journal entries for any agent. Enables cross-agent awareness — read your own journal for continuity, or another agent's journal to see what they've been working on.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Agent identifier to read (e.g. 'claude', 'gemini', 'user')"},
                "limit": {"type": "number", "description": "Number of recent entries (default: 10, max: 50)"}
            },
            "required": ["agent_name"]
        }
    },
    # Quest tools
    "create_quest": {
        "name": "create_quest",
        "description": "Create a quest — epic container for todo chains with progress tracking. Quests group related todos into ordered chains with optional parallel execution and gate dependencies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Quest name, e.g. 'Tag System Overhaul'"},
                "description": {"type": "string", "description": "Goal statement"},
                "project": {"type": "string", "description": "Project scope"},
                "chains": {"type": "string", "description": "JSON array of chain objects: [{\"label\": \"...\", \"todos\": [\"uuid\", ...], \"parallel\": false, \"gate_todo\": null}]"},
                "tags": {"type": "string", "description": "Comma-separated tags"},
                "success_criteria": {"type": "string", "description": "Comma-separated success criteria"}
            },
            "required": ["name", "description", "project"]
        }
    },
    "check_quest": {
        "name": "check_quest",
        "description": "Agent orientation tool. Returns quest progress, per-chain status, next actions, blockers, and natural language summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "quest_id": {"type": "string", "description": "Quest UUID"}
            },
            "required": ["quest_id"]
        }
    },
    "list_quests": {
        "name": "list_quests",
        "description": "List quests filtered by status (active|completed|archived|all) and project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: active|completed|archived|abandoned|all (default: active)"},
                "project": {"type": "string", "description": "Filter by project name (optional)"},
                "limit": {"type": "number", "description": "Max results (default: 20)"}
            }
        }
    },
    "link_quest": {
        "name": "link_quest",
        "description": "Add a todo to an existing quest chain retroactively. position=-1 appends.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "quest_id": {"type": "string", "description": "Quest UUID"},
                "todo_id": {"type": "string", "description": "Todo UUID to add"},
                "chain_label": {"type": "string", "description": "Name of the chain to add to"},
                "position": {"type": "number", "description": "Insert position (-1 = append, default: -1)"}
            },
            "required": ["quest_id", "todo_id", "chain_label"]
        }
    },
    "update_quest": {
        "name": "update_quest",
        "description": "Update quest fields (name, description, status, success_criteria, metadata). Pass updates as JSON string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "quest_id": {"type": "string", "description": "Quest UUID"},
                "updates": {"type": "string", "description": "JSON string of fields to update: {\"name\": \"...\", \"status\": \"completed\", ...}"}
            },
            "required": ["quest_id"]
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

            # Filter by subscription tier — free users don't see pro-only tools
            user_tier = user.get("subscription_tier", "free")
            enabled_tools = filter_by_tier(enabled_tools, user_tier)

            logger.info(f"🔧 MCP tools/list: Loading '{loadout}' loadout (remote mode, tier={user_tier}, {len(enabled_tools)} tools)")

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

            # Never allow client-provided ctx/user_ctx to collide with server ctx
            tool_arguments.pop("ctx", None)
            tool_arguments.pop("user_ctx", None)

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
                "complete_todo": tools.complete_todo,
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
                "preflight_rag": tools.preflight_rag,
                # Agent Journal tools
                "write_agent_journal": tools.write_agent_journal,
                "read_agent_journal": tools.read_agent_journal,
                # Quest tools
                "create_quest": tools.create_quest,
                "check_quest": tools.check_quest,
                "list_quests": tools.list_quests,
                "link_quest": tools.link_quest,
                "update_quest": tools.update_quest
            }

            if tool_name not in tool_functions:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"}
                })

            # Enforce subscription tier — block pro tools for free users
            user_tier = user.get("subscription_tier", "free")
            if is_pro_tool(tool_name) and user_tier not in ("pro", "admin"):
                logger.info(f"🚫 Tier gate: {user.get('email', 'unknown')} blocked from pro tool '{tool_name}' (tier: {user_tier})")
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32001,
                        "message": f"'{tool_name}' requires a Madness Pass. Upgrade at madnessinteractive.cc to unlock pro tools."
                    }
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
