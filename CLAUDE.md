# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Server

**SSE Web Server (Default)**:
```bash
# Development - run the SSE-based MCP server
python3.11 -m src.Omnispindle

# Using Makefile
make run  # Runs the server and publishes commit hash to MQTT
```

**Stdio MCP Server (for Claude Desktop)**:
```bash
# Run the stdio-based MCP server
python stdio_main.py

# Or as a module
python -m src.Omnispindle.stdio_server
```


## Architecture Overview

Omnispindle is a FastMCP-based todo management system that serves as part of the Madness Interactive ecosystem. It provides AI agents with standardized tools for task management through the Model Context Protocol (MCP).
It supports a dashboard 

### Core Components

**MCP Server (`src/Omnispindle/`)**:
- `__init__.py` - Main server class with tool registration and FastAPI setup
- `tools.py` - Implementation of all MCP tools for todo/lesson management
- `server.py` - FastMCP server core (if separate from __init__.py)
- `database.py` - MongoDB connection and operations
- `auth.py` - Authentication middleware for web endpoints
- `middleware.py` - Custom middleware for error handling and logging

**Data Layer**:
- MongoDB for persistent storage (todos, lessons, audit logs)
- Collections: todos, lessons, explanations, todo_logs
- MQTT for real-time messaging and cross-system coordination

**Dashboard (`Todomill_projectorium/`)**:
- Node-RED based visual dashboard
- Real-time updates via MQTT
- JavaScript/HTML components in separate directories for version control

### MCP Tool Interface

The server exposes standardized MCP tools that AI agents can call:

**Todo Management**:
- `add_todo` - Create new tasks with metadata
- `query_todos` - Search and filter tasks with MongoDB queries
- `update_todo` - Modify existing tasks
- `delete_todo` - Remove tasks
- `get_todo` - Retrieve single task
- `mark_todo_complete` - Complete tasks with optional comments
- `list_todos_by_status` - Filter by status (pending, completed, etc.)
- `list_project_todos` - Get recent tasks for specific projects
- `search_todos` - Text search across todo fields

**Knowledge Management**:
- `add_lesson` - Capture lessons learned with language/topic tags
- `get_lesson` / `update_lesson` / `delete_lesson` - Lesson CRUD operations
- `search_lessons` / `grep_lessons` - Search knowledge base
- `list_lessons` - Browse all lessons

**System Integration**:
- `list_projects` - Get available projects from filesystem
- `explain` / `add_explanation` - Topic explanations system
- `query_todo_logs` - Access audit logs

### Data Structures

**Todo Items**:
```python
{
    "todo_id": "uuid",
    "description": "Task description",
    "project": "project_name",  # Must be in VALID_PROJECTS list
    "status": "initial|pending|completed",
    "priority": "Low|Medium|High",
    "created": timestamp,
    "completed": timestamp,  # if completed
    "target_agent": "user|AI_name",
    "metadata": {"key": "value"}  # Optional custom fields
}
```

**Valid Projects**: See `VALID_PROJECTS` list in `tools.py` - includes madness_interactive, omnispindle, swarmonomicon, todomill_projectorium, etc.

### Configuration

**Environment Variables**:
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DB` - Database name (default: swarmonomicon)
- `MQTT_HOST` / `MQTT_PORT` - MQTT broker settings
- `AI_API_ENDPOINT` / `AI_MODEL` - AI integration (optional)

**MCP Integration**: 

For Claude Desktop stdio transport, configure in `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["stdio_main.py"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "swarmonomicon"
      }
    }
  }
}
```

For SSE web-based integration (legacy):
```json
{
  "mcpServers": {
    "omnispindle-sse": {
      "command": "python",
      "args": ["-m", "src.Omnispindle"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "swarmonomicon"
      }
    }
  }
}
```

### Development Patterns

**Error Handling**: Uses custom middleware (`middleware.py`) for connection errors and response processing.

**Logging**: Comprehensive logging with audit trail via `todo_log_service.py`.

**Testing**: Pytest-based test suite in `tests/` directory covering tools, database operations, and server functionality.

**Git Workflow**: Deployment handled through git hooks - commit when ready to deploy.

**Node-RED Integration**: Dashboard components are extracted to separate files for version control, then imported into Node-RED editor.
