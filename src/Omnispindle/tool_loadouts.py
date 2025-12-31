"""
Centralized tool loadout definitions for all MCP server modes.

This module is the single source of truth for tool registration across:
- stdio_server.py (local FastMCP stdio)
- http_server.py (remote FastMCP HTTP)
- mcp_handler.py (JSON-RPC endpoint)
"""

from typing import Dict, List
from .tool_metadata import filter_remote_safe_loadout


# Base loadout definitions (before security filtering for remote mode)
_BASE_LOADOUTS: Dict[str, List[str]] = {
    "full": [
        # Todo management (9 tools)
        "add_todo", "query_todos", "update_todo", "delete_todo", "get_todo",
        "mark_todo_complete", "list_todos_by_status", "search_todos", "list_project_todos",

        # Lessons (7 tools)
        "add_lesson", "get_lesson", "update_lesson", "delete_lesson", "search_lessons",
        "grep_lessons", "list_lessons",

        # Admin/System (5 tools)
        "query_todo_logs", "list_projects", "explain", "add_explanation", "point_out_obvious",

        # Custom Code (1 tool)
        "bring_your_own",

        # Inventorium Sessions (8 tools)
        "inventorium_sessions_list", "inventorium_sessions_get",
        "inventorium_sessions_create", "inventorium_sessions_spawn",
        "inventorium_sessions_fork", "inventorium_sessions_genealogy",
        "inventorium_sessions_tree", "inventorium_todos_link_session"
    ],

    "basic": [
        # Core CRUD operations (7 tools)
        "add_todo", "query_todos", "update_todo", "get_todo", "mark_todo_complete",
        "list_todos_by_status", "list_project_todos"
    ],

    "minimal": [
        # Absolute minimum (4 tools)
        "add_todo", "query_todos", "get_todo", "mark_todo_complete"
    ],

    "lessons": [
        # Knowledge management focus (7 tools)
        "add_lesson", "get_lesson", "update_lesson", "delete_lesson", "search_lessons",
        "grep_lessons", "list_lessons"
    ],

    "admin": [
        # Administrative tools + sessions (13 tools)
        "query_todos", "update_todo", "delete_todo", "query_todo_logs",
        "list_projects", "explain", "add_explanation",
        "inventorium_sessions_list", "inventorium_sessions_get",
        "inventorium_sessions_create", "inventorium_sessions_fork",
        "inventorium_sessions_genealogy", "inventorium_sessions_tree",
        "inventorium_todos_link_session"
    ],

    "write_only": [
        # Create/Update/Delete only (6 tools)
        "add_todo", "update_todo", "delete_todo",
        "mark_todo_complete", "add_lesson", "update_lesson"
    ],

    "read_only": [
        # Query/Get only (8 tools)
        "query_todos", "get_todo", "list_todos_by_status",
        "list_project_todos", "search_todos", "get_lesson",
        "search_lessons", "list_lessons"
    ],

    "lightweight": [
        # Token-optimized core functionality (10 tools)
        # These will use COMPACT documentation level for minimal token usage
        "add_todo", "query_todos", "update_todo", "get_todo",
        "mark_todo_complete", "add_lesson", "get_lesson",
        "search_lessons", "inventorium_sessions_list", "inventorium_sessions_create"
    ],

    # Backward compatibility - keeping hybrid_test from stdio_server.py
    "hybrid_test": [
        "add_todo", "query_todos", "get_todo", "mark_todo_complete",
        "get_hybrid_status", "test_api_connectivity"
    ]
}


def get_loadout(loadout_name: str, mode: str = "local") -> List[str]:
    """
    Get tool list for a loadout, filtered by deployment mode.

    Args:
        loadout_name: Name of the loadout (full, basic, minimal, lessons, admin,
                      write_only, read_only, lightweight, hybrid_test)
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
    tools = _BASE_LOADOUTS.get(loadout_name, _BASE_LOADOUTS["full"])

    if mode == "remote":
        # Filter out local-only tools for remote mode
        return filter_remote_safe_loadout(tools)

    return tools


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
        "full": "All available tools (30 local, 28 remote after filtering)",
        "basic": "Core CRUD operations (7 tools)",
        "minimal": "Absolute minimum functionality (4 tools)",
        "lessons": "Knowledge management focus (7 tools)",
        "admin": "Administrative tools and session management (13 tools)",
        "write_only": "Create, update, delete operations only (6 tools)",
        "read_only": "Query and get operations only (8 tools)",
        "lightweight": "Token-optimized core functionality (10 tools)",
        "hybrid_test": "Testing hybrid mode functionality (6 tools)"
    }

    tools = _BASE_LOADOUTS.get(loadout_name, [])
    return {
        "name": loadout_name,
        "tool_count": len(tools),
        "tools": tools,
        "description": loadout_descriptions.get(loadout_name, "Custom loadout")
    }
