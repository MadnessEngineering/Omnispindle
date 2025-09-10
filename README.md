# Omnispindle

**FastMCP-based task and knowledge management system for AI agents**

Omnispindle is the coordination layer of the Madness Interactive ecosystem. It provides standardized MCP tools for todo management, lesson capture, and cross-project coordination that AI agents can use to actually get work done.

## What it does

**For AI Agents:**
- Add, query, update, and complete todos with full audit logging
- Capture and search lessons learned across projects
- Access project-aware context and explanations
- Coordinate work across the Madness Interactive ecosystem

**For Humans:**
- Visual dashboard through [Inventorium](https://github.com/MadnessEngineering/Inventorium)
- Real-time updates via MQTT
- Claude Desktop integration via MCP
- Project-aware working directories

**For the Future:**
- Terraria mod integration (tools as inventory items - yes, really)
- SwarmDesk 3D workspace coordination
- Game-like AI context management for all skill levels

## Installation

### 📦 PyPI Installation (Recommended)

```bash
# Install from PyPI
pip install omnispindle

# Run the MCP stdio server
omnispindle-stdio

# Or run the web server
omnispindle
```

Available CLI commands after installation:
- `omnispindle` - Web server for authenticated endpoints
- `omnispindle-server` - Alias for web server
- `omnispindle-stdio` - MCP stdio server for Claude Desktop

### 🚀 Claude Desktop Integration (Zero Config!)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "your-email@example.com"
      }
    }
  }
}
```

**That's it!** The first time you use an Omnispindle tool:

1. 🌐 Your browser opens automatically for Auth0 login
2. 🔐 Log in with Google (or Auth0 credentials)
3. ✅ Token is saved locally for future use
4. 🎯 All MCP tools work seamlessly with your authenticated context

No tokens to copy, no manual config files, no complex setup!

### 🛠 Development Installation

```bash
# Clone the repository
git clone https://github.com/DanEdens/Omnispindle.git
cd Omnispindle

# Install dependencies
pip install -r requirements.txt

# Run the MCP server
python -m src.Omnispindle.stdio_server
```

For more details, see the [MCP Client Auth Guide](./docs/MCP_CLIENT_AUTH.md).

## Architecture

Omnispindle v1.0.0 features a modern API-first architecture:

### 🏗 Core Components
- **FastMCP Server** - High-performance MCP implementation with stdio/HTTP transports
- **API-First Design** - HTTP calls to `madnessinteractive.cc/api` (recommended)
- **Hybrid Mode** - API-first with local database fallback for reliability
- **Zero-Config Auth** - Automatic Auth0 device flow authentication
- **Tool Loadouts** - Configurable tool sets to reduce AI agent token usage

### 🔄 Operation Modes
- **`api`** - HTTP API calls only (recommended for production)
- **`hybrid`** - API-first with MongoDB fallback (default)
- **`local`** - Direct MongoDB connections (legacy mode)
- **`auto`** - Automatically choose best performing mode

### 🔐 Authentication & Security
- **Auth0 Integration** - JWT tokens from device flow authentication
- **API Key Support** - Alternative authentication method
- **User Isolation** - All data scoped to authenticated user context
- **Git-secrets Protection** - Automated credential scanning and prevention

## Configuration

### 🎛 Environment Variables

**Operation Mode**:
- `OMNISPINDLE_MODE` - `api`, `hybrid`, `local`, `auto` (default: `hybrid`)
- `OMNISPINDLE_TOOL_LOADOUT` - Tool loadout configuration (default: `full`)
- `OMNISPINDLE_FALLBACK_ENABLED` - Enable fallback in hybrid mode (default: `true`)

**Authentication**:
- `MADNESS_API_URL` - API base URL (default: `https://madnessinteractive.cc/api`)
- `MADNESS_AUTH_TOKEN` - JWT token from Auth0 device flow
- `MADNESS_API_KEY` - API key alternative authentication
- `MCP_USER_EMAIL` - User email for context isolation

**Local Database (hybrid/local modes)**:
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DB` - Database name (default: `swarmonomicon`)
- `MQTT_HOST` / `MQTT_PORT` - MQTT broker settings

### 🎯 Tool Loadouts

Configure `OMNISPINDLE_TOOL_LOADOUT` to control available functionality:

- **`full`** - All 22 tools available (default)
- **`basic`** - Essential todo management (7 tools)
- **`minimal`** - Core functionality only (4 tools)
- **`lessons`** - Knowledge management focus (7 tools)
- **`admin`** - Administrative tools (6 tools)
- **`hybrid_test`** - Testing hybrid functionality (6 tools)

## Integration

Part of the Madness Interactive ecosystem:
- **Inventorium** - Web dashboard and 3D workspace
- **SwarmDesk** - Project-specific AI environments
- **Terraria Integration** - Game-based AI interaction (coming soon)

## Development

```bash
# Run tests
pytest tests/

# Start STDIO MCP server (for Claude Desktop)
python stdio_main.py

# Start HTTP MCP server (for remote access)
python -m src.Omnispindle

# Check tool registration
python -c "from src.Omnispindle.stdio_server import OmniSpindleStdioServer; print(len(OmniSpindleStdioServer().server._tools))"
```

## Production Deployment

### Option 1: Local STDIO (Claude Desktop)

For local development and use with clients like Claude Desktop, the `stdio` server is recommended. It now supports secure authentication via Auth0 tokens.

1.  **Get Your Auth0 Token**: Follow the instructions in the [MCP Client Auth Guide](./docs/MCP_CLIENT_AUTH.md).

2.  **Configure Claude Desktop**: Update your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "AUTH0_TOKEN": "your_auth0_token_here",
        "OMNISPINDLE_TOOL_LOADOUT": "basic"
      }
    }
  }
}
```

This is now the preferred and most secure way to use Omnispindle with local MCP clients.

### Option 2: Remote HTTP (Cloudflare Protected)
```bash
# Start HTTP server
python -m src.Omnispindle

# Deploy infrastructure
cd OmniTerraformer/
./deploy.sh
```
Configure MCP client:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "mcp-remote",
      "args": ["https://madnessinteractive.cc/mcp/"]
    }
  }
}
```

## Privacy & Security

**This repository contains sensitive configurations:**
- Auth0 client credentials and domain settings
- Database connection strings and API endpoints
- MCP tool implementations with business logic
- Infrastructure as Code with account identifiers

**For production use:**
- Fork this repository for your own organization
- Update all authentication providers and credentials
- Configure your own domain and SSL certificates
- Review and modify tool permissions as needed

**Not recommended for public deployment without modification.**

## Philosophy

We build tools that make AI agents actually useful for real work. Simple interfaces, robust backends, and enough ambition to make it interesting.

The todo management works today. The Terraria integration will make your kids better at prompt engineering than most adults. The 3D workspace will make remote work feel like science fiction.

But first: get your todos managed properly.

---

*"Simple tools for complex minds, complex tools for simple minds"*
