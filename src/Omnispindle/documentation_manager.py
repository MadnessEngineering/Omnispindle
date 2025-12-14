"""
Documentation manager for loadout-aware MCP tool documentation.

Provides different levels of documentation detail based on the OMNISPINDLE_TOOL_LOADOUT
to optimize token usage while maintaining helpful context for AI agents.
"""

import os
from typing import Dict, Any, Optional
from enum import Enum


class DocumentationLevel(str, Enum):
    """Documentation detail levels corresponding to tool loadouts."""
    MINIMAL = "minimal"      # Tool name + core function only
    BASIC = "basic"          # Ultra-concise docs (1 line + essential params)
    LESSONS = "lessons"      # Knowledge management focus
    ADMIN = "admin"          # Administrative context
    FULL = "full"           # Comprehensive docs with examples, field descriptions


class DocumentationManager:
    """
    Manages documentation strings for MCP tools based on loadout configuration.
    
    Provides token-efficient documentation that scales with the complexity needs
    of different MCP client configurations.
    """
    
    def __init__(self, loadout: str = None):
        """
        Initialize documentation manager.
        
        Args:
            loadout: Tool loadout level, defaults to OMNISPINDLE_TOOL_LOADOUT env var
        """
        self.loadout = loadout or os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full").lower()
        self.level = self._get_documentation_level()
    
    def _get_documentation_level(self) -> DocumentationLevel:
        """Map loadout to documentation level."""
        mapping = {
            "minimal": DocumentationLevel.MINIMAL,
            "basic": DocumentationLevel.BASIC,
            "lessons": DocumentationLevel.BASIC,  # Use basic level for lessons loadout
            "admin": DocumentationLevel.ADMIN,
            "full": DocumentationLevel.FULL,
            "hybrid_test": DocumentationLevel.BASIC
        }
        return mapping.get(self.loadout, DocumentationLevel.FULL)
    
    def get_tool_documentation(self, tool_name: str) -> str:
        """
        Get documentation string for a tool based on current loadout.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Documentation string appropriate for the loadout level
        """
        docs = TOOL_DOCUMENTATION.get(tool_name, {})
        return docs.get(self.level.value, docs.get("full", "Tool documentation not found."))
    
    def get_parameter_hint(self, tool_name: str) -> Optional[str]:
        """
        Get parameter hints for a tool if applicable to the current loadout.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Parameter hint string or None for minimal loadouts
        """
        if self.level in [DocumentationLevel.MINIMAL]:
            return None
        
        hints = PARAMETER_HINTS.get(tool_name, {})
        return hints.get(self.level.value, hints.get("basic"))


# Tool documentation organized by detail level
TOOL_DOCUMENTATION = {
    "add_todo": {
        "minimal": "Create task",
        "basic": "Create task. Returns ID and project stats.",
        "admin": "Create task with metadata (files[], tags[], phase, complexity, acceptance_criteria). Returns ID + counts.",
        "full": """Creates a task in the specified project with the given priority and target agent.

Supports the standardized metadata schema with fields for:
- Technical context: files[], components[], commit_hash, branch
- Project organization: phase, epic, tags[]
- State tracking: current_state, target_state, blockers[]
- Deliverables: deliverables[], acceptance_criteria[]
- Analysis: complexity (Low|Medium|High|Complex), confidence (1-5)

Returns a compact representation with the created todo ID and current project statistics.
Metadata is validated against the TodoMetadata schema for consistency."""
    },
    
    "query_todos": {
        "minimal": "Search todos",
        "basic": "Query with MongoDB filters. Ex: {status: 'pending', project: 'name'}",
        "admin": "MongoDB query with filters (status, project, priority, metadata.tags) and projections. User-scoped.",
        "full": """Query todos with flexible filtering options from user's database.

Supports MongoDB-style query syntax with filters like:
- {"status": "pending"} - Filter by status
- {"project": "omnispindle"} - Filter by project
- {"metadata.tags": {"$in": ["bug", "feature"]}} - Filter by metadata tags
- {"priority": {"$in": ["High", "Critical"]}} - Filter by priority
- {"created_at": {"$gte": timestamp}} - Date range filters

Projection parameter allows selecting specific fields to return.
All queries are user-scoped for data isolation."""
    },
    
    "update_todo": {
        "minimal": "Update todo",
        "basic": "Update todo. Fields: description, priority, status, metadata.",
        "admin": "Update todo (all fields + metadata). Validates schema, logs changes.",
        "full": """Update a todo with the provided changes.

Supports updating any field:
- Core fields: description, priority, status, target_agent, project
- Metadata fields: any field in the TodoMetadata schema
- Completion fields: completed_by, completion_comment

Metadata updates are validated against the schema. All changes are logged
for audit purposes. The updated_at timestamp is automatically set."""
    },
    
    "get_todo": {
        "minimal": "Get todo by ID",
        "basic": "Get todo by ID",
        "admin": "Get todo by ID. Returns full object with metadata.",
        "full": "Get a specific todo by ID. Returns the complete todo object including all metadata fields, completion tracking, and audit information."
    },
    
    "mark_todo_complete": {
        "minimal": "Complete todo",
        "basic": "Mark completed. Optional comment.",
        "admin": "Mark completed. Calculates duration, logs event, stores comment in metadata.",
        "full": """Mark a todo as completed with optional completion comment.

Automatically:
- Sets status to "completed"
- Records completion timestamp
- Calculates duration from creation to completion
- Updates completed_by field with user information
- Stores completion comment in metadata if provided
- Logs completion event for audit trail"""
    },
    
    "list_todos_by_status": {
        "minimal": "List by status",
        "basic": "List by status: pending|completed|initial|blocked|in_progress",
        "admin": "Filter by status (pending|completed|initial|blocked|in_progress). Returns with metadata summary.",
        "full": "List todos filtered by their status. Valid status values: pending, completed, initial, blocked, in_progress. Results are formatted for efficiency with truncated descriptions to reduce token usage while preserving essential information."
    },
    
    "list_project_todos": {
        "minimal": "List project todos",
        "basic": "List recent pending todos for project",
        "admin": "List recent pending todos for project. Quick status overview.",
        "full": "List recent active todos for a specific project. Only returns pending todos to focus on current work. Useful for getting a quick overview of project status and active tasks."
    },
    
    "search_todos": {
        "minimal": "Search todos",
        "basic": "Text search across fields. Use 'project:Name' for project filter.",
        "admin": "Regex text search across description, project, metadata. Supports 'project:Name' syntax.",
        "full": """Search todos with text search capabilities across specified fields.

Default search fields: description, project
Custom fields can be specified in the fields parameter.
Supports regex patterns and case-insensitive search.

Special formats:
- "project:ProjectName" - Search by specific project
- Regular text searches across description and metadata fields"""
    },
    
    "delete_todo": {
        "minimal": "Delete todo",
        "basic": "Delete todo by ID",
        "admin": "Delete todo by ID. Logs deletion.",
        "full": "Delete a todo item by its ID. The deletion is logged for audit purposes and the todo is permanently removed from the user's database."
    },
    
    "add_lesson": {
        "minimal": "Add lesson",
        "basic": "Add lesson to knowledge base",
        "admin": "Add lesson with language, topic, tags. Invalidates cache.",
        "full": "Add a new lesson learned to the knowledge base with specified language, topic, content, and optional tags. The lesson is assigned a unique ID and timestamp."
    },

    "get_lesson": {
        "minimal": "Get lesson",
        "basic": "Get lesson by ID",
        "admin": "Get lesson by ID from knowledge base.",
        "full": "Retrieve a specific lesson by its unique ID from the user's knowledge base."
    },

    "update_lesson": {
        "minimal": "Update lesson",
        "basic": "Update lesson by ID",
        "admin": "Update lesson fields. Invalidates tag cache if tags modified.",
        "full": "Update an existing lesson by its ID. Can modify any field including language, topic, lesson_learned content, and tags. Tag cache is automatically invalidated if tags are changed."
    },

    "delete_lesson": {
        "minimal": "Delete lesson",
        "basic": "Delete lesson by ID",
        "admin": "Delete lesson by ID. Invalidates cache.",
        "full": "Delete a lesson by its ID from the knowledge base. The lesson tag cache is automatically invalidated after deletion."
    },

    "search_lessons": {
        "minimal": "Search lessons",
        "basic": "Text search lessons",
        "admin": "Regex search across topic, lesson_learned, tags.",
        "full": "Search lessons with text search capabilities across specified fields. Default search fields are topic, lesson_learned, and tags. Supports regex patterns and case-insensitive search."
    },

    "grep_lessons": {
        "minimal": "Grep lessons",
        "basic": "Pattern match across topic and content",
        "admin": "Regex pattern matching across topic and lesson_learned.",
        "full": "Search lessons using grep-style pattern matching with regex support. Searches across both topic and lesson_learned fields with case-insensitive matching."
    },

    "list_lessons": {
        "minimal": "List lessons",
        "basic": "List all lessons (newest first)",
        "admin": "List lessons from knowledge base, sorted by date.",
        "full": "List all lessons from the knowledge base, sorted by creation date in descending order (newest first). Supports optional brief mode for compact results."
    },
    
    "query_todo_logs": {
        "minimal": "Query logs",
        "basic": "Query audit logs with filtering",
        "admin": "Query audit logs by type (create|update|delete|complete) and project. Pagination support.",
        "full": "Query the todo audit logs with filtering and pagination options. Filter by operation type (create, update, delete, complete) and project. Includes pagination with configurable page size."
    },

    "list_projects": {
        "minimal": "List projects",
        "basic": "List all valid projects",
        "admin": "List projects. include_details: False|True|'filemanager'.",
        "full": "List all valid projects from the centralized project management system. The include_details parameter controls output format: False for names only, True for full metadata including git URLs and paths, or \"filemanager\" for UI-optimized format."
    },

    "explain": {
        "minimal": "Explain topic",
        "basic": "Explain project or concept",
        "admin": "Explain projects/concepts. Projects get dynamic summary with activity.",
        "full": "Provides a detailed explanation for a project or concept. For projects, it dynamically generates a comprehensive summary including recent activity, status, and related information."
    },

    "add_explanation": {
        "minimal": "Add explanation",
        "basic": "Add static explanation to knowledge base",
        "admin": "Add explanation with topic, content, kind, author. Uses upsert.",
        "full": "Add a new static explanation to the knowledge base with specified topic, content, kind (concept, project, etc.), and author information. Uses upsert to update existing explanations."
    },

    "point_out_obvious": {
        "minimal": "Point obvious",
        "basic": "Point out obvious with humor",
        "admin": "Point out obvious with sarcasm level (1-10). Logs to MQTT.",
        "full": "Points out something obvious to the human user with varying levels of humor and sarcasm. Sarcasm level ranges from 1 (gentle) to 10 (maximum sass). Observations are logged and published to MQTT for system integration."
    },

    "bring_your_own": {
        "minimal": "Custom tool",
        "basic": "Run custom code (Python|JS|Bash)",
        "admin": "Execute custom code with timeout. Rate limited. Logs execution.",
        "full": "Temporarily hijack the MCP server to run custom tool code. Supports Python, JavaScript, and Bash runtimes with configurable timeout and argument passing. Includes rate limiting for non-admin users and comprehensive execution logging. Use with caution - allows arbitrary code execution."
    },

    "inventorium_sessions_list": {
        "minimal": "List chat sessions",
        "basic": "List chat sessions. Filter by project.",
        "admin": "List sessions (short IDs, msg counts, todos, MCP token). Filter by project.",
        "full": "List chat sessions for the authenticated user. Parameters: project (optional) filters on project slug/name, limit controls results (default 50, max 200). Returns session metadata including short_id, message_count, linked_todo_ids, status, and mcp_token for MCP integrations."
    },

    "inventorium_sessions_get": {
        "minimal": "Get chat session",
        "basic": "Get session details by ID",
        "admin": "Get session (messages, todos, MCP token, genealogy) by UUID.",
        "full": "Fetch a chat session by session_id. Returns complete document including messages, linked todos, genealogy metadata, MCP token, agentic tool, and timestamps. Requires ownership via Auth0/API key."
    },

    "inventorium_sessions_create": {
        "minimal": "Create session",
        "basic": "Create chat session for project",
        "admin": "Create session with title, tool, prompt. Generates MCP token.",
        "full": "Create a new chat session for a project. Parameters: project (required), title (optional), agentic_tool (default claude-code), initial_prompt (optional user message). Generates MCP session token automatically and persists it with the session."
    },

    "inventorium_sessions_spawn": {
        "minimal": "Spawn child session",
        "basic": "Spawn child session from parent with prompt",
        "admin": "Spawn child (inherits project/tool, links todo, seeds prompt).",
        "full": "Spawn a child session to delegate work. Parameters: parent_session_id (required), prompt (required), todo_id/title optional. Inherits project + agentic tool, links todo if provided, registers genealogy.child, and seeds prompt as first message."
    },

    "inventorium_todos_link_session": {
        "minimal": "Link todo to session",
        "basic": "Link todo to session (idempotent)",
        "admin": "Link todo to session. Updates both session and todo metadata.",
        "full": "Link an Omnispindle todo to a chat session. Parameters: todo_id, session_id. Adds todo to session.linked_todo_ids (no duplicates) and updates todo metadata with linked_session_ids for downstream tooling."
    },

    "inventorium_sessions_fork": {
        "minimal": "Fork session",
        "basic": "Clone session (optional: copy history/todos)",
        "admin": "Fork with transcript/todo control. Records genealogy.",
        "full": "Fork a session to branch into a new idea. Parameters include session_id, optional title, include_messages (default true), inherit_todos (default true), and initial_status to set the new branch state. Returns the new session with updated genealogy."
    },

    "inventorium_sessions_genealogy": {
        "minimal": "Session genealogy",
        "basic": "Get parents and children for session",
        "admin": "Get genealogy tree (ancestors, children, metadata).",
        "full": "Retrieve genealogy for a session: base session info, ordered parents, and direct children (forks + spawns). Useful for visual trees and navigation."
    },

    "inventorium_sessions_tree": {
        "minimal": "Session tree",
        "basic": "Get full session tree for project",
        "admin": "Build tree (roots + children) by project, limited to N sessions.",
        "full": "Fetch the full session tree (roots + nested children) for the authenticated user, optionally filtered by project. Useful for UI tree renderers."
    }
}

# Additional parameter hints for complex tools (only for basic+ levels)
PARAMETER_HINTS = {
    "add_todo": {
        "basic": "priority: Critical|High|Medium|Low; metadata: {key: val} pairs",
        "admin": "metadata: files[], tags[], phase, complexity, confidence(1-5), acceptance_criteria[]",
        "full": """Parameters:
- description (str, required): Task description (max 500 chars)
- project (str, required): Project name from valid projects list
- priority (str, optional): Critical|High|Medium|Low (default: Medium)
- target_agent (str, optional): user|claude|system (default: user)
- metadata (dict, optional): Structured metadata following TodoMetadata schema
  - files: ["path/to/file.py"] - Related files
  - tags: ["bug", "feature"] - Categorization tags
  - phase: "implementation" - Project phase
  - complexity: Low|Medium|High|Complex - Complexity assessment
  - confidence: 1-5 - Confidence level
  - acceptance_criteria: ["criterion1", "criterion2"] - Completion criteria"""
    },

    "query_todos": {
        "basic": "filter: {status: 'pending'}; projection: {field: 1}",
        "admin": "Nested queries: {metadata.tags: {$in: ['bug']}}",
        "full": """Parameters:
- filter (dict, optional): MongoDB-style query filter
  Examples: {"status": "pending"}, {"metadata.tags": {"$in": ["bug"]}}
- projection (dict, optional): Fields to include/exclude
  Examples: {"description": 1, "status": 1}, {"metadata": 0}
- limit (int, optional): Maximum number of results (default: 100)
- ctx (str, optional): Additional context for the query"""
    }
}


# Global documentation manager instance
_doc_manager = None

def get_documentation_manager() -> DocumentationManager:
    """Get global documentation manager instance."""
    global _doc_manager
    if _doc_manager is None:
        _doc_manager = DocumentationManager()
    return _doc_manager

def get_tool_doc(tool_name: str) -> str:
    """Convenience function to get tool documentation."""
    return get_documentation_manager().get_tool_documentation(tool_name)

def get_param_hint(tool_name: str) -> Optional[str]:
    """Convenience function to get parameter hints."""
    return get_documentation_manager().get_parameter_hint(tool_name)

def build_tool_docstring(tool_name: str, param_descriptions: dict = None) -> str:
    """
    Build a complete docstring for FastMCP with tool description and parameter descriptions.

    Args:
        tool_name: Name of the tool
        param_descriptions: Dict of {param_name: description}

    Returns:
        Formatted docstring with Args: section for FastMCP
    """
    doc = get_tool_doc(tool_name)

    if param_descriptions:
        args_section = "\n\nArgs:\n"
        for param, desc in param_descriptions.items():
            args_section += f"    {param}: {desc}\n"
        doc = doc + args_section

    return doc
