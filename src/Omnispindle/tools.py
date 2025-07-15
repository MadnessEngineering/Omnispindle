import json
import os
import re
import ssl
import subprocess
import uuid
from datetime import datetime, UTC
from typing import Union, List, Dict, Optional, Any

import logging
from dotenv import load_dotenv

from .context import Context
from pymongo import MongoClient

from .database import db_connection
from .utils import create_response, mqtt_publish, _format_duration
from .todo_log_service import log_todo_create, log_todo_update, log_todo_delete, log_todo_complete

# Load environment variables
load_dotenv()

# Get the logger
logger = logging.getLogger(__name__)

# Cache constants
TAGS_CACHE_KEY = "all_lesson_tags"
TAGS_CACHE_EXPIRY = 43200  # Cache expiry in seconds (12 hours)
PROJECTS_CACHE_KEY = "all_valid_projects"
PROJECTS_CACHE_EXPIRY = 43200  # Cache expiry in seconds (12 hours)

# Valid project list - all lowercase for case-insensitive matching
# TODO: This will be migrated to MongoDB and deprecated
VALID_PROJECTS = [
    "madness_interactive", "regressiontestkit", "omnispindle",
    "todomill_projectorium", "swarmonomicon", "hammerspoon",

    "lab_management", "cogwyrm", "docker_implementation",
    "documentation", "eventghost", "hammerghost",
    "quality_assurance", "spindlewrit", "inventorium"
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
    # Normalize project name for validation
    project_lower = project.lower()

    # Check if the normalized project name is in the list of valid projects
    if project_lower in [p.lower() for p in VALID_PROJECTS]:
        return project_lower  # Return the lowercase version for consistency

    # Default to "madness_interactive" if not found
    return "madness_interactive"

async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None, ctx: Optional[Context] = None) -> str:
    """
    Creates a task in the specified project with the given priority and target agent.
    Returns a compact representation of the created todo with an ID for reference.
    """
    todo_id = str(uuid.uuid4())
    todo = {
        "id": todo_id,
        "description": description,
        "project": validate_project_name(project),
        "priority": priority,
        "status": "pending",
        "target_agent": target_agent,
        "created_at": int(datetime.now(UTC).timestamp()),
        "metadata": metadata or {}
    }
    try:
        db_connection.todos.insert_one(todo)
        user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
        logger.info(f"Todo created by {user_email}: {todo_id}")
        await log_todo_create(todo_id, description, project, user_email)
        return create_response(True,
            {
                "operation": "create",
                "status": "success",
                "todo_id": todo_id,
                "description": description[:40] + ("..." if len(description) > 40 else ""),
            },
            message=f"Todo '{description}' created successfully with ID {todo_id}."
        )
    except Exception as e:
        logger.error(f"Failed to create todo: {str(e)}")
        return create_response(False, message=str(e))

async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    Query todos with flexible filtering options.
    """
    try:
        cursor = db_connection.todos.find(filter or {}, projection).limit(limit)
        results = list(cursor)
        return create_response(True, {"items": results})
    except Exception as e:
        logger.error(f"Failed to query todos: {str(e)}")
        return create_response(False, message=str(e))

async def update_todo(todo_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """
    Update a todo with the provided changes.
    """
    if "updated_at" not in updates:
        updates["updated_at"] = int(datetime.now(UTC).timestamp())
    try:
        existing_todo = db_connection.todos.find_one({"id": todo_id})
        if not existing_todo:
            return create_response(False, message=f"Todo {todo_id} not found.")

        result = db_connection.todos.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo updated by {user_email}: {todo_id}")
            description = updates.get('description', existing_todo.get('description', 'Unknown'))
            project = updates.get('project', existing_todo.get('project', 'Unknown'))
            changes = [
                {"field": field, "old_value": existing_todo.get(field), "new_value": value}
                for field, value in updates.items()
                if field != 'updated_at' and existing_todo.get(field) != value
            ]
            await log_todo_update(todo_id, description, project, changes, user_email)
            return create_response(True, message=f"Todo {todo_id} updated successfully")
        else:
            return create_response(False, message=f"Todo {todo_id} not found or no changes made.")
    except Exception as e:
        logger.error(f"Failed to update todo: {str(e)}")
        return create_response(False, message=str(e))

async def delete_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """
    Delete a todo item by its ID.
    """
    try:
        existing_todo = db_connection.todos.find_one({"id": todo_id})
        if existing_todo:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo deleted by {user_email}: {todo_id}")
            await log_todo_delete(todo_id, existing_todo.get('description', 'Unknown'),
                                  existing_todo.get('project', 'Unknown'), user_email)
        result = db_connection.todos.delete_one({"id": todo_id})
        if result.deleted_count == 1:
            return create_response(True, message=f"Todo {todo_id} deleted successfully.")
        else:
            return create_response(False, message=f"Todo {todo_id} not found.")
    except Exception as e:
        logger.error(f"Failed to delete todo: {str(e)}")
        return create_response(False, message=str(e))

async def get_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """
    Get a specific todo item by its ID.
    """
    try:
        todo = db_connection.todos.find_one({"id": todo_id})
        if todo:
            return create_response(True, todo)
        else:
            return create_response(False, message=f"Todo with ID {todo_id} not found.")
    except Exception as e:
        logger.error(f"Failed to get todo: {str(e)}")
        return create_response(False, message=str(e))

async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """
    Mark a todo as completed.
    """
    try:
        existing_todo = db_connection.todos.find_one({"id": todo_id})
        if not existing_todo:
            return create_response(False, message=f"Todo {todo_id} not found.")

        completed_at = int(datetime.now(UTC).timestamp())
        duration_sec = completed_at - existing_todo.get('created_at', completed_at)
        updates = {
            "status": "completed",
            "completed_at": completed_at,
            "duration": _format_duration(duration_sec),
            "duration_sec": duration_sec,
            "updated_at": completed_at
        }
        if comment:
            updates["metadata.completion_comment"] = comment
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            updates["metadata.completed_by"] = user_email

        result = db_connection.todos.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo completed by {user_email}: {todo_id}")
            await log_todo_complete(todo_id, existing_todo.get('description', 'Unknown'),
                                    existing_todo.get('project', 'Unknown'), user_email)
            return create_response(True, message=f"Todo {todo_id} marked as complete.")
        else:
            return create_response(False, message=f"Failed to update todo {todo_id}.")
    except Exception as e:
        logger.error(f"Failed to mark todo complete: {str(e)}")
        return create_response(False, message=str(e))


async def list_todos_by_status(status: str, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    List todos filtered by their status.
    """
    if status.lower() not in ['pending', 'completed', 'initial']:
        return create_response(False, message="Invalid status. Must be one of 'pending', 'completed', 'initial'.")
    return await query_todos(filter={"status": status.lower()}, limit=limit)

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None, ctx: Optional[Context] = None) -> str:
    """
    Add a new lesson to the knowledge base.
    """
    lesson = {
        "id": str(uuid.uuid4()),
        "language": language,
        "topic": topic,
        "lesson_learned": lesson_learned,
        "tags": tags or [],
        "created_at": int(datetime.now(UTC).timestamp())
    }
    try:
        db_connection.lessons.insert_one(lesson)
        if tags:
            _cache.pop(TAGS_CACHE_KEY, None)
            _cache_expiry.pop(TAGS_CACHE_KEY, None)
        return create_response(True, lesson)
    except Exception as e:
        logger.error(f"Failed to add lesson: {str(e)}")
        return create_response(False, message=str(e))

async def get_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """
    Get a specific lesson by its ID.
    """
    try:
        lesson = db_connection.lessons.find_one({"id": lesson_id})
        if lesson:
            return create_response(True, lesson)
        else:
            return create_response(False, message=f"Lesson with ID {lesson_id} not found.")
    except Exception as e:
        logger.error(f"Failed to get lesson: {str(e)}")
        return create_response(False, message=str(e))

async def update_lesson(lesson_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """
    Update an existing lesson.
    """
    try:
        result = db_connection.lessons.update_one({"id": lesson_id}, {"$set": updates})
        if result.modified_count == 1:
            if 'tags' in updates:
                _cache.pop(TAGS_CACHE_KEY, None)
                _cache_expiry.pop(TAGS_CACHE_KEY, None)
            return create_response(True, message=f"Lesson {lesson_id} updated.")
        else:
            return create_response(False, message=f"Lesson {lesson_id} not found.")
    except Exception as e:
        logger.error(f"Failed to update lesson: {str(e)}")
        return create_response(False, message=str(e))

async def delete_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """
    Delete a lesson by its ID.
    """
    try:
        result = db_connection.lessons.delete_one({"id": lesson_id})
        if result.deleted_count == 1:
            _cache.pop(TAGS_CACHE_KEY, None)
            _cache_expiry.pop(TAGS_CACHE_KEY, None)
            return create_response(True, message=f"Lesson {lesson_id} deleted.")
        else:
            return create_response(False, message=f"Lesson {lesson_id} not found.")
    except Exception as e:
        logger.error(f"Failed to delete lesson: {str(e)}")
        return create_response(False, message=str(e))

async def search_todos(query: str, fields: Optional[list] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    Search todos with text search capabilities.
    """
    if fields is None:
        fields = ["description", "project"]
    search_query = {
        "$or": [{field: {"$regex": query, "$options": "i"}} for field in fields]
    }
    return await query_todos(filter=search_query, limit=limit)

async def grep_lessons(pattern: str, limit: int = 20, ctx: Optional[Context] = None) -> str:
    """
    Search lessons with grep-style pattern matching across topic and content.
    """
    try:
        search_query = {
            "$or": [
                {"topic": {"$regex": pattern, "$options": "i"}},
                {"lesson_learned": {"$regex": pattern, "$options": "i"}}
            ]
        }
        cursor = db_connection.lessons.find(search_query).limit(limit)
        results = list(cursor)
        return create_response(True, {"items": results})
    except Exception as e:
        logger.error(f"Failed to grep lessons: {str(e)}")
        return create_response(False, message=str(e))

async def list_project_todos(project: str, limit: int = 5, ctx: Optional[Context] = None) -> str:
    """
    List recent active todos for a specific project.
    """
    return await query_todos(
        filter={"project": project.lower(), "status": "pending"},
        limit=limit
    )

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, ctx: Optional[Context] = None) -> str:
    """
    Query the todo logs with filtering and pagination.
    """
    from .todo_log_service import get_service_instance
    service = get_service_instance()
    logs = await service.get_logs(filter_type, project, page, page_size)
    return create_response(True, logs)

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive", ctx: Optional[Context] = None) -> str:
    """
    List all valid projects from the centralized project management system.
    """
    # This tool now directly returns the hardcoded list of valid projects
    return create_response(True, {"projects": VALID_PROJECTS})

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Optional[Context] = None) -> str:
    """
    Add a new explanation to the knowledge base.
    """
    explanation = {
        "topic": topic,
        "content": content,
        "kind": kind,
        "author": author,
        "created_at": datetime.now(UTC)
    }
    try:
        db_connection.explanations.update_one(
            {"topic": topic},
            {"$set": explanation},
            upsert=True
        )
        return create_response(True, explanation, f"Explanation for '{topic}' added/updated.")
    except Exception as e:
        logger.error(f"Failed to add explanation: {str(e)}")
        return create_response(False, message=str(e))

async def get_explanation(topic: str, ctx: Optional[Context] = None) -> str:
    """Get an explanation for a given topic."""
    try:
        explanation = db_connection.explanations.find_one({"topic": topic})
        if explanation:
            return create_response(True, explanation)
        return create_response(False, message=f"Explanation for '{topic}' not found.")
    except Exception as e:
        logger.error(f"Failed to get explanation: {str(e)}")
        return create_response(False, message=str(e))

async def update_explanation(topic: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """Update an existing explanation."""
    try:
        result = db_connection.explanations.update_one({"topic": topic}, {"$set": updates})
        if result.modified_count:
            return create_response(True, message="Explanation updated.")
        return create_response(False, message="Explanation not found or no changes made.")
    except Exception as e:
        logger.error(f"Failed to update explanation: {str(e)}")
        return create_response(False, message=str(e))

async def delete_explanation(topic: str, ctx: Optional[Context] = None) -> str:
    """Delete an explanation for a given topic."""
    try:
        result = db_connection.explanations.delete_one({"topic": topic})
        if result.deleted_count:
            return create_response(True, message="Explanation deleted.")
        return create_response(False, message="Explanation not found.")
    except Exception as e:
        logger.error(f"Failed to delete explanation: {str(e)}")
        return create_response(False, message=str(e))


async def explain_tool(topic: str, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """
    Provides a detailed explanation for a project or concept.
    """
    from . import explain as explain_module
    explanation = await explain_module.explain(topic, brief)
    return create_response(True, {"topic": topic, "explanation": explanation})


async def list_lessons(limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """
    List all lessons, sorted by creation date.
    """
    try:
        cursor = db_connection.lessons.find().sort("created_at", -1).limit(limit)
        results = list(cursor)
        if brief:
            results = [{"id": r["id"], "topic": r["topic"], "language": r["language"]} for r in results]
        return create_response(True, {"items": results})
    except Exception as e:
        logger.error(f"Failed to list lessons: {str(e)}")
        return create_response(False, message=str(e))

async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """
    Search lessons with text search capabilities.
    """
    if fields is None:
        fields = ["topic", "lesson_learned", "tags"]
    search_query = {
        "$or": [{field: {"$regex": query, "$options": "i"}} for field in fields]
    }
    try:
        cursor = db_connection.lessons.find(search_query).limit(limit)
        results = list(cursor)
        if brief:
            results = [{"id": r["id"], "topic": r["topic"], "language": r["language"]} for r in results]
        return create_response(True, {"items": results})
    except Exception as e:
        logger.error(f"Failed to search lessons: {str(e)}")
        return create_response(False, message=str(e)) 
