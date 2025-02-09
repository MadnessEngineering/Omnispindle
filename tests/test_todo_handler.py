# Set test environment variables before importing
import os

# Test configuration
TEST_MONGODB_URI = "mongodb://localhost:27017"
TEST_MONGODB_DB = "test_swarmonomicon"
TEST_MONGODB_COLLECTION = "test_todos"

# Set environment variables
os.environ["MONGODB_URI"] = TEST_MONGODB_URI
os.environ["MONGODB_DB"] = TEST_MONGODB_DB
os.environ["MONGODB_COLLECTION"] = TEST_MONGODB_COLLECTION

# Import everything else after setting environment variables
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.fastmcp_todo_server import TodoServer
import json
from pymongo import MongoClient

@pytest.fixture
def todo_server():
    # Mock MongoDB client for unit tests
    server = TodoServer()
    server.mongo_client = MagicMock()
    server.db = MagicMock()
    server.collection = MagicMock()
    return server

@pytest.fixture
def integration_todo_server():
    # Create MongoDB client and clean up any existing data
    client = MongoClient(TEST_MONGODB_URI)
    db = client[TEST_MONGODB_DB]
    
    # Drop the collection if it exists
    if TEST_MONGODB_COLLECTION in db.list_collection_names():
        db[TEST_MONGODB_COLLECTION].drop()
    
    # Create a new collection without any unique indexes
    collection = db.create_collection(TEST_MONGODB_COLLECTION)
    
    # Close the client
    client.close()
    
    # Create server with real MongoDB connection
    return TodoServer()

@pytest.fixture
def mongo_client():
    # Create a MongoDB client for verification
    client = MongoClient(TEST_MONGODB_URI)
    yield client
    
    # Cleanup: Drop test database after tests
    client.drop_database(TEST_MONGODB_DB)
    client.close()

# Unit Tests
@pytest.mark.asyncio
async def test_add_todo_success(todo_server):
    # Test data
    description = "Test todo"
    priority = "high"
    target_agent = "test_agent"
    
    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "add_todo",
        {
            "description": description,
            "priority": priority,
            "target_agent": target_agent
        }
    )
    
    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert "todo_id" in result
    
    # Verify MongoDB interaction
    todo_server.collection.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_add_todo_with_defaults(todo_server):
    # Test with minimal data
    description = "Test todo"
    
    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "add_todo",
        {
            "description": description
        }
    )
    
    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert "todo_id" in result
    
    # Verify MongoDB interaction
    todo_server.collection.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_add_todo_with_error(todo_server):
    # Test data
    description = "Test todo"
    error_message = "Database error"
    
    # Mock error response
    todo_server.collection.insert_one.side_effect = Exception(error_message)
    
    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "add_todo",
        {
            "description": description
        }
    )
    
    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "error"
    assert result["message"] == error_message

# Integration Tests
@pytest.mark.asyncio
async def test_integration_add_todo(integration_todo_server):
    # Test data
    description = "Integration test todo"
    priority = "high"
    target_agent = "test_agent"
    
    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "add_todo",
        {
            "description": description,
            "priority": priority,
            "target_agent": target_agent
        }
    )
    
    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_add_todo: {result['message']}")
    assert result["status"] == "success"
    todo_id = result["todo_id"]
    
    # Verify the todo was actually inserted in MongoDB
    client = MongoClient(TEST_MONGODB_URI)
    db = client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    todo = collection.find_one({"id": todo_id})
    client.close()
    
    assert todo is not None
    assert todo["description"] == description
    assert todo["priority"] == priority
    assert todo["target_agent"] == target_agent
    assert todo["status"] == "pending"

@pytest.mark.asyncio
async def test_integration_add_todo_with_defaults(integration_todo_server):
    # Test with minimal data
    description = "Integration test todo with defaults"
    
    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "add_todo",
        {
            "description": description
        }
    )
    
    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_add_todo_with_defaults: {result['message']}")
    assert result["status"] == "success"
    todo_id = result["todo_id"]
    
    # Verify the todo was actually inserted in MongoDB with default values
    client = MongoClient(TEST_MONGODB_URI)
    db = client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    todo = collection.find_one({"id": todo_id})
    client.close()
    
    assert todo is not None
    assert todo["description"] == description
    assert todo["priority"] == "medium"  # Default value
    assert todo["target_agent"] == "user"  # Default value
    assert todo["status"] == "pending"
