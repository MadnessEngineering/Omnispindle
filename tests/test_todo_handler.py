import pytest
import json
from unittest.mock import MagicMock, patch
from src.fastmcp_todo_server import TodoHandler

@pytest.fixture
def todo_handler():
    with patch('src.fastmcp_todo_server.MongoClient') as mock_client:
        handler = TodoHandler()
        handler.collection = MagicMock()
        yield handler

@pytest.mark.asyncio
async def test_on_message_success(todo_handler):
    # Test data
    test_todo = {
        "description": "Test todo",
        "priority": "high",
        "target_agent": "test_agent"
    }
    
    # Call handler
    result = await todo_handler.on_message(json.dumps(test_todo))
    
    # Verify result
    assert result["status"] == "success"
    assert "todo_id" in result
    
    # Verify MongoDB interaction
    todo_handler.collection.insert_one.assert_called_once()
    inserted_todo = todo_handler.collection.insert_one.call_args[0][0]
    assert inserted_todo["description"] == "Test todo"
    assert inserted_todo["priority"] == "high"
    assert inserted_todo["target_agent"] == "test_agent"
    assert inserted_todo["status"] == "pending"
    assert inserted_todo["source_agent"] == "mcp_server"
    assert "created_at" in inserted_todo
    assert inserted_todo["completed_at"] is None

@pytest.mark.asyncio
async def test_on_message_invalid_json(todo_handler):
    # Test invalid JSON
    result = await todo_handler.on_message("invalid json")
    
    # Verify error handling
    assert result["status"] == "error"
    assert "message" in result
    
    # Verify no MongoDB interaction
    todo_handler.collection.insert_one.assert_not_called()

@pytest.mark.asyncio
async def test_on_message_missing_fields(todo_handler):
    # Test data with missing fields
    test_todo = {}
    
    # Call handler
    result = await todo_handler.on_message(json.dumps(test_todo))
    
    # Verify result
    assert result["status"] == "success"
    assert "todo_id" in result
    
    # Verify MongoDB interaction with default values
    todo_handler.collection.insert_one.assert_called_once()
    inserted_todo = todo_handler.collection.insert_one.call_args[0][0]
    assert inserted_todo["priority"] == "medium"
    assert inserted_todo["target_agent"] == "user"
    assert inserted_todo["source_agent"] == "mcp_server" 
