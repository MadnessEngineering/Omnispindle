import json
import os
import re
import ssl
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Union, List, Dict, Optional, Any

import logging
from dotenv import load_dotenv

from .context import Context
from pymongo import MongoClient

from .database import db_connection
from .utils import create_response, mqtt_publish, _format_duration
from .todo_log_service import log_todo_create, log_todo_update, log_todo_delete, log_todo_complete
from .schemas.todo_metadata_schema import validate_todo_metadata, validate_todo, TodoMetadata
from .query_handlers import enhance_todo_query, build_metadata_aggregation, get_query_enhancer
from .git_integration import enrich_metadata_with_git
from . import api_tools

# Load environment variables
load_dotenv()

# Get the logger
logger = logging.getLogger(__name__)

# Helper function to strip empty fields to save tokens
def strip_empty_fields(obj):
    """Recursively remove empty fields (None, empty strings, empty lists, empty dicts)"""
    if isinstance(obj, dict):
        return {k: strip_empty_fields(v) for k, v in obj.items()
                if v not in (None, "", [], {})}
    elif isinstance(obj, list):
        return [strip_empty_fields(item) for item in obj if item not in (None, "", [], {})]
    return obj

# Helper function for deep merging metadata
def deep_merge_metadata(existing: dict, updates: dict) -> dict:
    """
    Deep merge metadata updates with existing metadata.
    Preserves existing fields that aren't being updated.

    Args:
        existing: Existing metadata dict
        updates: New metadata updates to merge

    Returns:
        Merged metadata dict
    """
    if not existing:
        return updates.copy() if updates else {}
    if not updates:
        return existing.copy() if existing else {}

    merged = existing.copy()

    for key, value in updates.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            merged[key] = deep_merge_metadata(merged[key], value)
        else:
            # Replace/add the value
            merged[key] = value

    return merged

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
    "documentation", "eventghost-rust", "hammerghost",
    "quality_assurance", "spindlewrit", "inventorium"
]

# Cache utility functions
def cache_lesson_tags(tags_list, ctx=None):
    """
    Cache the list of all lesson tags in MongoDB.
    
    Args:
        tags_list: List of tags to cache
        ctx: Optional context for user-scoped collections
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        # Add timestamp for cache expiry management
        cache_entry = {
            "key": TAGS_CACHE_KEY,
            "tags": list(tags_list),
            "updated_at": int(datetime.now(timezone.utc).timestamp())
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

def get_cached_lesson_tags(ctx=None):
    """
    Retrieve the cached list of lesson tags from MongoDB.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        List of tags if cache exists and is valid, None otherwise
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        # Find the cache entry
        cache_entry = tags_cache_collection.find_one({"key": TAGS_CACHE_KEY})

        if not cache_entry:
            return None

        # Check if cache is expired
        current_time = int(datetime.now(timezone.utc).timestamp())
        if current_time - cache_entry["updated_at"] > TAGS_CACHE_EXPIRY:
            # Cache expired, invalidate it
            invalidate_lesson_tags_cache(ctx)
            return None

        return cache_entry["tags"]
    except Exception as e:
        logging.error(f"Failed to retrieve cached lesson tags: {str(e)}")
        return None

def invalidate_lesson_tags_cache(ctx=None):
    """
    Invalidate the lesson tags cache in MongoDB.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        tags_cache_collection.delete_one({"key": TAGS_CACHE_KEY})
        return True
    except Exception as e:
        logging.error(f"Failed to invalidate lesson tags cache: {str(e)}")
        return False

def get_all_lesson_tags(ctx=None):
    """
    Get all unique tags from lessons, with caching.
    
    First tries to fetch from cache, falls back to database if needed.
    Also updates the cache if fetching from database.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        List of all unique tags
    """
    cached_tags = get_cached_lesson_tags(ctx)
    if cached_tags is not None:
        return cached_tags

    # If not in cache, query from database
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

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
        cache_lesson_tags(all_tags, ctx)
        return all_tags
    except Exception as e:
        logging.error(f"Failed to aggregate lesson tags: {str(e)}")
        return []

# Project management functions
def cache_projects(projects_list, ctx=None):
    """
    Cache the list of valid projects in MongoDB.
    
    Args:
        projects_list: List of project names to cache
        ctx: Optional context for user-scoped collections
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        cache_entry = {
            "key": PROJECTS_CACHE_KEY,
            "projects": list(projects_list),
            "updated_at": int(datetime.now(timezone.utc).timestamp())
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

def get_cached_projects(ctx=None):
    """
    Retrieve the cached list of valid projects from MongoDB.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        List of project names if cache exists and is valid, None otherwise
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        cache_entry = tags_cache_collection.find_one({"key": PROJECTS_CACHE_KEY})

        if not cache_entry:
            return None

        # Check if cache is expired
        current_time = int(datetime.now(timezone.utc).timestamp())
        if current_time - cache_entry["updated_at"] > PROJECTS_CACHE_EXPIRY:
            invalidate_projects_cache(ctx)
            return None

        return cache_entry["projects"]
    except Exception as e:
        logging.error(f"Failed to retrieve cached projects: {str(e)}")
        return None

def invalidate_projects_cache(ctx=None):
    """
    Invalidate the projects cache in MongoDB.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        tags_cache_collection = collections['tags_cache']

        tags_cache_collection.delete_one({"key": PROJECTS_CACHE_KEY})
        return True
    except Exception as e:
        logging.error(f"Failed to invalidate projects cache: {str(e)}")
        return False

def initialize_projects_collection(ctx=None):
    """
    Initialize the projects collection with the current VALID_PROJECTS list.
    This is a one-time migration function that includes git URLs and paths.
    
    Args:
        ctx: Optional context for user-scoped collections
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        projects_collection = collections['projects']

        # Check if projects collection is already populated
        existing_count = projects_collection.count_documents({})
        if existing_count > 0:
            logging.info(f"Projects collection already has {existing_count} projects")
            return True

        # Insert all valid projects with enhanced metadata
        current_time = int(datetime.now(timezone.utc).timestamp())
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
            projects_collection.insert_many(projects_to_insert)
            logging.info(f"Successfully inserted {len(projects_to_insert)} projects into the collection")

        # Invalidate project cache after initialization
        invalidate_projects_cache(ctx)
        return True

    except Exception as e:
        logging.error(f"Failed to initialize projects collection: {str(e)}")
        return False

def get_all_projects(ctx=None):
    """
    Get all projects from the database, with caching.
    
    Args:
        ctx: Optional context for user-scoped collections
    """
    cached_projects = get_cached_projects(ctx)
    if cached_projects:
        return cached_projects

    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        projects_collection = collections['projects']

        # Get all projects from the database
        projects_from_db = list(projects_collection.find({}, {"_id": 0}))

        # If the database is empty, initialize it as a fallback
        if not projects_from_db:
            initialize_projects_collection(ctx)
            projects_from_db = list(projects_collection.find({}, {"_id": 0}))

        # Cache the results for future use
        cache_projects(projects_from_db, ctx)
        return projects_from_db
    except Exception as e:
        logging.error(f"Failed to get projects from database: {str(e)}")
        return []

def validate_project_name(project: str, ctx: Optional[Context] = None) -> str:
    """
    Validate project name against personal database first, then shared, then hardcoded list.
    This allows users to have their own projects while still accessing shared projects.
    """
    # Normalize project name for validation
    project_lower = project.lower()

    # Check personal database first (if authenticated)
    if ctx and ctx.user and ctx.user.get('sub'):
        try:
            user_projects = get_all_projects(ctx)
            user_project_names = [p.get('name', p.get('id', '')).lower() for p in user_projects]
            if project_lower in user_project_names:
                return project_lower
        except Exception as e:
            logger.debug(f"Could not check personal projects: {str(e)}")

    # Check shared database as fallback
    try:
        shared_projects = get_all_projects(None)
        shared_project_names = [p.get('name', p.get('id', '')).lower() for p in shared_projects]
        if project_lower in shared_project_names:
            return project_lower
    except Exception as e:
        logger.debug(f"Could not check shared projects: {str(e)}")

    # Check hardcoded list as final fallback
    if project_lower in [p.lower() for p in VALID_PROJECTS]:
        return project_lower

    # Default to "madness_interactive" if not found anywhere
    logger.warning(f"Project '{project}' not found in any database, defaulting to 'madness_interactive'")
    return "madness_interactive"

def _is_read_only_user(ctx: Optional[Context]) -> bool:
    """
    Check if the user is in read-only mode (unauthenticated demo user).
    Returns True if user should have read-only access.
    """
    return not ctx or not ctx.user or not ctx.user.get('sub')

async def add_todo(description: str, project: str, priority: str = "Medium", target_agent: str = "user", notes: str = "", ticket: str = "", metadata: Optional[Dict[str, Any]] = None, ctx: Optional[Context] = None) -> str:
    """
    Creates a task in the specified project with the given priority and target agent.

    Args:
        description: Task description
        project: Project name
        priority: Priority level (default: "Medium")
        target_agent: Who should work on this (default: "user")
        notes: User-facing notes/context about the todo (default: "")
        ticket: External ticket reference (default: "")
        metadata: Optional structured metadata (tags, files, etc.)
        ctx: Context with user information

    Returns a compact representation of the created todo with an ID for reference.
    """
    logger.info(f"🐛 tools.add_todo called with metadata type={type(metadata)}, value={metadata}")

    # Check for read-only mode (unauthenticated demo users)
    if _is_read_only_user(ctx):
        return create_response(False, message="Demo mode: Todo creation is disabled. Please authenticate to create todos.")

    todo_id = str(uuid.uuid4())
    validated_project = validate_project_name(project)

    validated_project = validate_project_name(project, ctx)

    # Validate metadata against schema if provided
    validated_metadata = {}
    logger.info(f"🐛 tools.add_todo before validation: metadata={metadata}")
    if metadata:
        try:
            validated_metadata_obj = validate_todo_metadata(metadata)
            validated_metadata = validated_metadata_obj.model_dump(exclude_none=True)
            logger.info(f"Metadata validated successfully for todo {todo_id}")
        except Exception as e:
            logger.warning(f"Metadata validation failed for todo {todo_id}: {str(e)}")
            # For backward compatibility, store raw metadata with validation warning
            validated_metadata = metadata.copy() if metadata else {}
            validated_metadata["_validation_warning"] = f"Schema validation failed: {str(e)}"

    # Enrich metadata with git context (branch, commit_hash) if available
    validated_metadata = enrich_metadata_with_git(validated_metadata)

    todo = {
        "id": todo_id,
        "description": description,
        "project": validated_project,
        "priority": priority,
        "status": "pending",
        "target_agent": target_agent,
        "created_at": int(datetime.now(timezone.utc).timestamp()),
        "notes": notes,  # ✅ User-facing notes field
        "ticket": ticket,  # ✅ External ticket reference
        "metadata": validated_metadata
    }
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        todos_collection = collections['todos']

        todos_collection.insert_one(todo)
        user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
        logger.info(f"Todo created by {user_email} in user database: {todo_id}")
        await log_todo_create(todo_id, description, project, user_email, ctx.user if ctx else None)

        return json.dumps({"id": todo_id})
    except Exception as e:
        logger.error(f"Failed to create todo: {str(e)}")
        return create_response(False, message=str(e))

async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, limit: int = 100, offset: int = 0, exclude_completed: bool = True, ctx: Optional[Context] = None) -> str:
    """
    Query todos with flexible filtering options and pagination.
    - Authenticated users: returns their personal todos
    - Unauthenticated users: returns shared database todos (read-only demo mode)
    - By default, excludes completed items (set exclude_completed=False to include them)
    - Supports pagination via offset parameter
    """
    try:
        user_context = ctx.user if ctx else None

        # For authenticated users with Auth0 'sub', use their personal database
        if user_context and user_context.get('sub'):
            collections = db_connection.get_collections(user_context)
            todos_collection = collections['todos']
            database_source = "personal"
        else:
            # For unauthenticated users, provide read-only access to shared database
            collections = db_connection.get_collections(None)  # None = shared database
            todos_collection = collections['todos']
            database_source = "shared (read-only demo)"

        # Build query filter
        query_filter = filter.copy() if filter else {}

        # Exclude completed items by default unless explicitly included in filter
        if exclude_completed and "status" not in query_filter:
            query_filter["status"] = {"$ne": "completed"}

        cursor = todos_collection.find(query_filter, projection).sort("created_at", -1).skip(offset).limit(limit)
        results = list(cursor)

        logger.info(f"Query returned {len(results)} todos from {database_source} database (offset={offset}, limit={limit}, exclude_completed={exclude_completed})")
        return json.dumps({"items": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Failed to query todos: {str(e)}")
        return create_response(False, message=str(e))

async def update_todo(todo_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """
    Update a todo with the provided changes.
    Metadata updates are MERGED with existing metadata instead of replacing it.
    """
    # Check for read-only mode (unauthenticated demo users)
    if _is_read_only_user(ctx):
        return create_response(False, message="Demo mode: Todo updates are disabled. Please authenticate to modify todos.")

    if "updated_at" not in updates:
        updates["updated_at"] = int(datetime.now(timezone.utc).timestamp())

    # NOTE: Metadata validation moved to AFTER fetching existing todo for proper merging
    try:
        user_context = ctx.user if ctx else None
        searched_databases = []
        existing_todo = None
        todos_collection = None
        database_source = None

        # First, try user-specific database
        if user_context and user_context.get('sub'):
            user_collections = db_connection.get_collections(user_context)
            user_todos_collection = user_collections['todos']
            user_db_name = user_collections['database'].name
            searched_databases.append(f"user database '{user_db_name}'")

            existing_todo = user_todos_collection.find_one({"id": todo_id})
            if existing_todo:
                todos_collection = user_todos_collection
                database_source = "user"

        # If not found in user database (or no user database), try shared database
        if not existing_todo:
            shared_collections = db_connection.get_collections(None)  # None = shared database
            shared_todos_collection = shared_collections['todos']
            shared_db_name = shared_collections['database'].name
            searched_databases.append(f"shared database '{shared_db_name}'")

            existing_todo = shared_todos_collection.find_one({"id": todo_id})
            if existing_todo:
                todos_collection = shared_todos_collection
                database_source = "shared"

        # If todo not found in any database
        if not existing_todo:
            searched_locations = " and ".join(searched_databases)
            return create_response(False, message=f"Todo {todo_id} not found. Searched in: {searched_locations}")

        # 🔧 MERGE metadata with existing instead of replacing
        if "metadata" in updates and updates["metadata"] is not None:
            existing_metadata = existing_todo.get("metadata", {})
            merged_metadata = deep_merge_metadata(existing_metadata, updates["metadata"])

            # Validate the merged metadata
            try:
                validated_metadata_obj = validate_todo_metadata(merged_metadata)
                updates["metadata"] = validated_metadata_obj.model_dump(exclude_none=True)
                logger.info(f"Metadata merged and validated for todo {todo_id}: {len(existing_metadata)} existing fields + {len(updates['metadata'])} updates")
            except Exception as e:
                logger.warning(f"Metadata validation failed for merged metadata in todo {todo_id}: {str(e)}")
                # For backward compatibility, keep merged metadata with validation warning
                if isinstance(merged_metadata, dict):
                    merged_metadata["_validation_warning"] = f"Schema validation failed: {str(e)}"
                updates["metadata"] = merged_metadata

        # Update the todo in the database where it was found
        result = todos_collection.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo updated by {user_email}: {todo_id} in {database_source} database")
            description = updates.get('description', existing_todo.get('description', 'Unknown'))
            project = updates.get('project', existing_todo.get('project', 'Unknown'))
            changes = [
                {"field": field, "old_value": existing_todo.get(field), "new_value": value}
                for field, value in updates.items()
                if field != 'updated_at' and existing_todo.get(field) != value
            ]
            await log_todo_update(todo_id, description, project, changes, user_email, ctx.user if ctx else None)
            return json.dumps({"id": todo_id})
        else:
            return create_response(False, message=f"Todo {todo_id} found but no changes made.")
    except Exception as e:
        logger.error(f"Failed to update todo: {str(e)}")
        return create_response(False, message=str(e))

async def delete_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """
    Delete a todo item by its ID.
    """
    # Check for read-only mode (unauthenticated demo users)
    if _is_read_only_user(ctx):
        return create_response(False, message="Demo mode: Todo deletion is disabled. Please authenticate to delete todos.")

    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        todos_collection = collections['todos']

        existing_todo = todos_collection.find_one({"id": todo_id})
        if existing_todo:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo deleted by {user_email}: {todo_id}")
            await log_todo_delete(todo_id, existing_todo.get('description', 'Unknown'),
                                  existing_todo.get('project', 'Unknown'), user_email, ctx.user if ctx else None)
        result = todos_collection.delete_one({"id": todo_id})
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
    Searches user database first, then falls back to shared database if not found.
    """
    try:
        user_context = ctx.user if ctx else None
        searched_databases = []

        # First, try user-specific database
        if user_context and user_context.get('sub'):
            user_collections = db_connection.get_collections(user_context)
            user_todos_collection = user_collections['todos']
            user_db_name = user_collections['database'].name
            searched_databases.append(f"user database '{user_db_name}'")

            todo = user_todos_collection.find_one({"id": todo_id})
            if todo:
                todo['source'] = 'user'
                # Remove MongoDB _id and strip empty fields
                if '_id' in todo:
                    del todo['_id']
                return json.dumps(strip_empty_fields(todo))

        # If not found in user database (or no user database), try shared database
        shared_collections = db_connection.get_collections(None)  # None = shared database
        shared_todos_collection = shared_collections['todos']
        shared_db_name = shared_collections['database'].name
        searched_databases.append(f"shared database '{shared_db_name}'")

        todo = shared_todos_collection.find_one({"id": todo_id})
        if todo:
            todo['source'] = 'shared'
            # Remove MongoDB _id and strip empty fields
            if '_id' in todo:
                del todo['_id']
            return json.dumps(strip_empty_fields(todo))

        # Not found in any database
        searched_locations = " and ".join(searched_databases)
        return create_response(False, message=f"Todo with ID {todo_id} not found. Searched in: {searched_locations}")

    except Exception as e:
        logger.error(f"Failed to get todo: {str(e)}")
        return create_response(False, message=str(e))

async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """
    Mark a todo as completed.
    """
    # Check for read-only mode (unauthenticated demo users)
    if _is_read_only_user(ctx):
        return create_response(False, message="Demo mode: Todo completion is disabled. Please authenticate to modify todos.")

    try:
        user_context = ctx.user if ctx else None
        searched_databases = []
        existing_todo = None
        todos_collection = None
        database_source = None

        # First, try user-specific database
        if user_context and user_context.get('sub'):
            user_collections = db_connection.get_collections(user_context)
            user_todos_collection = user_collections['todos']
            user_db_name = user_collections['database'].name
            searched_databases.append(f"user database '{user_db_name}'")

            existing_todo = user_todos_collection.find_one({"id": todo_id})
            if existing_todo:
                todos_collection = user_todos_collection
                database_source = "user"

        # If not found in user database (or no user database), try shared database
        if not existing_todo:
            shared_collections = db_connection.get_collections(None)  # None = shared database
            shared_todos_collection = shared_collections['todos']
            shared_db_name = shared_collections['database'].name
            searched_databases.append(f"shared database '{shared_db_name}'")

            existing_todo = shared_todos_collection.find_one({"id": todo_id})
            if existing_todo:
                todos_collection = shared_todos_collection
                database_source = "shared"

        # If todo not found in any database
        if not existing_todo:
            searched_locations = " and ".join(searched_databases)
            return create_response(False, message=f"Todo {todo_id} not found. Searched in: {searched_locations}")

        completed_at = int(datetime.now(timezone.utc).timestamp())
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

        # Add git context on completion (branch and commit hash at completion time)
        git_metadata = enrich_metadata_with_git()
        if "branch" in git_metadata:
            updates["metadata.completion_branch"] = git_metadata["branch"]
        if "commit_hash" in git_metadata:
            updates["metadata.completion_commit_hash"] = git_metadata["commit_hash"]

        # Complete the todo in the database where it was found
        result = todos_collection.update_one({"id": todo_id}, {"$set": updates})
        if result.modified_count == 1:
            user_email = ctx.user.get("email", "anonymous") if ctx and ctx.user else "anonymous"
            logger.info(f"Todo completed by {user_email}: {todo_id} in {database_source} database")
            await log_todo_complete(todo_id, existing_todo.get('description', 'Unknown'),
                                    existing_todo.get('project', 'Unknown'), user_email, ctx.user if ctx else None, comment)
            return json.dumps({"id": todo_id})
        else:
            return create_response(False, message=f"Todo {todo_id} found but failed to mark as complete.")
    except Exception as e:
        logger.error(f"Failed to mark todo complete: {str(e)}")
        return create_response(False, message=str(e))


async def list_todos_by_status(status: str, limit: int = 100, offset: int = 0, ctx: Optional[Context] = None) -> str:
    """
    List todos filtered by their status with pagination support.
    """
    if status.lower() not in ['pending', 'completed', 'initial', 'blocked', 'in_progress']:
        return create_response(False, message="Invalid status. Must be one of 'pending', 'completed', 'initial', 'blocked', 'in_progress'.")
    # When querying by status, don't apply the default completed filter
    return await query_todos(filter={"status": status.lower()}, limit=limit, offset=offset, exclude_completed=False, ctx=ctx)

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
        "created_at": int(datetime.now(timezone.utc).timestamp())
    }
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        lessons_collection.insert_one(lesson)
        if tags:
            # Invalidate the tags cache when new tags are added
            invalidate_lesson_tags_cache(ctx)
        return json.dumps({"id": lesson["id"]})
    except Exception as e:
        logger.error(f"Failed to add lesson: {str(e)}")
        return create_response(False, message=str(e))

async def get_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """
    Get a specific lesson by its ID.
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        lesson = lessons_collection.find_one({"id": lesson_id})
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
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        result = lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
        if result.modified_count == 1:
            if 'tags' in updates:
                # Invalidate the tags cache when tags are modified
                invalidate_lesson_tags_cache(ctx)
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
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        result = lessons_collection.delete_one({"id": lesson_id})
        if result.deleted_count == 1:
            # Invalidate the tags cache when lessons are deleted
            invalidate_lesson_tags_cache(ctx)
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

    user_id = ctx.user.get('sub') if ctx and ctx.user else 'anonymous'
    logger.info(f"search_todos called by {user_id}: query='{query}', fields={fields}, limit={limit}")
    logger.debug(f"MongoDB query: {search_query}")

    result = await query_todos(filter=search_query, limit=limit, ctx=ctx)

    # Parse result to log count
    try:
        import json
        result_data = json.loads(result)
        item_count = len(result_data.get('data', {}).get('items', [])) if result_data.get('success') else 0
        logger.info(f"search_todos returned {item_count} results for query '{query}'")
    except:
        pass

    return result


async def query_todos_by_metadata(metadata_filters: Dict[str, Any],
                                 base_filter: Optional[Dict[str, Any]] = None,
                                 limit: int = 100,
                                 ctx: Optional[Context] = None) -> str:
    """
    Query todos with enhanced metadata filtering capabilities.
    
    Args:
        metadata_filters: Metadata-specific filters like tags, complexity, confidence, etc.
        base_filter: Base MongoDB filter to combine with metadata filters
        limit: Maximum results to return
        ctx: User context
        
    Returns:
        JSON response with filtered todos
        
    Example metadata_filters:
        {
            "tags": ["bug", "urgent"],
            "complexity": "High", 
            "confidence": {"min": 3, "max": 5},
            "phase": "implementation",
            "files": {"files": ["*.jsx"], "match_type": "extension"}
        }
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        todos_collection = collections['todos']

        # Build enhanced query
        enhancer = get_query_enhancer()
        enhanced_filter = enhancer.enhance_query_filter(base_filter or {}, metadata_filters)

        logger.info(f"Enhanced metadata query: {enhanced_filter}")

        # Execute query
        cursor = todos_collection.find(enhanced_filter).limit(limit).sort("created_at", -1)
        results = list(cursor)

        return json.dumps({"items": results, "count": len(results)})

    except Exception as e:
        logger.error(f"Failed to query todos by metadata: {str(e)}")
        return create_response(False, message=str(e))


async def search_todos_advanced(query: str,
                               metadata_filters: Optional[Dict[str, Any]] = None,
                               fields: Optional[List[str]] = None,
                               limit: int = 100,
                               ctx: Optional[Context] = None) -> str:
    """
    Advanced todo search with metadata filtering and text search.
    
    Combines traditional text search with metadata filtering for precise results.
    
    Args:
        query: Text search query
        metadata_filters: Optional metadata filters to apply
        fields: Fields to search in (description, project by default)
        limit: Maximum results
        ctx: User context
        
    Returns:
        JSON response with search results
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        todos_collection = collections['todos']

        # Build text search filter
        if fields is None:
            fields = ["description", "project"]

        text_search_filter = {
            "$or": [{field: {"$regex": query, "$options": "i"}} for field in fields]
        }

        # Combine with metadata filters if provided
        if metadata_filters:
            enhancer = get_query_enhancer()
            combined_filter = enhancer.enhance_query_filter(text_search_filter, metadata_filters)
        else:
            combined_filter = text_search_filter

        logger.info(f"Advanced search query: {combined_filter}")

        # Use aggregation pipeline for better performance with complex queries
        if metadata_filters:
            pipeline = build_metadata_aggregation(
                text_search_filter,
                metadata_filters or {},
                limit=limit
            )
            results = list(todos_collection.aggregate(pipeline))
        else:
            # Simple query for text-only search
            cursor = todos_collection.find(combined_filter).limit(limit).sort("created_at", -1)
            results = list(cursor)

        return json.dumps({"items": results, "count": len(results)})

    except Exception as e:
        logger.error(f"Failed to perform advanced todo search: {str(e)}")
        return create_response(False, message=str(e))


async def get_metadata_stats(project: Optional[str] = None,
                           ctx: Optional[Context] = None) -> str:
    """
    Get statistics about metadata usage across todos.
    
    Provides insights into:
    - Most common tags
    - Complexity distribution  
    - Confidence levels
    - Phase usage
    - File type distribution
    
    Args:
        project: Optional project filter
        ctx: User context
        
    Returns:
        JSON response with metadata statistics
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        todos_collection = collections['todos']

        # Base match filter
        match_filter = {}
        if project:
            match_filter["project"] = project.lower()

        # Aggregation pipeline for metadata stats
        pipeline = [
            {"$match": match_filter},
            {
                "$facet": {
                    "tag_stats": [
                        {"$unwind": {"path": "$metadata.tags", "preserveNullAndEmptyArrays": True}},
                        {"$group": {"_id": "$metadata.tags", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 20}
                    ],
                    "complexity_stats": [
                        {"$group": {"_id": "$metadata.complexity", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}}
                    ],
                    "confidence_stats": [
                        {"$group": {"_id": "$metadata.confidence", "count": {"$sum": 1}}},
                        {"$sort": {"_id": 1}}
                    ],
                    "phase_stats": [
                        {"$group": {"_id": "$metadata.phase", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 15}
                    ],
                    "file_type_stats": [
                        {"$unwind": {"path": "$metadata.files", "preserveNullAndEmptyArrays": True}},
                        {
                            "$addFields": {
                                "file_extension": {
                                    "$arrayElemAt": [
                                        {"$split": ["$metadata.files", "."]}, -1
                                    ]
                                }
                            }
                        },
                        {"$group": {"_id": "$file_extension", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 10}
                    ],
                    "total_counts": [
                        {
                            "$group": {
                                "_id": None,
                                "total_todos": {"$sum": 1},
                                "with_metadata": {
                                    "$sum": {"$cond": [{"$ne": ["$metadata", {}]}, 1, 0]}
                                },
                                "with_tags": {
                                    "$sum": {"$cond": [{"$isArray": "$metadata.tags"}, 1, 0]}
                                },
                                "with_complexity": {
                                    "$sum": {"$cond": [{"$ne": ["$metadata.complexity", None]}, 1, 0]}
                                }
                            }
                        }
                    ]
                }
            }
        ]

        results = list(todos_collection.aggregate(pipeline))

        if results:
            stats = results[0]

            # Clean up None values from tag stats
            stats["tag_stats"] = [item for item in stats["tag_stats"] if item["_id"] is not None]
            stats["complexity_stats"] = [item for item in stats["complexity_stats"] if item["_id"] is not None]
            stats["confidence_stats"] = [item for item in stats["confidence_stats"] if item["_id"] is not None]
            stats["phase_stats"] = [item for item in stats["phase_stats"] if item["_id"] is not None]
            stats["file_type_stats"] = [item for item in stats["file_type_stats"] if item["_id"] is not None]

            return create_response(True, {
                "project_filter": project,
                "statistics": stats,
                "generated_at": int(datetime.now(timezone.utc).timestamp())
            })
        else:
            return create_response(True, {
                "project_filter": project,
                "statistics": {"message": "No todos found"},
                "generated_at": int(datetime.now(timezone.utc).timestamp())
            })

    except Exception as e:
        logger.error(f"Failed to get metadata stats: {str(e)}")
        return create_response(False, message=str(e))

async def grep_lessons(pattern: str, limit: int = 20, ctx: Optional[Context] = None) -> str:
    """
    Search lessons with grep-style pattern matching across topic and content.
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        user_id = ctx.user.get('sub') if ctx and ctx.user else 'anonymous'
        db_name = lessons_collection.database.name
        logger.info(f"grep_lessons called by {user_id}: pattern='{pattern}', limit={limit}, db={db_name}")

        search_query = {
            "$or": [
                {"topic": {"$regex": pattern, "$options": "i"}},
                {"lesson_learned": {"$regex": pattern, "$options": "i"}}
            ]
        }
        logger.debug(f"MongoDB query: {search_query}")

        cursor = lessons_collection.find(search_query).limit(limit)
        results = list(cursor)

        logger.info(f"grep_lessons returned {len(results)} results for pattern '{pattern}'")
        return json.dumps({"items": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Failed to grep lessons: {str(e)}")
        return create_response(False, message=str(e))

async def list_project_todos(project: str, limit: int = 5, offset: int = 0, ctx: Optional[Context] = None) -> str:
    """
    List recent active todos for a specific project with pagination support.
    Only returns pending todos by default.
    """
    return await query_todos(
        filter={"project": project.lower(), "status": "pending"},
        limit=limit,
        offset=offset,
        exclude_completed=False,  # Already filtering to pending
        ctx=ctx
    )

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, unified: bool = False, ctx: Optional[Context] = None) -> str:
    """
    Query the todo logs with filtering and pagination.
    Supports unified view to query both personal and shared databases.
    """
    from .todo_log_service import get_service_instance

    if unified and ctx and ctx.user and ctx.user.get('sub'):
        # Unified view: get logs from both personal and shared databases
        try:
            service = get_service_instance()

            # Get personal logs (user-specific database)
            personal_logs = await service.get_logs(filter_type, project, page, page_size, ctx.user)
            personal_entries = personal_logs.get('logEntries', [])

            # Get shared logs (shared database)
            shared_logs = await service.get_logs(filter_type, project, page, page_size, None)
            shared_entries = shared_logs.get('logEntries', [])

            # Create a set to track unique log entries and prevent duplicates
            seen_logs = set()
            all_logs = []

            # Process personal logs first
            for log in personal_entries:
                log_key = f"{log.get('todoId', '')}_{log.get('operation', '')}_{log.get('timestamp', '')}"
                if log_key not in seen_logs:
                    log['source'] = 'personal'
                    all_logs.append(log)
                    seen_logs.add(log_key)

            # Process shared logs, but only add if not already seen
            for log in shared_entries:
                log_key = f"{log.get('todoId', '')}_{log.get('operation', '')}_{log.get('timestamp', '')}"
                if log_key not in seen_logs:
                    log['source'] = 'shared'
                    all_logs.append(log)
                    seen_logs.add(log_key)

            # Sort by timestamp
            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

            # Apply pagination to combined results
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_logs = all_logs[start_index:end_index]

            combined_result = {
                'logEntries': paginated_logs,
                'totalCount': len(all_logs),
                'page': page,
                'pageSize': page_size,
                'hasMore': len(all_logs) > end_index,
                'projects': list(set([log.get('project') for log in all_logs if log.get('project')]))
            }

            logger.info(f"Unified view: personal={len(personal_entries)}, shared={len(shared_entries)}, unique={len(all_logs)}")
            return create_response(True, combined_result)

        except Exception as e:
            logger.error(f"Failed to query unified todo logs: {str(e)}")
            # Fallback to user-specific logs only
            service = get_service_instance()
            logs = await service.get_logs(filter_type, project, page, page_size, ctx.user if ctx else None)
            return create_response(True, logs)
    else:
        # Regular view: single database based on user context
        service = get_service_instance()
        logs = await service.get_logs(filter_type, project, page, page_size, ctx.user if ctx else None)

        # Add source tag for consistency
        log_entries = logs.get('logEntries', [])
        source = 'personal' if ctx and ctx.user and ctx.user.get('sub') else 'shared'
        for log in log_entries:
            log['source'] = source

        return create_response(True, logs)

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive", ctx: Optional[Context] = None) -> str:
    """
    List all valid projects from the centralized project management system.
    Prioritizes personal database for authenticated users, shows shared for demos.
    """
    try:
        # For authenticated users, show only personal projects
        if ctx and ctx.user and ctx.user.get('sub'):
            user_projects = get_all_projects(ctx)
            if user_projects:
                project_names = [p.get('name', p.get('id', '')) for p in user_projects]
                return create_response(True, {"projects": project_names, "source": "personal"})

        # For unauthenticated users (demo mode), show shared projects
        shared_projects = get_all_projects(None)
        if shared_projects:
            project_names = [p.get('name', p.get('id', '')) for p in shared_projects]
            return create_response(True, {"projects": project_names, "source": "shared"})

        # Final fallback to hardcoded list if database is empty
        return create_response(True, {"projects": VALID_PROJECTS, "source": "fallback"})

    except Exception as e:
        logger.error(f"Failed to list projects: {str(e)}")
        # Fallback to hardcoded list on error
        return create_response(True, {"projects": VALID_PROJECTS, "source": "fallback"})

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Optional[Context] = None) -> str:
    """
    Add a new explanation to the knowledge base.
    """
    explanation = {
        "topic": topic,
        "content": content,
        "kind": kind,
        "author": author,
        "created_at": datetime.now(timezone.utc)
    }
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        explanations_collection = collections['explanations']

        explanations_collection.update_one(
            {"topic": topic},
            {"$set": explanation},
            upsert=True
        )
        return json.dumps({"id": topic})
    except Exception as e:
        logger.error(f"Failed to add explanation: {str(e)}")
        return create_response(False, message=str(e))

async def get_explanation(topic: str, ctx: Optional[Context] = None) -> str:
    """Get an explanation for a given topic."""
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        explanations_collection = collections['explanations']

        explanation = explanations_collection.find_one({"topic": topic})
        if explanation:
            return create_response(True, explanation)
        return create_response(False, message=f"Explanation for '{topic}' not found.")
    except Exception as e:
        logger.error(f"Failed to get explanation: {str(e)}")
        return create_response(False, message=str(e))

async def update_explanation(topic: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """Update an existing explanation."""
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        explanations_collection = collections['explanations']

        result = explanations_collection.update_one({"topic": topic}, {"$set": updates})
        if result.modified_count:
            return create_response(True, message="Explanation updated.")
        return create_response(False, message="Explanation not found or no changes made.")
    except Exception as e:
        logger.error(f"Failed to update explanation: {str(e)}")
        return create_response(False, message=str(e))

async def delete_explanation(topic: str, ctx: Optional[Context] = None) -> str:
    """Delete an explanation for a given topic."""
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        explanations_collection = collections['explanations']

        result = explanations_collection.delete_one({"topic": topic})
        if result.deleted_count:
            return create_response(True, message="Explanation deleted.")
        return create_response(False, message="Explanation not found.")
    except Exception as e:
        logger.error(f"Failed to delete explanation: {str(e)}")
        return create_response(False, message=str(e))


async def explain_tool(topic: str, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """
    Provides a detailed explanation for a project or concept.
    Uses get_explanation to retrieve stored explanations from the database.
    """
    # Use the existing get_explanation function instead of importing non-existent module
    return await get_explanation(topic, ctx)


async def list_lessons(limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """
    List all lessons, sorted by creation date.
    """
    try:
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        user_id = ctx.user.get('sub') if ctx and ctx.user else 'anonymous'
        db_name = lessons_collection.database.name
        logger.info(f"list_lessons called by {user_id}: limit={limit}, brief={brief}, db={db_name}")

        cursor = lessons_collection.find().sort("created_at", -1).limit(limit)
        results = list(cursor)

        logger.info(f"list_lessons returned {len(results)} total lessons")

        if brief:
            results = [{"id": r["id"], "topic": r["topic"], "language": r["language"]} for r in results]
        return json.dumps({"items": results, "count": len(results)})
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
        # Get user-scoped collections
        collections = db_connection.get_collections(ctx.user if ctx else None)
        lessons_collection = collections['lessons']

        user_id = ctx.user.get('sub') if ctx and ctx.user else 'anonymous'
        db_name = lessons_collection.database.name
        logger.info(f"search_lessons called by {user_id}: query='{query}', fields={fields}, limit={limit}, brief={brief}, db={db_name}")
        logger.debug(f"MongoDB query: {search_query}")

        cursor = lessons_collection.find(search_query).limit(limit)
        results = list(cursor)

        logger.info(f"search_lessons returned {len(results)} results for query '{query}'")

        if brief:
            results = [{"id": r["id"], "topic": r["topic"], "language": r["language"]} for r in results]
        return json.dumps({"items": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Failed to search lessons: {str(e)}")
        return create_response(False, message=str(e))


async def point_out_obvious(observation: str, sarcasm_level: int = 5, ctx: Optional[Context] = None) -> str:
    """
    Points out something obvious to the human user with varying levels of humor.
    
    Args:
        observation: The obvious thing to point out
        sarcasm_level: Scale from 1-10 (1=gentle, 10=maximum sass)
        ctx: Optional context
    
    Returns:
        A response highlighting the obvious with appropriate commentary
    """
    import random

    # Sarcasm templates based on level
    templates = {
        1: ["Just a friendly observation: {obs}", "I noticed that {obs}"],
        2: ["It seems that {obs}", "Apparently, {obs}"],
        3: ["Fun fact: {obs}", "Did you know? {obs}"],
        4: ["Breaking news: {obs}", "Alert: {obs}"],
        5: ["Captain Obvious reporting: {obs}", "In today's episode of 'Things We Already Know': {obs}"],
        6: ["🎉 Congratulations! You've discovered that {obs}", "Achievement unlocked: Noticing that {obs}"],
        7: ["*drum roll* ... {obs}", "Stop the presses! {obs}"],
        8: ["I'm sure you're shocked to learn that {obs}", "Brace yourself: {obs}"],
        9: ["In other groundbreaking revelations: {obs}", "Nobel Prize committee, take note: {obs}"],
        10: ["🤯 Mind = Blown: {obs}", "Call the scientists, we've confirmed that {obs}"]
    }

    # Clamp sarcasm level
    level = max(1, min(10, sarcasm_level))

    # Pick a random template for the level
    template_options = templates.get(level, templates[5])
    template = random.choice(template_options)

    # Format the response
    response = template.format(obs=observation)

    # Add emoji based on level
    if level >= 7:
        emojis = ["🙄", "😏", "🤔", "🧐", "🎭"]
        response = f"{random.choice(emojis)} {response}"

    # Log the obvious observation (for science)
    logger.info(f"Obvious observation made (sarcasm={level}): {observation}")

    # Store in a special "obvious_things" collection if we have DB
    try:
        # Get user-scoped collections - use a generic collection access
        collections = db_connection.get_collections(ctx.user if ctx else None)
        # Access the database directly for custom collections like obvious_observations
        obvious_collection = collections.database["obvious_observations"]
        obvious_collection.insert_one({
            "observation": observation,
            "sarcasm_level": level,
            "timestamp": datetime.now(timezone.utc),
            "user": ctx.user.get("sub") if ctx and ctx.user else "anonymous",
            "response": response
        })
    except Exception as e:
        logger.debug(f"Failed to store obvious observation: {e}")

    # Publish to MQTT for other systems to enjoy the obviousness
    try:
        mqtt_publish("observations/obvious", {
            "observation": observation,
            "sarcasm_level": level,
            "response": response
        })
    except Exception as e:
        logger.debug(f"Failed to publish obvious observation: {e}")

    return create_response(True, {
        "response": response,
        "observation": observation,
        "sarcasm_level": level,
        "meta": {
            "obviousness_score": min(100, level * 10),
            "humor_attempted": True,
            "captain_obvious_mode": level >= 5
        }
    })


async def bring_your_own(tool_name: str, code: str, runtime: str = "python",
                         timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                         persist: bool = False, ctx: Optional[Context] = None) -> str:
    """
    DISABLED: Custom tool execution has been disabled for security reasons.
    
    This tool previously allowed arbitrary code execution which poses significant 
    security risks. It has been disabled until proper sandboxing can be implemented.
    
    Args:
        tool_name: Name for the temporary tool (ignored)
        code: The code to execute (ignored)  
        runtime: Runtime environment (ignored)
        timeout: Maximum execution time (ignored)
        args: Arguments to pass to the custom tool (ignored)
        persist: Whether to save this tool (ignored)
        ctx: Optional context
    
    Returns:
        The result of executing the custom tool
    
    Security Note: This is intentionally powerful and dangerous.
    Use with caution and proper sandboxing in production.
    """
    import tempfile
    import asyncio
    import hashlib
    import pickle

    # Security check (basic - you'd want more in production)
    if ctx and ctx.user:
        user_id = ctx.user.get("sub", "anonymous")
        # Check if user is allowed to bring their own tools
        if user_id != "system" and not user_id.startswith("admin"):
            # Rate limit non-admin users
            rate_limit_key = f"byo_tool_{user_id}"
            # Simple in-memory rate limiting (use Redis in production)
            if not hasattr(bring_your_own, "_rate_limits"):
                bring_your_own._rate_limits = {}

            last_call = bring_your_own._rate_limits.get(rate_limit_key, 0)
            now = datetime.now(timezone.utc).timestamp()
            if now - last_call < 10:  # 10 second cooldown
                return create_response(False,
                    message=f"Rate limited. Please wait {10 - (now - last_call):.1f} seconds")
            bring_your_own._rate_limits[rate_limit_key] = now
    else:
        user_id = "anonymous"

    # Validate runtime
    allowed_runtimes = ["python", "javascript", "bash"]
    if runtime not in allowed_runtimes:
        return create_response(False,
            message=f"Invalid runtime. Allowed: {allowed_runtimes}")

    # Create a unique ID for this tool
    tool_id = hashlib.md5(f"{tool_name}_{code}_{datetime.now(timezone.utc)}".encode()).hexdigest()[:8]
    full_tool_name = f"byo_{tool_name}_{tool_id}"

    logger.warning(f"BYO Tool execution requested: {full_tool_name} by {user_id}")

    try:
        if runtime == "python":
            # Create a temporary module for the code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                # Wrap the code in a module structure
                module_code = f"""
import asyncio
import json
from datetime import datetime

# User-provided code
{code}

# Execution wrapper
async def _execute_byo_tool(args):
    if 'main' in globals():
        if asyncio.iscoroutinefunction(main):
            return await main(**args)
        else:
            return main(**args)
    else:
        raise ValueError("No 'main' function defined in custom tool code")
"""
                f.write(module_code)
                temp_file = f.name

            # Execute the code with timeout
            try:
                # Import and run the temporary module
                import importlib.util
                spec = importlib.util.spec_from_file_location(full_tool_name, temp_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Execute with timeout
                result = await asyncio.wait_for(
                    module._execute_byo_tool(args or {}),
                    timeout=timeout
                )

                # Clean up
                os.unlink(temp_file)

            except asyncio.TimeoutError:
                os.unlink(temp_file)
                return create_response(False,
                    message=f"Tool execution timed out after {timeout} seconds")
            except Exception as e:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                logger.error(f"BYO tool execution failed: {str(e)}")
                return create_response(False,
                    message=f"Tool execution failed: {str(e)}")

        elif runtime == "javascript":
            # Use subprocess to run Node.js
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                js_code = f"""
{code}

// Execution wrapper
(async () => {{
    const args = {json.dumps(args or {})};
    if (typeof main === 'function') {{
        const result = await main(args);
        console.log(JSON.stringify(result));
    }} else {{
        throw new Error("No 'main' function defined");
    }}
}})();
"""
                f.write(js_code)
                temp_file = f.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    'node', temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                os.unlink(temp_file)

                if proc.returncode != 0:
                    return create_response(False,
                        message=f"JavaScript execution failed: {stderr.decode()}")

                result = json.loads(stdout.decode())

            except asyncio.TimeoutError:
                proc.kill()
                os.unlink(temp_file)
                return create_response(False,
                    message=f"Tool execution timed out after {timeout} seconds")

        elif runtime == "bash":
            # Execute bash commands
            try:
                proc = await asyncio.create_subprocess_shell(
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )

                if proc.returncode != 0:
                    return create_response(False,
                        message=f"Bash execution failed: {stderr.decode()}")

                result = stdout.decode()

            except asyncio.TimeoutError:
                proc.kill()
                return create_response(False,
                    message=f"Tool execution timed out after {timeout} seconds")

        # Store execution history
        try:
            # Get user-scoped collections - use database access for custom collections
            collections = db_connection.get_collections(ctx.user if ctx else None)
            byo_collection = collections.database["byo_tools"]
            execution_record = {
                "tool_id": tool_id,
                "tool_name": tool_name,
                "full_name": full_tool_name,
                "code": code[:1000],  # Store first 1000 chars
                "runtime": runtime,
                "args": args,
                "result": str(result)[:500] if result else None,  # Store first 500 chars
                "user": user_id,
                "timestamp": datetime.now(timezone.utc),
                "persist": persist,
                "success": True
            }
            byo_collection.insert_one(execution_record)

            # If persist is True, save to a persistent tools collection
            if persist:
                persistent_tools = collections.database["persistent_byo_tools"]
                persistent_tools.update_one(
                    {"tool_name": tool_name},
                    {"$set": {
                        "tool_name": tool_name,
                        "code": code,
                        "runtime": runtime,
                        "created_by": user_id,
                        "created_at": datetime.now(timezone.utc),
                        "last_used": datetime.now(timezone.utc),
                        "execution_count": 1
                    }, "$inc": {"execution_count": 1}},
                    upsert=True
                )

        except Exception as e:
            logger.debug(f"Failed to store BYO tool execution: {e}")

        # Publish to MQTT for monitoring
        mqtt_publish("tools/byo/execution", {
            "tool_id": tool_id,
            "tool_name": full_tool_name,
            "runtime": runtime,
            "user": user_id,
            "success": True
        })

        return create_response(True, {
            "tool_id": tool_id,
            "tool_name": full_tool_name,
            "result": result,
            "runtime": runtime,
            "execution_time": f"{timeout}s max",
            "persisted": persist,
            "meta": {
                "warning": "Custom tool executed successfully. Use with caution.",
                "security_note": "This tool allows arbitrary code execution.",
                "user": user_id
            }
        })

    except Exception as e:
        logger.error(f"BYO tool creation/execution failed: {str(e)}")

        # Log failure
        try:
            # Get user-scoped collections - use database access for custom collections
            collections = db_connection.get_collections(ctx.user if ctx else None)
            byo_collection = collections.database["byo_tools"]
            byo_collection.insert_one({
                "tool_id": tool_id,
                "tool_name": tool_name,
                "error": str(e),
                "user": user_id,
                "timestamp": datetime.now(timezone.utc),
                "success": False
            })
        except:
            pass

        return create_response(False,
            message=f"Failed to create/execute custom tool: {str(e)}")


# --- Chat session API wrappers (Phase 2) ---

async def inventorium_sessions_list(project: Optional[str] = None, limit: int = 50, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_list(project=project, limit=limit, ctx=ctx)

async def inventorium_sessions_get(session_id: str, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_get(session_id, ctx=ctx)

async def inventorium_sessions_create(project: str, title: Optional[str] = None, initial_prompt: Optional[str] = None,
                                      agentic_tool: str = "claude-code", ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_create(project, title, initial_prompt, agentic_tool, ctx=ctx)

async def inventorium_sessions_spawn(parent_session_id: str, prompt: str, todo_id: Optional[str] = None,
                                     title: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_spawn(parent_session_id, prompt, todo_id, title, ctx=ctx)

async def inventorium_todos_link_session(todo_id: str, session_id: str, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_todos_link_session(todo_id, session_id, ctx=ctx)

async def inventorium_sessions_fork(session_id: str, title: Optional[str] = None, include_messages: bool = True,
                                    inherit_todos: bool = True, initial_status: Optional[str] = None,
                                    ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_fork(session_id, title, include_messages, inherit_todos, initial_status, ctx=ctx)

async def inventorium_sessions_genealogy(session_id: str, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_genealogy(session_id, ctx=ctx)

async def inventorium_sessions_tree(project: Optional[str] = None, limit: int = 200, ctx: Optional[Context] = None) -> str:
    return await api_tools.inventorium_sessions_tree(project, limit, ctx=ctx)
