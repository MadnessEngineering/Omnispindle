"""tools/call argument validation.

Regression guard for the day three remote calls (create_quest without `project`,
link_todos with a `todo_ids` array, search_todos with a `project` kwarg) each came
back as -32603 "Internal error" — the calling agent could not see that it had
simply passed the wrong arguments, and gave up on MCP writes entirely.
"""

from src.Omnispindle.mcp_handler import (
    TOOL_SCHEMAS,
    _param_signature,
    _schemas_at_level,
    _tool_params,
    _validate_tool_arguments,
    get_tool_functions,
)


def _check(tool_name, arguments):
    return _validate_tool_arguments(tool_name, get_tool_functions()[tool_name], arguments)


def test_missing_required_param_is_named():
    err = _check("create_quest", {"name": "Q", "description": "goal"})
    assert err is not None
    assert "'project'" in err
    assert "name*, description*, project*" in err


def test_unknown_param_is_named():
    err = _check("search_todos", {"query": "dream funnel", "project": "omnispindle"})
    assert err is not None
    assert "unknown 'project'" in err
    assert "query*" in err


def test_missing_and_unknown_reported_together():
    err = _check("link_todos", {"todo_ids": ["a", "b"]})
    assert "missing required 'blocker_id', 'blocked_id'" in err
    assert "unknown 'todo_ids'" in err


def test_valid_arguments_pass():
    assert _check("create_quest", {"name": "Q", "description": "g", "project": "omnispindle"}) is None
    assert _check("query_todos", {}) is None
    assert _check("get_todo", {"todo_id": "abc"}) is None


def test_ctx_is_never_demanded_from_the_client():
    """ctx is server-supplied; it must not show up as a required param."""
    functions = get_tool_functions()
    for name, func in functions.items():
        accepted, required, _ = _tool_params(name, func)
        assert "ctx" not in accepted and "ctx" not in required, name


def test_every_dispatched_tool_is_introspectable():
    """A tool that swallows **kwargs would silently skip validation."""
    opaque = []
    for name, func in get_tool_functions().items():
        accepted, _, accepts_kwargs = _tool_params(name, func)
        if accepts_kwargs and not accepted:
            opaque.append(name)
    assert not opaque, f"tools with no introspectable params: {opaque}"


def test_param_line_appears_in_every_listed_description():
    """tools/list prose must state the params, at every doc level."""
    for level in ("minimal", "basic", "full"):
        for name, schema in _schemas_at_level(level).items():
            props = TOOL_SCHEMAS[name].get("inputSchema", {}).get("properties", {})
            if not props:
                continue
            assert "\nParams: " in schema["description"], f"{name} @ {level}"
            for param in props:
                assert param in schema["description"], f"{name}.{param} missing @ {level}"


def test_param_line_marks_required():
    desc = _schemas_at_level("basic")["create_quest"]["description"]
    assert desc.rstrip().endswith("Params: name*, description*, project*, chains, tags, success_criteria (* = required)")


def test_param_signature_without_required_params():
    assert _param_signature(("status", "limit"), ()) == "status, limit"
    assert _param_signature((), ()) == "(no parameters)"
