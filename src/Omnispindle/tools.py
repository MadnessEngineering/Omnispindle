import json
import os
import ssl
import subprocess
import uuid
from datetime import datetime, UTC

import logging
from dotenv import load_dotenv
from fastmcp import Context
from pymongo import MongoClient

from .mqtt import mqtt_publish
from .utils import _format_duration
from .utils import create_response

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# Create MongoDB connection at module level
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
lessons_collection = db["lessons_learned"]


async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """
    
    Creates a task in the specified project with the given priority and target agent.
    Returns a compact representation of the created todo with an ID for reference.
    
    Parameters:
        description: Content of the todo item (task description)
        project: Project identifier (organizing category for the task)
        priority: Priority level [Low, Medium, High] (default: Medium)
        target_agent: Entity responsible for completing the task (default: user)
        metadata: Optional additional structured data for the todo
            { "ticket": "ticket number", "tags": ["tag1", "tag2"], "notes": "notes" }
        ctx: Optional context for logging
    
    Returns:
        JSON containing:
        - todo_id: Unique identifier for the created todo
        - description: Truncated task description
        - project: The project name
        - next_actions: Available actions for this todo
        - target_agent: Who should complete this (default: user)
        - metadata: Optional additional structured data for the todo
    """
    todo = {
        "id": str(uuid.uuid4()),
        "description": description,
        "project": project.lower(),
        "priority": priority,
        "source_agent": "Omnispindle",
        "target_agent": target_agent,
        "status": "initial",
        "created_at": int(datetime.now(UTC).timestamp()),
        "completed_at": None,
        "metadata": metadata or {}
    }

    try:
        collection.insert_one(todo)
    except Exception as e:
        # collection and mongo stats
        data = {
            "collection": MONGODB_COLLECTION,
            "mongo_stats": mongo_client.admin.command("dbstats")
        }
        return create_response(False, data, message=f"Failed to insert todo: {str(e)}", return_context=False)

    # MQTT publish as confirmation after the database operation - completely non-blocking
    try:
        mqtt_message = f"description: {description}, project: {project}, priority: {priority}, target_agent: {target_agent}"
        # Use a separate try/except to catch any issues with mqtt_publish itself
        try:
            publish_success = await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/add_todo", mqtt_message, ctx)
            if not publish_success:
                print(f"Warning: MQTT publish returned False for todo {todo['id']}")
        except Exception as mqtt_err:
            print(f"MQTT publish function error: {str(mqtt_err)}")
    except Exception as e:
        # Catch absolutely any errors in the MQTT process
        print(f"MQTT processing error (non-fatal): {str(e)}")

    # Return optimized response with essentials only
    # Description is truncated to save context tokens while still being identifiable
    if len(description) > 10:
        truncated_desc = description[:10] + "..." + description[-10:]
    else:
        truncated_desc = description
    return create_response(True, {
        "todo_id": todo["id"],
        "description": truncated_desc,
        "project": project,
        "next_actions": ["get_todo_tool", "update_todo_tool", "mark_todo_complete_tool"],
        "target_agent": target_agent,
        "metadata": metadata
    }, return_context=False)

async def query_todos(filter: dict = None, project: dict = None, limit: int = 100, ctx=None) -> str:
    """
    Query todos with flexible filtering options.
    
    Searches the todo database using MongoDB-style query filters and projections.
    Returns a collection of todos matching the filter criteria.
    
    Parameters:
        filter: MongoDB-style query object to filter todos (e.g., {"status": "pending"})
        project: Fields to include/exclude in results (e.g., {"description": 1})
        limit: Maximum number of todos to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of todos found
        - items: Array of matching todos with essential fields
        - projects: List of unique projects in the results (if multiple exist)
    """
    # Find matching todos first
    cursor = collection.find(
        filter or {},
        projection=project,
        limit=limit
    )
    results = list(cursor)

    # Create a summary to reduce context size
    summary = {
        "count": len(results),
        "items": []
    }

    # Include only essential fields for each todo
    for todo in results:
        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"],
            "project": todo["project"],
            "status": todo["status"],
            "priority": todo["priority"]
        })

    # MQTT publish as confirmation after the database query

    mqtt_message = f"filter: {json.dumps(filter)}, project: {json.dumps(project)}, limit: {limit}"
    await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/query_todos", mqtt_message, ctx)

    return create_response(True, summary)

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update an existing todo by ID.
    
    Modifies specified fields of a todo item. Common fields to update include 
    status, priority, description, and project.
    
    Parameters:
        todo_id: Unique identifier of the todo to update
        updates: Dictionary of fields to update and their new values
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and confirmation message
    """
    result = collection.update_one({"id": todo_id}, {"$set": updates})

    if result.modified_count == 0:
        return create_response(False, message="Todo not found")

    if ctx is not None:
        try:
            ctx.info(f"Updated todo {todo_id}")
        except ValueError:
            pass

    # MQTT publish as confirmation after the database update
    try:
        mqtt_message = f"todo_id: {todo_id}, updates: {json.dumps(updates)}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/update_todo", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Todo {todo_id} updated successfully")

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """
    Delete a todo by ID.
    
    Permanently removes a todo item from the database.
    This action cannot be undone.
    
    Parameters:
        todo_id: Unique identifier of the todo to delete
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and confirmation message
    """
    result = collection.delete_one({"id": todo_id})

    if result.deleted_count == 0:
        return create_response(False, message="Todo not found")

    if ctx is not None:
        try:
            ctx.info(f"Deleted todo {todo_id}")
        except ValueError:
            pass

    # MQTT publish as confirmation after the database deletion
    try:
        mqtt_message = f"todo_id: {todo_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/delete_todo", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Todo {todo_id} deleted")

async def get_todo(todo_id: str) -> str:
    """
    Get a specific todo by ID.
    
    Retrieves detailed information about a todo item including its 
    description, status, priority, and creation/completion information.
    
    Parameters:
        todo_id: Unique identifier of the todo to retrieve
        
    Returns:
        JSON containing the todo's details with fields:
        - id: Unique identifier
        - description: Full task description
        - project: Project category 
        - status: Current status (initial, pending, completed)
        - priority: Task priority
        - target: Entity responsible for the task
        - created: Creation timestamp
        - completed: Completion timestamp (if applicable)
        - duration: Time between creation and completion (if applicable)
    """
    todo = collection.find_one({"id": todo_id})

    if todo is None:
        return create_response(False, message="Todo not found")

    # Format todo with optimized information - keeping essentials and removing verbosity
    formatted_todo = {
        "id": todo["id"],
        "description": todo["description"],
        "project": todo["project"],
        "status": todo["status"],
        "priority": todo["priority"],
        "target": todo.get("target_agent", "user"),
        "created": todo["created_at"]
    }

    # Add completion information if available (using compact format)
    if todo.get("completed_at"):
        formatted_todo["completed"] = todo["completed_at"]
        # Only add duration when completed
        duration_seconds = todo["completed_at"] - todo["created_at"]
        formatted_todo["duration"] = _format_duration(duration_seconds)

    # MQTT publish without try/except to reduce code verbosity
    await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/get_todo", f"todo_id: {todo_id}")

    return create_response(True, formatted_todo)

async def mark_todo_complete(todo_id: str, ctx: Context = None) -> str:
    """
    Mark a todo as completed.
    
    Updates a todo's status to 'completed' and records the completion timestamp.
    This allows tracking of when tasks were completed and calculating the 
    duration between creation and completion.
    
    Parameters:
        todo_id: Unique identifier of the todo to mark as complete
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and completion information:
        - todo_id: The ID of the completed todo
        - completed_at: Formatted timestamp of when the todo was marked complete
    """
    completed_time = int(datetime.now(UTC).timestamp())

    result = collection.update_one(
        {"id": todo_id},
        {"$set": {"status": "review", "completed_at": completed_time}}
    )

    if result.modified_count == 0:
        return create_response(False, message="Todo not found or already completed")

    if ctx is not None:
        try:
            ctx.info(f"Completed todo {todo_id}")
        except ValueError:
            pass

    # MQTT publish as confirmation after marking todo complete
    try:
        mqtt_message = f"todo_id: {todo_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/mark_todo_complete", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, {
        "todo_id": todo_id,
        "completed_at": datetime.fromtimestamp(completed_time, UTC).strftime("%Y-%m-%d %H:%M")
    })

async def list_todos_by_status(status: str, limit: int = 100) -> str:
    """
    List todos filtered by status.
    
    Retrieves a collection of todos with the specified status.
    Common status values: 'initial', 'pending', 'completed'.
    Results are formatted for efficiency with truncated descriptions.
    
    Parameters:
        status: Status value to filter by
        limit: Maximum number of todos to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of todos found
        - status: The status that was queried
        - items: Array of matching todos (with truncated descriptions)
        - projects: List of unique projects (only included if multiple exist)
    """
    cursor = collection.find(
        {"status": status},
        limit=limit
    )
    results = list(cursor)

    # Create an optimized summary with only essential data
    summary = {
        "count": len(results),
        "status": status,
        "items": []
    }

    # Track unique projects (often useful for AI agents)
    unique_projects = set()

    # Add todo items with minimal but useful information
    for todo in results:
        project = todo.get("project", "unspecified")
        unique_projects.add(project)

        # Use concise format for list items to save tokens
        summary["items"].append({
            "id": todo["id"],
            "desc": todo["description"][:40] + ("..." if len(todo["description"]) > 40 else ""),
            "project": project
        })

    # Only add projects if there are multiple (otherwise it's not useful info)
    if len(unique_projects) > 1:
        summary["projects"] = list(unique_projects)

    # Publish MQTT status with minimal error handling
    await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/list_todos_by_status",
                      f"status: {status}, limit: {limit}, found: {len(results)}")

    return create_response(True, summary)

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    """
    Add a new lesson learned.
    
    Records knowledge or experiences in a structured format for future reference.
    Lessons are used to document important discoveries, solutions, or techniques.
    
    Parameters:
        language: Programming language or technology related to the lesson
        topic: Brief subject/title of the lesson
        lesson_learned: Detailed content describing what was learned
        tags: Optional list of keyword tags for categorization
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and the created lesson's ID and topic
    """
    lesson = {
        "id": str(uuid.uuid4()),
        "language": language,
        "topic": topic,
        "lesson_learned": lesson_learned,
        "tags": tags or [],
        "created_at": int(datetime.now(UTC).timestamp())
    }

    lessons_collection.insert_one(lesson)

    # MQTT publish as confirmation after adding lesson
    try:
        mqtt_message = f"language: {language}, topic: {topic}, tags: {tags}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/add_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, {"lesson_id": lesson["id"], "topic": topic})

async def get_lesson(lesson_id: str) -> str:
    """
    Get a specific lesson by ID.
    
    Retrieves detailed information about a previously recorded lesson.
    Includes the full content of the lesson and all associated metadata.
    
    Parameters:
        lesson_id: Unique identifier of the lesson to retrieve
        
    Returns:
        JSON containing the lesson's details with fields:
        - id: Unique identifier
        - language: Programming language or technology 
        - topic: Subject or title
        - lesson_learned: Full content
        - tags: Categorization tags
        - created: Formatted creation date
    """
    lesson = lessons_collection.find_one({"id": lesson_id})

    if lesson is None:
        return create_response(False, message="Lesson not found")

    # Format lesson for concise display
    formatted_lesson = {
        "id": lesson["id"],
        "language": lesson["language"],
        "topic": lesson["topic"],
        "lesson_learned": lesson["lesson_learned"],
        "tags": lesson.get("tags", []),
        "created": datetime.fromtimestamp(lesson["created_at"], UTC).strftime("%Y-%m-%d")
    }

    # MQTT publish as confirmation after getting lesson
    try:
        mqtt_message = f"lesson_id: {lesson_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/get_lesson", mqtt_message)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, formatted_lesson)

async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update an existing lesson by ID.
    
    Modifies specified fields of a lesson. Common fields to update include
    topic, lesson_learned content, and tags.
    
    Parameters:
        lesson_id: Unique identifier of the lesson to update
        updates: Dictionary of fields to update and their new values
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and confirmation message
    """
    result = lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
    if result.modified_count == 0:
        return create_response(False, message="Lesson not found")

    # MQTT publish as confirmation after updating lesson
    try:
        mqtt_message = f"lesson_id: {lesson_id}, updates: {json.dumps(updates)}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/update_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Lesson {lesson_id} updated successfully")

async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
    """
    Delete a lesson by ID.
    
    Permanently removes a lesson from the database.
    This action cannot be undone.
    
    Parameters:
        lesson_id: Unique identifier of the lesson to delete
        ctx: Optional context for logging
        
    Returns:
        JSON with success status and confirmation message
    """
    result = lessons_collection.delete_one({"id": lesson_id})

    if result.deleted_count == 0:
        return create_response(False, message="Lesson not found")

    # MQTT publish as confirmation after deleting lesson
    try:
        mqtt_message = f"lesson_id: {lesson_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/delete_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Lesson {lesson_id} deleted")

async def list_lessons(limit: int = 100) -> str:
    """
    List all lessons learned.
    
    Retrieves a collection of lessons with preview content.
    Each lesson includes a truncated preview of its content to reduce response size.
    
    Parameters:
        limit: Maximum number of lessons to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of lessons found
        - items: Array of lessons with preview content, including:
          - id: Lesson identifier
          - language: Programming language or technology
          - topic: Subject or title
          - tags: List of categorization tags
          - preview: Truncated content preview
    """
    cursor = lessons_collection.find(limit=limit)
    results = list(cursor)

    # Create a summary format
    summary = {
        "count": len(results),
        "items": []
    }

    # Add simplified lesson items
    for lesson in results:
        summary["items"].append({
            "id": lesson["id"],
            "language": lesson["language"],
            "topic": lesson["topic"],
            "tags": lesson.get("tags", []),
            "preview": lesson["lesson_learned"][:40] + ("..." if len(lesson["lesson_learned"]) > 40 else "")
        })

    # MQTT publish as confirmation after listing lessons
    try:
        mqtt_message = f"limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/list_lessons", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def search_todos(query: str, fields: list = None, limit: int = 100) -> str:
    """
    Search todos with text search capabilities.
    
    Performs a case-insensitive text search across specified fields in todos.
    Uses regex pattern matching to find todos matching the query string.
    
    Parameters:
        query: Text string to search for
        fields: List of fields to search in (default: ["description"])
        limit: Maximum number of todos to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of matching todos
        - query: The search query that was used
        - matches: Array of todos matching the search criteria with fields:
          - id: Todo identifier
          - description: Truncated task description
          - project: Project category
          - status: Current status
    """
    if not fields:
        fields = ["description"]

    # Create a regex pattern for case-insensitive search
    regex_pattern = {"$regex": query, "$options": "i"}

    # Build the query with OR conditions for each field
    search_conditions = []
    for field in fields:
        search_conditions.append({field: regex_pattern})

    search_query = {"$or": search_conditions}

    # Execute the search
    cursor = collection.find(search_query, limit=limit)
    results = list(cursor)

    # Create a compact summary of results
    summary = {
        "count": len(results),
        "query": query,
        "matches": []
    }

    # Include only essential fields for each todo
    for todo in results:
        summary["matches"].append({
            "id": todo["id"],
            "description": todo["description"][:50] + ("..." if len(todo["description"]) > 50 else ""),
            "project": todo["project"],
            "status": todo["status"]
        })

    # MQTT publish as confirmation after searching todos
    try:
        mqtt_message = f"query: {query}, fields: {fields}, limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/search_todos", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def search_lessons(query: str, fields: list = None, limit: int = 100) -> str:
    """
    Search lessons with text search capabilities.
    
    Performs a case-insensitive text search across specified fields in lessons.
    Uses regex pattern matching to find lessons matching the query string.
    
    Parameters:
        query: Text string to search for
        fields: List of fields to search in (default: ["topic", "lesson_learned"])
        limit: Maximum number of lessons to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of matching lessons
        - query: The search query that was used
        - matches: Array of lessons matching the search criteria with fields:
          - id: Lesson identifier
          - language: Programming language or technology 
          - topic: Subject or title
          - preview: Truncated content preview
          - tags: Categorization tags
    """
    if not fields:
        fields = ["topic", "lesson_learned"]

    # Create a regex pattern for case-insensitive search
    regex_pattern = {"$regex": query, "$options": "i"}

    # Build the query with OR conditions for each field
    search_conditions = []
    for field in fields:
        search_conditions.append({field: regex_pattern})

    search_query = {"$or": search_conditions}

    # Execute the search
    cursor = lessons_collection.find(search_query, limit=limit)
    results = list(cursor)

    # Create a compact summary of results
    summary = {
        "count": len(results),
        "query": query,
        "matches": []
    }

    # Include only essential fields for each lesson
    for lesson in results:
        summary["matches"].append({
            "id": lesson["id"],
            "language": lesson["language"],
            "topic": lesson["topic"],
            "preview": lesson["lesson_learned"][:40] + ("..." if len(lesson["lesson_learned"]) > 40 else ""),
            "tags": lesson.get("tags", [])
        })

    # MQTT publish as confirmation after searching lessons
    try:
        mqtt_message = f"query: {query}, fields: {fields}, limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/search_lessons", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)
