"""
Tool metadata for security classification and feature detection.

This module provides security classifications and feature markers for all MCP tools,
enabling proper filtering between local and remote deployment modes.
"""

from typing import Set, Dict, List
from enum import Enum


class ToolAccessLevel(str, Enum):
    """Security classification for tools."""
    REMOTE_SAFE = "remote_safe"      # Can be exposed remotely
    LOCAL_ONLY = "local_only"        # Requires local filesystem
    PRIVILEGED = "privileged"        # Requires admin access


class ToolFeature(str, Enum):
    """Features that tools may provide."""
    AUTO_GIT_METADATA = "auto_git_metadata"      # Adds git context automatically
    FILESYSTEM_ACCESS = "filesystem_access"       # Reads/writes filesystem
    CODE_EXECUTION = "code_execution"            # Executes arbitrary code
    MQTT_BROADCAST = "mqtt_broadcast"            # Publishes to MQTT
    DATABASE_WRITE = "database_write"            # Modifies database
    DATABASE_READ = "database_read"              # Reads database


# Tool classification registry
TOOL_ACCESS_LEVELS: Dict[str, ToolAccessLevel] = {
    # Local-only tools (security risk if remote)
    "bring_your_own": ToolAccessLevel.LOCAL_ONLY,
    "list_projects": ToolAccessLevel.LOCAL_ONLY,

    # Remote-safe tools (all others default to REMOTE_SAFE)
    # Explicitly listing for clarity
    "add_todo": ToolAccessLevel.REMOTE_SAFE,
    "query_todos": ToolAccessLevel.REMOTE_SAFE,
    "update_todo": ToolAccessLevel.REMOTE_SAFE,
    "delete_todo": ToolAccessLevel.REMOTE_SAFE,
    "get_todo": ToolAccessLevel.REMOTE_SAFE,
    "mark_todo_complete": ToolAccessLevel.REMOTE_SAFE,
    "list_todos_by_status": ToolAccessLevel.REMOTE_SAFE,
    "search_todos": ToolAccessLevel.REMOTE_SAFE,
    "list_project_todos": ToolAccessLevel.REMOTE_SAFE,
    "add_lesson": ToolAccessLevel.REMOTE_SAFE,
    "get_lesson": ToolAccessLevel.REMOTE_SAFE,
    "update_lesson": ToolAccessLevel.REMOTE_SAFE,
    "delete_lesson": ToolAccessLevel.REMOTE_SAFE,
    "search_lessons": ToolAccessLevel.REMOTE_SAFE,
    "grep_lessons": ToolAccessLevel.REMOTE_SAFE,
    "list_lessons": ToolAccessLevel.REMOTE_SAFE,
    "query_todo_logs": ToolAccessLevel.REMOTE_SAFE,
    "explain": ToolAccessLevel.REMOTE_SAFE,
    "add_explanation": ToolAccessLevel.REMOTE_SAFE,
    "point_out_obvious": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_list": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_get": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_create": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_spawn": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_fork": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_genealogy": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_sessions_tree": ToolAccessLevel.REMOTE_SAFE,
    "inventorium_todos_link_session": ToolAccessLevel.REMOTE_SAFE,
}


# Feature markers for tools
TOOL_FEATURES: Dict[str, Set[ToolFeature]] = {
    "bring_your_own": {
        ToolFeature.CODE_EXECUTION,
        ToolFeature.FILESYSTEM_ACCESS,
    },
    "list_projects": {
        ToolFeature.FILESYSTEM_ACCESS,
    },
    "get_todo": {
        ToolFeature.AUTO_GIT_METADATA,  # Only in local mode
        ToolFeature.DATABASE_READ,
    },
    "mark_todo_complete": {
        ToolFeature.AUTO_GIT_METADATA,  # Only in local mode
        ToolFeature.DATABASE_WRITE,
    },
    "add_todo": {
        ToolFeature.AUTO_GIT_METADATA,  # Only in local mode
        ToolFeature.DATABASE_WRITE,
    },
    "point_out_obvious": {
        ToolFeature.MQTT_BROADCAST,
    },
    "query_todos": {
        ToolFeature.DATABASE_READ,
    },
    "update_todo": {
        ToolFeature.DATABASE_WRITE,
    },
    "delete_todo": {
        ToolFeature.DATABASE_WRITE,
    },
    "list_todos_by_status": {
        ToolFeature.DATABASE_READ,
    },
    "search_todos": {
        ToolFeature.DATABASE_READ,
    },
    "list_project_todos": {
        ToolFeature.DATABASE_READ,
    },
    "add_lesson": {
        ToolFeature.DATABASE_WRITE,
    },
    "get_lesson": {
        ToolFeature.DATABASE_READ,
    },
    "update_lesson": {
        ToolFeature.DATABASE_WRITE,
    },
    "delete_lesson": {
        ToolFeature.DATABASE_WRITE,
    },
    "search_lessons": {
        ToolFeature.DATABASE_READ,
    },
    "grep_lessons": {
        ToolFeature.DATABASE_READ,
    },
    "list_lessons": {
        ToolFeature.DATABASE_READ,
    },
    "query_todo_logs": {
        ToolFeature.DATABASE_READ,
    },
}


def is_remote_safe(tool_name: str) -> bool:
    """
    Check if tool can be safely exposed remotely.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if tool can be exposed remotely, False if local-only
    """
    return TOOL_ACCESS_LEVELS.get(tool_name, ToolAccessLevel.REMOTE_SAFE) == ToolAccessLevel.REMOTE_SAFE


def has_feature(tool_name: str, feature: ToolFeature) -> bool:
    """
    Check if tool has specific feature.

    Args:
        tool_name: Name of the tool
        feature: Feature to check for

    Returns:
        True if tool has the feature, False otherwise
    """
    return feature in TOOL_FEATURES.get(tool_name, set())


def get_local_only_tools() -> Set[str]:
    """
    Get all tools that require local filesystem access.

    Returns:
        Set of tool names that can only run locally
    """
    return {
        tool for tool, level in TOOL_ACCESS_LEVELS.items()
        if level == ToolAccessLevel.LOCAL_ONLY
    }


def filter_remote_safe_loadout(tools: List[str]) -> List[str]:
    """
    Filter loadout to only include remote-safe tools.

    Args:
        tools: List of tool names to filter

    Returns:
        Filtered list containing only remote-safe tools
    """
    return [tool for tool in tools if is_remote_safe(tool)]


def get_tools_with_feature(feature: ToolFeature) -> Set[str]:
    """
    Get all tools that have a specific feature.

    Args:
        feature: Feature to search for

    Returns:
        Set of tool names that have the feature
    """
    return {
        tool for tool, features in TOOL_FEATURES.items()
        if feature in features
    }
