"""
Unit tests for tool_loadouts module.

Tests centralized loadout definitions and mode-based filtering.
"""

import pytest
from src.Omnispindle.tool_loadouts import (
    get_loadout,
    get_all_loadouts,
    get_loadout_names,
    get_loadout_info
)


class TestToolLoadouts:
    """Test suite for tool loadout management."""

    def test_local_mode_includes_all_tools(self):
        """Local mode should include all tools including local-only."""
        full = get_loadout("full", mode="local")
        assert "bring_your_own" in full
        assert "list_projects" in full
        assert len(full) == 30  # All tools

    def test_remote_mode_filters_local_only(self):
        """Remote mode should exclude local-only tools."""
        full = get_loadout("full", mode="remote")
        assert "bring_your_own" not in full
        assert "list_projects" not in full
        assert len(full) == 28  # Excluding 2 local-only

    def test_write_only_loadout(self):
        """Write-only loadout should only have create/update/delete tools."""
        write_only = get_loadout("write_only", mode="local")
        assert "add_todo" in write_only
        assert "update_todo" in write_only
        assert "delete_todo" in write_only
        assert "mark_todo_complete" in write_only
        assert "query_todos" not in write_only
        assert "get_todo" not in write_only
        assert len(write_only) == 6

    def test_read_only_loadout(self):
        """Read-only loadout should only have query/get tools."""
        read_only = get_loadout("read_only", mode="local")
        assert "query_todos" in read_only
        assert "get_todo" in read_only
        assert "list_todos_by_status" in read_only
        assert "add_todo" not in read_only
        assert "update_todo" not in read_only
        assert "delete_todo" not in read_only
        assert len(read_only) == 8

    def test_lightweight_has_minimal_token_cost(self):
        """Lightweight loadout should have 10 tools for token optimization."""
        lightweight = get_loadout("lightweight", mode="local")
        assert len(lightweight) == 10
        # Should include core functionality
        assert "add_todo" in lightweight
        assert "query_todos" in lightweight
        assert "get_todo" in lightweight
        assert "mark_todo_complete" in lightweight

    def test_basic_loadout(self):
        """Basic loadout should have 7 core CRUD tools."""
        basic = get_loadout("basic", mode="local")
        assert len(basic) == 7
        assert "add_todo" in basic
        assert "query_todos" in basic
        assert "update_todo" in basic
        assert "get_todo" in basic
        assert "mark_todo_complete" in basic

    def test_minimal_loadout(self):
        """Minimal loadout should have only 4 essential tools."""
        minimal = get_loadout("minimal", mode="local")
        assert len(minimal) == 4
        assert "add_todo" in minimal
        assert "query_todos" in minimal
        assert "get_todo" in minimal
        assert "mark_todo_complete" in minimal

    def test_lessons_loadout(self):
        """Lessons loadout should have 7 knowledge management tools."""
        lessons = get_loadout("lessons", mode="local")
        assert len(lessons) == 7
        assert "add_lesson" in lessons
        assert "get_lesson" in lessons
        assert "search_lessons" in lessons

    def test_admin_loadout(self):
        """Admin loadout should have administrative and session tools."""
        admin = get_loadout("admin", mode="local")
        assert len(admin) == 13
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
        assert info["name"] == "basic"
        assert info["tool_count"] == 7
        assert "tools" in info
        assert "description" in info
        assert len(info["tools"]) == 7

    def test_invalid_loadout_defaults_to_full(self):
        """Invalid loadout name should default to full loadout."""
        result = get_loadout("invalid_loadout_name", mode="local")
        full = get_loadout("full", mode="local")
        assert result == full

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
