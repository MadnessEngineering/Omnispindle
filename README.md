# Omnispindle

**A todo system that went too deep**

Started as "let's give Claude some memory." Ended up as a multi-mode, API-first, zero-config-auth MCP server with MongoDB fallbacks, MQTT messaging, tool loadouts, and plans for Terraria integration.

We contain multitudes. Also todos.

## What it actually does

**The boring (useful) parts:**
- AI agents can manage todos, capture lessons, search knowledge bases
- Full audit logging because trust issues are valid
- Project-aware context so your agent knows where it is
- Configurable tool loadouts (4 to 30 tools, pick your poison)
- Zero-config Auth0 authentication (browser opens, you login, done)

**The interesting (ambitious) parts:**
- Three operation modes: API-first, hybrid with fallbacks, or pure local
- MQTT for real-time cross-system coordination
- Visual dashboard via [Inventorium](https://github.com/MadnessEngineering/Inventorium)
- Integration with the Madness Interactive ecosystem

**The weird (future) parts:**
- Terraria mod where AI tools are actual inventory items
- SwarmDesk 3D workspace coordination
- Teaching kids prompt engineering through video games

First we manage todos properly. Then we get weird with it.

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

Omnispindle v1.0.0: where "just a todo app" went wonderfully wrong.

### 🏗 What's Inside
- **FastMCP Server** - Talks stdio and HTTP (your AI's new best friend)
- **API-First Design** - HTTP calls to `madnessinteractive.cc/api` (works great)
- **Hybrid Mode** - API-first with MongoDB parachute (just in case)
- **Zero-Config Auth** - Browser pops open, you login, magic happens
- **Tool Loadouts** - 4 to 30 tools depending on your token budget

### 🔄 Operation Modes
- **`api`** - HTTP API calls only (cloud-native, no database required)
- **`hybrid`** - API-first with MongoDB safety net (default, plays it safe)
- **`local`** - Direct MongoDB connections (old school, still works)
- **`auto`** - Picks the fastest option (let the system decide)

### 🔐 Authentication & Security
- **Auth0 Integration** - JWT tokens via device flow (browser handles it)
- **API Key Support** - For when you want long-lived tokens
- **User Isolation** - Your todos stay yours (database-level separation)
- **Git-secrets Protection** - Catches credentials before they hit GitHub

## Configuration

### 🎛 Environment Variables

**Operation Mode**:
- `OMNISPINDLE_MODE` - `api`, `hybrid`, `local`, `auto` (default: `hybrid`)
- `OMNISPINDLE_TOOL_LOADOUT` - Tool loadout configuration (default: `full`)
- `OMNISPINDLE_FALLBACK_ENABLED` - Enable fallback in hybrid mode (default: `true`)

**Authentication**:
- `MADNESS_API_URL` - API base URL (default: `https://madnessinteractive.cc/api`)
- `AUTH0_TOKEN` - JWT token from Auth0 device flow (for stdio/local MCP)
- `MADNESS_AUTH_TOKEN` - Alternative token name (used by API client in api/hybrid modes)
- `MADNESS_API_KEY` - API key alternative authentication
- `MCP_USER_EMAIL` - User email for context isolation

**Local Database (hybrid/local modes)**:
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DB` - Database name (default: `swarmonomicon`)
- `MQTT_HOST` / `MQTT_PORT` - MQTT broker settings

### 🎯 Tool Loadouts

Configure `OMNISPINDLE_TOOL_LOADOUT` to control available functionality:

- **`full`** - All 30 tools available (default)
- **`basic`** - Essential todo management (7 tools)
- **`minimal`** - Core functionality only (4 tools)
- **`lessons`** - Knowledge management focus (7 tools)
- **`admin`** - Administrative tools and session management (13 tools)
- **`lightweight`** - Token-optimized core functionality (10 tools)
- **`write_only`** - Create, update, delete operations only (6 tools)
- **`read_only`** - Query and get operations only (8 tools)
- **`hybrid_test`** - Testing hybrid functionality (6 tools)

## Integration

Part of the Madness Interactive ecosystem (yes, we named it that):
- **Inventorium** - Web dashboard and 3D workspace for humans who like GUIs
- **SwarmDesk** - Project-specific AI environments (think context switching, but spatial)
- **Terraria Integration** - Tools as inventory items (because why not)

## Development

```bash
# Run tests
pytest tests/

# Start STDIO MCP server (for Claude Desktop)
python -m src.Omnispindle.stdio_server

# Check tool registration
python -c "from src.Omnispindle.stdio_server import OmniSpindleStdioServer; print(len(OmniSpindleStdioServer().server._tools))"
```

## Usage with Claude Desktop

### STDIO Server Setup

The `stdio` server is how Claude Desktop talks to Omnispindle. Zero-config auth means you literally just run it.

1.  **Authentication**: Browser opens, you login, done. (Want manual token setup? See the [MCP Client Auth Guide](./docs/MCP_CLIENT_AUTH.md))

2.  **Configure Claude Desktop**: Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "OMNISPINDLE_TOOL_LOADOUT": "basic"
      }
    }
  }
}
```

That's it. Browser auth, local server, AI agents with todo superpowers.

## Privacy & Security

**Fair warning:** This repo has our Auth0 configs, database strings, and infrastructure-as-code with real account IDs. It's open source for learning and forking, not for deploying as-is to production.

**If you're actually using this:**
1. Fork it
2. Change all the auth providers and credentials
3. Point it at your own domains and databases
4. Review the tool permissions (we're pretty permissive)
5. Don't blame us if you deploy our configs to prod

This is a working system for our ecosystem. For yours, you'll need to make it your own.

## Philosophy

Most people build todo apps with 5 features and call it a day. We built one with 30 MCP tools, three operation modes, zero-config OAuth, and a roadmap involving Minecraft-adjacent technology.

This is either exactly the right amount of complexity or way too much. Time will tell.

**What works now:**
- Todo management for AI agents (rock solid)
- Knowledge capture across projects (actually useful)
- Zero-setup authentication (shockingly smooth)
- API-first architecture with MongoDB parachute (overkill? maybe. reliable? absolutely.)

**What's coming:**
- Teaching kids prompt engineering through Terraria (ambitious)
- 3D workspace coordination (science fiction vibes)
- Making AI context management feel like inventory management (weird, might work)

The complexity serves a purpose: AI agents need real tools for real work. We just happen to think "real work" shouldn't be boring.

---

*"Over-engineered? Maybe. Under-ambitious? Never."*
