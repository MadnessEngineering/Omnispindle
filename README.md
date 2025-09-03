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

### Automatic Authentication (Zero Config!)

Just add Omnispindle to your MCP client:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle.stdio_server"],
      "cwd": "/path/to/Omnispindle"
    }
  }
}
```

**That's it!** The first time you use an Omnispindle tool, your browser will open for authentication. After logging in with Auth0 (or Google), you're all set. No tokens to copy, no environment variables to set.

### Manual Setup (Optional)

If you prefer manual configuration:

```bash
# Install dependencies
pip install -r requirements.txt

# Set your token (optional - automatic auth will handle this)
export AUTH0_TOKEN="your_token_here"

# Run the MCP server
python -m src.Omnispindle.stdio_server
```

For more details, see the [MCP Client Auth Guide](./docs/MCP_CLIENT_AUTH.md).

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
