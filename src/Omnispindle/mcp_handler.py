
import inspect
import json
import logging
import os
from typing import Dict, Any, Callable, Coroutine, Optional, Tuple

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from .tool_loadouts import get_loadout, filter_by_tier, get_loadout_names
from .tool_metadata import is_pro_tool
from .documentation_manager import DocumentationLevel, DocumentationManager, get_tool_doc

logger = logging.getLogger(__name__)

# Remote clients (Claude Code, Claude Desktop over HTTP) cannot set the server's
# env vars, so before this default they were stuck with 'full': 41 tools, ~7.5k
# tokens of tools/list paid on every session before a single tool is called.
# 'basic' is ~15 tools. Callers that want more ask per-request (see
# _resolve_client_prefs); tools/call is NOT loadout-gated, so a client that knows
# a tool name can still call it — this shrinks discovery, not capability.
DEFAULT_REMOTE_LOADOUT = "basic"

# Protocol versions this handler can serve. Newest first — PROTOCOL_VERSION is what
# we announce when the client asks for something we don't speak (or asks for nothing).
# We stay conservative here: claiming a version means claiming its semantics, and the
# 2026-07-28 generation drops the initialize handshake entirely, which this handler
# still relies on.
PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def _server_version() -> str:
    """Installed package version, falling back to the pyproject value."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version("omnispindle")
    except Exception:
        return "1.0.0"


def _as_text(result: Any) -> str:
    """
    Serialize a tool result for MCP text content exactly once.

    Every tool in tools.py already returns a JSON string (via create_response or
    json.dumps). Running json.dumps over that string again re-encoded it as a JSON
    *string literal* — every quote escaped to \\" — which cost ~10-15% extra tokens
    and forced clients to parse twice. Strings pass through untouched; anything else
    is serialized here. Matches FastMCP's own stdio behaviour (_convert_to_content).
    """
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str)


# ── Argument validation ─────────────────────────────────────────────
# tools/call splats client arguments straight into the tool function. A missing
# required param or a hallucinated one used to raise a bare TypeError, which the
# handler reported as -32603 "Internal error" — and most clients render only
# `message`, so the agent saw nothing actionable and concluded the whole server
# was down. Validate first, and say exactly what was wrong in `message`.

_SIGNATURE_CACHE: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], bool]] = {}

# Server-supplied; a client never passes these (they are stripped before dispatch).
_SERVER_PARAMS = ("ctx", "user_ctx", "self")


def _tool_params(tool_name: str, tool_func: Any) -> Tuple[Tuple[str, ...], Tuple[str, ...], bool]:
    """(accepted, required, accepts_kwargs) read off the tool's real signature.

    The signature is the truth at call time — TOOL_SCHEMAS is kept in sync with it
    by tests/test_schema_consistency.py, but a drift there must not turn into a
    misleading error message here.
    """
    cached = _SIGNATURE_CACHE.get(tool_name)
    if cached is not None:
        return cached

    try:
        sig = inspect.signature(tool_func)
    except (TypeError, ValueError):
        # Un-introspectable callable: accept anything and let the call decide.
        return ((), (), True)

    accepted, required, accepts_kwargs = [], [], False
    for pname, param in sig.parameters.items():
        if pname in _SERVER_PARAMS:
            continue
        if param.kind is param.VAR_KEYWORD:
            accepts_kwargs = True
            continue
        if param.kind is param.VAR_POSITIONAL:
            continue
        accepted.append(pname)
        if param.default is param.empty:
            required.append(pname)

    result = (tuple(accepted), tuple(required), accepts_kwargs)
    _SIGNATURE_CACHE[tool_name] = result
    return result


def _param_signature(accepted: Tuple[str, ...], required: Tuple[str, ...]) -> str:
    """'name*, description*, project*, chains, tags (* = required)'"""
    if not accepted:
        return "(no parameters)"
    rendered = ", ".join(f"{p}*" if p in required else p for p in accepted)
    return f"{rendered} (* = required)" if required else rendered


def _validate_tool_arguments(tool_name: str, tool_func: Any, arguments: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable reason the args are invalid, or None if they're fine."""
    accepted, required, accepts_kwargs = _tool_params(tool_name, tool_func)
    if not accepted and accepts_kwargs:
        return None

    problems = []
    missing = [p for p in required if p not in arguments]
    if missing:
        problems.append("missing required " + ", ".join(f"'{p}'" for p in missing))
    if not accepts_kwargs:
        unknown = [k for k in arguments if k not in accepted]
        if unknown:
            problems.append("unknown " + ", ".join(f"'{k}'" for k in unknown))

    if not problems:
        return None
    return f"{tool_name}: {'; '.join(problems)}. Accepts: {_param_signature(accepted, required)}"



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
        "description": "Query todos with pagination. Excludes completed items by default. Use 'since' for change detection. Use 'graph_root' to return a dependency subgraph. Response includes diet: 'full'|'brief'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "object", "description": "{project: 'name', status: 'pending'|'completed'}"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"},
                "exclude_completed": {"type": "boolean", "description": "Exclude completed items (default: true)"},
                "since": {"type": "number", "description": "Unix timestamp — only return items modified after this time"},
                "projection": {"type": "object", "description": "{field: 1} to include, {field: 0} to exclude"},
                "graph_root": {"type": "string", "description": "Todo ID or short prefix — returns dependency subgraph: {root, nodes, edges} traversing metadata.blockers up to 2 hops in both directions"},
                "brief": {"type": "boolean", "description": "Force strip notes + prose metadata. Omit for auto: a fat multi-item set slims to id/description/project/status/priority/tags + metadata.tags/files."}
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
        "description": "Quick status filter. Returns todos matching a single status with pagination. Brief by default — pass brief=false for full notes/metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "pending|completed|initial|blocked|in_progress|review"},
                "limit": {"type": "number", "description": "Max results (default: 100)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"},
                "brief": {"type": "boolean", "description": "Strip notes + non-essential metadata (default: true)"}
            },
            "required": ["status"]
        }
    },
    "search_todos": {
        "name": "search_todos",
        "description": "Text search todos. Two-pass: strict AND-match first; fuzzy OR ranked by token density if empty. No project param — filter by project with query_todos(filter={\"project\": \"name\"}). Response includes search_mode: 'strict'|'fuzzy_or' and diet: 'full'|'brief'|'truncated'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text. Tokenized regex across description+project."},
                "limit": {"type": "number", "description": "Max results (default: 20)"},
                "fields": {"type": "array", "description": "Fields to search (default: description, project)"},
                "brief": {"type": "boolean", "description": "Force strip notes + non-essential metadata. Omit for auto: multi-hit sets go brief when notes are fat, long descriptions become match-centred snippets, coordinates are dropped; single hit keeps notes."}
            },
            "required": ["query"]
        }
    },
    "list_project_todos": {
        "name": "list_project_todos",
        "description": "Quick project filter. Returns recent pending and in_progress todos for one project. Brief by default — pass brief=false for full notes/metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "limit": {"type": "number", "description": "Max results (default: 5)"},
                "offset": {"type": "number", "description": "Skip N results for pagination (default: 0)"},
                "brief": {"type": "boolean", "description": "Strip notes + non-essential metadata (default: true)"},
                "projection": {"type": "object", "description": "{field: 1} include / {field: 0} exclude — passes through to MongoDB"}
            },
            "required": ["project"]
        }
    },
    "query_todos_near": {
        "name": "query_todos_near",
        "description": "Find todos in the same district or within spatial radius. Requires todo_id (inherits district+coords) or district name. Powers SwarmDesk neighborhood queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Anchor todo UUID — inherit its district and coordinates"},
                "district": {"type": "string", "description": "District label to match (e.g. 'rag', 'ui', 'infra')"},
                "radius": {"type": "number", "description": "Max Euclidean distance for coordinate matching (default: 2.0)"},
                "limit": {"type": "number", "description": "Max results (default: 20)"}
            }
        }
    },
    "link_todos": {
        "name": "link_todos",
        "description": "Mark blocker_id as a dependency of blocked_id. Exactly two ids per call — no todo_ids array; call once per edge. Adds to metadata.blockers. Use query_todos(graph_root=id) to visualize.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blocker_id": {"type": "string", "description": "Todo that must complete first"},
                "blocked_id": {"type": "string", "description": "Todo that depends on blocker_id"}
            },
            "required": ["blocker_id", "blocked_id"]
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
    "config": {
        "name": "config",
        "description": (
            "Read or change which tool loadout and documentation level your MCP sessions "
            "get. Call with no arguments to see the current setting plus every available "
            "option and its tool count. Remote clients default to 'basic' (21 of 43 "
            "tools); 'full' adds the rest. Takes effect on the next tools/list — "
            "reconnect (/mcp) to pick it up."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "loadout": {
                    "type": "string",
                    "description": "Loadout name to store, e.g. 'full' or 'basic'. Omit to leave unchanged."
                },
                "doc_level": {
                    "type": "string",
                    "description": "Documentation detail level for tool descriptions. Omit to derive it from the loadout."
                }
            },
            "required": []
        }
    },
    "regenerate_embedding": {
        "name": "regenerate_embedding",
        "description": "Recompute vector embedding for a lesson and stamp embedding_updated_at. Use after edits or to fix stale/missing embeddings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson UUID"}
            },
            "required": ["lesson_id"]
        }
    },
    "search_lessons": {
        "name": "search_lessons",
        "description": "Two-pass text search across lesson topic, content, and tags. Pass 1: strict AND (all tokens must match). Pass 2: OR ranked fallback when strict returns nothing. Response includes search_mode: 'strict'|'fuzzy_or' and diet: 'full'|'brief'|'truncated'. For semantic search, use find_relevant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text"},
                "fields": {"type": "array", "description": "Fields to search (default: topic, lesson_learned, tags)"},
                "limit": {"type": "number", "description": "Max results (default: 20)"},
                "brief": {"type": "boolean", "description": "Force topic+tags only, no lesson_learned. Omit for auto: fat sets return a match-relevant snippet, small ones keep full text."}
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
        "description": "Fetch all lessons paginated. Broad browse — use search_lessons or grep_lessons for targeted lookup. Response includes diet: 'full'|'brief'|'truncated'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Max results (default: 20)"},
                "brief": {"type": "boolean", "description": "Force topic+tags only, no lesson_learned. Omit for auto: lesson_learned is snipped once the set gets fat, kept whole when small."}
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
        "description": "Create a quest — epic container for todo chains. Requires name, description AND project. TODOS FIRST: add_todo for each task, collect IDs, then create_quest with chains pre-loaded. chains todos[] must be existing todo UUIDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Quest name, e.g. 'Tag System Overhaul'"},
                "description": {"type": "string", "description": "Goal statement"},
                "project": {"type": "string", "description": "Project scope"},
                "chains": {"type": "string", "description": "JSON array of chain objects. todos[] must be EXISTING todo UUIDs — create todos with add_todo first, then list their IDs here: [{\"label\": \"Phase 1\", \"todos\": [\"uuid1\", \"uuid2\"], \"parallel\": false, \"gate_todo\": null}]"},
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

# Hand-written fallbacks, captured before the doc manager overwrites them. Used when
# a tool has no entry in TOOL_DOCUMENTATION at the requested level — otherwise the
# manager hands back "Tool documentation not found."
_FALLBACK_DESCRIPTIONS = {_n: _s.get("description", "") for _n, _s in TOOL_SCHEMAS.items()}

# Apply tier-aware descriptions at startup — reads OMNISPINDLE_DOC_LEVEL / OMNISPINDLE_TOOL_LOADOUT
for _name, _schema in TOOL_SCHEMAS.items():
    _doc = get_tool_doc(_name)
    if _doc:
        _schema["description"] = _doc

# Per-doc-level schema cache. tools/list is hot and the schemas are immutable once
# built, so build each level once and reuse.
_SCHEMA_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}



def _with_param_line(doc: str, schema: Dict[str, Any]) -> str:
    """Append the tool's parameter list to its prose description.

    inputSchema already carries this, but prose is what a model actually reads —
    and every misuse in the logs (create_quest without `project`, link_todos with
    `todo_ids`, search_todos with `project`) was a param invented or dropped while
    the schema sat right there. Generated from the schema, so it can never drift
    out of date the way a hand-written "Params:" line does.
    """
    props = schema.get("inputSchema", {}).get("properties", {})
    if not props:
        return doc
    required = set(schema.get("inputSchema", {}).get("required", []))
    rendered = ", ".join(f"{p}*" if p in required else p for p in props)
    suffix = f"Params: {rendered}" + (" (* = required)" if required else "")
    return f"{doc.rstrip()}\n{suffix}"


def _schemas_at_level(doc_level: str) -> Dict[str, Dict[str, Any]]:
    """Return {tool_name: schema} with descriptions rendered at `doc_level`."""
    cached = _SCHEMA_CACHE.get(doc_level)
    if cached is not None:
        return cached

    manager = DocumentationManager()
    manager.level = DocumentationLevel(doc_level)

    built = {}
    for name, schema in TOOL_SCHEMAS.items():
        doc = manager.get_tool_documentation(name)
        if not doc or doc == "Tool documentation not found.":
            doc = _FALLBACK_DESCRIPTIONS.get(name) or schema.get("description", "")
        built[name] = {**schema, "description": _with_param_line(doc, schema)}

    _SCHEMA_CACHE[doc_level] = built
    return built


def _resolve_client_prefs(request: Request, user: Optional[Dict[str, Any]] = None) -> tuple:
    """
    Resolve (loadout, doc_level) for this request.

    Precedence: query param -> header -> stored user pref -> env -> DEFAULT_REMOTE_LOADOUT.
    The stored pref is what the `config` tool writes, so an agent can widen its own tool
    list without the user editing client config. Remote clients
    can only control the URL and headers, so both are accepted:
        POST /api/mcp/?loadout=refine&doc_level=basic
        X-Omnispindle-Loadout: refine
        X-Omnispindle-Doc-Level: basic
    Unknown values fall back to the default rather than erroring — a bad hint should
    degrade the tool list, never break the session.
    """
    params = request.query_params
    headers = request.headers

    explicit_loadout = params.get("loadout") or headers.get("x-omnispindle-loadout")
    explicit_level = params.get("doc_level") or headers.get("x-omnispindle-doc-level")

    # Only pay for the lookup when the client did not say. An explicit per-request hint
    # should never cost a database round trip, and this runs on every tools/call.
    stored = {}
    if user and (not explicit_loadout or not explicit_level):
        try:
            from . import tools as _tools
            stored = _tools.get_stored_client_prefs(user)
        except Exception as e:
            logger.warning(f"Stored client prefs unavailable: {e}")

    loadout = (
        explicit_loadout
        or stored.get("loadout")
        or os.getenv("OMNISPINDLE_TOOL_LOADOUT")
        or DEFAULT_REMOTE_LOADOUT
    ).strip().lower()

    if loadout not in get_loadout_names():
        logger.warning(f"Unknown loadout '{loadout}' requested; using '{DEFAULT_REMOTE_LOADOUT}'")
        loadout = DEFAULT_REMOTE_LOADOUT

    requested_level = (
        explicit_level
        or stored.get("doc_level")
        or os.getenv("OMNISPINDLE_DOC_LEVEL")
        or ""
    ).strip().lower()

    valid_levels = {level.value for level in DocumentationLevel}
    if requested_level in valid_levels:
        doc_level = requested_level
    else:
        if requested_level:
            logger.warning(f"Unknown doc_level '{requested_level}' requested; deriving from loadout")
        # Same loadout -> level mapping the doc manager uses.
        doc_level = DocumentationManager(loadout=loadout).level.value

    return loadout, doc_level


def _build_tool_functions() -> Dict[str, Any]:
    """
    Tool name -> callable, for tools/call dispatch.

    Built once at import instead of rebuilt on every single call, and module-level
    so tests/test_schema_consistency.py can assert it against the other registries.
    Imported lazily inside the function to keep the tools module out of the import
    cycle at module load.
    """
    from . import tools

    return {
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
        "query_todos_near": tools.query_todos_near,
        "link_todos": tools.link_todos,
        # Lesson tools
        "add_lesson": tools.add_lesson,
        "get_lesson": tools.get_lesson,
        "update_lesson": tools.update_lesson,
        "delete_lesson": tools.delete_lesson,
        "regenerate_embedding": tools.regenerate_embedding,
        "config": tools.config,
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


_TOOL_FUNCTIONS: Optional[Dict[str, Any]] = None


def get_tool_functions() -> Dict[str, Any]:
    """Memoized tools/call dispatch table."""
    global _TOOL_FUNCTIONS
    if _TOOL_FUNCTIONS is None:
        _TOOL_FUNCTIONS = _build_tool_functions()
    return _TOOL_FUNCTIONS


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

        # Notifications carry no id and MUST NOT get a JSON-RPC response object —
        # returning an error for notifications/initialized is itself a violation.
        if isinstance(method, str) and method.startswith("notifications/"):
            return JSONResponse(content=None, status_code=202)

        # Handle different MCP methods
        if method == "initialize":
            # Echo the client's protocol version when we speak it, rather than
            # unilaterally announcing ours — a client that strict-matches the
            # version string would otherwise refuse the connection.
            requested = params.get("protocolVersion")
            negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": negotiated,
                        "serverInfo": {
                            "name": "Omnispindle",
                            "version": _server_version()
                        },
                        # Advertise ONLY what the dispatch below actually answers.
                        # This previously claimed prompts and resources; neither has
                        # a handler, so a client that trusted the handshake got
                        # -32601 where the spec promises an empty list.
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
            )
        elif method == "ping":
            return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "tools/list":
            # Get tools dynamically based on loadout (remote mode - filters local-only tools)
            loadout, doc_level = _resolve_client_prefs(request, user)
            enabled_tools = get_loadout(loadout, mode="remote")

            # Filter by subscription tier — free users don't see pro-only tools
            user_tier = user.get("subscription_tier", "free")
            enabled_tools = filter_by_tier(enabled_tools, user_tier)

            logger.info(f"🔧 MCP tools/list: Loading '{loadout}' loadout at '{doc_level}' docs (remote mode, tier={user_tier}, {len(enabled_tools)} tools)")

            # Build tools list dynamically from TOOL_SCHEMAS
            schemas = _schemas_at_level(doc_level)
            tools = [
                schemas[tool_name]
                for tool_name in enabled_tools
                if tool_name in schemas
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

            from .context import Context

            # Create context for the user
            ctx = Context(user=user)

            tool_functions = get_tool_functions()

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

            tool_func = tool_functions[tool_name]

            # Validate before splatting. A bad call is the caller's to fix, so it
            # gets -32602 with the reason in `message` — clients that render only
            # `message` (most of them) still show the agent what to correct.
            arg_error = _validate_tool_arguments(tool_name, tool_func, tool_arguments)
            if arg_error:
                logger.info(f"⚠️ Invalid params: {arg_error}")
                accepted, required, _ = _tool_params(tool_name, tool_func)
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Invalid params — {arg_error}",
                        "data": {
                            "tool": tool_name,
                            "accepted": list(accepted),
                            "required": list(required),
                            "received": sorted(tool_arguments.keys()),
                        }
                    }
                })

            try:
                result = await tool_func(**tool_arguments, ctx=ctx)

                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": _as_text(result)}]}
                })

            except TypeError as tool_error:
                # Validation above catches name-level mistakes; a TypeError that
                # still names this tool's signature is an arg problem, not a server
                # fault (e.g. a param passed positionally-only or of the wrong kind).
                if f"{tool_name}()" in str(tool_error):
                    accepted, required, _ = _tool_params(tool_name, tool_func)
                    logger.info(f"⚠️ Invalid params: {tool_error}")
                    return JSONResponse(content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": f"Invalid params — {tool_error}. Accepts: {_param_signature(accepted, required)}",
                            "data": {"tool": tool_name, "accepted": list(accepted), "required": list(required)}
                        }
                    })
                logger.error(f"Tool execution error in {tool_name}: {tool_error}", exc_info=True)
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Internal error in {tool_name}: {tool_error}", "data": str(tool_error)}
                })

            except Exception as tool_error:
                logger.error(f"Tool execution error in {tool_name}: {tool_error}", exc_info=True)
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Internal error in {tool_name}: {tool_error}", "data": str(tool_error)}
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
