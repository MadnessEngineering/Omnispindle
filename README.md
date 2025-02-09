# FastMCP Todo Server

A FastMCP-based Todo Server for the Swarmonomicon project. This server receives todo requests via FastMCP and stores them in MongoDB for processing by the Swarmonomicon todo worker.

## Features

- FastMCP server for receiving todo requests
- MongoDB integration for todo storage
- Compatible with Swarmonomicon todo worker
- Python-based implementation

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/DanEdens/fastmcp-todo-server.git
   cd fastmcp-todo-server
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your configuration:
   ```bash
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB=swarmonomicon
   MONGODB_COLLECTION=todos
   ```

## Usage

1. Start the FastMCP server:
   ```bash
   python -m src.fastmcp_todo_server
   ```

2. Send todo requests to the server using FastMCP:
   ```python
   from fastmcp import FastMCPClient
   
   client = FastMCPClient()
   client.send_message({
       "description": "Example todo",
       "priority": "high",
       "target_agent": "user"
   })
   ```

## Development

1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run tests:
   ```bash
   pytest
   ```

## License

MIT License
