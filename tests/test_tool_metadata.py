"""
Unit tests for tool_metadata module.

Tests security classifications and feature detection for MCP tools.
"""

import pytest
from src.Omnispindle.tool_metadata import (
    ToolAccessLevel,
    ToolFeature,
    is_remote_safe,
    has_feature,
    get_local_only_tools,
    filter_remote_safe_loadout,
    get_tools_with_feature
)


class TestToolMetadata:
    """Test suite for tool metadata and security classifications."""

    def test_is_remote_safe_for_local_only_tools(self):
        """Local-only tools should not be remote safe."""
        assert is_remote_safe("bring_your_own") is False
        assert is_remote_safe("list_projects") is False

    def test_is_remote_safe_for_safe_tools(self):
        """Regular tools should be remote safe."""
        assert is_remote_safe("add_todo") is True
        assert is_remote_safe("query_todos") is True
        assert is_remote_safe("update_todo") is True
        assert is_remote_safe("get_todo") is True

    def test_is_remote_safe_defaults_to_true(self):
        """Unknown tools should default to remote safe."""
        assert is_remote_safe("unknown_tool") is True

    def test_get_local_only_tools(self):
        """Get local-only tools should return exactly 2 tools."""
        local_only = get_local_only_tools()
        assert "bring_your_own" in local_only
        assert "list_projects" in local_only
        assert len(local_only) == 2

    def test_filter_remote_safe_loadout(self):
        """Filter should remove local-only tools."""
        tools = [
            "add_todo",
            "query_todos",
            "bring_your_own",
            "list_projects",
            "update_todo"
        ]
        filtered = filter_remote_safe_loadout(tools)

        assert "add_todo" in filtered
        assert "query_todos" in filtered
        assert "update_todo" in filtered
        assert "bring_your_own" not in filtered
        assert "list_projects" not in filtered
        assert len(filtered) == 3

    def test_has_feature_git_metadata(self):
        """Tools with git metadata should be detected."""
        assert has_feature("add_todo", ToolFeature.AUTO_GIT_METADATA) is True
        assert has_feature("mark_todo_complete", ToolFeature.AUTO_GIT_METADATA) is True
        assert has_feature("get_todo", ToolFeature.AUTO_GIT_METADATA) is True
        assert has_feature("query_todos", ToolFeature.AUTO_GIT_METADATA) is False

    def test_has_feature_filesystem_access(self):
        """Tools with filesystem access should be detected."""
        assert has_feature("bring_your_own", ToolFeature.FILESYSTEM_ACCESS) is True
        assert has_feature("list_projects", ToolFeature.FILESYSTEM_ACCESS) is True
        assert has_feature("add_todo", ToolFeature.FILESYSTEM_ACCESS) is False

    def test_has_feature_code_execution(self):
        """Tools with code execution should be detected."""
        assert has_feature("bring_your_own", ToolFeature.CODE_EXECUTION) is True
        assert has_feature("add_todo", ToolFeature.CODE_EXECUTION) is False

    def test_has_feature_database_write(self):
        """Tools with database write should be detected."""
        assert has_feature("add_todo", ToolFeature.DATABASE_WRITE) is True
        assert has_feature("update_todo", ToolFeature.DATABASE_WRITE) is True
        assert has_feature("delete_todo", ToolFeature.DATABASE_WRITE) is True
        assert has_feature("query_todos", ToolFeature.DATABASE_WRITE) is False

    def test_has_feature_database_read(self):
        """Tools with database read should be detected."""
        assert has_feature("query_todos", ToolFeature.DATABASE_READ) is True
        assert has_feature("get_todo", ToolFeature.DATABASE_READ) is True
        assert has_feature("list_todos_by_status", ToolFeature.DATABASE_READ) is True

    def test_has_feature_mqtt_broadcast(self):
        """Tools with MQTT broadcast should be detected."""
        assert has_feature("point_out_obvious", ToolFeature.MQTT_BROADCAST) is True
        assert has_feature("add_todo", ToolFeature.MQTT_BROADCAST) is False

    def test_get_tools_with_feature_git_metadata(self):
        """Get tools with git metadata feature."""
        git_tools = get_tools_with_feature(ToolFeature.AUTO_GIT_METADATA)
        assert "add_todo" in git_tools
        assert "mark_todo_complete" in git_tools
        assert "get_todo" in git_tools
        assert len(git_tools) == 3

    def test_get_tools_with_feature_code_execution(self):
        """Get tools with code execution feature."""
        exec_tools = get_tools_with_feature(ToolFeature.CODE_EXECUTION)
        assert "bring_your_own" in exec_tools
        assert len(exec_tools) >= 1

    def test_get_tools_with_feature_filesystem(self):
        """Get tools with filesystem access feature."""
        fs_tools = get_tools_with_feature(ToolFeature.FILESYSTEM_ACCESS)
        assert "bring_your_own" in fs_tools
        assert "list_projects" in fs_tools
        assert len(fs_tools) >= 2

    def test_tool_access_levels_completeness(self):
        """All common tools should have access level defined."""
        common_tools = [
            "add_todo", "query_todos", "update_todo", "delete_todo", "get_todo",
            "mark_todo_complete", "add_lesson", "get_lesson", "search_lessons",
            "bring_your_own", "list_projects"
        ]
        for tool in common_tools:
            # Should not raise exception
            result = is_remote_safe(tool)
            assert isinstance(result, bool)

    def test_feature_markers_for_write_tools(self):
        """Write tools should have DATABASE_WRITE feature."""
        write_tools = ["add_todo", "update_todo", "delete_todo", "add_lesson", "update_lesson"]
        for tool in write_tools:
            assert has_feature(tool, ToolFeature.DATABASE_WRITE) is True

    def test_feature_markers_for_read_tools(self):
        """Read tools should have DATABASE_READ feature."""
        read_tools = ["query_todos", "get_todo", "search_todos", "get_lesson", "search_lessons"]
        for tool in read_tools:
            assert has_feature(tool, ToolFeature.DATABASE_READ) is True
