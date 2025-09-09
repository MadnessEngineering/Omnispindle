# Omnispindle MCP Tools API Documentation

## Overview

Omnispindle provides a comprehensive set of MCP tools for todo management, knowledge capture, and project coordination. All tools support different operation modes and tool loadouts for optimal performance.

## Tool Loadouts

Configure via `OMNISPINDLE_TOOL_LOADOUT` environment variable:

- **`full`** - All 22 tools (default)
- **`basic`** - Essential todo management (7 tools)  
- **`minimal`** - Core functionality (4 tools)
- **`lessons`** - Knowledge management (7 tools)
- **`admin`** - Administrative tools (6 tools)
- **`hybrid_test`** - Hybrid mode testing (6 tools)

## Authentication Context

All tools automatically inherit user context from:
- **JWT Tokens** - Primary authentication via Auth0 device flow
- **API Keys** - Alternative authentication method
- **User Email** - Specified via `MCP_USER_EMAIL` environment variable

## Todo Management Tools

### add_todo
**Description**: Create a new todo item with metadata and project assignment.

**Parameters**:
- `description` (string, required) - Task description
- `project` (string, required) - Project name (must be in VALID_PROJECTS)
- `priority` (string, optional) - "Low", "Medium", "High" (default: "Medium")
- `target_agent` (string, optional) - Assigned agent (default: "user")
- `metadata` (object, optional) - Custom metadata fields

**Returns**: Todo creation confirmation with assigned ID

**Example**:
```json
{
  "description": "Implement user authentication",
  "project": "omnispindle",
  "priority": "High",
  "target_agent": "claude",
  "metadata": {"epic": "security", "estimate": "3h"}
}
```

### query_todos
**Description**: Search and filter todos with MongoDB-style queries.

**Parameters**:
- `filter` (object, optional) - MongoDB query filter
- `limit` (number, optional) - Maximum results (default: 100)
- `projection` (object, optional) - Field projection
- `ctx` (string, optional) - Additional context

**Returns**: Array of matching todo items

**Example Filters**:
```json
{"status": "pending", "priority": "High"}
{"project": "omnispindle", "created": {"$gte": "2025-01-01"}}
{"metadata.epic": "security"}
```

### update_todo
**Description**: Modify existing todo item fields.

**Parameters**:
- `todo_id` (string, required) - Todo identifier
- `updates` (object, required) - Fields to update

**Returns**: Update confirmation

**Example**:
```json
{
  "todo_id": "12345",
  "updates": {
    "priority": "Low",
    "metadata": {"epic": "documentation"}
  }
}
```

### get_todo
**Description**: Retrieve a specific todo by ID.

**Parameters**:
- `todo_id` (string, required) - Todo identifier

**Returns**: Complete todo object

### mark_todo_complete
**Description**: Mark todo as completed with optional completion comment.

**Parameters**:
- `todo_id` (string, required) - Todo identifier
- `comment` (string, optional) - Completion notes

**Returns**: Completion confirmation with timestamp

### list_todos_by_status
**Description**: Get todos filtered by status.

**Parameters**:
- `status` (string, required) - "pending", "completed", "initial"
- `limit` (number, optional) - Maximum results (default: 100)

**Returns**: Array of todos with specified status

### list_project_todos
**Description**: Get recent todos for a specific project.

**Parameters**:
- `project` (string, required) - Project name
- `limit` (number, optional) - Maximum results (default: 5)

**Returns**: Recent todos for the project

## Knowledge Management Tools

### add_lesson
**Description**: Capture lessons learned with categorization.

**Parameters**:
- `title` (string, required) - Lesson title
- `content` (string, required) - Lesson content
- `language` (string, optional) - Programming language
- `topic` (string, optional) - Subject area
- `project` (string, optional) - Related project
- `metadata` (object, optional) - Additional metadata

**Returns**: Lesson creation confirmation

### get_lesson / update_lesson / delete_lesson
**Description**: CRUD operations for lessons.

**Parameters**: Lesson ID and appropriate data fields

### search_lessons
**Description**: Full-text search across lesson content.

**Parameters**:
- `query` (string, required) - Search terms
- `limit` (number, optional) - Maximum results

**Returns**: Matching lessons with relevance scoring

### list_lessons
**Description**: Browse all lessons with optional filtering.

**Parameters**:
- `limit` (number, optional) - Maximum results
- `filter` (object, optional) - Optional filters

**Returns**: Array of lessons

## Administrative Tools

### query_todo_logs
**Description**: Access audit trail for todo modifications.

**Parameters**:
- `filter` (object, optional) - Log entry filters
- `limit` (number, optional) - Maximum results

**Returns**: Audit log entries

### list_projects
**Description**: Get available project names from filesystem.

**Returns**: Array of valid project names

### explain / add_explanation
**Description**: Manage topic explanations and documentation.

**Parameters**: Topic name and explanation content

## Hybrid Mode Tools

### get_hybrid_status
**Description**: Check current operation mode and connectivity status.

**Returns**: Mode status, API connectivity, fallback availability

### test_api_connectivity  
**Description**: Test connection to madnessinteractive.cc/api.

**Returns**: Connectivity test results

## Error Handling

All tools return standardized error responses:

```json
{
  "success": false,
  "error": "Error description",
  "error_code": "SPECIFIC_ERROR_CODE"
}
```

Common error codes:
- `AUTH_ERROR` - Authentication failure
- `VALIDATION_ERROR` - Invalid parameters
- `NOT_FOUND` - Resource not found
- `API_ERROR` - API connectivity issues
- `DATABASE_ERROR` - Database operation failure

## Tool Configuration

### Valid Projects
Tools validate project names against a predefined list including:
- `omnispindle` - Main MCP server
- `inventorium` - Web dashboard
- `madness_interactive` - Ecosystem root
- `swarmdesk` - AI environments
- And others defined in `VALID_PROJECTS`

### Data Scoping
All operations are automatically scoped to the authenticated user context. Users cannot access other users' data.

### Performance Considerations
- Use tool loadouts to reduce token consumption
- API mode provides better performance than local database
- Hybrid mode offers reliability with automatic fallback
- Batch operations when possible using query filters

## Integration Examples

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

### Programmatic Usage
```python
from omnispindle import OmnispindleClient

client = OmnispindleClient(mode="api")
result = await client.add_todo(
    description="API integration task",
    project="omnispindle", 
    priority="High"
)
```