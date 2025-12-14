# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Server

**Stdio MCP Server (Primary)**:
```bash
# Run the stdio-based MCP server
python stdio_main.py

# Or as a module
python -m src.Omnispindle.stdio_server
```

**Web Server (for authenticated endpoints)**:
```bash
# Development - run the FastAPI web server
python3.11 -m src.Omnispindle

# Using Makefile
make run  # Runs the server and publishes commit hash to MQTT
```


## Architecture Overview

Omnispindle is a FastMCP-based todo management system that serves as part of the Madness Interactive ecosystem. It provides AI agents with standardized tools for task management through the Model Context Protocol (MCP).
It supports a dashboard 

### Core Components

**MCP Server (`src/Omnispindle/`)**:
- `stdio_server.py` - Primary MCP server using FastMCP with stdio transport
- `__init__.py` - FastAPI web server for authenticated endpoints
- `tools.py` - Local database implementation of all MCP tools (legacy mode)
- `api_tools.py` - API-based implementation of MCP tools
- `hybrid_tools.py` - Hybrid mode with API-first, database fallback
- `api_client.py` - HTTP client for madnessinteractive.cc/api
- `database.py` - MongoDB connection and operations (local mode only)
- `auth.py` - Authentication middleware for web endpoints
- `middleware.py` - Custom middleware for error handling and logging

**Data Layer**:
- **API Mode**: HTTP calls to madnessinteractive.cc/api (recommended)
- **Local Mode**: Direct MongoDB connections for todos, lessons, audit logs
- **Hybrid Mode**: API-first with local fallback for reliability
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

### Operation Modes

**Available Modes** (set via `OMNISPINDLE_MODE`):
- `hybrid` (default) - API-first with local database fallback
- `api` - HTTP API calls only to madnessinteractive.cc/api 
- `local` - Direct MongoDB connections only (legacy mode)
- `auto` - Automatically choose best performing mode

**API Authentication**:
- JWT tokens from Auth0 device flow (preferred)
- API keys from madnessinteractive.cc/api
- Automatic token refresh and error handling
- Graceful degradation when authentication fails

**Benefits of API Mode**:
- Simplified authentication (handled by API)
- Database access centralized behind API security
- Consistent user isolation across all clients
- No direct MongoDB dependency needed
- Better monitoring and logging via API layer

### Configuration

**Environment Variables**:

*Operation Mode Configuration*:
- `OMNISPINDLE_MODE` - Operation mode: `hybrid`, `api`, `local`, `auto` (default: `hybrid`)
- `OMNISPINDLE_TOOL_LOADOUT` - Tool loadout configuration (see Tool Loadouts below)
- `OMNISPINDLE_FALLBACK_ENABLED` - Enable fallback in hybrid mode (default: `true`)
- `OMNISPINDLE_API_TIMEOUT` - API request timeout in seconds (default: `10.0`)

*API Authentication*:
- `MADNESS_API_URL` - API base URL (default: `https://madnessinteractive.cc/api`)
- `MADNESS_AUTH_TOKEN` - JWT token from Auth0 device flow
- `MADNESS_API_KEY` - API key from madnessinteractive.cc

*Local Database (for local/hybrid modes)*:
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DB` - Database name (default: swarmonomicon)
- `MQTT_HOST` / `MQTT_PORT` - MQTT broker settings
- `AI_API_ENDPOINT` / `AI_MODEL` - AI integration (optional)

**MCP Integration**: 

For Claude Desktop stdio transport, add to your `claude_desktop_config.json`:

*API Mode (Recommended)*:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MADNESS_AUTH_TOKEN": "your_jwt_token_here",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

*Hybrid Mode (API + Local Fallback)*:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python", 
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "OMNISPINDLE_MODE": "hybrid",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MADNESS_AUTH_TOKEN": "your_jwt_token_here",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

*Local Mode (Direct Database)*:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "OMNISPINDLE_MODE": "local",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

**🚀 Zero-Config Authentication**:
No setup required! The system automatically:
1. Detects when authentication is needed
2. Opens your browser for Auth0 login
3. Saves tokens locally for future use
4. Works seamlessly across all MCP clients

**Manual Authentication (Optional)**:
If you need manual token setup:
```bash
python -m src.Omnispindle.token_exchange
```

**Testing API Integration**:
```bash
# Test the API client directly
python test_api_client.py

# Run with authentication
MADNESS_AUTH_TOKEN="your_token" python test_api_client.py

# Test specific mode
OMNISPINDLE_MODE="api" python test_api_client.py
```

### Development Patterns

**Error Handling**: Uses custom middleware (`middleware.py`) for connection errors and response processing.

**Logging**: Comprehensive logging with audit trail via `todo_log_service.py`.

**Testing**: Pytest-based test suite in `tests/` directory covering tools, database operations, and server functionality.

**Git Workflow**: Deployment handled through git hooks - commit when ready to deploy.

**Node-RED Integration**: Dashboard components are extracted to separate files for version control, then imported into Node-RED editor.

### Tool Loadouts

Omnispindle supports variable tool loadouts to reduce token usage for AI agents. Configure via the `OMNISPINDLE_TOOL_LOADOUT` environment variable:

**Available Loadouts**:
- `full` (default) - All 22 tools available
- `basic` - Essential todo management (7 tools): add_todo, query_todos, update_todo, get_todo, mark_todo_complete, list_todos_by_status, list_project_todos
- `minimal` - Core functionality only (4 tools): add_todo, query_todos, get_todo, mark_todo_complete
- `lessons` - Knowledge management focus (7 tools): add_lesson, get_lesson, update_lesson, delete_lesson, search_lessons, grep_lessons, list_lessons
- `admin` - Administrative tools (6 tools): query_todos, update_todo, delete_todo, query_todo_logs, list_projects, explain, add_explanation
- `hybrid_test` - Testing hybrid functionality (6 tools): add_todo, query_todos, get_todo, mark_todo_complete, get_hybrid_status, test_api_connectivity

**Usage**:
```bash
# Set loadout for stdio server
export OMNISPINDLE_TOOL_LOADOUT=minimal
export MCP_USER_EMAIL=user@example.com
python -m src.Omnispindle.stdio_server

# Set loadout for web server
export OMNISPINDLE_TOOL_LOADOUT=basic
python -m src.Omnispindle

# Or in Claude Desktop config
{
  "mcpServers": {
    "omnispindle": {
      "env": {
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```
