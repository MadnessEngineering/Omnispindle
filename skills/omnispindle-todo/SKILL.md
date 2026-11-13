---
name: omnispindle-todo
description: Comprehensive todo management workflow for Omnispindle's task tracking system. Use this skill when users need to create, update, track, or complete todos in Omnispindle. Handles the full lifecycle from creation (with metadata, notes, priorities, and project assignment) through updates as work progresses, to final completion. Essential for project management, task tracking, and coordinating work across Omnispindle's various projects.
---

# Omnispindle Todo Management

This skill provides a structured workflow for managing todos in Omnispindle's task tracking system throughout their complete lifecycle.

## Core Workflow

Follow this three-phase workflow for todo management:

### Phase 1: Create Todo

When a task needs to be tracked, create a todo with complete context:

```python
omnispindle:add_todo(
    description="Clear, actionable description of the task",
    project="project-name",  # Required - see valid projects in references
    priority="Medium",       # Critical|High|Medium|Low
    notes="Additional context, background, or requirements",
    target_agent="user",     # user|AI name (who will work on this)
    metadata={               # Optional key-value pairs for tracking
        "component": "frontend",
        "estimated_hours": "4",
        "dependencies": ["todo_id_123"]
    },
    ticket=""               # Optional external ticket reference (e.g., "JIRA-123")
)
```

**Priority Guidelines:**
- **Critical**: Blocking work, urgent fixes, production issues
- **High**: Important features, significant bugs, time-sensitive work
- **Medium**: Standard tasks, improvements, moderate importance
- **Low**: Nice-to-haves, minor improvements, background work

**Metadata Examples:**
- Technical context: `{"component": "api", "language": "python"}`
- Dependencies: `{"blocked_by": "todo_xyz", "relates_to": "feature_abc"}`
- Estimates: `{"estimated_hours": "8", "complexity": "high"}`
- Categories: `{"type": "bug", "area": "performance"}`

### Phase 2: Update as Work Progresses

As developments occur, update the todo to maintain accurate status:

```python
omnispindle:update_todo(
    todo_id="returned_id_from_creation",
    updates={
        "status": "in_progress",  # pending|in_progress|blocked|completed|initial
        "notes": "Updated notes with progress information",
        "priority": "High",       # Adjust if priority changes
        "metadata": {             # Update or add new metadata
            "progress": "60%",
            "blocker": "waiting for API approval"
        }
    }
)
```

**Status Guidelines:**
- **initial**: Just created, not yet started
- **pending**: Ready to work on, in queue
- **in_progress**: Currently being worked on
- **blocked**: Cannot proceed due to dependency or issue
- **completed**: Work finished and verified

**When to Update:**
- Status changes (started work, blocked, etc.)
- Priority shifts based on new information
- Progress milestones reached
- Dependencies or blockers identified
- Context or requirements change

### Phase 3: Complete Todo

When work is finished, mark complete with optional summary:

```python
omnispindle:mark_todo_complete(
    todo_id="todo_id",
    comment="Optional: Summary of what was accomplished, challenges overcome, or relevant notes"
)
```

## Finding and Querying Todos

### Search by Text

Search across todo fields for keywords:

```python
omnispindle:search_todos(
    query="authentication",
    limit=100,
    fields=["description", "notes"],  # Optional: specify which fields to search
    ctx="Looking for security-related tasks"
)

# Search within specific project
omnispindle:search_todos(
    query="project:omnispindle database migration"
)
```

### Query by Filters

Use MongoDB-style filters for precise queries:

```python
omnispindle:query_todos(
    filter={
        "project": "omnispindle",
        "priority": "High",
        "status": {"$ne": "completed"}
    },
    exclude_completed=True,  # Default: true
    limit=100,
    offset=0  # For pagination
)
```

### List by Status

Get todos in specific status:

```python
omnispindle:list_todos_by_status(
    status="in_progress",  # pending|in_progress|blocked|completed|initial
    limit=100,
    offset=0
)
```

### List Project Todos

Get recent pending todos for a project:

```python
omnispindle:list_project_todos(
    project="omnispindle",
    limit=5,
    offset=0
)
```

## Valid Projects

For the complete list of valid project names, see `references/projects.md`. Common projects include:
- omnispindle
- madness_interactive
- inventorium
- swarmonomicon
- regressiontestkit
- cogwyrm
- And 20+ others (see references for full list)

## Best Practices

1. **Complete Context**: Always include notes with background and requirements
2. **Meaningful Metadata**: Use metadata for trackable, searchable attributes
3. **Regular Updates**: Update status and notes as work progresses
4. **Clear Descriptions**: Write actionable descriptions that clearly state the task
5. **Appropriate Priority**: Set priority based on urgency and impact
6. **Completion Comments**: Add completion comments to document outcomes

## Common Patterns

**Feature Development:**
```python
add_todo(
    description="Implement user authentication system",
    project="omnispindle",
    priority="High",
    notes="Need OAuth2 support, session management, and password reset",
    metadata={"component": "auth", "estimated_hours": "16", "type": "feature"}
)
```

**Bug Fix:**
```python
add_todo(
    description="Fix memory leak in background worker",
    project="madness_interactive",
    priority="Critical",
    notes="Worker process grows to 2GB+ over 24 hours",
    metadata={"type": "bug", "severity": "high", "component": "worker"}
)
```

**Research Task:**
```python
add_todo(
    description="Research vector database options for semantic search",
    project="cogwyrm",
    priority="Medium",
    notes="Compare Pinecone, Weaviate, and Qdrant for our use case",
    metadata={"type": "research", "estimated_hours": "4"}
)
```
