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
        "basic": "Creates a task in the specified project with the given priority and target agent. Returns a compact representation of the created todo with an ID for reference.",
        "admin": "Creates a task in the specified project. Supports standardized metadata schema including files[], tags[], phase, complexity, and acceptance_criteria. Returns todo with project counts.",
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
        "basic": "Query todos with flexible filtering options. Searches the todo database using MongoDB-style query filters and projections.",
        "admin": "Query todos with MongoDB-style filters and projections. Supports filtering by status, project, priority, metadata fields, and date ranges. Results include user-scoped data.",
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
        "basic": "Update a todo with the provided changes. Common fields to update: description, priority, status, metadata.",
        "admin": "Update a todo with the provided changes. Supports updating all core fields and metadata. Validates metadata schema. Tracks changes in audit logs.",
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
        "basic": "Get a specific todo by ID.",
        "admin": "Get a specific todo by ID from user's database. Returns full todo object including metadata and completion details.",
        "full": "Get a specific todo by ID. Returns the complete todo object including all metadata fields, completion tracking, and audit information."
    },
    
    "mark_todo_complete": {
        "minimal": "Complete todo",
        "basic": "Mark a todo as completed. Calculates the duration from creation to completion.",
        "admin": "Mark a todo as completed. Calculates duration, updates status, adds completion timestamp. Optional completion comment is stored in metadata.",
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
        "basic": "List todos filtered by status ('initial', 'pending', 'completed'). Results are formatted for efficiency with truncated descriptions.",
        "admin": "List todos filtered by status from user's database. Status options: pending, completed, initial, blocked, in_progress. Results include metadata summary.",
        "full": "List todos filtered by their status. Valid status values: pending, completed, initial, blocked, in_progress. Results are formatted for efficiency with truncated descriptions to reduce token usage while preserving essential information."
    },
    
    "list_project_todos": {
        "minimal": "List project todos",
        "basic": "List recent active todos for a specific project.",
        "admin": "List recent active (pending) todos for a specific project from user's database. Useful for project status overview.",
        "full": "List recent active todos for a specific project. Only returns pending todos to focus on current work. Useful for getting a quick overview of project status and active tasks."
    },
    
    "search_todos": {
        "minimal": "Search todos",
        "basic": "Search todos with text search capabilities across specified fields. Special format: \"project:ProjectName\" to search by project.",
        "admin": "Search todos with regex text search across configurable fields (description, project, metadata). Supports project-specific searches.",
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
        "basic": "Delete a todo by its ID.",
        "admin": "Delete a todo by its ID from user's database. Logs deletion event for audit trail.",
        "full": "Delete a todo item by its ID. The deletion is logged for audit purposes and the todo is permanently removed from the user's database."
    },
    
    "add_lesson": {
        "minimal": "Add lesson", 
        "basic": "Add a new lesson learned to the knowledge base.",
        "admin": "Add a new lesson with language, topic, and tags. Invalidates lesson tag cache automatically.",
        "full": "Add a new lesson learned to the knowledge base with specified language, topic, content, and optional tags. The lesson is assigned a unique ID and timestamp."
    },
    
    "get_lesson": {
        "minimal": "Get lesson",
        "basic": "Get a specific lesson by ID.",
        "admin": "Get a specific lesson by ID from user's knowledge base.",
        "full": "Retrieve a specific lesson by its unique ID from the user's knowledge base."
    },
    
    "update_lesson": {
        "minimal": "Update lesson",
        "basic": "Update an existing lesson by ID.",
        "admin": "Update an existing lesson by ID. Supports updating all lesson fields. Invalidates tag cache if tags modified.",
        "full": "Update an existing lesson by its ID. Can modify any field including language, topic, lesson_learned content, and tags. Tag cache is automatically invalidated if tags are changed."
    },
    
    "delete_lesson": {
        "minimal": "Delete lesson", 
        "basic": "Delete a lesson by ID.",
        "admin": "Delete a lesson by ID from user's knowledge base. Invalidates lesson tag cache.",
        "full": "Delete a lesson by its ID from the knowledge base. The lesson tag cache is automatically invalidated after deletion."
    },
    
    "search_lessons": {
        "minimal": "Search lessons",
        "basic": "Search lessons with text search capabilities.",
        "admin": "Search lessons with regex text search across configurable fields (topic, lesson_learned, tags).",
        "full": "Search lessons with text search capabilities across specified fields. Default search fields are topic, lesson_learned, and tags. Supports regex patterns and case-insensitive search."
    },
    
    "grep_lessons": {
        "minimal": "Grep lessons",
        "basic": "Search lessons with grep-style pattern matching across topic and content.",
        "admin": "Search lessons with grep-style regex pattern matching across topic and lesson_learned fields.",
        "full": "Search lessons using grep-style pattern matching with regex support. Searches across both topic and lesson_learned fields with case-insensitive matching."
    },
    
    "list_lessons": {
        "minimal": "List lessons",
        "basic": "List all lessons, sorted by creation date.",
        "admin": "List all lessons from user's knowledge base, sorted by creation date (newest first).",
        "full": "List all lessons from the knowledge base, sorted by creation date in descending order (newest first). Supports optional brief mode for compact results."
    },
    
    "query_todo_logs": {
        "minimal": "Query logs",
        "basic": "Query todo logs with filtering options.",
        "admin": "Query todo audit logs with filtering by type (create, update, delete, complete) and project. Supports pagination.",
        "full": "Query the todo audit logs with filtering and pagination options. Filter by operation type (create, update, delete, complete) and project. Includes pagination with configurable page size."
    },
    
    "list_projects": {
        "minimal": "List projects",
        "basic": "List all valid projects from the centralized project management system.",
        "admin": "List all valid projects. include_details: False (names only), True (full metadata), \"filemanager\" (for UI).",
        "full": "List all valid projects from the centralized project management system. The include_details parameter controls output format: False for names only, True for full metadata including git URLs and paths, or \"filemanager\" for UI-optimized format."
    },
    
    "explain": {
        "minimal": "Explain topic",
        "basic": "Provides a detailed explanation for a project or concept.",
        "admin": "Provides detailed explanation for projects or concepts. For projects, dynamically generates summary with recent activity.",
        "full": "Provides a detailed explanation for a project or concept. For projects, it dynamically generates a comprehensive summary including recent activity, status, and related information."
    },
    
    "add_explanation": {
        "minimal": "Add explanation",
        "basic": "Add a new static explanation to the knowledge base.",
        "admin": "Add a new static explanation with topic, content, kind (concept/project/etc), and author.",
        "full": "Add a new static explanation to the knowledge base with specified topic, content, kind (concept, project, etc.), and author information. Uses upsert to update existing explanations."
    },
    
    "point_out_obvious": {
        "minimal": "Point obvious",
        "basic": "Points out something obvious to the human user with humor.",
        "admin": "Points out obvious things with configurable sarcasm levels (1-10). Stores observations and publishes to MQTT.",
        "full": "Points out something obvious to the human user with varying levels of humor and sarcasm. Sarcasm level ranges from 1 (gentle) to 10 (maximum sass). Observations are logged and published to MQTT for system integration."
    },
    
    "bring_your_own": {
        "minimal": "Custom tool",
        "basic": "Temporarily hijack the MCP server to run custom tool code.",
        "admin": "Execute custom tool code in Python, JavaScript, or Bash runtimes. Includes rate limiting and execution history.",
        "full": "Temporarily hijack the MCP server to run custom tool code. Supports Python, JavaScript, and Bash runtimes with configurable timeout and argument passing. Includes rate limiting for non-admin users and comprehensive execution logging. Use with caution - allows arbitrary code execution."
    }
}

# Additional parameter hints for complex tools
PARAMETER_HINTS = {
    "add_todo": {
        "basic": "Required: description, project. Optional: priority (Critical|High|Medium|Low), target_agent, metadata",
        "admin": "Metadata supports: files[], tags[], phase, complexity, confidence(1-5), acceptance_criteria[]",
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
        "basic": "filter (dict): MongoDB query, projection (dict): fields to return, limit (int): max results",
        "admin": "Supports nested metadata queries: {'metadata.tags': {'$in': ['bug']}}, user-scoped results",
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