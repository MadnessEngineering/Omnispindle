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
    COMPACT = "compact"      # Ultra-compact for token optimization (~100 tokens/tool)
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
        explicit = os.getenv("OMNISPINDLE_DOC_LEVEL", "").lower()
        if explicit in ("minimal", "compact", "basic", "full"):
            self.level = DocumentationLevel[explicit.upper()]
        else:
            self.level = self._get_documentation_level()
    
    def _get_documentation_level(self) -> DocumentationLevel:
        """Map loadout to documentation level."""
        mapping = {
            "minimal": DocumentationLevel.MINIMAL,
            "lightweight": DocumentationLevel.COMPACT,  # Token-optimized
            "basic": DocumentationLevel.BASIC,
            "lessons": DocumentationLevel.BASIC,
            "admin": DocumentationLevel.ADMIN,
            "full": DocumentationLevel.FULL,
            "write_only": DocumentationLevel.BASIC,
            "read_only": DocumentationLevel.BASIC,
            "agent_preflight": DocumentationLevel.BASIC,
            "refine": DocumentationLevel.BASIC,
            "npc": DocumentationLevel.COMPACT,
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
        # Cascade: requested level → basic (not full) → full → fallback
        # Prevents compact falling through to verbose full descriptions
        level_val = self.level.value
        return (
            docs.get(level_val)
            or docs.get("basic")
            or docs.get("full")
            or "Tool documentation not found."
        )
    
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
    
    "complete_todo": {
        "minimal": "Stage todo for review",
        "basic": "Mark done → status=review. Pass comment= with what was accomplished.",
        "admin": "Sets status=review. Calculates duration, logs event, stores comment in metadata.",
        "full": """Mark a todo as done (stages it for review) with optional completion comment.

Automatically:
- Sets status to "review" (staged for human review before archiving)
- Records completion timestamp
- Calculates duration from creation to completion
- Updates completed_by field with user information
- Stores completion comment in metadata if provided
- Logs completion event for audit trail

Always pass comment= — it's the only place to record what was actually accomplished."""
    },
    
    "list_todos_by_status": {
        "minimal": "List by status",
        "basic": "List by status: pending|completed|initial|blocked|in_progress|review",
        "admin": "Filter by status (pending|completed|initial|blocked|in_progress|review). Returns with metadata summary.",
        "full": "List todos filtered by their status. Valid status values: pending, completed, initial, blocked, in_progress, review. Results are formatted for efficiency with truncated descriptions to reduce token usage while preserving essential information."
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

    "regenerate_embedding": {
        "minimal": "Refresh lesson embedding",
        "basic": "Recompute vector embedding for a lesson",
        "admin": "Regenerate embedding via Gemini text-embedding-004; stamps embedding_updated_at.",
        "full": "Recompute the 768-dim vector embedding for a lesson and stamp embedding_updated_at. Used by the Lessons Exploratory Viewer to refresh stale or missing embeddings on demand or after edits."
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
    },

    "get_context_bundle": {
        "minimal": "Context bundle",
        "compact": "Bundle slim todo/lesson/session summaries in one call. Use 'since' for change detection. Params: project, keywords[], include_completed, since.",
        "basic": "Bundle slim context summaries (todos, lessons, sessions) into one response for AI agent startup. Returns IDs + short fields only. Use 'since' (unix timestamp) to add changed_todos section.",
        "admin": "RAG context bundler. Returns slim projections: todos (id, description, priority, status, project), lessons (id, topic, language, tags), sessions (id, title, status). 'since' adds changed_todos with updated_by. Each section independent.",
        "full": """Bundle multiple context queries into a single slim response for AI agent session startup (~800-1000 tokens worst case).

Returns up to 7 sections with projected fields (not full documents):
- project_todos: id, description, priority, status, project, created_at (limit 5)
- related_lessons: id, topic, language, tags — NO lesson_learned content (limit 3). Use get_lesson(id) for full text.
- keyword_todos: Same fields as project_todos, cross-project, deduped (limit 5)
- recent_completions: Same fields, requires include_completed=true (limit 3)
- blocked_todos: Same fields, status=blocked (limit 5)
- changed_todos: Items modified after 'since' timestamp, includes updated_at + updated_by (limit 10). Use for session continuity.
- last_session: id, title, project, status, created_at (limit 1)

Each section degrades independently — if one query fails, others still return.
Response includes summary with sections_returned and sections_failed lists."""
    },

    "find_relevant": {
        "minimal": "Semantic search",
        "compact": "Semantic similarity search across todos and/or lessons. Falls back to regex. Params: query (required), types[] (todos|lessons), limit.",
        "basic": "Semantic similarity search across todos and/or lessons using vector embeddings. Falls back to regex if embeddings unavailable. Use for ad-hoc 'find related items' queries.",
        "admin": "Semantic search via Gemini embeddings (768-dim cosine similarity). Falls back to tokenized regex on description/topic fields. types=['todos','lessons'] controls scope. Returns items with similarity_score when semantic.",
        "full": """Semantic similarity search across todos and/or lessons. Uses vector embeddings when available, falls back to regex.

Returns structured JSON per type:
- todos: id, description, priority, status, project, created_at, similarity_score
- lessons: id, topic, language, tags, lesson_learned, similarity_score
- method: 'semantic' or 'regex' per type

Use this for ad-hoc 'find related items' queries mid-task. For session startup context, use get_context_bundle. For pre-task lessons review, use preflight_rag."""
    },

    "preflight_rag": {
        "minimal": "Preflight lessons check",
        "compact": "Query lessons learned before starting work. Returns past solutions, pitfalls, suggestions. Params: intent (required), project, tags[], limit.",
        "basic": "Pre-processing RAG tool: search lessons learned against agent intent before beginning work. Returns categorised results: lessons (past solutions), pitfalls (known issues), and suggestions. Supports semantic + regex fallback.",
        "admin": "Preflight RAG. Searches lessons via semantic embeddings (falls back to regex). Project filter boosts project-specific lessons. Tags narrow results. Classifies lessons vs pitfalls by keyword detection in lesson_learned text.",
        "full": """Pre-processing RAG tool for agent preflight checks. Call at the start of a task to review what has been learned before.

Returns structured JSON with:
- lessons: Past solutions and decisions relevant to the intent
- pitfalls: Known issues, mistakes, things to avoid (detected by warning keywords)
- suggestions: Summary of findings and recommended actions
- method: 'semantic' or 'regex' (search method used)
- message: Human-readable status

Search strategy:
1. Semantic search against intent (or regex fallback)
2. If project specified, project-specific lessons are boosted to top
3. If tags specified, results are re-ranked by tag overlap
4. Results classified as lessons vs pitfalls by keyword analysis"""
    },
    "write_agent_journal": {
        "minimal": "Write agent journal entry",
        "compact": "Append timestamped entry to agent's persistent journal. Visible in SwarmDesk 3D. Params: agent_name (required), content (required), entry_type.",
        "basic": "Append a timestamped entry to an agent's persistent journal. Entries are visible in SwarmDesk's 3D world and readable by other agents for cross-agent awareness.",
        "full": """Append a timestamped entry to an agent's persistent journal.

AI agents call this to leave working notes, session context, or status updates
that are visible in SwarmDesk's 3D workspace. Other agents can read your journal
entries via read_agent_journal for cross-agent coordination.

Entry types: note (default), annotation, session_start, session_end.
Entries are capped at 200 per agent (oldest dropped)."""
    },
    "read_agent_journal": {
        "minimal": "Read agent journal",
        "compact": "Read recent journal entries for any agent. Cross-agent awareness. Params: agent_name (required), limit.",
        "basic": "Read recent journal entries for any agent. Read your own journal for session continuity, or another agent's journal to see what they've been working on.",
        "full": """Read recent journal entries for any agent. Enables cross-agent awareness.

Any agent can read any other agent's journal — this is how agents see
what their peers have been working on and coordinate without direct messaging.

Returns: agent name, entries array (timestamp, content, type, author), count, total entries."""
    },

    # ── Quest system ────────────────────────────────────────────────────────
    # Model: Quest → Chains → Todos
    #   Quest   = the epic goal (e.g. "Ship auth overhaul")
    #   Chain   = a named sequence/phase of todos (e.g. "Backend", "Frontend")
    #   Todo    = one atomic task inside a chain (created with add_todo)
    # Use create_quest when grouping multiple todos toward a shared objective.
    # Use add_todo for individual tasks that don't belong to a multi-chain goal.

    "create_quest": {
        "minimal": "Create quest (epic goal container)",
        "compact": "Create a Quest — epic container for todo chains. TODOS FIRST: add_todo for each task, collect IDs, then create_quest with chains=[{label, todos:[id1,id2,...]}]. NOT a todo itself.",
        "basic": """Create a Quest — epic container grouping chains of todos toward a goal.
Model: Quest → Chains (phases/workstreams) → Todos (atomic tasks, created with add_todo).

TODOS FIRST workflow:
1. add_todo for each task → collect the IDs
2. create_quest with chains pre-loaded: '[{"label":"Phase 1","todos":["id1","id2"]}]'
3. link_quest for any todos added later""",
        "full": """Create a Quest — the top-level epic container in the Quest→Chain→Todo hierarchy.

  Quest  = the goal (e.g. "Ship tag system overhaul")
  Chain  = a named sequence or workstream (e.g. "Backend", "Testing", "Docs")
  Todo   = one atomic task inside a chain — MUST be created with add_todo first

CORRECT WORKFLOW — todos first, then quest:
  Step 1: add_todo for every task you know about → collect all returned IDs
  Step 2: create_quest with chains pre-loaded using those IDs:
            chains='[{"label":"Backend","todos":["uuid1","uuid2"]},
                     {"label":"Testing","todos":["uuid3"]}]'
  Step 3: For tasks discovered later → link_quest(quest_id, new_todo_id, chain_label)
  Step 4: check_quest to get progress, next actions, blockers

WRONG: create_quest with placeholder text in todos array — IDs must be real existing todos.
WRONG: creating the quest first and leaving chains empty, then forgetting to link_quest.

chains JSON schema:
[{"label": "string", "todos": ["uuid",...], "parallel": false, "gate_todo": null}]
  - label: chain/phase name
  - todos: array of existing todo UUIDs (empty array OK if none yet)
  - parallel: true = all todos can proceed simultaneously
  - gate_todo: UUID of a todo that must complete before this chain unlocks"""
    },

    "check_quest": {
        "minimal": "Check quest progress",
        "compact": "Get quest progress: per-chain status, next actions, blockers, summary. Agent orientation tool. Param: quest_id.",
        "basic": "Get quest progress: overall %, per-chain status, next actions, blockers. Call after create_quest or when re-orienting on a goal.",
        "full": """Get a progress report for a quest — the agent orientation tool.

Returns:
- Overall completion % across all chains
- Per-chain status (done/total, blocked todos, next actions)
- Natural language summary an agent can use to orient itself
- List of blockers with their blocking todo details
- Suggested next_actions in priority order

Call this at session start when resuming work on a quest, or any time
you need to re-orient on the quest's current state."""
    },

    "list_quests": {
        "minimal": "List quests",
        "compact": "List quests by status/project. Params: status (active|completed|all), project, limit.",
        "basic": "List quests filtered by status and project. Returns id, name, chain_count, todo_count, updated_at.",
        "full": """List quests with optional filters.

Returns lightweight quest summaries (id, name, project, status, chain_count, todo_count, updated_at).
Use check_quest(quest_id) for full progress detail on a specific quest.

Params:
- status: active|completed|paused|all (default: active)
- project: filter to one project
- limit: max results (default: 20)"""
    },

    "link_quest": {
        "minimal": "Link todo to quest chain",
        "compact": "Add existing todo to a quest chain. Creates chain if not found. Params: quest_id, todo_id, chain_label, position.",
        "basic": "Add an existing todo to a quest chain (creates chain on demand). Use after add_todo when you forgot to specify chains at create_quest time.",
        "full": """Add an existing todo to a quest chain retroactively.

Creates the chain if it doesn't exist (so you can start with create_quest(chains=[])
then link todos in as you create them with add_todo).

Backlinks the todo (sets metadata.quest_id) automatically.

Params:
- quest_id: the quest to add to
- todo_id: an existing todo ID (create with add_todo first)
- chain_label: name of the chain/phase (e.g. "Backend", "Testing")
- position: index to insert at (-1 = append, default)"""
    },

    "query_todos_near": {
        "minimal": "Find nearby todos",
        "compact": "Find todos in same district or within spatial radius. Pass todo_id or district.",
        "basic": "Find todos by spatial proximity. Match on metadata.district (exact) or metadata.coordinates (Euclidean). Pass todo_id to inherit anchor's district+coords, or district= directly.",
        "full": """Spatial neighborhood query for SwarmDesk 3D view.

Matches todos by:
1. metadata.district — exact label match (e.g. 'rag', 'ui', 'infra')
2. metadata.coordinates — Euclidean distance on {x, y, z} within radius

Returns union of both, deduped, excluding completed todos.

Args:
- todo_id: anchor todo — inherits its district and coordinates
- district: override/direct district filter
- radius: max coordinate distance (default: 2.0)
- limit: max results (default: 20)

Response: {items: [...], count, anchor_district, anchor_coords, radius}"""
    },
    "link_todos": {
        "minimal": "Link todo dependency",
        "compact": "Mark blocker_id as dependency of blocked_id. Adds to metadata.blockers.",
        "basic": "Set blocker_id as a prerequisite for blocked_id. blocker must complete before blocked. Use query_todos(graph_root=id) to visualize the dependency graph.",
        "full": """Create a dependency edge between two todos.

blocker_id must be completed before blocked_id can proceed.
Adds blocker_id to blocked_id.metadata.blockers array ($push, idempotent).

To remove: update_todo(blocked_id, {metadata: {blockers: {$pull: blocker_id}}})
To visualize: query_todos(graph_root=blocked_id) → {nodes, edges}"""
    },
    "update_quest": {
        "minimal": "Update quest",
        "compact": "Update quest fields (name, description, status, success_criteria, metadata). Param: quest_id, updates (JSON).",
        "basic": "Update quest fields. Allowed: name, description, status, success_criteria, metadata. Pass updates as JSON string.",
        "full": """Update quest-level fields.

Allowed fields in updates JSON:
- name: rename the quest
- description: update the goal statement
- status: active|completed|paused|cancelled
- success_criteria: list of completion criteria strings
- metadata: arbitrary key-value pairs (tags, etc.)

To modify chains or todos within a quest, use link_quest instead.
To mark a quest done: update_quest(quest_id, '{"status": "completed"}')"""
    },
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
    },

    "get_context_bundle": {
        "basic": "project: scope to project; keywords[]: search terms; since: unix timestamp for change detection",
        "admin": "7 sections: project_todos, related_lessons, keyword_todos, recent_completions, blocked_todos, changed_todos, last_session. Each degrades independently.",
        "full": """Parameters:
- project (str, optional): Project name — enables project_todos, recent_completions, blocked_todos, last_session sections
- keywords (list[str], optional): Search terms — enables related_lessons and keyword_todos sections
- include_completed (bool, optional): Include recent completed todos (default: false)
- since (int, optional): Unix timestamp — adds changed_todos section with items modified after this time. Use for session continuity."""
    },

    "preflight_rag": {
        "basic": "intent: what you're about to do; project: scope lessons; tags[]: narrow search",
        "admin": "Semantic search against intent, project-specific boost, tag re-ranking. Returns lessons[] + pitfalls[] + suggestions[].",
        "full": """Parameters:
- intent (str, required): Natural language description of what you're about to do
- project (str, optional): Project name — project-specific lessons are boosted to top of results
- tags (list[str], optional): Tags to narrow search — results re-ranked by tag overlap
- limit (int, optional): Max lessons to return (default: 5)"""
    },

    "find_relevant": {
        "basic": "query: natural language search; types[]: 'todos','lessons'; limit: per type",
        "admin": "Semantic via Gemini embeddings when available, regex fallback. Returns similarity_score per item.",
        "full": """Parameters:
- query (str, required): Natural language search query
- types (list[str], optional): Types to search — ['todos', 'lessons'] (default: both)
- limit (int, optional): Max results per type (default: 5)"""
    },

    "inventorium_sessions_fork": {
        "basic": "session_id: source session; include_messages: copy chat history; inherit_todos: link parent todos",
        "full": """Parameters:
- session_id (str, required): Session ID to fork from
- title (str, optional): Title for the forked session
- include_messages (bool, optional): Copy message history to fork (default: true)
- inherit_todos (bool, optional): Link parent session's todos to fork (default: true)
- initial_status (str, optional): Override status for forked session"""
    },

    "query_todo_logs": {
        "basic": "filter_type: all|create|update|delete|complete; project: filter by project",
        "full": """Parameters:
- filter_type (str, optional): Log type — all|create|update|delete|complete (default: all)
- project (str, optional): Project name filter (default: all)
- page (int, optional): Page number (default: 1)
- page_size (int, optional): Results per page (default: 20)
- unified (bool, optional): Query both personal and shared databases (default: false)"""
    },

    "point_out_obvious": {
        "basic": "observation: what to point out; sarcasm_level: 1-10",
        "full": """Parameters:
- observation (str, required): The obvious thing to point out
- sarcasm_level (int, optional): Scale from 1 (gentle) to 10 (maximum sass, default: 5)"""
    },

    "update_todo": {
        "basic": "todo_id: UUID; updates: {field: new_value}. metadata is MERGED, not replaced.",
        "full": """Parameters:
- todo_id (str, required): UUID of the todo to update
- updates (dict, required): Fields to update — {field: new_value}
  - metadata updates are MERGED with existing metadata (not replaced)
  - status: pending|in_progress|blocked|completed
  - priority: Critical|High|Medium|Low"""
    },

    "list_projects": {
        "basic": "include_details: true for metadata; madness_root: override root dir",
        "full": """Parameters:
- include_details (bool|str, optional): Include project metadata like todo counts (default: false)
- madness_root (str, optional): Override lab root directory path"""
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
