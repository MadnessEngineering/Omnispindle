# Omnispindle

**A todo system that went wonderfully, intentionally wrong.**

Omnispindle is the coordination spine of the Madness Interactive ecosystem — a Python FastMCP server with 32 tools that lets AI agents manage tasks, capture knowledge, coordinate sessions, and navigate the whole workshop from a single, standardized interface. PyPI packaged. Auth0 integrated. Runs anywhere a Claude Desktop config lives.

It started as "let's do todos properly." It became the central nervous system for a multi-project AI-assisted development lab. Both of these things are fine.

---

## What it actually does

**Todo management** — the boring part that enables everything else. Agents can create, query, update, complete, and audit tasks across any project in the ecosystem with full metadata, priority, target agent tracking, and change detection.

**Knowledge capture** — lessons learned get stored with language, topic, and tag metadata. Searchable by regex, text, or vector embedding. The institutional memory doesn't evaporate when the conversation ends.

**Session tracking** — AI work sessions in Inventorium can be forked, spawned, linked to todos, and traced through a full genealogy tree. Every thread of work has a parent and a lineage.

**Semantic search** — `find_relevant` uses vector embeddings to surface todos and lessons by meaning, not just keywords. `get_context_bundle` gives an agent the full project picture in one call.

**Bring your own tool** — inject Python, JavaScript, or shell code as a live MCP tool at runtime. No restart required. We did this because we needed it.

---

## Installation

```bash
pip install omnispindle
```

CLI commands available after install:
- `omnispindle-stdio` — MCP stdio server for Claude Desktop
- `omnispindle` / `omnispindle-server` — HTTP web server for authenticated endpoints

### Claude Desktop (zero config)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "you@example.com"
      }
    }
  }
}
```

First tool call opens your browser for Auth0 login. Token saves locally. That's it.

### Development

```bash
git clone https://github.com/DanEdens/Omnispindle.git
cd Omnispindle
pip install -r requirements.txt
python -m src.Omnispindle.stdio_server
```

---

## Tools

Full loadout is 32 tools across 6 categories. Control what's available — and your agent's token budget — with `OMNISPINDLE_TOOL_LOADOUT`.

### Todo Management (9 tools)
| Tool | What it does |
|------|-------------|
| `add_todo` | Create a task with project, priority, target agent, notes, and metadata |
| `query_todos` | MongoDB-style filter queries with projection, limit, offset, and `since` change detection |
| `update_todo` | Patch any fields; tracks `updated_by` for audit trail |
| `delete_todo` | Remove a task |
| `get_todo` | Fetch a single task by ID |
| `mark_todo_complete` | Complete with optional comment; writes to audit log |
| `list_todos_by_status` | Filter by status: pending, initial, completed |
| `search_todos` | Tokenized multi-word fuzzy text search |
| `list_project_todos` | Recent tasks for a specific project |

### Knowledge / Lessons (7 tools)
| Tool | What it does |
|------|-------------|
| `add_lesson` | Capture a lesson with language, topic, and tags |
| `get_lesson` | Fetch by ID |
| `update_lesson` | Patch lesson content or metadata |
| `delete_lesson` | Remove |
| `search_lessons` | Text search across lesson fields |
| `grep_lessons` | Regex pattern search |
| `list_lessons` | Browse all lessons, with brief mode for summaries |

### Inventorium Sessions (8 tools)
| Tool | What it does |
|------|-------------|
| `inventorium_sessions_list` | List sessions, optionally filtered by project |
| `inventorium_sessions_get` | Fetch a session by ID |
| `inventorium_sessions_create` | Start a new AI work session |
| `inventorium_sessions_spawn` | Spawn a child session from a parent, linked to a todo |
| `inventorium_sessions_fork` | Fork a session with optional message inheritance |
| `inventorium_sessions_genealogy` | Full ancestor/descendant trace for a session |
| `inventorium_sessions_tree` | Visual session tree for a project |
| `inventorium_todos_link_session` | Link a todo to a session |

### Context & Search (2 tools)
| Tool | What it does |
|------|-------------|
| `get_context_bundle` | One call: recent todos, lessons, session state, project stats for an agent's working context |
| `find_relevant` | Semantic RAG search via vector embeddings — finds related todos and lessons by meaning |

### System / Admin (5 tools)
| Tool | What it does |
|------|-------------|
| `query_todo_logs` | Audit log queries: filter by type, project, date range |
| `list_projects` | Enumerate known projects from filesystem |
| `explain` / `add_explanation` | Topic explanation system: persistent knowledge cards |
| `point_out_obvious` | Logs an observation with configurable sarcasm. Useful for marking known issues during automated runs. |

### Custom Code (1 tool)
| Tool | What it does |
|------|-------------|
| `bring_your_own` | Inject a Python, JavaScript, or shell function as a live MCP tool at runtime |

---

## Tool Loadouts

Set `OMNISPINDLE_TOOL_LOADOUT` to control what's registered:

| Loadout | Tools | Use case |
|---------|-------|----------|
| `full` | 32 | Everything |
| `basic` | 8 | Core todo CRUD + `get_context_bundle` |
| `minimal` | 4 | Add, query, get, mark complete |
| `lessons` | 7 | Knowledge management only |
| `admin` | 13 | Admin tasks + session management |
| `write_only` | 6 | Create/update/delete only |
| `read_only` | 10 | Query/get only |
| `lightweight` | 12 | Token-optimized core |
| `hybrid_test` | 6 | API connectivity testing |

---

## Operation Modes

Set via `OMNISPINDLE_MODE`:

- **`api`** — HTTP calls to `madnessinteractive.cc/api`. No local database needed. Best for cloud-native or multi-user setups.
- **`hybrid`** *(default)* — API-first with MongoDB fallback. Reliable when the network isn't.
- **`local`** — Direct MongoDB connections only. Good for offline development.
- **`auto`** — Benchmarks both and picks the faster one.

---

## Authentication

**Zero-config device flow**: On first tool call, a browser window opens for Auth0 login. Token is saved locally. All subsequent calls are authenticated without any configuration.

**Manual token setup** (optional):
```bash
python -m src.Omnispindle.token_exchange
```

**Environment variables**:
- `MADNESS_AUTH_TOKEN` or `AUTH0_TOKEN` — JWT from Auth0 device flow
- `MCP_USER_EMAIL` — required for per-user data isolation
- `MADNESS_API_URL` — override API base (default: `https://madnessinteractive.cc/api`)

All data is scoped per user at the database level. Your todos stay yours.

---

## Configuration

```bash
# Operation mode
OMNISPINDLE_MODE=hybrid          # api | hybrid | local | auto
OMNISPINDLE_TOOL_LOADOUT=basic   # see loadouts table above
OMNISPINDLE_FALLBACK_ENABLED=true

# Authentication
MADNESS_AUTH_TOKEN=<jwt>
MCP_USER_EMAIL=you@example.com

# Local/hybrid database
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=swarmonomicon

# Real-time events
MQTT_HOST=localhost
MQTT_PORT=1883
```

---

## Ecosystem

Omnispindle is the AI interface layer. The rest of the workshop:

**[Inventorium](https://madnessinteractive.cc)** — React web dashboard and SwarmDesk 3D spatial workspace. Humans use this. It reads todos and sessions via the REST API directly — not MCP, which is strictly for AI agents. If you're clicking buttons, you're in Inventorium. If you're an agent, you're calling MCP tools.

**[cartogomancy](https://github.com/DanEdens/cartogomancy)** — JS/TS codebase analysis tool (`npm install -g @madnessengineering/cartogomancy`). Point it at any JavaScript or TypeScript project; get back a rich JSON map of structure, complexity, git blame, and cross-references. Feed that map to SwarmDesk and your codebase becomes a 3D city you can walk through.

**SwarmDesk** — The 3D spatial visualization layer inside Inventorium. Todos, sessions, and cartogomancy code maps rendered as explorable architecture. Your project as a place, not a list.

**MadnessVR** — Quest 2 VR version of SwarmDesk. Put on the headset, walk through your codebase as actual geometry. This one is on the roadmap, not the release notes. But the plan exists and it's detailed.

**Cogwyrm** — AI chat companion integrated into the ecosystem. Uses Omnispindle MCP tools during conversations to read and write shared context.

**Swarmonomicon** — The core database layer. MongoDB, `swarmonomicon` database. Everything persistent lives here.

### The architecture rule

```
UI (Inventorium, forms, dashboards) → REST API → Database
AI agents (Claude, Cogwyrm, any MCP client) → MCP tools → Backend → Database
```

Never route UI through MCP. Never call the REST API directly from an AI agent. The separation is intentional and load-bearing.

---

## Development

```bash
# Tests
pytest tests/

# Stdio server (Claude Desktop)
python -m src.Omnispindle.stdio_server

# Web server
python -m src.Omnispindle

# Check tool count
python -c "from src.Omnispindle.tool_loadouts import _BASE_LOADOUTS; print(len(_BASE_LOADOUTS['full']), 'tools in full loadout')"
```

### PyPI Publishing

```bash
# Build and check
python -m build
python -m twine check dist/*

# Publish
python -m twine upload dist/*
```

---

## Privacy & Security

This repo contains Auth0 configs and infrastructure-as-code for our ecosystem. It's open source for learning and forking — not for deploying as-is.

If you're actually running this for your own setup:
1. Fork it
2. Replace all auth providers and credentials
3. Point it at your own domain and database
4. Review tool permissions (we're permissive by default)

This is a working system for our lab. For yours, make it yours.

---

## Philosophy

Most people build a todo app with 5 features. We built one with 32 MCP tools, three operation modes, session genealogy trees, vector embeddings, zero-config OAuth, and a roadmap that includes walking through your code in VR.

This is the right amount of complexity. Every piece is load-bearing.

**Working now:**
- Todo management for AI agents — robust, audited, per-user
- Persistent knowledge capture across projects
- Session tracking with full lineage
- Semantic search via vector embeddings
- Zero-config Auth0 that doesn't require a setup guide

**Coming:**
- MadnessVR: SwarmDesk on Quest 2
- Teaching prompt engineering through Terraria-style inventory mechanics
- cartogomancy → SwarmDesk → VR as one continuous pipeline

We write careful code. We're not afraid to push the boundaries when it's practical.

---

*"Over-engineered? Maybe. Under-ambitious? Never."*
