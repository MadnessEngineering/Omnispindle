# AI Agent Guide for Omnispindle MCP Tools

## Overview

This guide helps AI agents effectively use the Omnispindle MCP todo management tools. These tools are designed for seamless AI-to-AI handoffs and context sharing.

## Key Concepts

### Enhanced Descriptions for AI Context

- The `enhanced_description` field is specifically for AI agents
- Contains detailed context, technical requirements, and next steps
- Use markdown formatting for structure
- Include file paths, technical details, and implementation notes
- **Important**: Some legacy todos may have boolean `false`/`true` instead of strings

### Project Validation

- Project names are case-insensitive and support partial matching
- Always converted to lowercase for storage consistency
- Falls back to "madness_interactive" if no exact match found
- Valid projects include: omnispindle, swarmonomicon, todomill_projectorium, regressiontestkit, etc.

### Status-Based Field Optimization

- **Active todos** (pending/initial): Include priority, target, metadata for work context
- **Completed todos**: Include completion time, duration, resolution notes for historical context
- This reduces token usage while maintaining relevant information

## Tool Usage Patterns

### Getting Todo Details

```python
# Always check for enhanced_description field for AI context
result = get_todo_tool("todo-id")
data = json.loads(result)["data"]
if "enhanced_description" in data:
    # Use this for detailed context and next steps
    context = data["enhanced_description"]
```

### Searching vs Filtering

```python
# Text search (returns matches with preview)
search_results = query_todos_tool("authentication bug", ["description"])

# Database filter (returns full objects)
filter_results = query_todos_tool({"status": "pending", "priority": "High"})
```

### Creating AI-Friendly Todos

```python
add_todo_tool(
    description="Brief task description",
    project="omnispindle", 
    priority="High",
    metadata={
        "tags": ["ai-handoff", "phase-2"],
        "notes": "Context for next AI agent"
    }
)

# Then update with enhanced description
update_todo_tool(todo_id, {
    "enhanced_description": """
## Technical Context
- File: src/components/Widget.tsx
- Issue: Authentication timeout on line 42
- Dependencies: Auth service, JWT handling

## Next Steps
1. Review auth token refresh logic
2. Add error boundary for timeout cases
3. Update tests in __tests__/Widget.test.tsx

## Success Criteria
- [ ] No more 401 errors in production
- [ ] Graceful handling of expired tokens
- [ ] Test coverage >90%
"""
})
```

## Data Consistency Notes

### Common Issues AI Agents Should Handle

1. **Boolean enhanced_description**: Some todos have `false`/`true` instead of strings
2. **Missing optional fields**: Always check for field existence before using
3. **Lowercase project names**: All project names stored in lowercase
4. **Timestamp formats**: Unix timestamps for created_at, completed_at

### Defensive Coding Patterns

```python
# Safe field access
todo_data = json.loads(get_todo_tool(todo_id))["data"]
enhanced_desc = todo_data.get("enhanced_description", "")
if isinstance(enhanced_desc, str) and enhanced_desc.strip():
    # Use the enhanced description
    process_context(enhanced_desc)

# Project name normalization
project = project.lower().strip()

# Metadata safety
metadata = todo_data.get("metadata", {})
tags = metadata.get("tags", [])
```

## Best Practices for AI Handoffs

### 1. Context Preservation

- Always include technical details in `enhanced_description`
- Reference specific files, line numbers, and implementation notes
- Include success criteria and testing requirements

### 2. Progress Tracking

- Use completion comments to document solutions
- Include links to related changes or commits
- Mention any blockers or dependencies discovered

### 3. Error Recovery

- Handle missing fields gracefully
- Provide fallback behavior for data inconsistencies  
- Log issues but continue processing when possible

## Tool Reference Quick Start

| Tool | Purpose | Key Parameters | Returns |
|------|---------|----------------|---------|
| `get_todo_tool` | Get single todo | `todo_id` | Full todo object with status-optimized fields |
| `query_todos_tool` | Search/filter | `query_or_filter`, `fields_or_projection` | Search matches or filtered results |
| `add_todo_tool` | Create todo | `description`, `project` | `{success, todo_id, message}` |
| `update_todo_tool` | Modify todo | `todo_id`, `updates` | `{success, message}` |
| `mark_todo_complete_tool` | Complete todo | `todo_id`, `comment` | `{todo_id, completed_at, duration}` |
| `list_todos_by_status_tool` | Get by status | `status`, `limit` | `{count, status, items[]}` |

## Common Workflows

### 1. Taking over from another AI agent

```python
# Get the todo with context
todo = get_todo_tool(handoff_todo_id)
context = json.loads(todo)["data"].get("enhanced_description", "")

# Process the context and continue work
# Update with progress
update_todo_tool(handoff_todo_id, {
    "enhanced_description": context + "\n\n## Progress Update\n- Started implementation..."
})
```

### 2. Completing work and handing off

```python
# Mark current phase complete
mark_todo_complete_tool(current_todo_id, 
    "Completed Phase 1: Authentication system implemented. See commit abc123.")

# Create next phase todo
next_todo_id = add_todo_tool(
    "Phase 2: Frontend integration", 
    "omnispindle",
    enhanced_description="""
## Context from Phase 1
Authentication backend is complete (see previous todo).

## Phase 2 Requirements  
- Integrate auth endpoints with React frontend
- Add login/logout UI components
- Handle token refresh flows
...
"""
)
```

This guide should help AI agents work more effectively with the Omnispindle todo system! 🤖✨
