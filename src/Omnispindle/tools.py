import json
import os
import ssl
import subprocess
import uuid
from datetime import datetime, UTC
from typing import Union

import logging
from dotenv import load_dotenv
from fastmcp import Context
from pymongo import MongoClient

from .mqtt import mqtt_publish
from .utils import _format_duration
from .utils import create_response
from .todo_log_service import get_service_instance as get_log_service
from .todo_log_service import log_todo_create, log_todo_update, log_todo_complete, log_todo_delete

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
tags_cache_collection = db["tags_cache"]
projects_collection = db["projects"]

# Cache constants
TAGS_CACHE_KEY = "all_lesson_tags"
TAGS_CACHE_EXPIRY = 43200  # Cache expiry in seconds (12 hours)
PROJECTS_CACHE_KEY = "all_valid_projects"
PROJECTS_CACHE_EXPIRY = 43200  # Cache expiry in seconds (12 hours)

# Valid project list - all lowercase for case-insensitive matching
# TODO: This will be migrated to MongoDB and deprecated
VALID_PROJECTS = [
    "madness_interactive",
    "regressiontestkit",
    "omnispindle",
    "todomill_projectorium",
    "swarmonomicon",
    "hammerspoon",
    "lab_management",
    "cogwyrm",
    "docker_implementation",
    "documentation",
    "eventghost",
    "hammerghost",
    "quality_assurance",
    "spindlewrit",
    "inventorium"
]

# Cache utility functions
def cache_lesson_tags(tags_list):
    """
    Cache the list of all lesson tags in MongoDB.
    
    Args:
        tags_list: List of tags to cache
    """
    try:
        # Add timestamp for cache expiry management
        cache_entry = {
            "key": TAGS_CACHE_KEY,
            "tags": list(tags_list),
            "updated_at": int(datetime.now(UTC).timestamp())
        }

        # Use upsert to update if exists or insert if not
        tags_cache_collection.update_one(
            {"key": TAGS_CACHE_KEY},
            {"$set": cache_entry},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"Failed to cache lesson tags: {str(e)}")
        return False

def get_cached_lesson_tags():
    """
    Retrieve the cached list of lesson tags from MongoDB.
    
    Returns:
        List of tags if cache exists and is valid, None otherwise
    """
    try:
        # Find the cache entry
        cache_entry = tags_cache_collection.find_one({"key": TAGS_CACHE_KEY})

        if not cache_entry:
            return None

        # Check if cache is expired
        current_time = int(datetime.now(UTC).timestamp())
        if current_time - cache_entry["updated_at"] > TAGS_CACHE_EXPIRY:
            # Cache expired, invalidate it
            invalidate_lesson_tags_cache()
            return None

        return cache_entry["tags"]
    except Exception as e:
        logging.error(f"Failed to retrieve cached lesson tags: {str(e)}")
        return None

def invalidate_lesson_tags_cache():
    """
    Invalidate the lesson tags cache in MongoDB.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        tags_cache_collection.delete_one({"key": TAGS_CACHE_KEY})
        return True
    except Exception as e:
        logging.error(f"Failed to invalidate lesson tags cache: {str(e)}")
        return False

def get_all_lesson_tags():
    """
    Get all unique tags from lessons, with caching.
    
    First tries to fetch from cache, falls back to database if needed.
    Also updates the cache if fetching from database.
    
    Returns:
        List of all unique tags
    """
    # Try to get from cache first
    cached_tags = get_cached_lesson_tags()
    if cached_tags is not None:
        return cached_tags

    # If not in cache, query from database
    try:
        # Use MongoDB aggregation to get all unique tags
        pipeline = [
            {"$project": {"tags": 1}},
            {"$unwind": "$tags"},
            {"$group": {"_id": None, "unique_tags": {"$addToSet": "$tags"}}},
        ]
        result = list(lessons_collection.aggregate(pipeline))

        # Extract tags from result
        all_tags = []
        if result and 'unique_tags' in result[0]:
            all_tags = result[0]['unique_tags']

        # Cache the results for future use
        cache_lesson_tags(all_tags)
        return all_tags
    except Exception as e:
        logging.error(f"Failed to aggregate lesson tags: {str(e)}")
        return []

# Project management functions
def cache_projects(projects_list):
    """
    Cache the list of valid projects in MongoDB.
    
    Args:
        projects_list: List of project names to cache
    """
    try:
        cache_entry = {
            "key": PROJECTS_CACHE_KEY,
            "projects": list(projects_list),
            "updated_at": int(datetime.now(UTC).timestamp())
        }

        tags_cache_collection.update_one(
            {"key": PROJECTS_CACHE_KEY},
            {"$set": cache_entry},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"Failed to cache projects: {str(e)}")
        return False

def get_cached_projects():
    """
    Retrieve the cached list of valid projects from MongoDB.
    
    Returns:
        List of project names if cache exists and is valid, None otherwise
    """
    try:
        cache_entry = tags_cache_collection.find_one({"key": PROJECTS_CACHE_KEY})

        if not cache_entry:
            return None

        # Check if cache is expired
        current_time = int(datetime.now(UTC).timestamp())
        if current_time - cache_entry["updated_at"] > PROJECTS_CACHE_EXPIRY:
            invalidate_projects_cache()
            return None

        return cache_entry["projects"]
    except Exception as e:
        logging.error(f"Failed to retrieve cached projects: {str(e)}")
        return None

def invalidate_projects_cache():
    """
    Invalidate the projects cache in MongoDB.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        tags_cache_collection.delete_one({"key": PROJECTS_CACHE_KEY})
        return True
    except Exception as e:
        logging.error(f"Failed to invalidate projects cache: {str(e)}")
        return False

def initialize_projects_collection():
    """
    Initialize the projects collection with the current VALID_PROJECTS list.
    This is a one-time migration function that includes git URLs and paths.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if projects collection is already populated
        existing_count = projects_collection.count_documents({})
        if existing_count > 0:
            logging.info(f"Projects collection already has {existing_count} projects")
            return True

        # Insert all valid projects with enhanced metadata
        current_time = int(datetime.now(UTC).timestamp())
        projects_to_insert = []

        # Enhanced project definitions with git URLs and paths
        project_definitions = {
            "madness_interactive": {
                "git_url": "https://github.com/d-edens/madness_interactive.git",
                "relative_path": "",
                "description": "Main Madness Interactive project hub"
            },
            "regressiontestkit": {
                "git_url": "https://github.com/d-edens/regressiontestkit.git",
                "relative_path": "../regressiontestkit",
                "description": "Regression testing framework"
            },
            "omnispindle": {
                "git_url": "https://github.com/d-edens/madness_interactive.git",
                "relative_path": "projects/python/Omnispindle",
                "description": "MCP server for todo management"
            },
            "todomill_projectorium": {
                "git_url": "https://github.com/d-edens/todomill_projectorium.git",
                "relative_path": "projects/python/Omnispindle/Todomill_projectorium",
                "description": "Node-RED dashboard for todo management"
            },
            "swarmonomicon": {
                "git_url": "https://github.com/d-edens/swarmonomicon.git",
                "relative_path": "projects/common/Swarmonomicon",
                "description": "AI agent swarm coordination system"
            },
            "hammerspoon": {
                "git_url": "https://github.com/d-edens/hammerspoon-config.git",
                "relative_path": "projects/lua/hammerspoon",
                "description": "Hammerspoon automation scripts"
            },
            "lab_management": {
                "git_url": None,
                "relative_path": "lab",
                "description": "Lab infrastructure management"
            },
            "cogwyrm": {
                "git_url": "https://github.com/d-edens/cogwyrm.git",
                "relative_path": "projects/mobile/Cogwyrm",
                "description": "Mobile application project"
            },
            "docker_implementation": {
                "git_url": None,
                "relative_path": "docker",
                "description": "Docker containerization configs"
            },
            "documentation": {
                "git_url": None,
                "relative_path": "docs",
                "description": "Project documentation"
            },
            "eventghost": {
                "git_url": "https://github.com/d-edens/eventghost-rust.git",
                "relative_path": "projects/rust/EventGhost-Rust",
                "description": "EventGhost automation in Rust"
            },
            "hammerghost": {
                "git_url": None,
                "relative_path": "projects/lua/hammerghost",
                "description": "Hammerspoon-EventGhost bridge"
            },
            "quality_assurance": {
                "git_url": None,
                "relative_path": "qa",
                "description": "Quality assurance tools and processes"
            },
            "spindlewrit": {
                "git_url": None,
                "relative_path": "projects/common/spindlewrit",
                "description": "Documentation generation tools"
            },
            "inventorium": {
                "git_url": "https://github.com/d-edens/inventorium.git",
                "relative_path": "projects/common/Inventorium",
                "description": "Asset and inventory management"
            }
        }

        for project_name in VALID_PROJECTS:
            project_def = project_definitions.get(project_name, {})

            project_doc = {
                "id": project_name,
                "name": project_name,
                "display_name": project_name.replace("_", " ").title(),
                "active": True,
                "git_url": project_def.get("git_url"),
                "relative_path": project_def.get("relative_path", f"projects/{project_name}"),
                "description": project_def.get("description", f"{project_name} project"),
                "created_at": current_time,
                "updated_at": current_time
            }
            projects_to_insert.append(project_doc)

        # Bulk insert all projects
        projects_collection.insert_many(projects_to_insert)
        logging.info(f"Initialized projects collection with {len(projects_to_insert)} projects")

        # Cache the project names
        cache_projects(VALID_PROJECTS)

        return True
    except Exception as e:
        logging.error(f"Failed to initialize projects collection: {str(e)}")
        return False

def get_all_projects():
    """
    Get all valid projects, with caching.
    
    First tries to fetch from cache, falls back to database if needed.
    Also initializes the database if it's empty.
    
    Returns:
        List of project names
    """
    # Try to get from cache first
    cached_projects = get_cached_projects()
    if cached_projects is not None:
        return cached_projects

    # If not in cache, query from database
    try:
        # Initialize collection if it's empty
        if projects_collection.count_documents({}) == 0:
            initialize_projects_collection()

        # Query projects from database
        cursor = projects_collection.find({}, {"id": 1, "_id": 0})
        project_names = [doc["id"] for doc in cursor]

        # Fallback to VALID_PROJECTS if database query fails
        if not project_names:
            logging.warning("No projects found in database, falling back to VALID_PROJECTS")
            project_names = VALID_PROJECTS.copy()

        # Cache the results for future use
        cache_projects(project_names)
        return project_names
    except Exception as e:
        logging.error(f"Failed to get projects from database: {str(e)}")
        # Fallback to hardcoded list
        return VALID_PROJECTS.copy()

def validate_project_name(project: str) -> str:
    """
    Validates and normalizes project names to ensure they match the allowed projects.
    Now uses the centralized project management system.
    
    Args:
        project: Project name to validate (any case)
        
    Returns:
        Normalized project name (lowercase) if valid, or "madness_interactive" as fallback
    """
    if not project:
        logging.warning(f"Empty project name received, defaulting to madness_interactive")
        return "madness_interactive"

    # Convert to lowercase for case-insensitive matching
    project_lower = project.lower()

    # Get valid projects from centralized system
    valid_projects = get_all_projects()

    # Direct match with valid projects
    if project_lower in valid_projects:
        return project_lower

    # Try to find a partial match (common issue with typos)
    for valid_proj in valid_projects:
        if valid_proj in project_lower or project_lower in valid_proj:
            logging.info(f"Project '{project}' matched to '{valid_proj}' instead")
            return valid_proj

    # No match found, use default
    logging.warning(f"Invalid project name '{project}', defaulting to madness_interactive")
    return "madness_interactive"


async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """
    
    Creates a task in the specified project with the given priority and target agent.
    Returns a compact representation of the created todo with an ID for reference.
    
    Parameters:
        description: Content of the todo item (task description)
        project: Project identifier (organizing category for the task)
        priority: Importance level ("Low", "Medium", "High")
        target_agent: The agent or system responsible for this todo
        metadata: Additional data like ticket number, tags, notes
        ctx: Optional context object with user agent info
        
    Returns:
        JSON containing:
        - success: Boolean indicating if the operation succeeded
        - message: Status message about the operation
        - data: Created todo item information (ID, description, project)
    """
    # Validate the project name
    project = validate_project_name(project)

    # Ensure priority is one of the allowed values
    if priority not in ["Low", "Medium", "High"]:
        priority = "Medium"

    # Create the todo object
    todo_id = str(uuid.uuid4())
    created_at = int(datetime.now(UTC).timestamp())

    todo = {
        "id": todo_id,
        "description": description,
        "project": project,
        "priority": priority,
        "status": "pending",
        "target": target_agent,
        "created_at": created_at
    }

    # Add metadata if provided
    if metadata:
        todo["metadata"] = metadata

    # Insert into MongoDB
    try:
        collection.insert_one(todo)
        logging.info(f"Todo created: {todo_id}")

        # Log the todo creation
        user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
        await log_todo_create(todo_id, description, project, user_agent)

        # Create a success response with the todo ID and truncated description
        return create_response(True,
            {
                "todo_id": todo_id,
                "description": description[:40] + ("..." if len(description) > 40 else ""),
                "project": project
            },
            "Todo created successfully"
        )
    except Exception as e:
        error_msg = f"Failed to create todo: {str(e)}"
        logging.error(error_msg)
        return create_response(False, message=error_msg)

async def query_todos(filter: dict = None, projection: dict = None, limit: int = 100, ctx=None) -> str:
    """
    Query todos with flexible filtering options.
    
    Searches the todo database using MongoDB-style query filters and projections.
    Returns a collection of todos matching the filter criteria.
    
    Parameters:
        filter: MongoDB-style query object to filter todos (e.g., {"status": "pending"})
        projection: Fields to include/exclude in results (e.g., {"description": 1})
        limit: Maximum number of todos to return (default: 100)
        
    Returns:
        JSON containing:
        - count: Number of todos found
        - items: Array of matching todos with essential fields
        - projects: List of unique projects in the results (if multiple exist)
    """
    # Process filter to ensure project and status fields are case insensitive
    if filter and isinstance(filter, dict):
        processed_filter = {}
        for key, value in filter.items():
            if key == "project" and isinstance(value, str):
                # Apply project name validation to project filters
                processed_filter[key] = validate_project_name(value)
            elif key == "status" and isinstance(value, str):
                # Make status case insensitive
                processed_filter[key] = value.lower()
            else:
                processed_filter[key] = value
        filter = processed_filter

    # Find matching todos first
    cursor = collection.find(
        filter or {},
        projection=projection,
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
        # Check if enhanced_description exists and has content
        enhanced_description = bool(todo.get("enhanced_description"))

        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"],
            "project": todo["project"],
            "status": todo["status"],
            "enhanced_description": enhanced_description
        })

    # MQTT publish as confirmation after the database query
    try:
        mqtt_message = f"filter: {json.dumps(filter)}, limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/query_todos", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update a todo with the provided changes.
    
    Updates specific fields of an existing todo without affecting other fields.
    Common fields to update: description, priority, status, metadata.
    
    Parameters:
        todo_id: Identifier of the todo to update
        updates: Dictionary of fields to update with their new values
        ctx: Optional context object with user agent info
        
    Returns:
        JSON containing:
        - success: Boolean indicating if the operation succeeded
        - message: Status message about the operation
    """
    # Check if todo exists
    existing_todo = collection.find_one({"id": todo_id})
    if not existing_todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")

    # Validate specific fields
    if 'project' in updates:
        updates['project'] = validate_project_name(updates['project'])

    if 'priority' in updates and updates['priority'] not in ["Low", "Medium", "High"]:
        updates['priority'] = "Medium"

    # Add updated timestamp
    updates['updated_at'] = int(datetime.now(UTC).timestamp())

    try:
        result = collection.update_one(
            {"id": todo_id},
            {"$set": updates}
        )

        if result.modified_count == 1:
            logging.info(f"Todo updated: {todo_id}")

            # Log the todo update
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            description = updates.get('description', existing_todo.get('description', 'Unknown'))
            project = updates.get('project', existing_todo.get('project', 'Unknown'))

            # Create changes list for logging
            changes = [
                {
                    'field': field,
                    'oldValue': existing_todo.get(field),
                    'newValue': value
                }
                for field, value in updates.items()
                if field != 'updated_at' and existing_todo.get(field) != value
            ]

            await log_todo_update(todo_id, description, project, changes, user_agent)

            return create_response(True, message=f"Todo {todo_id} updated successfully")
        else:
            return create_response(False, message=f"No changes were made to todo {todo_id}")

    except Exception as e:
        error_msg = f"Failed to update todo: {str(e)}"
        logging.error(error_msg)
        return create_response(False, message=error_msg)

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """
    Delete a todo by its ID.
    
    Permanently removes a todo from the database.
    
    Parameters:
        todo_id: Identifier of the todo to delete
        ctx: Optional context object with user agent info
        
    Returns:
        JSON containing:
        - success: Boolean indicating if the operation succeeded
        - message: Status message about the operation
    """
    # Check if todo exists
    existing_todo = collection.find_one({"id": todo_id})
    if not existing_todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")

    try:
        result = collection.delete_one({"id": todo_id})

        if result.deleted_count == 1:
            logging.info(f"Todo deleted: {todo_id}")

            # Log the todo deletion
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            description = existing_todo.get('description', 'Unknown')
            project = existing_todo.get('project', 'Unknown')

            await log_todo_delete(todo_id, description, project, user_agent)

            return create_response(True, message=f"Todo {todo_id} deleted successfully")
        else:
            return create_response(False, message=f"Failed to delete todo {todo_id}")

    except Exception as e:
        error_msg = f"Failed to delete todo: {str(e)}"
        logging.error(error_msg)
        return create_response(False, message=error_msg)

async def get_todo(todo_id: str) -> str:
    """
    Get a specific todo by ID.
    
    Retrieves detailed information about a todo item, returning different fields
    based on the todo's status to optimize context usage for AI agents.
    
    Parameters:
        todo_id: Unique identifier of the todo to retrieve
        
    Returns:
        JSON containing the todo's details with fields:
        - id: Unique identifier
        - description: Full task description
        - project: Project category 
        - status: Current status (initial, pending, completed)
        - enhanced_description: Detailed description with markdown (if exists and not empty)
        
        For active todos (not completed):
        - priority: Task priority level
        - target: Target agent/user
        - metadata: Additional task metadata (if exists)
        
        For completed todos:
        - completed: Completion timestamp
        - duration: Formatted duration from creation to completion
        - completion_comment: Optional comment about completion (if exists)
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
    }

    # Add enhanced_description if it exists and has content
    enhanced_description = todo.get("enhanced_description")
    if enhanced_description and enhanced_description.strip():
        formatted_todo["enhanced_description"] = enhanced_description

    # Add different fields based on status to optimize context
    if todo.get("completed_at"):
        # For completed todos, focus on completion info
        formatted_todo["completed"] = todo["completed_at"]
        duration_seconds = todo["completed_at"] - todo["created_at"]
        formatted_todo["duration"] = _format_duration(duration_seconds)

        # Include completion comment if it exists
        if todo.get("completion_comment"):
            formatted_todo["completion_comment"] = todo["completion_comment"]
    else:
        # For active todos, include more working fields
        if todo.get("priority"):
            formatted_todo["priority"] = todo["priority"]

        if todo.get("target"):
            formatted_todo["target"] = todo["target"]

        # Include metadata for active todos if it exists
        if todo.get("metadata"):
            formatted_todo["metadata"] = todo["metadata"]

    # MQTT publish without try/except to reduce code verbosity
    await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/get_todo", f"todo_id: {todo_id}")

    return create_response(True, formatted_todo)

async def mark_todo_complete(todo_id: str, comment: str = None, ctx: Context = None) -> str:
    """
    Mark a todo as completed.
    
    Updates a todo's status to "completed" and records the completion time.
    Also calculates the duration from creation to completion.
    
    Parameters:
        todo_id: Identifier of the todo to mark complete
        comment: Optional comment about the completion (e.g., solution notes, outcome details)
        ctx: Optional context object with user agent info
        
    Returns:
        JSON containing:
        - success: Boolean indicating if the operation succeeded
        - message: Status message about the operation
        - data: Information about the completed todo (ID, completion time)
    """
    # Check if todo exists and isn't already completed
    existing_todo = collection.find_one({"id": todo_id})

    if not existing_todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")

    if existing_todo.get("status") == "completed":
        return create_response(False, message=f"Todo {todo_id} is already marked as completed")

    # Record completion time and calculate duration
    completed_at = int(datetime.now(UTC).timestamp())
    created_at = existing_todo.get("created_at", completed_at)
    duration_sec = completed_at - created_at
    duration = _format_duration(duration_sec)

    updates = {
        "status": "completed",
        "completed_at": completed_at,
        "duration": duration,
        "duration_sec": duration_sec,
        "updated_at": completed_at
    }

    # Add completion comment if provided
    if comment:
        updates["completion_comment"] = comment

    try:
        result = collection.update_one(
            {"id": todo_id},
            {"$set": updates}
        )

        if result.modified_count == 1:
            logging.info(f"Todo marked complete: {todo_id}" + (f" with comment: {comment[:50]}..." if comment else ""))

            # Log the todo completion
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            description = existing_todo.get('description', 'Unknown')
            project = existing_todo.get('project', 'Unknown')

            await log_todo_complete(todo_id, description, project, user_agent)

            # Return a success response
            response_data = {
                "todo_id": todo_id,
                "completed_at": datetime.fromtimestamp(completed_at, UTC).strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration
            }

            # Include comment in response if provided
            if comment:
                response_data["completion_comment"] = comment

            return create_response(True,
                response_data,
                f"Todo {todo_id} marked as completed" + (f" with comment" if comment else "")
            )
        else:
            return create_response(False, message=f"Failed to mark todo {todo_id} as completed")

    except Exception as e:
        error_msg = f"Failed to mark todo as complete: {str(e)}"
        logging.error(error_msg)
        return create_response(False, message=error_msg)

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
        {"status": status.lower()},
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

    # Invalidate tags cache since we added new tags
    invalidate_lesson_tags_cache()

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
    # Check if we're updating tags
    tags_updated = "tags" in updates

    result = lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
    if result.modified_count == 0:
        return create_response(False, message="Lesson not found")

    # Invalidate tags cache if tags were updated
    if tags_updated:
        invalidate_lesson_tags_cache()

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
    # Get lesson first to check if it has tags
    lesson = lessons_collection.find_one({"id": lesson_id})
    has_tags = lesson and lesson.get("tags") and len(lesson.get("tags")) > 0

    result = lessons_collection.delete_one({"id": lesson_id})

    if result.deleted_count == 0:
        return create_response(False, message="Lesson not found")

    # Invalidate tags cache if the deleted lesson had tags
    if has_tags:
        invalidate_lesson_tags_cache()

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
    Additionally returns a list of all unique tags across all lessons.
    
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
        - all_tags: List of all unique tags across all lessons
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
        # Extract tags from the lesson
        lesson_tags = lesson.get("tags", [])

        summary["items"].append({
            "id": lesson["id"],
            "language": lesson["language"],
            "topic": lesson["topic"],
            "tags": lesson_tags,
            "preview": lesson["lesson_learned"][:40] + ("..." if len(lesson["lesson_learned"]) > 40 else "")
        })

    # Get all unique tags using the cached mechanism
    summary["all_tags"] = get_all_lesson_tags()

    # MQTT publish as confirmation after listing lessons
    try:
        mqtt_message = f"limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/list_lessons", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def search_todos(query: str, fields: list = None, limit: int = 100, ctx=None) -> str:
    """
    Search todos with text search capabilities.
    
    Performs a case-insensitive text search across specified fields in todos.
    Uses regex pattern matching to find todos matching the query string.
    Special handling for project field ensures proper project name validation.
    
    Parameters:
        query: Text string to search for
              Special format: "project:ProjectName" to search by project
        fields: List of fields to search in (default: ["description"])
                Can include special values:
                - "all" to search all text fields
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
    # Handle project-specific search format "project:ProjectName"
    if isinstance(query, str) and query.lower().startswith("project:"):
        try:
            # Extract project name - everything after "project:"
            project_name = query[8:].strip()
            if not project_name:
                return create_response(False, message="Project name is empty. Use format 'project:ProjectName'")

            # Validate the project name
            validated_project = validate_project_name(project_name)

            # Use direct lookup for project search
            search_query = {"project": validated_project}

            logging.info(f"Project search: '{project_name}' validated to '{validated_project}'")
        except Exception as e:
            logging.error(f"Project search parsing error: {str(e)}")
            return create_response(False, message=f"Invalid project search format. Use 'project:ProjectName'. Error: {str(e)}")

    # Handle normal text search
    else:
        if not fields:
            fields = ["description"]

        # Support "all" as a special field value to search across multiple fields
        if "all" in fields:
            fields = ["description", "project", "status", "priority", "notes"]

        # Create a regex pattern for case-insensitive search
        regex_pattern = {"$regex": query, "$options": "i"}

        # Build the query with OR conditions for each field
        search_conditions = []
        for field in fields:
            # If searching project field, validate project name first
            if field == "project" and query:
                validated_project = validate_project_name(query)
                search_conditions.append({"project": validated_project})
            else:
                search_conditions.append({field: regex_pattern})

        search_query = {"$or": search_conditions}

    # Execute the search
    try:
        cursor = collection.find(search_query, limit=limit)
        results = list(cursor)
        logging.info(f"Search found {len(results)} results for query: {query}")
    except Exception as e:
        logging.error(f"Search query failed: {e}")
        return create_response(False, message=f"Search failed: {str(e)}")

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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/search_todos", mqtt_message, ctx)
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

async def list_project_todos(project: str, limit: int = 5) -> str:
    """
    List recent todos for a specific project.
    
    Retrieves the most recently updated todos for a specific project.
    Results are sorted by the last update time (created or last modified).
    Excludes completed todos to focus on active items.
    
    Parameters:
        project: Project name to filter by
        limit: Maximum number of todos to return (default: 5)
        
    Returns:
        JSON containing:
        - count: Number of todos found
        - project: The project that was queried
        - items: Array of matching todos with ID and description
    """
    # Validate and normalize the project name
    validated_project = validate_project_name(project)

    # Find todos for this project and sort by last update (created_at or updated_at if exists)
    # We use sort on created_at to get the newest todos first
    # Exclude completed todos to focus on active items
    cursor = collection.find(
        {
            "project": validated_project,
            "status": {"$ne": "completed"}  # Exclude completed todos
        },
        sort=[("created_at", -1)],  # -1 means descending order, newest first
        limit=limit
    )
    results = list(cursor)

    # Create an optimized summary with only essential data
    summary = {
        "count": len(results),
        "project": validated_project,
        "items": []
    }

    # Add todo items with minimal but useful information
    for todo in results:
        # Include ID and description only to keep response concise
        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"],
            "status": todo["status"],
            "created_at": datetime.fromtimestamp(todo["created_at"], UTC).strftime("%Y-%m-%d %H:%M")
        })

    # Publish MQTT status with minimal error handling
    try:
        await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/list_project_todos",
                        f"project: {validated_project}, limit: {limit}, found: {len(results)}")
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, ctx: Context = None) -> str:
    """
    Query todo logs with filtering options.
    
    Gets log entries from the TodoLogService showing changes to todo items.
    Returns a collection of log entries matching the filter criteria.
    
    Parameters:
        filter_type: Type of operation to filter by ('all', 'create', 'update', 'delete', 'complete')
        project: Project name to filter by ('all' for all projects)
        page: Page number (1-based)
        page_size: Maximum number of logs to return (default: 20)
        ctx: Optional context for logging
        
    Returns:
        JSON containing:
        - logEntries: Array of matching log entries
        - totalCount: Total number of logs matching the filter
        - page: Current page number
        - pageSize: Number of items per page
        - hasMore: Whether there are more logs beyond this page
        - projects: List of unique projects for filtering
    """
    try:
        # Validate and normalize project name if not 'all'
        if project != 'all':
            project = validate_project_name(project)

        # Get the TodoLogService instance
        log_service = get_log_service()

        # Initialize the service if it's not running
        if not log_service.running:
            await log_service.start()

        # Query the logs
        result = await log_service.get_logs(
            filter_type=filter_type,
            project=project,
            page=page,
            page_size=page_size
        )

        return create_response(True, result, return_context=False)

    except Exception as e:
        return create_response(False, message=f"Failed to query todo logs: {str(e)}", return_context=False)

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
    """
    List all valid projects from the centralized project management system.
    
    Retrieves the list of projects that can be used for todos and other operations.
    This replaces the hardcoded VALID_PROJECTS list with a database-driven approach.
    
    Parameters:
        include_details: If False, returns project names only. If True, returns detailed metadata.
                        If "filemanager", returns FileManager format with absolute paths.
        madness_root: Absolute path to the madness_interactive root directory (for filemanager mode)
        
    Returns:
        JSON containing:
        - count: Number of projects found
        - projects: Array of project names, detailed objects, or FileManager objects
        - cached: Boolean indicating if result was served from cache
    """
    try:
        # Check if we're serving from cache
        cached_projects = get_cached_projects()
        served_from_cache = cached_projects is not None

        if include_details == "filemanager":
            # FileManager-specific format with absolute paths
            try:
                # Initialize collection if needed
                if projects_collection.count_documents({}) == 0:
                    initialize_projects_collection()

                # Get all projects with path information
                cursor = projects_collection.find({})
                projects = []
                
                for doc in cursor:
                    relative_path = doc.get("relative_path", "")
                    
                    # Calculate absolute path
                    if relative_path == "":
                        # Root project (madness_interactive)
                        absolute_path = madness_root
                    elif relative_path.startswith("../"):
                        # Parent directory project (like regressiontestkit)
                        absolute_path = os.path.join(os.path.dirname(madness_root), relative_path[3:])
                    else:
                        # Project within madness root
                        absolute_path = os.path.join(madness_root, relative_path)
                    
                    project = {
                        "name": doc["id"],
                        "path": absolute_path,
                        "display_name": doc["display_name"],
                        "git_url": doc.get("git_url"),
                        "description": doc.get("description")
                    }
                    projects.append(project)

                return create_response(True, {
                    "count": len(projects),
                    "projects": projects,
                    "cached": served_from_cache
                })
            except Exception as e:
                logging.error(f"Failed to get FileManager projects: {str(e)}")
                # Fallback to simple list
                project_names = get_all_projects()
                simple_projects = [{"name": name, "path": madness_root, "display_name": name.replace("_", " ").title()} for name in project_names]
                return create_response(True, {
                    "count": len(simple_projects),
                    "projects": simple_projects,
                    "cached": served_from_cache
                })

        elif include_details:
            # Get detailed project information from database
            try:
                # Initialize collection if needed
                if projects_collection.count_documents({}) == 0:
                    initialize_projects_collection()

                # Query detailed project information
                cursor = projects_collection.find({})
                projects = []
                
                for doc in cursor:
                    project = {
                        "id": doc["id"],
                        "name": doc["name"],
                        "display_name": doc["display_name"],
                        "git_url": doc.get("git_url"),
                        "relative_path": doc.get("relative_path"),
                        "description": doc.get("description"),
                        "created_at": datetime.fromtimestamp(doc["created_at"], UTC).strftime("%Y-%m-%d")
                    }
                    projects.append(project)

                return create_response(True, {
                    "count": len(projects),
                    "projects": projects,
                    "cached": False  # Detailed queries are not cached
                })
            except Exception as e:
                logging.error(f"Failed to get detailed projects: {str(e)}")
                # Fallback to simple list
                project_names = get_all_projects()
                simple_projects = [{"id": name, "name": name, "display_name": name.replace("_", " ").title()} for name in project_names]
                return create_response(True, {
                    "count": len(simple_projects),
                    "projects": simple_projects,
                    "cached": served_from_cache
                })
        else:
            # Get simple list of project names
            project_names = get_all_projects()
            return create_response(True, {
                "count": len(project_names),
                "projects": project_names,
                "cached": served_from_cache
            })

    except Exception as e:
        error_msg = f"Failed to list projects: {str(e)}"
        logging.error(error_msg)
        return create_response(False, message=error_msg)
