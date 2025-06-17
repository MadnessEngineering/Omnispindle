"""
Tests for the search functionality in the FastMCP Todo Server
"""
import json
import pytest
import asyncio
import sys
import os
import uuid
from datetime import datetime, UTC
from pymongo import MongoClient
from dotenv import load_dotenv

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from fastmcp_todo_server.tools import search_todos, grep_lessons

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

@pytest.fixture
def mongo_client():
    """Create a MongoDB client for testing"""
    client = MongoClient(MONGODB_URI)
    yield client
    client.close()

@pytest.fixture
def test_db(mongo_client):
    """Get the test database"""
    return mongo_client[MONGODB_DB]

@pytest.fixture
def test_collections(test_db):
    """Get the test collections"""
    todos = test_db[MONGODB_COLLECTION]
    lessons = test_db["lessons_learned"]
    return todos, lessons

@pytest.fixture
async def sample_data(test_collections):
    """Insert sample data for testing the search functionality"""
    todos_collection, lessons_collection = test_collections
    
    # Sample todos
    todo_ids = []
    sample_todos = [
        {
            "id": str(uuid.uuid4()),
            "description": "Implement search functionality for todos",
            "project": "search_project",
            "priority": "high",
            "source_agent": "test",
            "target_agent": "user",
            "status": "pending",
            "created_at": int(datetime.now(UTC).timestamp()),
            "completed_at": None,
            "metadata": {
                "github_repo": "https://github.com/example/todo-server",
                "related_ticket": "SRCH-123"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "description": "Create documentation for the API",
            "project": "docs_project",
            "priority": "medium",
            "source_agent": "test",
            "target_agent": "dev-team",
            "status": "pending",
            "created_at": int(datetime.now(UTC).timestamp()),
            "completed_at": None,
            "metadata": {
                "doc_url": "https://example.com/api-docs"
            }
        }
    ]
    
    for todo in sample_todos:
        todos_collection.insert_one(todo)
        todo_ids.append(todo["id"])
    
    # Sample lessons
    lesson_ids = []
    sample_lessons = [
        {
            "id": str(uuid.uuid4()),
            "language": "python",
            "topic": "MongoDB Text Search",
            "lesson_learned": "Using regex patterns for basic text search works well for small datasets",
            "tags": ["mongodb", "search", "python"],
            "created_at": int(datetime.now(UTC).timestamp())
        },
        {
            "id": str(uuid.uuid4()),
            "language": "javascript",
            "topic": "React Frontend Development",
            "lesson_learned": "Always use functional components with hooks in React",
            "tags": ["react", "frontend", "javascript"],
            "created_at": int(datetime.now(UTC).timestamp())
        }
    ]
    
    for lesson in sample_lessons:
        lessons_collection.insert_one(lesson)
        lesson_ids.append(lesson["id"])
    
    yield todo_ids, lesson_ids
    
    # Clean up
    for todo_id in todo_ids:
        todos_collection.delete_one({"id": todo_id})
    
    for lesson_id in lesson_ids:
        lessons_collection.delete_one({"id": lesson_id})

@pytest.mark.asyncio
async def test_search_todos():
    """Test search_todos functionality"""
    # Search for todos with "search" in the description
    result = await search_todos("search")
    result_dict = json.loads(result)
    
    assert result_dict["status"] == "success"
    # We might have other todos with "search" in the description,
    # so we don't assert an exact count
    assert "count" in result_dict
    assert "todos" in result_dict
    
    # Check if at least one todo contains "search" in the description
    found = False
    for todo in result_dict["todos"]:
        if "search" in todo["description"].lower():
            found = True
            break
    
    assert found, "No todos found with 'search' in the description"

@pytest.mark.asyncio
async def test_search_todos_custom_fields():
    """Test search_todos with custom fields"""
    # Search for todos with "high" in the priority field
    result = await search_todos("high", fields=["priority"])
    result_dict = json.loads(result)
    
    assert result_dict["status"] == "success"
    assert "count" in result_dict
    assert "todos" in result_dict
    
    # Check if all returned todos have "high" priority
    for todo in result_dict["todos"]:
        assert "high" in todo["priority"].lower()

@pytest.mark.asyncio
async def test_grep_lessons():
    """Test grep_lessons functionality"""
    
    result = await grep_lessons("mongodb")
    
    # Parse the JSON response
    response = json.loads(result)
    
    # Verify response structure
    assert response["success"] is True
    assert "data" in response
    
    data = response["data"]
    assert "count" in data
    assert "pattern" in data
    assert "matches" in data
    assert data["pattern"] == "mongodb"
    
    # Verify matches structure if any results found
    if data["count"] > 0:
        match = data["matches"][0]
        assert "id" in match
        assert "language" in match
        assert "topic" in match
        assert "preview" in match
        assert "tags" in match
        
        # Verify preview is truncated appropriately
        assert len(match["preview"]) <= 63  # 60 chars + "..."
    
    print(f"✓ Found {data['count']} lessons matching 'mongodb'")


@pytest.mark.asyncio
async def test_grep_lessons_no_results():
    """Test grep_lessons with pattern that should return no results"""
    
    result = await grep_lessons("nonexistentpattern12345")
    
    # Parse the JSON response
    response = json.loads(result)
    
    # Verify response structure
    assert response["success"] is True
    assert "data" in response
    
    data = response["data"]
    assert data["count"] == 0
    assert data["pattern"] == "nonexistentpattern12345"
    assert data["matches"] == []
    
    print("✓ No results found for non-existent pattern (as expected)")

# Run tests
if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__])) 
