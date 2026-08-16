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
_SKIP_PARAMS = {"ctx", "self", "extra"}  # extra = **kwargs catch-all in add_todo

# Tools the remote JSON-RPC handler deliberately cannot serve. bring_your_own
# executes arbitrary code (LOCAL_ONLY), so it has no schema and no remote dispatch
# entry — exempting it here is a decision, not an oversight. See
# test_local_only_asymmetries_are_deliberate.
_REMOTE_EXEMPT = {"bring_your_own"}

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
    "query_todos_near": tools_module.query_todos_near,
    "link_todos": tools_module.link_todos,
    "regenerate_embedding": tools_module.regenerate_embedding,
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


def test_registries_do_not_drift():
    """
    Every registry that names tools must name the SAME tools.

    There are five of them and they were previously hand-synced, which is how
    bring_your_own ended up in the full loadout with no schema. TOOL_GROUPS is the
    source; the others must agree with it.
    """
    from src.Omnispindle.mcp_handler import get_tool_functions
    from src.Omnispindle.tool_loadouts import _BASE_LOADOUTS
    from src.Omnispindle.tool_metadata import TOOL_GROUPS

    groups = set(TOOL_GROUPS)

    # 'full' is derived from TOOL_GROUPS, so this asserts the derivation stays wired.
    assert set(_BASE_LOADOUTS["full"]) == groups, "full loadout drifted from TOOL_GROUPS"

    # The remote JSON-RPC handler serves everything EXCEPT the local-only exemptions.
    missing = groups - set(TOOL_SCHEMAS) - _REMOTE_EXEMPT
    extra = set(TOOL_SCHEMAS) - groups
    assert not missing, f"in TOOL_GROUPS but no TOOL_SCHEMAS entry: {sorted(missing)}"
    assert not extra, f"in TOOL_SCHEMAS but not registered in TOOL_GROUPS: {sorted(extra)}"

    # Dispatch table must cover exactly what we advertise a schema for.
    dispatch = set(get_tool_functions())
    assert dispatch == set(TOOL_SCHEMAS), (
        f"tools/call dispatch != TOOL_SCHEMAS; "
        f"only-in-dispatch={sorted(dispatch - set(TOOL_SCHEMAS))} "
        f"only-in-schemas={sorted(set(TOOL_SCHEMAS) - dispatch)}"
    )

    # This test's own map has to keep up too.
    assert set(TOOL_FUNCTION_MAP) == groups, (
        f"TOOL_FUNCTION_MAP drifted from TOOL_GROUPS: "
        f"{sorted(groups ^ set(TOOL_FUNCTION_MAP))}"
    )


def test_local_only_asymmetries_are_deliberate():
    """
    Pin the two known asymmetries so they stay choices rather than accidents.

    bring_your_own executes arbitrary code — it is LOCAL_ONLY and deliberately has
    no schema and no entry in the remote dispatch table, so the remote JSON-RPC
    handler cannot reach it at all.

    list_projects touches the filesystem, so it is filtered out of remote tools/list
    by mode='remote' — but it IS in the remote dispatch table and therefore callable
    by name. Discovery is narrowed; capability is not. That asymmetry is intentional
    (it mirrors loadouts, which shrink tools/list without gating tools/call).
    """
    from src.Omnispindle.mcp_handler import get_tool_functions
    from src.Omnispindle.tool_loadouts import get_loadout
    from src.Omnispindle.tool_metadata import ToolAccessLevel, TOOL_ACCESS_LEVELS

    assert TOOL_ACCESS_LEVELS["bring_your_own"] == ToolAccessLevel.LOCAL_ONLY
    assert "bring_your_own" not in TOOL_SCHEMAS
    assert "bring_your_own" not in get_tool_functions()

    assert TOOL_ACCESS_LEVELS["list_projects"] == ToolAccessLevel.LOCAL_ONLY
    assert "list_projects" not in get_loadout("full", mode="remote")
    assert "list_projects" in get_tool_functions()


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
