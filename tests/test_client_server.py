from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json
import pytest
import sys
import os
from fastapi.testclient import TestClient
from fastmcp import FastMCPServer

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from fastmcp_todo_server.server import create_app

async def main():
    # Create server parameters
    server_params = StdioServerParameters(
        command="python",
        args=["__init__.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", tools)

            # Add a todo
            result = await session.call_tool(
                "add_todo",
                arguments={
                    "description": "Test todo item",
                    "priority": "high",
                    "target_agent": "tester"
                }
            )
            print("\nAdd todo result:", result)

            # Query todos
            result = await session.call_tool(
                "query_todos",
                arguments={}
            )
            print("\nQuery todos result:", result)

@pytest.fixture
def test_client():
    app = create_app()
    return TestClient(app)

@pytest.fixture
def mcp_server():
    server = FastMCPServer()
    return server

def test_todo_creation(test_client):
    """Test creating a new todo item"""
    response = test_client.post(
        "/todos/",
        json={"title": "Test todo", "completed": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test todo"
    assert data["completed"] is False
    assert "id" in data

def test_todo_list(test_client):
    """Test getting list of todos"""
    # First create a todo
    test_client.post(
        "/todos/",
        json={"title": "Test todo", "completed": False}
    )

    response = test_client.get("/todos/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_todo_update(test_client):
    """Test updating a todo item"""
    # Create a todo first
    create_response = test_client.post(
        "/todos/",
        json={"title": "Test todo", "completed": False}
    )
    todo_id = create_response.json()["id"]

    # Update the todo
    response = test_client.put(
        f"/todos/{todo_id}",
        json={"title": "Updated todo", "completed": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated todo"
    assert data["completed"] is True

def test_todo_delete(test_client):
    """Test deleting a todo item"""
    # Create a todo first
    create_response = test_client.post(
        "/todos/",
        json={"title": "Test todo", "completed": False}
    )
    todo_id = create_response.json()["id"]

    # Delete the todo
    response = test_client.delete(f"/todos/{todo_id}")
    assert response.status_code == 200

    # Verify it's deleted
    get_response = test_client.get(f"/todos/{todo_id}")
    assert get_response.status_code == 404

def test_tool_registration(mcp_server):
    """Test that tools are properly registered"""
    tools = mcp_server.list_tools()
    assert len(tools) > 0
    # Verify expected tools are present
    tool_names = [tool.name for tool in tools]
    assert "create_todo" in tool_names
    assert "list_todos" in tool_names
    assert "update_todo" in tool_names
    assert "delete_todo" in tool_names

if __name__ == "__main__":
    asyncio.run(main())
