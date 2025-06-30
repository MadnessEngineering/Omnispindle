import json
import os
import re
import ssl
import subprocess
import uuid
from datetime import datetime, UTC
from typing import Union, List, Dict

import logging
from dotenv import load_dotenv
from fastmcp import Context
from pymongo import MongoClient

from .database import db_connection
from .utils import create_response, mqtt_publish, _format_duration
from .todo_log_service import log_todo_create, log_todo_update, log_todo_delete, log_todo_complete

# Load environment variables
load_dotenv()

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
    if db_connection.tags_cache is None:
        logging.error("Failed to cache lesson tags: Database connection is not available.")
        return False
    try:
        # Add timestamp for cache expiry management
        cache_entry = {
            "key": TAGS_CACHE_KEY,
            "tags": list(tags_list),
            "updated_at": int(datetime.now(UTC).timestamp())
        }

        # Use upsert to update if exists or insert if not
        db_connection.tags_cache.update_one(
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
    if db_connection.tags_cache is None:
        logging.error("Failed to retrieve cached lesson tags: Database connection is not available.")
        return None
    try:
        # Find the cache entry
        cache_entry = db_connection.tags_cache.find_one({"key": TAGS_CACHE_KEY})

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
    if db_connection.tags_cache is None:
        logging.error("Failed to invalidate lesson tags cache: Database connection is not available.")
        return False
    try:
        db_connection.tags_cache.delete_one({"key": TAGS_CACHE_KEY})
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
    cached_tags = get_cached_lesson_tags()
    if cached_tags is not None:
        return cached_tags

    # If not in cache, query from database
    if db_connection.lessons is None:
        logging.error("Failed to aggregate lesson tags: Database connection is not available.")
        return []
    try:
        # Use MongoDB aggregation to get all unique tags
        pipeline = [
            {"$project": {"tags": 1}},
            {"$unwind": "$tags"},
            {"$group": {"_id": None, "unique_tags": {"$addToSet": "$tags"}}},
        ]
        result = list(db_connection.lessons.aggregate(pipeline))

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
    if db_connection.tags_cache is None:
        logging.error("Failed to cache projects: Database connection is not available.")
        return False
    try:
        cache_entry = {
            "key": PROJECTS_CACHE_KEY,
            "projects": list(projects_list),
            "updated_at": int(datetime.now(UTC).timestamp())
        }
        db_connection.tags_cache.update_one(
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
    if db_connection.tags_cache is None:
        logging.error("Failed to retrieve cached projects: Database connection is not available.")
        return None
    try:
        cache_entry = db_connection.tags_cache.find_one({"key": PROJECTS_CACHE_KEY})

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
    if db_connection.tags_cache is None:
        logging.error("Failed to invalidate projects cache: Database connection is not available.")
        return False
    try:
        db_connection.tags_cache.delete_one({"key": PROJECTS_CACHE_KEY})
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
    if db_connection.projects is None:
        logging.error("Failed to initialize projects collection: Database connection is not available.")
        return False
    try:
        # Check if projects collection is already populated
        existing_count = db_connection.projects.count_documents({})
        if existing_count > 0:
            logging.info(f"Projects collection already has {existing_count} projects")
            return True

        # Insert all valid projects with enhanced metadata
        current_time = int(datetime.now(UTC).timestamp())
        project_definitions = {
            "madness_interactive": {
                "git_url": "https://github.com/d-edens/madness_interactive.git",
                "relative_path": "",
                "description": "Main Madness Interactive project hub"
            },
            "regressiontestkit": {
                "git_url": "https://github.com/d-edens/RegressionTestKit.git",
                "relative_path": "../RegressionTestKit",
                "description": "A toolkit for regression testing"
            }
        }
        projects_to_insert = [
            {
                "id": name,
                "name": name,
                "display_name": name.replace("_", " ").title(),
                "created_at": current_time,
                **project_definitions.get(name, {})
            }
            for name in VALID_PROJECTS
        ]
        
        if projects_to_insert:
            db_connection.projects.insert_many(projects_to_insert)
            logging.info(f"Successfully inserted {len(projects_to_insert)} projects into the collection")
            
        # Invalidate project cache after initialization
        invalidate_projects_cache()
        return True

    except Exception as e:
        logging.error(f"Failed to initialize projects collection: {str(e)}")
        return False

def get_all_projects():
    """
    Get all projects from the database, with caching.
    """
    cached_projects = get_cached_projects()
    if cached_projects:
        return cached_projects

    if db_connection.projects is None:
        logging.error("Failed to get all projects: Database connection is not available.")
        return []
    try:
        # Get all projects from the database
        projects_from_db = list(db_connection.projects.find({}, {"_id": 0}))

        # If the database is empty, initialize it as a fallback
        if not projects_from_db:
            initialize_projects_collection()
            projects_from_db = list(db_connection.projects.find({}, {"_id": 0}))

        # Cache the results for future use
        cache_projects(projects_from_db)
        return projects_from_db
    except Exception as e:
        logging.error(f"Failed to get projects from database: {str(e)}")
        return []

def validate_project_name(project: str) -> str:
    """
    Validates and normalizes a project name.
    
    Args:
        project: The project name to validate.
        
    Returns:
        A valid, normalized project name.
    """
    if not project or not isinstance(project, str):
        return "madness_interactive"  # Default project

    # Normalize to lowercase for case-insensitive matching
    normalized_project = project.lower()

    # Get all valid projects
    all_projects = get_all_projects()
    
    # Handle both dictionary and string formats
    project_names = []
    try:
        for p in all_projects:
            if isinstance(p, dict):
                project_names.append(p.get('name', ''))
            elif isinstance(p, str):
                project_names.append(p)
    except Exception as e:
        logging.error(f"Error processing projects list: {str(e)}")
        # Fallback to VALID_PROJECTS if there's an issue
        project_names = VALID_PROJECTS

    if normalized_project in project_names:
        return normalized_project
    
    # Fallback to default if no match is found
    return "madness_interactive"

async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """
    Creates a task in the specified project with the given priority and target agent.
    Returns a compact representation of the created todo with an ID for reference.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection not available.")

    project = validate_project_name(project)
    if priority not in ["Low", "Medium", "High"]:
        priority = "Medium"

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
    if metadata:
        todo["metadata"] = metadata

    try:
        db_connection.todos.insert_one(todo)
        logging.info(f"Todo created: {todo_id}")
        user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
        await log_todo_create(todo_id, description, project, user_agent)
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
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")

    if filter and isinstance(filter, dict):
        processed_filter = {}
        for key, value in filter.items():
            if key == "project" and isinstance(value, str):
                processed_filter[key] = validate_project_name(value)
            elif key == "status" and isinstance(value, str):
                processed_filter[key] = value.lower()
            else:
                processed_filter[key] = value
        filter = processed_filter

    try:
        cursor = db_connection.todos.find(filter or {}, projection=projection, limit=limit)
        results = list(cursor)
        summary = {
            "count": len(results),
            "items": []
        }
        for todo in results:
            enhanced_description = bool(todo.get("enhanced_description"))
            summary["items"].append({
                "id": todo["id"],
                "description": todo["description"],
                "project": todo["project"],
                "status": todo["status"],
                "enhanced_description": enhanced_description
            })
        return create_response(True, summary)
    except Exception as e:
        return create_response(False, message=f"Failed to query todos: {str(e)}")

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update a todo with the provided changes.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")

    existing_todo = db_connection.todos.find_one({"id": todo_id})
    if not existing_todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")

    if 'project' in updates:
        updates['project'] = validate_project_name(updates['project'])
    if 'priority' in updates and updates['priority'] not in ["Low", "Medium", "High"]:
        updates['priority'] = "Medium"
    updates['updated_at'] = int(datetime.now(UTC).timestamp())

    try:
        result = db_connection.todos.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            logging.info(f"Todo updated: {todo_id}")
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            description = updates.get('description', existing_todo.get('description', 'Unknown'))
            project = updates.get('project', existing_todo.get('project', 'Unknown'))
            changes = [
                {'field': field, 'oldValue': existing_todo.get(field), 'newValue': value}
                for field, value in updates.items()
                if field != 'updated_at' and existing_todo.get(field) != value
            ]
            await log_todo_update(todo_id, description, project, changes, user_agent)
            return create_response(True, message=f"Todo {todo_id} updated successfully")
        else:
            return create_response(False, message=f"Todo {todo_id} not found or no changes made.")
    except Exception as e:
        return create_response(False, message=f"Failed to update todo: {str(e)}")

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """
    Delete a todo item by its ID.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")

    try:
        existing_todo = db_connection.todos.find_one({"id": todo_id})
        if existing_todo:
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            await log_todo_delete(todo_id, existing_todo.get('description', 'Unknown'),
                                  existing_todo.get('project', 'Unknown'), user_agent)
        result = db_connection.todos.delete_one({"id": todo_id})
        if result.deleted_count == 1:
            logging.info(f"Todo deleted: {todo_id}")
            return create_response(True, message=f"Todo {todo_id} deleted successfully.")
        else:
            return create_response(False, message=f"Todo with ID {todo_id} not found.")
    except Exception as e:
        return create_response(False, message=f"Failed to delete todo: {str(e)}")

async def get_todo(todo_id: str) -> str:
    """
    Get a specific todo item by its ID.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")
    
    todo = db_connection.todos.find_one({"id": todo_id})
    if not todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")

    return create_response(True, todo)

async def mark_todo_complete(todo_id: str, comment: str = None, ctx: Context = None) -> str:
    """
    Mark a todo as completed.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")

    existing_todo = db_connection.todos.find_one({"id": todo_id})
    if not existing_todo:
        return create_response(False, message=f"Todo with ID {todo_id} not found")
    if existing_todo.get("status") == "completed":
        return create_response(False, message=f"Todo {todo_id} is already marked as completed")

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
    if comment:
        updates["completion_comment"] = comment

    try:
        result = db_connection.todos.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            logging.info(f"Todo completed: {todo_id}")
            user_agent = ctx.user_agent if ctx and hasattr(ctx, 'user_agent') else None
            await log_todo_complete(todo_id, existing_todo.get('description', 'Unknown'),
                                    existing_todo.get('project', 'Unknown'), user_agent)
            return create_response(True, message=f"Todo {todo_id} marked as complete.")
        else:
            return create_response(False, message=f"Failed to update todo {todo_id}.")
    except Exception as e:
        return create_response(False, message=f"Failed to mark todo complete: {str(e)}")

async def list_todos_by_status(status: str, limit: int = 100) -> str:
    """
    List todos filtered by their status.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")
    
    valid_statuses = ["pending", "completed", "initial", "all"]
    if status not in valid_statuses:
        return create_response(False, message=f"Invalid status. Must be one of: {valid_statuses}")

    query = {}
    if status != "all":
        query["status"] = status
    
    try:
        cursor = db_connection.todos.find(query, limit=limit)
        todos = list(cursor)
        return create_response(True, {"count": len(todos), "items": todos})
    except Exception as e:
        return create_response(False, message=f"Failed to list todos by status: {str(e)}")

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    """
    Add a new lesson to the knowledge base.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection not available.")

    lesson_id = str(uuid.uuid4())
    lesson = {
        "id": lesson_id,
        "language": language,
        "topic": topic,
        "lesson_learned": lesson_learned,
        "created_at": int(datetime.now(UTC).timestamp()),
        "tags": tags or []
    }
    try:
        db_connection.lessons.insert_one(lesson)
        invalidate_lesson_tags_cache()
        logging.info(f"Lesson created: {lesson_id}")
        return create_response(True, {"lesson_id": lesson_id, "topic": topic})
    except Exception as e:
        return create_response(False, message=f"Failed to add lesson: {str(e)}")

async def get_lesson(lesson_id: str) -> str:
    """
    Get a specific lesson by its ID.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection not available.")
    
    lesson = db_connection.lessons.find_one({"id": lesson_id})
    if not lesson:
        return create_response(False, message=f"Lesson with ID {lesson_id} not found")
    
    return create_response(True, lesson)

async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """
    Update an existing lesson.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection not available.")
    
    try:
        result = db_connection.lessons.update_one({"id": lesson_id}, {"$set": updates})
        if result.modified_count == 1:
            invalidate_lesson_tags_cache()
            logging.info(f"Lesson updated: {lesson_id}")
            return create_response(True, message=f"Lesson {lesson_id} updated successfully.")
        else:
            return create_response(False, message=f"Lesson with ID {lesson_id} not found or no changes made.")
    except Exception as e:
        return create_response(False, message=f"Failed to update lesson: {str(e)}")

async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
    """
    Delete a lesson by its ID.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection is not available.")
    
    try:
        result = db_connection.lessons.delete_one({"id": lesson_id})
        if result.deleted_count == 1:
            invalidate_lesson_tags_cache()
            logging.info(f"Lesson deleted: {lesson_id}")
            return create_response(True, message=f"Lesson {lesson_id} deleted successfully.")
        else:
            return create_response(False, message=f"Lesson with ID {lesson_id} not found.")
    except Exception as e:
        return create_response(False, message=f"Failed to delete lesson: {str(e)}")

async def search_todos(query: str, fields: list = None, limit: int = 100, ctx=None) -> str:
    """
    Search todos with text search capabilities.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")
    
    if "project:" in query:
        try:
            project_name = query.split("project:")[1].strip()
            normalized_project_name = validate_project_name(project_name)
            search_query = {"project": {"$regex": f"^{re.escape(normalized_project_name)}$", "$options": "i"}}
        except IndexError:
            return create_response(False, message="Invalid project filter format. Expected 'project:name'.")
    else:
        search_query = {"$text": {"$search": query}}

    try:
        cursor = db_connection.todos.find(search_query, limit=limit)
        results = list(cursor)
        return create_response(True, {"count": len(results), "items": results})
    except Exception as e:
        return create_response(False, message=f"Failed to search todos: {str(e)}")

async def grep_lessons(pattern: str, limit: int = 20) -> str:
    """
    Search lessons with grep-style pattern matching across topic and content.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection is not available.")
    try:
        query = {
            "$or": [
                {"topic": {"$regex": pattern, "$options": "i"}},
                {"lesson_learned": {"$regex": pattern, "$options": "i"}}
            ]
        }
        cursor = db_connection.lessons.find(query).limit(limit)
        results = list(cursor)
        return create_response(True, {"count": len(results), "matches": results})
    except Exception as e:
        return create_response(False, message=f"Failed to search lessons: {str(e)}")

async def list_project_todos(project: str, limit: int = 5) -> str:
    """
    List recent active todos for a specific project.
    """
    if db_connection.todos is None:
        return create_response(False, message="Database connection is not available.")

    normalized_project = validate_project_name(project)
    query = {
        "project": normalized_project,
        "status": {"$ne": "completed"}
    }
    try:
        cursor = db_connection.todos.find(query).sort("created_at", -1).limit(limit)
        todos = list(cursor)
        return create_response(True, {"count": len(todos), "project": normalized_project, "items": todos})
    except Exception as e:
        return create_response(False, message=f"Failed to list project todos: {str(e)}")

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, ctx: Context = None) -> str:
    """
    Query the todo logs with filtering and pagination.
    """
    if db_connection.logs is None:
        return create_response(False, message="Database connection is not available.")
    
    query = {}
    if filter_type != 'all':
        query['operation'] = filter_type
    if project != 'all':
        query['project'] = validate_project_name(project)

    try:
        total_records = db_connection.logs.count_documents(query)
        skips = page_size * (page - 1)
        cursor = db_connection.logs.find(query).sort("timestamp", -1).skip(skips).limit(page_size)
        logs = list(cursor)
        return create_response(True, {
            "logEntries": logs,
            "totalCount": total_records,
            "page": page,
            "pageSize": page_size,
            "hasMore": total_records > page * page_size
        })
    except Exception as e:
        return create_response(False, message=f"Failed to query todo logs: {str(e)}")

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive") -> str:
    """
    List all valid projects from the centralized project management system.
    """
    projects = get_all_projects()
    if include_details:
        return create_response(True, {"count": len(projects), "projects": projects})
    else:
        project_names = [p['name'] for p in projects]
        return create_response(True, {"count": len(project_names), "projects": project_names})

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Context = None) -> str:
    """
    Add a new explanation to the knowledge base.
    """
    if db_connection.explanations is None:
        return create_response(False, message="Database connection not available.")
    
    explanation = {
        "topic": topic,
        "content": content,
        "kind": kind,
        "author": author,
        "created_at": int(datetime.now(UTC).timestamp()),
        "updated_at": int(datetime.now(UTC).timestamp())
    }
    try:
        db_connection.explanations.update_one(
            {"topic": topic},
            {"$set": explanation},
            upsert=True
        )
        logging.info(f"Explanation added/updated for topic '{topic}'")
        return create_response(True, {"topic": topic})
    except Exception as e:
        return create_response(False, message=f"Failed to add explanation: {str(e)}")

async def get_explanation(topic: str) -> str:
    """Get an explanation for a given topic."""
    if db_connection.explanations is None:
        return create_response(False, message="Database connection not available.")
    
    explanation = db_connection.explanations.find_one({"topic": topic})
    if explanation:
        explanation.pop('_id', None)
        return create_response(True, explanation)
    else:
        return create_response(False, message=f"Explanation for topic '{topic}' not found.")

async def update_explanation(topic: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing explanation."""
    if db_connection.explanations is None:
        return create_response(False, message="Database connection not available.")
    
    updates['updated_at'] = int(datetime.now(UTC).timestamp())
    result = db_connection.explanations.update_one(
        {"topic": topic},
        {"$set": updates}
    )
    if result.modified_count > 0:
        return create_response(True, message=f"Explanation for '{topic}' updated successfully.")
    else:
        return create_response(False, message=f"Explanation for '{topic}' not found or no changes made.")

async def delete_explanation(topic: str, ctx: Context = None) -> str:
    """Delete an explanation for a given topic."""
    if db_connection.explanations is None:
        return create_response(False, message="Database connection not available.")
    
    result = db_connection.explanations.delete_one({"topic": topic})
    if result.deleted_count > 0:
        return create_response(True, message=f"Explanation for '{topic}' deleted successfully.")
    else:
        return create_response(False, message=f"Explanation for topic '{topic}' not found.")

async def explain_tool(topic: str, brief: bool = False, ctx: Context = None) -> str:
    """
    Provides a detailed explanation for a project or concept.
    """
    if db_connection.explanations is not None:
        static_explanation = db_connection.explanations.find_one({"topic": topic})
        if static_explanation:
            if brief:
                return create_response(True, {
                    "topic": static_explanation["topic"],
                    "summary": static_explanation["content"][:200] + "..." if len(static_explanation["content"]) > 200 else static_explanation["content"],
                    "type": "static"
                })
            static_explanation.pop('_id', None)
            return create_response(True, static_explanation)

    if db_connection.todos is None:
        return create_response(False, message="Database connection not available for project details.")
        
    all_projects = get_all_projects()
    project_info = next((p for p in all_projects if p.get("name", "").lower() == topic.lower()), None)

    if project_info:
        project_name = project_info["name"]
        
        active_todos_cursor = db_connection.todos.find({"project": project_name, "status": {"$ne": "completed"}})
        active_todos = list(active_todos_cursor)
        
        recent_completed_cursor = db_connection.todos.find({"project": project_name, "status": "completed"}).sort("completed_at", -1).limit(3)
        recent_completed = list(recent_completed_cursor)

        if db_connection.lessons is not None:
            recent_lessons_cursor = db_connection.lessons.find({"topic": {"$regex": f"^{project_name}$", "$options": "i"}}).sort("created_at", -1).limit(3)
            recent_lessons = list(recent_lessons_cursor)
        else:
            recent_lessons = []

        if brief:
            summary = (
                f"**{project_info.get('display_name', project_name)}** is a project with "
                f"{len(active_todos)} active tasks. "
                f"Recent work includes: " +
                ", ".join([f"'{t['description'][:30]}...'" for t in recent_completed]) +
                ". Key lessons learned focus on: " +
                ", ".join([f"'{l['topic']}'" for l in recent_lessons]) + "."
            )
            return create_response(True, {"summary": summary, "type": "dynamic_brief"})

        # Generate a detailed Markdown explanation
        explanation = f"""
### Project Explanation: {project_info.get('display_name', project_name)}

**Description:** {project_info.get('description', 'No description available.')}
**Git Repository:** [{project_info.get('git_url', 'Not specified')}]({project_info.get('git_url', 'Not specified')})

#### Current Status
- **Active Todos:** {len(active_todos)}

#### Recently Completed Work
"""
        if recent_completed:
            for todo in recent_completed:
                completion_date = datetime.fromtimestamp(todo['completed_at']).strftime('%Y-%m-%d')
                explanation += f"- **{todo['description']}** (Completed: {completion_date})\n"
        else:
            explanation += "- No recently completed todos.\n"

        explanation += "\n#### Recent Lessons Learned\n"
        if recent_lessons:
            for lesson in recent_lessons:
                lesson_date = datetime.fromtimestamp(lesson['created_at']).strftime('%Y-%m-%d')
                explanation += f"- **{lesson['topic']}:** {lesson['lesson_learned'][:100]}... (Created: {lesson_date})\n"
        else:
            explanation += "- No recent lessons learned for this project.\n"
            
        return create_response(True, {"explanation": explanation, "type": "dynamic_detailed"})

    return create_response(False, message=f"Could not find an explanation for '{topic}'.")

async def list_lessons(limit: int = 100, brief: bool = False, ctx: Context = None) -> str:
    """
    List all lessons, sorted by creation date.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection is not available.")

    try:
        cursor = db_connection.lessons.find({}, limit=limit).sort("created_at", -1)
        lessons = list(cursor)
        if brief:
            items = [{"topic": l["topic"], "preview": l["lesson_learned"][:40] + "..." if len(l["lesson_learned"]) > 40 else ""} for l in lessons]
        else:
            items = lessons
        return create_response(True, {"count": len(lessons), "items": items})
    except Exception as e:
        return create_response(False, message=f"Failed to list lessons: {str(e)}")

async def search_lessons(query: str, fields: list = None, limit: int = 100, brief: bool = False, ctx: Context = None) -> str:
    """
    Search lessons with text search capabilities.
    """
    if db_connection.lessons is None:
        return create_response(False, message="Database connection is not available.")

    search_query = {"$text": {"$search": query}}
    try:
        cursor = db_connection.lessons.find(search_query, limit=limit)
        results = list(cursor)
        if brief:
            matches = [{"topic": r["topic"], "preview": r["lesson_learned"][:40] + "..." if len(r["lesson_learned"]) > 40 else ""} for r in results]
        else:
            matches = results
        return create_response(True, {"count": len(results), "matches": matches})
    except Exception as e:
        return create_response(False, message=f"Failed to search lessons: {str(e)}") 
