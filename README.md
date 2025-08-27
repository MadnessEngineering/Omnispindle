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
- Visual dashboard through [Inventorium](../Inventorium) 
- Real-time updates via MQTT
- Claude Desktop integration via MCP
- Project-aware working directories

**For the Future:**
- Terraria mod integration (tools as inventory items - yes, really)
- SwarmDesk 3D workspace coordination
- Game-like AI context management for all skill levels

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up authentication
python -m src.Omnispindle auth --setup

# Run the MCP server
python stdio_main.py
```

Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["stdio_main.py"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "your@email.com"
      }
    }
  }
}
```

## Architecture

**MCP Tools** - Standard interface for AI agents to manage work
**MongoDB** - Persistent storage with audit trails  
**MQTT** - Real-time coordination across components
**FastMCP** - High-performance MCP server implementation
**Auth0/Cloudflare** - Secure authentication and access control

## Tool Loadouts

Configure `OMNISPINDLE_TOOL_LOADOUT` to control available functionality:

- `basic` - Essential todo management (7 tools)
- `minimal` - Core functionality only (4 tools) 
- `lessons` - Knowledge management focus (7 tools)
- `full` - Everything (22 tools)

## Integration

Part of the Madness Interactive ecosystem:
- **Inventorium** - Web dashboard and 3D workspace
- **SwarmDesk** - Project-specific AI environments  
- **Terraria Integration** - Game-based AI interaction (coming soon)

## Development

```bash
# Run tests
pytest tests/

# Start web server (for auth endpoints)
python -m src.Omnispindle

# Check tool registration
python -c "from src.Omnispindle.stdio_server import OmniSpindleStdioServer; print(len(OmniSpindleStdioServer().server._tools))"
```

## Philosophy

We build tools that make AI agents actually useful for real work. Simple interfaces, robust backends, and enough ambition to make it interesting.

The todo management works today. The Terraria integration will make your kids better at prompt engineering than most adults. The 3D workspace will make remote work feel like science fiction.

But first: get your todos managed properly.

---

*"Simple tools for complex minds, complex tools for simple minds"*
