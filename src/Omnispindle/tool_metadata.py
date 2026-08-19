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


class ToolTier(str, Enum):
    """Subscription tier required to use a tool."""
    FREE = "free"       # Available to all users
    PRO = "pro"         # Requires Madness Pass subscription


class ToolGroup(str, Enum):
    """
    Functional grouping — what area of the server a tool belongs to.

    Exactly one group per tool. This is the SOURCE that loadouts derive from, not a
    parallel list to keep in sync: `_BASE_LOADOUTS["full"]` and the single-area
    loadouts are computed from TOOL_GROUPS, so adding a tool here is what makes it
    exist everywhere else.

    Distinct from ToolFeature, which is a many-to-many capability vocabulary
    (a tool can be both DATABASE_READ and MQTT_BROADCAST while belonging to one group).
    """
    TODOS = "todos"
    LESSONS = "lessons"
    QUESTS = "quests"
    RAG = "rag"                  # context assembly + semantic retrieval
    SESSIONS = "sessions"        # Inventorium chat sessions
    JOURNAL = "journal"          # cross-agent journal
    ADMIN = "admin"              # audit logs, projects, explanations, utilities
    CUSTOM_CODE = "custom_code"  # arbitrary execution — local only


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
    "complete_todo": ToolAccessLevel.REMOTE_SAFE,
    "list_todos_by_status": ToolAccessLevel.REMOTE_SAFE,
    "search_todos": ToolAccessLevel.REMOTE_SAFE,
    "list_project_todos": ToolAccessLevel.REMOTE_SAFE,
    "add_lesson": ToolAccessLevel.REMOTE_SAFE,
    "get_lesson": ToolAccessLevel.REMOTE_SAFE,
    "update_lesson": ToolAccessLevel.REMOTE_SAFE,
    "delete_lesson": ToolAccessLevel.REMOTE_SAFE,
    "regenerate_embedding": ToolAccessLevel.REMOTE_SAFE,
    "config": ToolAccessLevel.REMOTE_SAFE,
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
    "get_context_bundle": ToolAccessLevel.REMOTE_SAFE,
    "find_relevant": ToolAccessLevel.REMOTE_SAFE,
    "preflight_rag": ToolAccessLevel.REMOTE_SAFE,
    "write_agent_journal": ToolAccessLevel.REMOTE_SAFE,
    "read_agent_journal": ToolAccessLevel.REMOTE_SAFE,
    # Quest system (Quest → Chains → Todos)
    "create_quest": ToolAccessLevel.REMOTE_SAFE,
    "check_quest": ToolAccessLevel.REMOTE_SAFE,
    "list_quests": ToolAccessLevel.REMOTE_SAFE,
    "link_quest": ToolAccessLevel.REMOTE_SAFE,
    "update_quest": ToolAccessLevel.REMOTE_SAFE,
}


# Functional grouping — the single source loadouts derive from.
# Every tool the server can dispatch MUST appear here exactly once;
# tests/test_schema_consistency.py enforces that against the other registries.
TOOL_GROUPS: Dict[str, ToolGroup] = {
    # Todos
    "add_todo": ToolGroup.TODOS,
    "query_todos": ToolGroup.TODOS,
    "update_todo": ToolGroup.TODOS,
    "delete_todo": ToolGroup.TODOS,
    "get_todo": ToolGroup.TODOS,
    "complete_todo": ToolGroup.TODOS,
    "list_todos_by_status": ToolGroup.TODOS,
    "search_todos": ToolGroup.TODOS,
    "list_project_todos": ToolGroup.TODOS,
    "query_todos_near": ToolGroup.TODOS,
    "link_todos": ToolGroup.TODOS,

    # Lessons
    "add_lesson": ToolGroup.LESSONS,
    "get_lesson": ToolGroup.LESSONS,
    "update_lesson": ToolGroup.LESSONS,
    "delete_lesson": ToolGroup.LESSONS,
    "regenerate_embedding": ToolGroup.LESSONS,
    # Server-side client preferences (loadout / doc level) — a utility.
    "config": ToolGroup.ADMIN,
    "search_lessons": ToolGroup.LESSONS,
    "grep_lessons": ToolGroup.LESSONS,
    "list_lessons": ToolGroup.LESSONS,

    # Quests (Quest → Chains → Todos)
    "create_quest": ToolGroup.QUESTS,
    "check_quest": ToolGroup.QUESTS,
    "list_quests": ToolGroup.QUESTS,
    "link_quest": ToolGroup.QUESTS,
    "update_quest": ToolGroup.QUESTS,

    # RAG / context
    "get_context_bundle": ToolGroup.RAG,
    "find_relevant": ToolGroup.RAG,
    "preflight_rag": ToolGroup.RAG,

    # Inventorium sessions
    "inventorium_sessions_list": ToolGroup.SESSIONS,
    "inventorium_sessions_get": ToolGroup.SESSIONS,
    "inventorium_sessions_create": ToolGroup.SESSIONS,
    "inventorium_sessions_spawn": ToolGroup.SESSIONS,
    "inventorium_sessions_fork": ToolGroup.SESSIONS,
    "inventorium_sessions_genealogy": ToolGroup.SESSIONS,
    "inventorium_sessions_tree": ToolGroup.SESSIONS,
    "inventorium_todos_link_session": ToolGroup.SESSIONS,

    # Agent journal
    "write_agent_journal": ToolGroup.JOURNAL,
    "read_agent_journal": ToolGroup.JOURNAL,

    # Admin / system
    "query_todo_logs": ToolGroup.ADMIN,
    "list_projects": ToolGroup.ADMIN,
    "explain": ToolGroup.ADMIN,
    "add_explanation": ToolGroup.ADMIN,
    "point_out_obvious": ToolGroup.ADMIN,

    # Custom code execution (local only)
    "bring_your_own": ToolGroup.CUSTOM_CODE,
}


def get_group_tools(group: ToolGroup) -> List[str]:
    """All tool names in a functional group, in registry order."""
    return [name for name, g in TOOL_GROUPS.items() if g == group]


def get_tool_group(tool_name: str) -> ToolGroup:
    """Group for a tool. Unregistered tools are ADMIN — visible, not silently hidden."""
    return TOOL_GROUPS.get(tool_name, ToolGroup.ADMIN)


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
    "complete_todo": {
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
    "regenerate_embedding": {
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
    "get_context_bundle": {
        ToolFeature.DATABASE_READ,
    },
    "find_relevant": {
        ToolFeature.DATABASE_READ,
    },
    "preflight_rag": {
        ToolFeature.DATABASE_READ,
    },
    "write_agent_journal": {
        ToolFeature.DATABASE_WRITE,
    },
    "read_agent_journal": {
        ToolFeature.DATABASE_READ,
    },
    "create_quest": {
        ToolFeature.DATABASE_WRITE,
    },
    "check_quest": {
        ToolFeature.DATABASE_READ,
    },
    "list_quests": {
        ToolFeature.DATABASE_READ,
    },
    "link_quest": {
        ToolFeature.DATABASE_WRITE,
    },
    "update_quest": {
        ToolFeature.DATABASE_WRITE,
    },
}


# Subscription tier requirements for tools
# Tools not listed here default to FREE (available to all users)
TOOL_TIERS: Dict[str, ToolTier] = {
    # Inventorium session tools — AI agent workspace (pro only)
    "inventorium_sessions_list": ToolTier.PRO,
    "inventorium_sessions_get": ToolTier.PRO,
    "inventorium_sessions_create": ToolTier.PRO,
    "inventorium_sessions_spawn": ToolTier.PRO,
    "inventorium_sessions_fork": ToolTier.PRO,
    "inventorium_sessions_genealogy": ToolTier.PRO,
    "inventorium_sessions_tree": ToolTier.PRO,
    "inventorium_todos_link_session": ToolTier.PRO,
    # Semantic search / RAG (pro only)
    "find_relevant": ToolTier.PRO,
    "preflight_rag": ToolTier.PRO,
    # MQTT broadcast (pro only)
    "point_out_obvious": ToolTier.PRO,
}


def is_pro_tool(tool_name: str) -> bool:
    """Check if a tool requires a Pro subscription."""
    return TOOL_TIERS.get(tool_name, ToolTier.FREE) == ToolTier.PRO


def get_pro_tools() -> Set[str]:
    """Get all tools that require a Pro subscription."""
    return {
        tool for tool, tier in TOOL_TIERS.items()
        if tier == ToolTier.PRO
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
