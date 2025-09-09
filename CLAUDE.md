# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### 🚀 v1.0.0 Deployment Status (IMPORTANT!)

**Current Release**: v1.0.0 production-ready with comprehensive deployment modernization completed through Phase 6

**Completed Phases**:
- ✅ **Phase 1**: PM2 ecosystem modernized (Python 3.13, GitHub Actions, modern env vars)
- ✅ **Phase 2**: Docker infrastructure updated (Python 3.13, API-first, health checks)
- ✅ **Phase 3**: PyPI package preparation complete (build scripts, MANIFEST.in, entry points)
- ✅ **Phase 4**: Security review complete (git-secrets, credential audit, hardcoded IP cleanup)
- ✅ **Phase 6**: Documentation review (README.md updated, this CLAUDE.md refresh)

**Key Changes Made**:
- Modernized to Python 3.13 across all deployment configs
- Removed MongoDB dependencies from Docker (API-first architecture)
- Added comprehensive PyPI packaging with CLI entry points
- Implemented git-secrets protection with AWS patterns
- Enhanced .gitignore with comprehensive security patterns
- Updated all hardcoded IPs to use environment variables

**CLI Commands Available** (after `pip install omnispindle`):
- `omnispindle` - Web server for authenticated endpoints  
- `omnispindle-server` - Alias for web server
- `omnispindle-stdio` - MCP stdio server for Claude Desktop

### Running the Server

**PyPI Installation (Recommended)**:
```bash
# Install from PyPI
pip install omnispindle

# Run MCP stdio server 
omnispindle-stdio

# Run web server
omnispindle
```

**Development (Local)**:
```bash
# Run the stdio-based MCP server
python -m src.Omnispindle.stdio_server

# Run web server (Python 3.13 preferred)
python3.13 -m src.Omnispindle

# Using Makefile
make run  # Runs the server and publishes commit hash to MQTT
```

**Docker (Modernized)**:
```bash
# Build with modern Python 3.13 base
docker build -t omnispindle:v1.0.0 .

# Run with API-first configuration
docker run -e OMNISPINDLE_MODE=api omnispindle:v1.0.0
```

### PyPI Publishing

**Build and Test**:
```bash
# Use the build script
./build-and-publish-pypi.sh

# Manual build
python -m build
python -m twine check dist/*
```

**Publish**:
```bash
# Test PyPI
python -m twine upload --repository testpypi dist/*

# Production PyPI  
python -m twine upload dist/*
```


## Architecture Overview

**Omnispindle v1.0.0** is a production-ready, API-first MCP server for todo and knowledge management. It serves as the coordination layer for the Madness Interactive ecosystem, providing standardized tools for AI agents through the Model Context Protocol.

### 🏗 Core Components (v1.0.0)

**MCP Server (`src/Omnispindle/`)**:
- `stdio_server.py` - Primary MCP server using FastMCP with stdio transport (CLI: `omnispindle-stdio`)
- `__main__.py` - CLI entry point and web server (CLI: `omnispindle`)
- `api_tools.py` - API-first implementation (recommended for production)
- `hybrid_tools.py` - Hybrid mode with API fallback (default mode)
- `tools.py` - Local database implementation (legacy mode)
- `api_client.py` - HTTP client for madnessinteractive.cc/api with JWT/API key auth
- `database.py` - MongoDB operations (hybrid/local modes only)
- `auth.py` - Authentication middleware with Auth0 integration
- `auth_setup.py` - Zero-config Auth0 device flow setup

**🔄 Operation Modes (Key Architecture Decision)**:
- **`api`** - Pure API mode, HTTP calls to madnessinteractive.cc/api (recommended)
- **`hybrid`** - API-first with MongoDB fallback (default, most reliable)
- **`local`** - Direct MongoDB connections only (legacy, local development)
- **`auto`** - Automatically choose best performing mode

**🔐 Authentication Layer**:
- **Zero-Config Auth**: Automatic Auth0 device flow with browser authentication
- **JWT Tokens**: Primary authentication method via Auth0
- **API Keys**: Alternative authentication for programmatic access
- **User Context Isolation**: All data scoped to authenticated user

**📊 Data Layer**:
- **Primary**: madnessinteractive.cc/api (centralized, secure, multi-user)
- **Fallback**: Local MongoDB (todos, lessons, explanations, audit logs)
- **Real-time**: MQTT messaging for cross-system coordination
- **Collections**: todos, lessons, explanations, todo_logs (when using local storage)
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
