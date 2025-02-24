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
from datetime import datetime, UTC

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

@pytest.mark.asyncio
async def test_delete_todo_success(todo_server):
    # Mock a todo in the database
    todo_id = "test_id"
    todo_server.collection.delete_one.return_value = MagicMock(deleted_count=1)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "delete_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"

    # Verify MongoDB interaction
    todo_server.collection.delete_one.assert_called_once_with({"id": todo_id})

@pytest.mark.asyncio
async def test_delete_todo_not_found(todo_server):
    # Mock a todo not found in the database
    todo_id = "test_id"
    todo_server.collection.delete_one.return_value = MagicMock(deleted_count=0)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "delete_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "error"
    assert result["message"] == "Todo not found"

    # Verify MongoDB interaction
    todo_server.collection.delete_one.assert_called_once_with({"id": todo_id})

@pytest.mark.asyncio
async def test_get_todo_success(todo_server):
    # Mock a todo in the database
    todo_id = "test_id"
    todo = {
        "id": todo_id,
        "description": "Test todo",
        "priority": "high",
        "source_agent": "fastmcp",
        "target_agent": "test_agent",
        "status": "pending",
        "created_at": 1234567890,
        "completed_at": None
    }
    todo_server.collection.find_one.return_value = todo

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "get_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert result["todo"] == todo

    # Verify MongoDB interaction
    todo_server.collection.find_one.assert_called_once_with({"id": todo_id})

@pytest.mark.asyncio
async def test_get_todo_not_found(todo_server):
    # Mock a todo not found in the database
    todo_id = "test_id"
    todo_server.collection.find_one.return_value = None

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "get_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "error"
    assert result["message"] == "Todo not found"

    # Verify MongoDB interaction
    todo_server.collection.find_one.assert_called_once_with({"id": todo_id})

@pytest.mark.asyncio
async def test_mark_todo_complete_success(todo_server):
    # Mock a todo in the database
    todo_id = "test_id"
    todo_server.collection.update_one.return_value = MagicMock(modified_count=1)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "mark_todo_complete",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"

    # Verify MongoDB interaction
    todo_server.collection.update_one.assert_called_once_with(
        {"id": todo_id},
        {"$set": {"status": "completed", "completed_at": int(datetime.now(UTC).timestamp())}}
    )

@pytest.mark.asyncio
async def test_mark_todo_complete_not_found(todo_server):
    # Mock a todo not found in the database
    todo_id = "test_id"
    todo_server.collection.update_one.return_value = MagicMock(modified_count=0)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "mark_todo_complete",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "error"
    assert result["message"] == "Todo not found"

    # Verify MongoDB interaction
    todo_server.collection.update_one.assert_called_once_with(
        {"id": todo_id},
        {"$set": {"status": "completed", "completed_at": int(datetime.now(UTC).timestamp())}}
    )

@pytest.mark.asyncio
async def test_list_todos_by_status_success(todo_server):
    # Mock todos in the database
    todos = [
        {
            "id": "test_id_1",
            "description": "Test todo 1",
            "priority": "high",
            "source_agent": "fastmcp",
            "target_agent": "test_agent",
            "status": "pending",
            "created_at": 1234567890,
            "completed_at": None
        },
        {
            "id": "test_id_2",
            "description": "Test todo 2",
            "priority": "medium",
            "source_agent": "fastmcp",
            "target_agent": "test_agent",
            "status": "pending",
            "created_at": 1234567891,
            "completed_at": None
        }
    ]
    todo_server.collection.find.return_value = todos

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "list_todos_by_status",
        {
            "status": "pending"
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert result["todos"] == todos

    # Verify MongoDB interaction
    todo_server.collection.find.assert_called_once_with({"status": "pending"}, limit=100)

@pytest.mark.asyncio
async def test_list_todos_by_status_no_results(todo_server):
    # Mock no todos in the database
    todo_server.collection.find.return_value = []

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "list_todos_by_status",
        {
            "status": "completed"
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert result["todos"] == []

    # Verify MongoDB interaction
    todo_server.collection.find.assert_called_once_with({"status": "completed"}, limit=100)

# Unit Tests for Lessons Learned
@pytest.mark.asyncio
async def test_add_lesson_success(todo_server):
    # Test data
    language = "Python"
    topic = "Testing"
    lesson_learned = "Always write tests for your code."
    tags = ["testing", "best practices"]

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "add_lesson",
        {
            "language": language,
            "topic": topic,
            "lesson_learned": lesson_learned,
            "tags": tags
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert "lesson_id" in result

    # Verify MongoDB interaction
    todo_server.lessons_collection.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_get_lesson_success(todo_server):
    # Mock a lesson in the database
    lesson_id = "lesson_id_1"
    lesson = {
        "id": lesson_id,
        "language": "Python",
        "topic": "Testing",
        "lesson_learned": "Always write tests for your code.",
        "tags": ["testing", "best practices"],
        "created_at": 1234567890
    }
    todo_server.lessons_collection.find_one.return_value = lesson

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "get_lesson",
        {
            "lesson_id": lesson_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert result["lesson"] == lesson

    # Verify MongoDB interaction
    todo_server.lessons_collection.find_one.assert_called_once_with({"id": lesson_id})

@pytest.mark.asyncio
async def test_update_lesson_success(todo_server):
    # Mock a lesson in the database
    lesson_id = "lesson_id_1"
    todo_server.lessons_collection.update_one.return_value = MagicMock(modified_count=1)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "update_lesson",
        {
            "lesson_id": lesson_id,
            "updates": {"lesson_learned": "Updated lesson learned."}
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"

    # Verify MongoDB interaction
    todo_server.lessons_collection.update_one.assert_called_once_with(
        {"id": lesson_id},
        {"$set": {"lesson_learned": "Updated lesson learned."}}
    )

@pytest.mark.asyncio
async def test_delete_lesson_success(todo_server):
    # Mock a lesson in the database
    lesson_id = "lesson_id_1"
    todo_server.lessons_collection.delete_one.return_value = MagicMock(deleted_count=1)

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "delete_lesson",
        {
            "lesson_id": lesson_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"

    # Verify MongoDB interaction
    todo_server.lessons_collection.delete_one.assert_called_once_with({"id": lesson_id})

@pytest.mark.asyncio
async def test_list_lessons_success(todo_server):
    # Mock lessons in the database
    lessons = [
        {
            "id": "lesson_id_1",
            "language": "Python",
            "topic": "Testing",
            "lesson_learned": "Always write tests for your code.",
            "tags": ["testing", "best practices"],
            "created_at": 1234567890
        },
        {
            "id": "lesson_id_2",
            "language": "JavaScript",
            "topic": "Async Programming",
            "lesson_learned": "Use promises for better readability.",
            "tags": ["async", "promises"],
            "created_at": 1234567891
        }
    ]
    todo_server.lessons_collection.find.return_value = lessons

    # Call handler through FastMCP
    response = await todo_server.server.call_tool(
        "list_lessons",
        {
            "limit": 100
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    assert result["status"] == "success"
    assert result["lessons"] == lessons

    # Verify MongoDB interaction
    todo_server.lessons_collection.find.assert_called_once_with(limit=100)

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

@pytest.mark.asyncio
async def test_integration_delete_todo(integration_todo_server, mongo_client):
    # Add a todo to the database
    todo_id = "integration_test_id"
    todo = {
        "id": todo_id,
        "description": "Integration test todo",
        "priority": "high",
        "source_agent": "fastmcp",
        "target_agent": "test_agent",
        "status": "pending",
        "created_at": int(datetime.now(UTC).timestamp()),
        "completed_at": None
    }
    db = mongo_client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    collection.insert_one(todo)

    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "delete_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_delete_todo: {result['message']}")
    assert result["status"] == "success"

    # Verify the todo was actually deleted from MongoDB
    todo_after_delete = collection.find_one({"id": todo_id})
    assert todo_after_delete is None

@pytest.mark.asyncio
async def test_integration_get_todo(integration_todo_server, mongo_client):
    # Add a todo to the database
    todo_id = "integration_test_id"
    todo = {
        "id": todo_id,
        "description": "Integration test todo",
        "priority": "high",
        "source_agent": "fastmcp",
        "target_agent": "test_agent",
        "status": "pending",
        "created_at": int(datetime.now(UTC).timestamp()),
        "completed_at": None
    }
    db = mongo_client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    collection.insert_one(todo)

    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "get_todo",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_get_todo: {result['message']}")
    assert result["status"] == "success"
    assert result["todo"] == todo

@pytest.mark.asyncio
async def test_integration_mark_todo_complete(integration_todo_server, mongo_client):
    # Add a todo to the database
    todo_id = "integration_test_id"
    todo = {
        "id": todo_id,
        "description": "Integration test todo",
        "priority": "high",
        "source_agent": "fastmcp",
        "target_agent": "test_agent",
        "status": "pending",
        "created_at": int(datetime.now(UTC).timestamp()),
        "completed_at": None
    }
    db = mongo_client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    collection.insert_one(todo)

    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "mark_todo_complete",
        {
            "todo_id": todo_id
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_mark_todo_complete: {result['message']}")
    assert result["status"] == "success"

    # Verify the todo was actually marked as completed in MongoDB
    updated_todo = collection.find_one({"id": todo_id})
    assert updated_todo["status"] == "completed"
    assert updated_todo["completed_at"] is not None

@pytest.mark.asyncio
async def test_integration_list_todos_by_status(integration_todo_server, mongo_client):
    # Add todos to the database
    todos = [
        {
            "id": "integration_test_id_1",
            "description": "Integration test todo 1",
            "priority": "high",
            "source_agent": "fastmcp",
            "target_agent": "test_agent",
            "status": "pending",
            "created_at": int(datetime.now(UTC).timestamp()),
            "completed_at": None
        },
        {
            "id": "integration_test_id_2",
            "description": "Integration test todo 2",
            "priority": "medium",
            "source_agent": "fastmcp",
            "target_agent": "test_agent",
            "status": "pending",
            "created_at": int(datetime.now(UTC).timestamp()),
            "completed_at": None
        }
    ]
    db = mongo_client[TEST_MONGODB_DB]
    collection = db[TEST_MONGODB_COLLECTION]
    collection.insert_many(todos)

    # Call handler through FastMCP
    response = await integration_todo_server.server.call_tool(
        "list_todos_by_status",
        {
            "status": "pending"
        }
    )

    # Parse response
    result = json.loads(response[0].text)
    if result["status"] == "error":
        print(f"Error in test_integration_list_todos_by_status: {result['message']}")
    assert result["status"] == "success"
    assert len(result["todos"]) == 2
    assert result["todos"][0]["id"] == "integration_test_id_1"
    assert result["todos"][1]["id"] == "integration_test_id_2"
