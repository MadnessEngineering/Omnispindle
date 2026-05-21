"""
Schema consistency validation.

Ensures that:
1. TOOL_SCHEMAS in mcp_handler.py stays in sync with actual tools.py function signatures.
2. Every schema property has a description (agent clarity).
3. The canonical valid-status set matches what tools.py enforces.

When you add or rename a parameter in tools.py, this test will fail until
mcp_handler.py TOOL_SCHEMAS is updated to match. That's the whole point.
"""

import inspect
import pytest

from src.Omnispindle import tools as tools_module
from src.Omnispindle.mcp_handler import TOOL_SCHEMAS

# Params that exist on every async tool but are never part of the MCP schema
_SKIP_PARAMS = {"ctx", "self"}

# Map schema tool names → actual functions (explain uses explain_tool internally)
TOOL_FUNCTION_MAP = {
    "add_todo": tools_module.add_todo,
    "query_todos": tools_module.query_todos,
    "update_todo": tools_module.update_todo,
    "delete_todo": tools_module.delete_todo,
    "get_todo": tools_module.get_todo,
    "complete_todo": tools_module.complete_todo,
    "list_todos_by_status": tools_module.list_todos_by_status,
    "search_todos": tools_module.search_todos,
    "list_project_todos": tools_module.list_project_todos,
    "add_lesson": tools_module.add_lesson,
    "get_lesson": tools_module.get_lesson,
    "update_lesson": tools_module.update_lesson,
    "delete_lesson": tools_module.delete_lesson,
    "search_lessons": tools_module.search_lessons,
    "grep_lessons": tools_module.grep_lessons,
    "list_lessons": tools_module.list_lessons,
    "query_todo_logs": tools_module.query_todo_logs,
    "list_projects": tools_module.list_projects,
    "explain": tools_module.explain_tool,
    "add_explanation": tools_module.add_explanation,
    "point_out_obvious": tools_module.point_out_obvious,
    "bring_your_own": tools_module.bring_your_own,
    "inventorium_sessions_list": tools_module.inventorium_sessions_list,
    "inventorium_sessions_get": tools_module.inventorium_sessions_get,
    "inventorium_sessions_create": tools_module.inventorium_sessions_create,
    "inventorium_sessions_spawn": tools_module.inventorium_sessions_spawn,
    "inventorium_sessions_fork": tools_module.inventorium_sessions_fork,
    "inventorium_sessions_genealogy": tools_module.inventorium_sessions_genealogy,
    "inventorium_sessions_tree": tools_module.inventorium_sessions_tree,
    "inventorium_todos_link_session": tools_module.inventorium_todos_link_session,
    "get_context_bundle": tools_module.get_context_bundle,
    "find_relevant": tools_module.find_relevant,
    "preflight_rag": tools_module.preflight_rag,
    "write_agent_journal": tools_module.write_agent_journal,
    "read_agent_journal": tools_module.read_agent_journal,
    "create_quest": tools_module.create_quest,
    "check_quest": tools_module.check_quest,
    "list_quests": tools_module.list_quests,
    "link_quest": tools_module.link_quest,
    "update_quest": tools_module.update_quest,
}

# Canonical set of valid todo statuses — update here when statuses change,
# then fix mcp_handler.py, documentation_manager.py, and stdio_server.py to match.
VALID_STATUSES = {"pending", "completed", "initial", "blocked", "in_progress", "review"}


def _func_params(func) -> set:
    sig = inspect.signature(func)
    return {name for name in sig.parameters if name not in _SKIP_PARAMS}


def _schema_params(schema: dict) -> set:
    return set(schema.get("inputSchema", {}).get("properties", {}).keys())


def test_schema_params_match_function_signatures():
    """TOOL_SCHEMAS properties must exactly match tools.py function param names."""
    failures = []
    for tool_name, schema in TOOL_SCHEMAS.items():
        if tool_name not in TOOL_FUNCTION_MAP:
            # Schema has a tool with no mapped function — likely a new tool not yet mapped here
            failures.append(f"{tool_name}: in TOOL_SCHEMAS but not in TOOL_FUNCTION_MAP (update this test)")
            continue

        s_params = _schema_params(schema)
        f_params = _func_params(TOOL_FUNCTION_MAP[tool_name])

        missing = f_params - s_params
        extra = s_params - f_params

        if missing:
            failures.append(f"{tool_name}: func params absent from schema → add to mcp_handler.py: {sorted(missing)}")
        if extra:
            failures.append(f"{tool_name}: schema params not in func → remove from mcp_handler.py: {sorted(extra)}")

    assert not failures, "Schema drift detected:\n" + "\n".join(failures)


def test_all_schema_properties_have_descriptions():
    """Every schema property should carry a description so agents know what to pass."""
    failures = []
    for tool_name, schema in TOOL_SCHEMAS.items():
        props = schema.get("inputSchema", {}).get("properties", {})
        for param_name, param_schema in props.items():
            if not param_schema.get("description"):
                failures.append(f"{tool_name}.{param_name}: no description in mcp_handler.py TOOL_SCHEMAS")
    assert not failures, "Missing descriptions (agents see blank hints):\n" + "\n".join(failures)


def test_list_todos_by_status_schema_includes_all_valid_statuses():
    """The status field description should enumerate every valid status value."""
    schema = TOOL_SCHEMAS.get("list_todos_by_status", {})
    description = (
        schema.get("inputSchema", {})
        .get("properties", {})
        .get("status", {})
        .get("description", "")
    )
    missing = [s for s in VALID_STATUSES if s not in description]
    assert not missing, (
        f"list_todos_by_status schema description missing statuses: {missing}. "
        "Update TOOL_SCHEMAS in mcp_handler.py, documentation_manager.py, and stdio_server.py."
    )
