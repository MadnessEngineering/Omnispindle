[![Verified on MseeP](https://mseep.ai/badge.svg)](https://mseep.ai/app/7cd85c5a-291d-4027-9497-78bffcb8fd4e)

# Omnispindle - Advanced MCP Todo Management System


A comprehensive **FastMCP-based todo management system** that serves as the central nervous system for multi-project task coordination. Part of the larger [Madness Interactive](https://github.com/MadnessEngineering/Madness_Interactive) ecosystem, Omnispindle combines AI-powered task insights, real-time MQTT messaging, and a sophisticated Node-RED dashboard to transform chaos into productivity.

## 🔮 Architecture Overview

Omnispindle consists of multiple integrated components:

- **MCP Server Core**: FastMCP-based server providing standardized tool interfaces for AI agents
- **Todomill Projectorium**: Node-RED dashboard for visual task management and AI insights
- **MongoDB Backend**: Persistent storage for todos, lessons learned, and audit logs
- **MQTT Integration**: Real-time messaging for cross-system coordination
- **AI Assistant**: Integrated AI suggestions and task analysis capabilities

## ✨ Key Features

### 🤖 **AI Agent Integration**
- **MCP Tool Interface**: Standardized tools for AI agents to create, update, and manage todos
- **Multi-Project Support**: Organize tasks across Madness_Interactive, Omnispindle, Swarmonomicon, and more
- **Intelligent Suggestions**: AI-powered task analysis, effort estimation, and duplicate detection
- **Automated Workflows**: Agent-driven task orchestration and status updates

### 📊 **Visual Dashboard (Todomill Projectorium)**
- **Interactive Node-RED Interface**: Rich web-based dashboard with filtering and sorting
- **Real-time Updates**: Live task synchronization via MQTT messaging
- **AI-Enhanced Views**: Visual indicators for AI suggestions and insights
- **Project-based Organization**: Sidebar navigation and project-specific views

### 📈 **Advanced Task Management**
- **Comprehensive Metadata**: Priority, status, project assignment, and custom fields
- **Audit Logging**: Complete history tracking for all task operations
- **Lessons Learned**: Knowledge capture system for development insights
- **Smart Scheduling**: AI-assisted deadline and time slot suggestions

### 🔗 **System Integration**
- **MQTT Messaging**: Pub/sub architecture for real-time coordination
- **MongoDB Storage**: Scalable document storage with flexible querying
- **Cross-Platform APIs**: RESTful and MCP interfaces for diverse integrations
- **Docker Support**: Containerized deployment with docker-compose orchestration

## 💡 Use Cases

### AI-Powered Side Quest Management

One of Omnispindle's most powerful features is enabling AI agents to capture and manage spontaneous ideas and "side quests" without disrupting your main workflow. When you're deep in development and a brilliant idea strikes, or you're in a meeting and remember a critical task - AI agents can seamlessly capture, categorize, and schedule these thoughts.

![Use Case Example: Saving a Side Quest for Later](../../docs/assets/images/Use-case-example-saving-a-side-quest-for-later.png)

This MCP-powered workflow demonstrates how:
- **AI agents automatically categorize** new tasks by project and priority
- **Context-aware scheduling** suggests optimal timing based on your current workload
- **Cross-project coordination** ensures tasks are visible across your entire ecosystem
- **Real-time dashboard updates** via MQTT keep all stakeholders informed
- **Intelligent suggestions** help reduce redundancy and optimize task organization

The captured tasks integrate seamlessly with the Todomill Projectorium dashboard, where you can review, refine, and execute them when you're ready to tackle them.

## 🚀 Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DanEdens/Omnispindle.git
   cd Omnispindle
   ```

2. **Install with uv (recommended):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv venv
   source .venv/bin/activate  # On Unix/macOS
   uv pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your MongoDB and MQTT settings
   ```

4. **Start with Docker (easiest):**
   ```bash
   docker-compose up -d
   ```

### Configuration

Create a `.env` file with your settings:

```bash
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=todo_app
MONGODB_COLLECTION=todos

# MQTT Configuration
MQTT_HOST=localhost
MQTT_PORT=1883

# AI Integration (optional)
AI_API_ENDPOINT=http://localhost:1234/v1
AI_MODEL=qwen2.5-7b-instruct
```

## 🛠 Usage

### MCP Integration (Claude Desktop)

#### Docker Configuration

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "host",
        "-e", "MONGODB_URI=mongodb://localhost:27017",
        "-e", "MONGODB_DB=swarmonomicon",
        "-e", "MQTT_HOST=localhost",
        "danedens31/omnispindle:latest"
      ]
    }
  }
}
```

#### Docker Compose Configuration

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env-file", "/path/to/your/.env",
        "--network", "omnispindle_default",
        "danedens31/omnispindle:latest"
      ]
    }
  }
}
```

#### Local Development Configuration

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "python",
      "args": ["-m", "src.Omnispindle"],
      "cwd": "/path/to/Omnispindle",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "swarmonomicon",
        "MQTT_HOST": "localhost"
      }
    }
  }
}
```

### Available MCP Tools

The server exposes the following tools for AI agents:

- `add_todo_tool` - Create new tasks with metadata
- `query_todos_tool` - Search and filter tasks
- `update_todo_tool` - Modify existing tasks
- `mark_todo_complete_tool` - Complete tasks
- `list_project_todos_tool` - Get tasks by project
- `add_lesson_tool` - Capture lessons learned
- `search_lessons_tool` - Query knowledge base
- `mqtt_publish_tool` - Send real-time messages
- `mqtt_get_tool` - Retrieve MQTT messages

### Starting the MCP Server

```bash
# Development mode
python -m src.Omnispindle

# Production mode
uvicorn src.Omnispindle.server:app --host 0.0.0.0 --port 8000
```

### Using MCP Tools (for AI Agents)

The server exposes standardized MCP tools that AI agents can call:

```python
# Example: AI agent creating a todo
await add_todo_tool(
    description="Implement user authentication",
    project="Omnispindle",
    priority="High",
    target_agent="developer",
    metadata={"ticket": "AUTH-123", "tags": ["security", "backend"]}
)

# Example: AI agent querying todos
results = await query_todos_tool(
    query_or_filter="project:Omnispindle",
    fields_or_projection="all",
    limit=50
)
```

### API Usage

```python
from fastmcp import FastMCPClient

# Connect to Omnispindle
client = FastMCPClient("http://localhost:8000")

# Create a new todo
response = await client.call_tool("add_todo_tool", {
    "description": "Fix critical bug in authentication",
    "project": "Madness_interactive",
    "priority": "High"
})

# Get project todos
todos = await client.call_tool("list_project_todos_tool", {
    "project": "Omnispindle",
    "limit": 10
})
```

### Node-RED Dashboard

1. **Access the dashboard** at `http://localhost:1880/ui`
2. **Import flows** from `Todomill_projectorium/ExportedNodeRedTabs/`
3. **Configure MQTT** connection to point to your Omnispindle instance

## 📁 Project Structure

```
Omnispindle/
├── src/Omnispindle/           # Main MCP server implementation
│   ├── __init__.py           # Tool registration and initialization
│   ├── server.py             # FastMCP server core
│   ├── tools.py              # Todo and lesson management tools
│   ├── ai_assistant.py       # AI integration and suggestions
│   ├── scheduler.py          # Smart scheduling features
│   ├── mqtt.py               # MQTT messaging integration
│   └── todo_log_service.py   # Audit logging service
├── Todomill_projectorium/     # Node-RED dashboard subrepo
│   ├── ExportedNodeRedTabs/  # Node-RED flow definitions
│   ├── JavascriptFromFunctionNode/  # Dashboard logic
│   ├── HtmlFromTemplateNode/ # UI templates
│   └── UIComponents/         # Reusable UI components
├── tests/                    # Test suite
├── config/                   # Configuration files
├── docs/                     # Documentation
├── docker-compose.yml        # Container orchestration
└── pyproject.toml           # Project metadata
```

## 🔧 Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific tests
pytest tests/test_todo_log.py -v
```

### Working with the Node-RED Dashboard

1. **Edit JavaScript/HTML** files in `Todomill_projectorium/`
2. **Copy changes** to Node-RED editor
3. **Export updated flows** to JSON files
4. **Commit both** the extracted files and JSON exports

### Adding New MCP Tools

1. **Define the tool function** in `src/Omnispindle/tools.py`
2. **Register the tool** in `src/Omnispindle/__init__.py`
3. **Add tests** in `tests/`
4. **Update documentation**

## 🌐 Integration Examples

### Swarmonomicon Integration

```python
# Omnispindle works with Swarmonomicon for distributed task processing
from swarmonomicon import TaskAgent

agent = TaskAgent("omnispindle-worker")
agent.register_mcp_server("http://localhost:8000")

# Agent can now create and manage todos via MCP
await agent.execute_task("create_todo", {
    "description": "Process data pipeline",
    "project": "Swarmonomicon"
})
```

### GitHub Issues Sync

```python
# Sync todos with GitHub issues
todo_id = await add_todo_tool(
    description="Fix authentication bug",
    project="Madness_interactive",
    metadata={"github_issue": 1234}
)
```

### MQTT Event Streaming

```bash
# Subscribe to todo events
mosquitto_sub -t "omnispindle/todos/+/+"

# Publish todo creation request
mosquitto_pub -t "omnispindle/todos/create" -m '{
    "description": "Deploy to production",
    "project": "Omnispindle",
    "priority": "High"
}'
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Run the test suite**: `pytest tests/`
5. **Submit a pull request**

### Development Guidelines

- Follow [PEP 8](https://pep8.org/) for Python code style
- Write tests for new features
- Update documentation for API changes
- Use semantic commit messages

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- **[Madness Interactive](https://github.com/MadnessEngineering/Madness_Interactive)** - Parent project ecosystem
- **[Swarmonomicon](https://github.com/DanEdens/madness_interactive/tree/main/projects/common/Swarmonomicon)** - Distributed task processing system
- **[FastMCP](https://github.com/jlowin/fastmcp)** - Model Context Protocol server framework

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/DanEdens/Omnispindle/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DanEdens/Omnispindle/discussions)
- **Documentation**: [docs/](docs/) directory

---

*"In the chaotic symphony of development tasks, Omnispindle conducts with AI-powered precision!"* 🎭✨
