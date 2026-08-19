"""
Centralized tool loadout definitions for all MCP server modes.

This module is the single source of truth for tool registration across:
- stdio_server.py (local FastMCP stdio)
- http_server.py (remote FastMCP HTTP)
- mcp_handler.py (JSON-RPC endpoint)
"""

import logging
from typing import Dict, List
from .tool_metadata import (
    TOOL_GROUPS,
    ToolGroup,
    filter_remote_safe_loadout,
    get_group_tools,
    is_pro_tool,
)

logger = logging.getLogger(__name__)


# Base loadout definitions (before security filtering for remote mode)
_BASE_LOADOUTS: Dict[str, List[str]] = {
    # Derived, not hand-written: 'full' means every tool the server can dispatch,
    # and TOOL_GROUPS is the registry that says what those are. Maintaining this as
    # a literal list is what let bring_your_own sit in the loadout with no schema.
    "full": list(TOOL_GROUPS),

    "basic": [
        # The default for remote HTTP clients. Read as "everything you want for a
        # normal working session" — not "core CRUD". Deliberately excluded:
        # sessions, agent journal, explain/add_explanation, point_out_obvious,
        # bring_your_own, and the destructive deletes. Those are specialist tools;
        # a client that needs them asks for 'full' or 'admin' per request.

        # Todo CRUD (7 tools)
        "add_todo", "query_todos", "update_todo", "get_todo", "complete_todo",
        "list_todos_by_status", "list_project_todos",
        # Finding things — search_todos and the RAG pair are normal operation,
        # not extras. Working without them means re-deriving context by hand.
        "search_todos", "get_context_bundle", "find_relevant", "preflight_rag",
        # Lessons: read and write. Capturing a lesson is part of doing the work.
        "add_lesson", "get_lesson", "search_lessons",
        # Spatial + dependency (2 tools)
        "query_todos_near", "link_todos",
        # Quest system — include so agents know epics exist (5 tools)
        "create_quest", "check_quest", "list_quests", "link_quest", "update_quest",
    ],

    "minimal": [
        # Absolute minimum (4 tools)
        "add_todo", "query_todos", "get_todo", "complete_todo"
    ],

    # Whole-group loadout — derived so a new lesson tool joins it automatically.
    "lessons": get_group_tools(ToolGroup.LESSONS),

    "admin": [
        # Administrative tools + sessions (13 tools)
        "query_todos", "update_todo", "delete_todo", "query_todo_logs",
        "list_projects", "explain", "add_explanation",
        "inventorium_sessions_list", "inventorium_sessions_get",
        "inventorium_sessions_create", "inventorium_sessions_fork",
        "inventorium_sessions_genealogy", "inventorium_sessions_tree",
        "inventorium_todos_link_session",
        "write_agent_journal", "read_agent_journal"
    ],

    "write_only": [
        # Create/Update/Delete only (6 tools)
        "add_todo", "update_todo", "delete_todo",
        "complete_todo", "add_lesson", "update_lesson"
    ],

    "read_only": [
        # Query/Get only (16 tools)
        "query_todos", "get_todo", "list_todos_by_status",
        "list_project_todos", "search_todos", "query_todos_near", "get_lesson",
        "search_lessons", "list_lessons", "get_context_bundle",
        "find_relevant", "preflight_rag",
        "inventorium_sessions_list", "inventorium_sessions_get",
        "inventorium_sessions_genealogy", "inventorium_sessions_tree",
        "read_agent_journal"
    ],

    "lightweight": [
        # Token-optimized core functionality (12 tools)
        # These will use COMPACT documentation level for minimal token usage
        "add_todo", "query_todos", "update_todo", "get_todo",
        "complete_todo", "add_lesson", "get_lesson",
        "search_lessons", "inventorium_sessions_list", "inventorium_sessions_create",
        "get_context_bundle", "find_relevant", "preflight_rag"
    ],

    "agent_preflight": [
        # Startup context for agents beginning work (6 tools)
        "get_context_bundle", "preflight_rag", "find_relevant",
        "query_todos", "get_todo", "get_lesson"
    ],

    "refine": [
        # Discovery — find todos needing enrichment (6 tools)
        "query_todos", "search_todos", "get_todo",
        "list_todos_by_status", "list_project_todos", "query_todos_near",

        # Enrichment — write improved metadata (2 tools)
        "update_todo", "link_todos",

        # Context & intelligence (4 tools)
        "get_context_bundle", "find_relevant", "preflight_rag", "search_lessons",

        # Coordination (2 tools)
        "inventorium_todos_link_session", "inventorium_sessions_tree",

        # Utility (1 tool)
        "point_out_obvious",
    ],

    "npc": [
        # Context — what's happening in the world (4 tools)
        "get_context_bundle", "find_relevant", "preflight_rag", "query_todos_near",

        # Knowledge — lore, lessons, explanations (4 tools)
        "get_lesson", "search_lessons", "grep_lessons", "explain",

        # Todo awareness — read missions/objectives (3 tools)
        "query_todos", "get_todo", "list_todos_by_status",

        # Journal — NPC can record observations (2 tools)
        "write_agent_journal", "read_agent_journal",

        # Placeholder — NPC-specific tools added here as built
    ]
}


# Tools every loadout must expose regardless of how narrow it is.
ALWAYS_PRESENT: List[str] = ["config"]


def get_loadout(loadout_name: str, mode: str = "local") -> List[str]:
    """
    Get tool list for a loadout, filtered by deployment mode.

    Args:
        loadout_name: Name of the loadout (full, basic, minimal, lessons, admin,
                      write_only, read_only, lightweight, agent_preflight, refine, npc)
        mode: Deployment mode - 'local' for stdio/local, 'remote' for HTTP/API

    Returns:
        List of tool names appropriate for the mode

    Examples:
        >>> get_loadout("full", mode="local")
        ['add_todo', 'query_todos', ..., 'bring_your_own']  # 30 tools

        >>> get_loadout("full", mode="remote")
        ['add_todo', 'query_todos', ...]  # 28 tools (filters bring_your_own, list_projects)

        >>> get_loadout("lightweight", mode="local")
        ['add_todo', 'query_todos', ...]  # 10 tools
    """
    # Unknown name falls back NARROW, not wide. This used to return 'full', so a
    # typo in a loadout hint quietly widened exposure to every tool — the opposite
    # of what a bad input should do. Matches mcp_handler's DEFAULT_REMOTE_LOADOUT.
    tools = _BASE_LOADOUTS.get(loadout_name)
    if tools is None:
        logger.warning(f"Unknown loadout '{loadout_name}'; falling back to 'basic'")
        tools = _BASE_LOADOUTS["basic"]

    # ALWAYS_PRESENT is injected here rather than added to each list, so a loadout
    # derived from TOOL_GROUPS (lessons, read_only, refine, npc, ...) cannot silently
    # omit it. config is how a client widens its own tool list; a loadout that hid it
    # would be a one-way door, since tools/call is reachable by name but an agent
    # cannot call a tool it was never shown.
    tools = list(tools) + [t for t in ALWAYS_PRESENT if t not in tools]

    if mode == "remote":
        # Filter out local-only tools for remote mode
        return filter_remote_safe_loadout(tools)

    return tools


def filter_by_tier(tools: List[str], tier: str) -> List[str]:
    """
    Filter tool list by user subscription tier.

    Pro/admin users see all tools. Free users see only free-tier tools.

    Args:
        tools: List of tool names to filter
        tier: User subscription tier ('free', 'pro', 'admin')

    Returns:
        Filtered list of tools available to the user's tier
    """
    if tier in ("pro", "admin"):
        return tools
    return [tool for tool in tools if not is_pro_tool(tool)]


def get_all_loadouts() -> Dict[str, List[str]]:
    """
    Get all available loadouts (local mode, unfiltered).

    Returns:
        Dictionary mapping loadout names to tool lists
    """
    return _BASE_LOADOUTS.copy()


def get_loadout_names() -> List[str]:
    """
    Get list of all available loadout names.

    Returns:
        List of loadout names
    """
    return list(_BASE_LOADOUTS.keys())


def get_loadout_info(loadout_name: str) -> Dict[str, any]:
    """
    Get detailed information about a loadout.

    Args:
        loadout_name: Name of the loadout

    Returns:
        Dictionary with loadout metadata (name, tool_count, description)
    """
    loadout_descriptions = {
        "full": "All available tools (33 local, 31 remote after filtering)",
        "basic": "Default for remote HTTP. Normal working session: todo CRUD + search + RAG (find_relevant, preflight_rag, get_context_bundle) + lessons read/write + spatial/dependency + quests (21 tools). No sessions, journal, explain, point_out_obvious, bring_your_own, or deletes.",
        "minimal": "Absolute minimum functionality (4 tools)",
        "lessons": "Knowledge management focus (8 tools)",
        "admin": "Administrative tools and session management (14 tools)",
        "write_only": "Create, update, delete operations only (6 tools)",
        "read_only": "Query, get, and search operations + sessions (15 tools)",
        "lightweight": "Token-optimized core functionality (13 tools)",
        "agent_preflight": "Startup context for agents beginning work (6 tools)",
        "refine": "Todo enrichment: audit + enrich metadata (tags, files, district, coordinates, blockers) for 3D visualization and dependency graph quality (13 tools)",
        "npc": "NPC Brain: context awareness + knowledge lookup + todo observation + journal. Placeholder for NPC-specific tools as built (13 tools)"
    }

    # Report what get_loadout actually returns, injection included — reading
    # _BASE_LOADOUTS directly made tool_count disagree with the real tool list.
    # Unknown names still report empty rather than get_loadout's basic fallback.
    tools = get_loadout(loadout_name, mode="local") if loadout_name in _BASE_LOADOUTS else []
    return {
        "name": loadout_name,
        "tool_count": len(tools),
        "tools": tools,
        "description": loadout_descriptions.get(loadout_name, "Custom loadout")
    }
