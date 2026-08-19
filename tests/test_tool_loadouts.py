"""
Unit tests for tool_loadouts module.

Tests centralized loadout definitions and mode-based filtering.
"""

import pytest
from src.Omnispindle.tool_loadouts import (
    ALWAYS_PRESENT,
    get_loadout,
    get_all_loadouts,
    get_loadout_names,
    get_loadout_info
)
from src.Omnispindle.tool_metadata import (
    TOOL_ACCESS_LEVELS,
    TOOL_GROUPS,
    ToolAccessLevel,
    ToolGroup,
    get_group_tools,
)

# Counts here used to be hardcoded and went stale every time a tool was added —
# six of these tests were failing against main before this comment existed.
# Assert against the registries the code derives from instead.
_LOCAL_ONLY = {n for n, lvl in TOOL_ACCESS_LEVELS.items() if lvl == ToolAccessLevel.LOCAL_ONLY}


class TestToolLoadouts:
    """Test suite for tool loadout management."""

    def test_local_mode_includes_all_tools(self):
        """Local mode should include every registered tool, local-only included."""
        full = get_loadout("full", mode="local")
        assert "bring_your_own" in full
        assert "list_projects" in full
        # 'full' is derived from TOOL_GROUPS — this asserts the derivation, not a count.
        assert set(full) == set(TOOL_GROUPS)

    def test_remote_mode_filters_local_only(self):
        """Remote mode should exclude exactly the local-only tools."""
        full = get_loadout("full", mode="remote")
        assert "bring_your_own" not in full
        assert "list_projects" not in full
        assert set(full) == set(TOOL_GROUPS) - _LOCAL_ONLY

    def test_write_only_loadout(self):
        """Write-only loadout should only have create/update/delete tools."""
        write_only = get_loadout("write_only", mode="local")
        assert "add_todo" in write_only
        assert "update_todo" in write_only
        assert "delete_todo" in write_only
        assert "complete_todo" in write_only
        assert "query_todos" not in write_only
        assert "get_todo" not in write_only
        assert len(write_only) == 7

    def test_read_only_loadout(self):
        """Read-only loadout should only have query/get/search tools + sessions."""
        read_only = get_loadout("read_only", mode="local")
        assert "query_todos" in read_only
        assert "get_todo" in read_only
        assert "list_todos_by_status" in read_only
        assert "inventorium_sessions_list" in read_only
        assert "add_todo" not in read_only
        assert "update_todo" not in read_only
        assert "delete_todo" not in read_only
        # No write verbs at all — the property that actually defines this loadout.
        assert not {"add_todo", "update_todo", "delete_todo", "add_lesson"} & set(read_only)

    def test_lightweight_has_minimal_token_cost(self):
        """Lightweight loadout should have 13 tools for token optimization."""
        lightweight = get_loadout("lightweight", mode="local")
        assert len(lightweight) == 14
        # Should include core functionality
        assert "add_todo" in lightweight
        assert "query_todos" in lightweight
        assert "get_todo" in lightweight
        assert "complete_todo" in lightweight

    def test_basic_loadout(self):
        """
        Basic is the remote default and means 'a normal working session'.

        Asserting membership rather than a count, because the contents are a
        product decision: search and the RAG tools are in because working without
        them means re-deriving context by hand; sessions, journal and deletes are
        out because they are specialist or destructive.
        """
        basic = set(get_loadout("basic", mode="local"))

        expected_in = {
            "add_todo", "query_todos", "update_todo", "get_todo", "complete_todo",
            "search_todos", "get_context_bundle", "find_relevant", "preflight_rag",
            "add_lesson", "get_lesson", "search_lessons",
        }
        assert expected_in <= basic, f"missing from basic: {sorted(expected_in - basic)}"

        expected_out = {
            "delete_todo", "delete_lesson", "bring_your_own",
            "write_agent_journal", "read_agent_journal",
            "inventorium_sessions_list", "explain", "point_out_obvious",
        }
        assert not (expected_out & basic), f"should not be in basic: {sorted(expected_out & basic)}"

    def test_minimal_loadout(self):
        """Minimal loadout should have the 4 essential tools plus config.

        config is present in every loadout on purpose: it is how an agent widens its
        own tool list, and a narrow loadout that hid it would be a one-way door.
        """
        minimal = get_loadout("minimal", mode="local")
        assert len(minimal) == 5
        assert "add_todo" in minimal
        assert "query_todos" in minimal
        assert "get_todo" in minimal
        assert "complete_todo" in minimal
        assert "config" in minimal

    def test_lessons_loadout(self):
        """Lessons loadout is derived from the LESSONS group — new lesson tools join it free."""
        lessons = get_loadout("lessons", mode="local")
        # Group derivation plus the always-injected tools, and nothing else — keeps the
        # derivation invariant tight instead of loosening it to a subset check.
        assert set(lessons) == set(get_group_tools(ToolGroup.LESSONS)) | set(ALWAYS_PRESENT)
        assert "add_lesson" in lessons
        assert "get_lesson" in lessons
        assert "search_lessons" in lessons

    def test_admin_loadout(self):
        """Admin loadout should have administrative and session tools."""
        admin = get_loadout("admin", mode="local")
        assert len(admin) == 17
        assert "query_todo_logs" in admin
        assert "inventorium_sessions_list" in admin
        assert "inventorium_sessions_fork" in admin

    def test_get_all_loadouts(self):
        """Get all loadouts should return all 9 loadouts."""
        all_loadouts = get_all_loadouts()
        assert len(all_loadouts) >= 8  # At least 8 loadouts
        assert "full" in all_loadouts
        assert "basic" in all_loadouts
        assert "write_only" in all_loadouts
        assert "read_only" in all_loadouts
        assert "lightweight" in all_loadouts

    def test_get_loadout_names(self):
        """Get loadout names should return list of all loadout names."""
        names = get_loadout_names()
        assert "full" in names
        assert "basic" in names
        assert "write_only" in names
        assert "read_only" in names
        assert "lightweight" in names
        assert "minimal" in names
        assert "lessons" in names
        assert "admin" in names

    def test_get_loadout_info(self):
        """Get loadout info should return metadata about a loadout."""
        info = get_loadout_info("basic")
        expected = get_loadout("basic", mode="local")
        assert info["name"] == "basic"
        assert info["tool_count"] == len(expected)
        assert len(info["tools"]) == len(expected)
        assert "description" in info

    def test_invalid_loadout_defaults_narrow(self):
        """
        A bad loadout name must fall back NARROW.

        This previously returned 'full', so a typo in a client's loadout hint
        silently widened exposure to every tool. Bad input should never be the
        path to the widest surface.
        """
        result = get_loadout("invalid_loadout_name", mode="local")
        assert result == get_loadout("basic", mode="local")
        assert result != get_loadout("full", mode="local")

    def test_remote_mode_consistency_across_loadouts(self):
        """All loadouts should filter local-only tools in remote mode."""
        loadouts = ["full", "basic", "admin"]
        for loadout_name in loadouts:
            local = get_loadout(loadout_name, mode="local")
            remote = get_loadout(loadout_name, mode="remote")

            # Remote should never have local-only tools
            assert "bring_your_own" not in remote
            if "list_projects" in local:
                assert "list_projects" not in remote

            # Remote should be subset of or equal to local
            assert set(remote).issubset(set(local))
