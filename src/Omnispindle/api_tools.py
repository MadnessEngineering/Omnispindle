"""
API-based tools for Omnispindle MCP server.
Replaces direct database operations with HTTP API calls to madnessinteractive.cc/api
"""
import json
import uuid
import logging
from typing import Union, List, Dict, Optional, Any
from datetime import datetime, timezone

from .api_client import MadnessAPIClient, APIResponse, get_default_client
from .context import Context
from .utils import create_response

logger = logging.getLogger(__name__)

# Project validation - will be fetched from API
FALLBACK_VALID_PROJECTS = [
    "madness_interactive", "regressiontestkit", "omnispindle",
    "todomill_projectorium", "swarmonomicon", "hammerspoon",
    "lab_management", "cogwyrm", "docker_implementation",
    "documentation", "eventghost-rust", "hammerghost",
    "quality_assurance", "spindlewrit", "inventorium"
]

def _get_auth_from_context(ctx: Optional[Context]) -> tuple[Optional[str], Optional[str]]:
    """Extract authentication tokens from context"""
    auth_token = None
    api_key = None
    
    if ctx and ctx.user:
        # Try to extract JWT token from user context
        auth_token = ctx.user.get("access_token")
        # Or API key if provided
        api_key = ctx.user.get("api_key")
    
    return auth_token, api_key

def _convert_api_todo_to_mcp_format(api_todo: dict) -> dict:
    """
    Convert API todo format to MCP format for backward compatibility
    """
    # API uses different field names than our MCP tools expect
    mcp_todo = {
        "id": api_todo.get("id"),
        "description": api_todo.get("description"),
        "project": api_todo.get("project"),
        "priority": api_todo.get("priority", "Medium"),
        "status": api_todo.get("status", "pending"),
        "created_at": api_todo.get("created_at"),
        "metadata": api_todo.get("metadata", {})
    }
    
    # Handle completion data
    if api_todo.get("completed_at"):
        mcp_todo["completed_at"] = api_todo["completed_at"]
    if api_todo.get("duration"):
        mcp_todo["duration"] = api_todo["duration"]
    if api_todo.get("duration_sec"):
        mcp_todo["duration_sec"] = api_todo["duration_sec"]
    
    # Handle completion comment from metadata
    if api_todo.get("completion_comment"):
        mcp_todo["metadata"]["completion_comment"] = api_todo["completion_comment"]
    
    return mcp_todo

def _handle_api_response(api_response: APIResponse) -> str:
    """
    Convert API response to MCP tool response format
    """
    if not api_response.success:
        return create_response(False, message=api_response.error or "API request failed")
    
    return create_response(True, api_response.data)

async def add_todo(description: str, project: str, priority: str = "Medium", 
                  target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None, 
                  ctx: Optional[Context] = None) -> str:
    """
    Creates a task in the specified project with the given priority and target agent.
    Returns a compact representation of the created todo with an ID for reference.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        # Add target_agent to metadata if provided
        if not metadata:
            metadata = {}
        if target_agent and target_agent != "user":
            metadata["target_agent"] = target_agent
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.create_todo(
                description=description,
                project=project,
                priority=priority,
                metadata=metadata
            )
            
            if not api_response.success:
                return create_response(False, message=api_response.error or "Failed to create todo")
            
            # Extract todo from API response
            api_data = api_response.data
            if isinstance(api_data, dict) and 'todo' in api_data:
                todo_data = api_data['todo']
            elif isinstance(api_data, dict) and 'data' in api_data:
                todo_data = api_data['data']
            else:
                todo_data = api_data
            
            # Convert to MCP format
            mcp_todo = _convert_api_todo_to_mcp_format(todo_data)
            
            # Create compact response similar to original
            return create_response(True, {
                "operation": "create",
                "status": "success", 
                "todo_id": mcp_todo["id"],
                "description": description[:40] + ("..." if len(description) > 40 else ""),
                "project": project
            }, message=f"Todo '{description[:30]}...' created in '{project}'.")
            
    except Exception as e:
        logger.error(f"Failed to create todo via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, 
                     limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    Query todos with flexible filtering options from API.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        # Convert MongoDB-style filter to API query parameters
        project = None
        status = None
        priority = None
        
        if filter:
            project = filter.get("project")
            status = filter.get("status")
            priority = filter.get("priority")
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.get_todos(
                project=project,
                status=status, 
                priority=priority,
                limit=limit
            )
            
            if not api_response.success:
                return create_response(False, message=api_response.error or "Failed to query todos")
            
            # Extract todos from API response
            api_data = api_response.data
            if isinstance(api_data, dict) and 'todos' in api_data:
                todos_list = api_data['todos']
            else:
                todos_list = api_data if isinstance(api_data, list) else []
            
            # Convert each todo to MCP format
            mcp_todos = [_convert_api_todo_to_mcp_format(todo) for todo in todos_list]
            
            return create_response(True, {"items": mcp_todos})
            
    except Exception as e:
        logger.error(f"Failed to query todos via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def update_todo(todo_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """
    Update a todo with the provided changes.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.update_todo(todo_id, updates)
            
            if not api_response.success:
                return create_response(False, message=api_response.error or f"Failed to update todo {todo_id}")
            
            return create_response(True, message=f"Todo {todo_id} updated successfully")
            
    except Exception as e:
        logger.error(f"Failed to update todo via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def delete_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """
    Delete a todo item by its ID.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.delete_todo(todo_id)
            
            if not api_response.success:
                return create_response(False, message=api_response.error or f"Failed to delete todo {todo_id}")
            
            return create_response(True, message=f"Todo {todo_id} deleted successfully.")
            
    except Exception as e:
        logger.error(f"Failed to delete todo via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def get_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """
    Get a specific todo item by its ID.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.get_todo(todo_id)
            
            if not api_response.success:
                return create_response(False, message=api_response.error or f"Todo with ID {todo_id} not found.")
            
            # Convert to MCP format
            mcp_todo = _convert_api_todo_to_mcp_format(api_response.data)
            return create_response(True, mcp_todo)
            
    except Exception as e:
        logger.error(f"Failed to get todo via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """
    Mark a todo as completed.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.complete_todo(todo_id, comment)
            
            if not api_response.success:
                return create_response(False, message=api_response.error or f"Failed to complete todo {todo_id}")
            
            return create_response(True, message=f"Todo {todo_id} marked as complete.")
            
    except Exception as e:
        logger.error(f"Failed to complete todo via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def list_todos_by_status(status: str, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    List todos filtered by their status.
    """
    if status.lower() not in ['pending', 'completed', 'review']:
        return create_response(False, message="Invalid status. Must be one of 'pending', 'completed', 'review'.")
    
    return await query_todos(filter={"status": status.lower()}, limit=limit, ctx=ctx)

async def search_todos(query: str, fields: Optional[list] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """
    Search todos with text search capabilities.
    For API-based search, we'll use the general query endpoint for now.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        # For now, we'll fetch all todos and filter client-side
        # In future, the API should support text search parameters
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.get_todos(limit=limit)
            
            if not api_response.success:
                return create_response(False, message=api_response.error or "Failed to search todos")
            
            # Extract todos from API response
            api_data = api_response.data
            if isinstance(api_data, dict) and 'todos' in api_data:
                todos_list = api_data['todos']
            else:
                todos_list = api_data if isinstance(api_data, list) else []
            
            # Client-side text search
            if fields is None:
                fields = ["description", "project"]
            
            filtered_todos = []
            query_lower = query.lower()
            
            for todo in todos_list:
                for field in fields:
                    if field in todo and query_lower in str(todo[field]).lower():
                        filtered_todos.append(_convert_api_todo_to_mcp_format(todo))
                        break  # Don't add the same todo multiple times
            
            return create_response(True, {"items": filtered_todos})
            
    except Exception as e:
        logger.error(f"Failed to search todos via API: {str(e)}")
        return create_response(False, message=f"API error: {str(e)}")

async def list_project_todos(project: str, limit: int = 5, ctx: Optional[Context] = None) -> str:
    """
    List recent active todos for a specific project.
    """
    return await query_todos(
        filter={"project": project.lower(), "status": "pending"},
        limit=limit,
        ctx=ctx
    )

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive", ctx: Optional[Context] = None) -> str:
    """
    List all valid projects from the API.
    """
    try:
        auth_token, api_key = _get_auth_from_context(ctx)
        
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            api_response = await client.get_projects()
            
            if not api_response.success:
                # Fallback to hardcoded projects if API fails
                logger.warning(f"API projects fetch failed, using fallback: {api_response.error}")
                return create_response(True, {"projects": FALLBACK_VALID_PROJECTS})
            
            # Extract projects from API response
            api_data = api_response.data
            if isinstance(api_data, dict) and 'projects' in api_data:
                projects_list = api_data['projects']
                # Extract just the project names for compatibility
                project_names = [proj.get('id', proj.get('name', '')) for proj in projects_list]
                return create_response(True, {"projects": project_names})
            else:
                return create_response(True, {"projects": FALLBACK_VALID_PROJECTS})
            
    except Exception as e:
        logger.error(f"Failed to get projects via API: {str(e)}")
        # Fallback to hardcoded projects
        return create_response(True, {"projects": FALLBACK_VALID_PROJECTS})

# Placeholder functions for non-todo operations that aren't yet available via API
# These maintain backward compatibility while we transition

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None, ctx: Optional[Context] = None) -> str:
    """Add a new lesson to the knowledge base - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def get_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """Get a specific lesson by its ID - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def update_lesson(lesson_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """Update an existing lesson - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def delete_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """Delete a lesson by its ID - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """Search lessons with text search capabilities - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def grep_lessons(pattern: str, limit: int = 20, ctx: Optional[Context] = None) -> str:
    """Search lessons with grep-style pattern matching - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def list_lessons(limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """List all lessons, sorted by creation date - API not yet available"""
    return create_response(False, message="Lesson management not yet available via API. Use local mode.")

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, ctx: Optional[Context] = None) -> str:
    """Query todo logs - API not yet available"""
    return create_response(False, message="Todo logs not yet available via API. Use local mode.")

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Optional[Context] = None) -> str:
    """Add explanation - API not yet available"""
    return create_response(False, message="Explanations not yet available via API. Use local mode.")

async def explain_tool(topic: str, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """Explain tool - API not yet available"""
    return create_response(False, message="Explanations not yet available via API. Use local mode.")

async def point_out_obvious(observation: str, sarcasm_level: int = 5, ctx: Optional[Context] = None) -> str:
    """Point out obvious - API not yet available"""
    return create_response(False, message="This tool is not yet available via API. Use local mode.")

async def bring_your_own(tool_name: str, code: str, runtime: str = "python", 
                         timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                         persist: bool = False, ctx: Optional[Context] = None) -> str:
    """Bring your own tool - API not yet available"""
    return create_response(False, message="Custom tools not yet available via API. Use local mode.")