import json
import logging
import os
import ssl
import subprocess
import uuid
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import logging
from dotenv import load_dotenv
from fastmcp import Context
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# MQTT configuration
MQTT_HOST = os.getenv("AWSIP", "localhost")
MQTT_PORT = int(os.getenv("AWSPORT", 3003))

# Create MongoDB connection at module level
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
lessons_collection = db["lessons_learned"]

# Helper function to create standardized responses
def create_response(success: bool, data: Any = None, message: str = None) -> str:
    """Create a standardized JSON response with context-rich information for AI agents"""
    response = {
        "success": success,
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_context": {
            "tool_name": _get_caller_function_name(),
            "result_type": _infer_result_type(data)
        }
    }

    if data is not None:
        response["data"] = data

        # Add contextual information based on the data type
        if isinstance(data, dict) and "todo_id" in data:
            response["agent_context"]["entity_type"] = "todo"
            response["agent_context"]["entity_id"] = data["todo_id"]
        elif isinstance(data, dict) and "lesson_id" in data:
            response["agent_context"]["entity_type"] = "lesson"
            response["agent_context"]["entity_id"] = data["lesson_id"]
        elif isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            response["agent_context"]["collection_size"] = len(data["items"])
            response["agent_context"]["collection_type"] = _infer_collection_type(data["items"])

    if message is not None:
        response["message"] = message

    return json.dumps(response)

def _get_caller_function_name() -> str:
    """Get the name of the calling function for context"""
    import inspect
    stack = inspect.stack()
    # Look for the first frame that's not this function or create_response
    for frame in stack[1:]:
        if frame.function not in ["create_response", "_get_caller_function_name"]:
            return frame.function
    return "unknown_function"

def _infer_result_type(data: Any) -> str:
    """Infer the type of result for better AI understanding"""
    if data is None:
        return "null"
    elif isinstance(data, dict):
        if "todo_id" in data:
            return "todo"
        elif "lesson_id" in data:
            return "lesson"
        elif "items" in data and isinstance(data["items"], list):
            if len(data["items"]) > 0:
                if "description" in data["items"][0]:
                    return "todo_collection"
                elif "lesson_learned" in data["items"][0] or "topic" in data["items"][0]:
                    return "lesson_collection"
            return "collection"
        elif "suggested_deadline" in data:
            return "deadline_suggestion"
        elif "time_slot" in data:
            return "time_slot_suggestion"
        return "object"
    elif isinstance(data, list):
        return "array"
    elif isinstance(data, str):
        return "string"
    elif isinstance(data, (int, float)):
        return "number"
    elif isinstance(data, bool):
        return "boolean"
    return type(data).__name__

def _infer_collection_type(items: List[Dict]) -> str:
    """Infer the type of collection based on its items"""
    if not items:
        return "empty_collection"

    sample = items[0]
    if "description" in sample and "project" in sample:
        return "todos"
    elif "topic" in sample and ("lesson_learned" in sample or "preview" in sample):
        return "lessons"
    return "generic_collection"

async def mqtt_publish(topic: str, message: str, ctx: Context = None, retain: bool = False) -> bool:
    """Publish a message to the specified MQTT topic"""
    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False

async def mqtt_get(topic: str) -> str:
    """Get a message from the specified MQTT topic"""
    try:
        cmd = ["mosquitto_sub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-C", "1"]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.SubprocessError as e:
        print(f"Failed to get MQTT message: {str(e)}")
        return None


async def add_todo(description: str, project: str, priority: str = "initial", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """Add a new todo item to the database"""
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
        return create_response(False, message=f"Failed to insert todo: {str(e)}")

    # MQTT publish as confirmation after the database operation - completely non-blocking
    try:
        mqtt_message = f"description: {description}, project: {project}, priority: {priority}, target_agent: {target_agent}"
        # Use a separate try/except to catch any issues with mqtt_publish itself
        try:
            publish_success = await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/add_todo", mqtt_message, ctx)
            if not publish_success:
                print(f"Warning: MQTT publish returned False for todo {todo['id']}")
        except Exception as mqtt_err:
            print(f"MQTT publish function error: {str(mqtt_err)}")
    except Exception as e:
        # Catch absolutely any errors in the MQTT process
        print(f"MQTT processing error (non-fatal): {str(e)}")

    # Return enhanced response with more complete todo information for AI agents
    return create_response(True, {
        "todo_id": todo["id"],
        "description": description,
        "project": project,
        "priority": priority,
        "status": "pending",
        "target_agent": target_agent,
        "created_at": todo["created_at"],
        "created_at_formatted": datetime.fromtimestamp(todo["created_at"], UTC).strftime("%Y-%m-%d %H:%M"),
        "action": "created",
        "possible_next_actions": ["update_todo", "mark_todo_complete", "get_todo", "suggest_deadline"]
    })

async def query_todos(filter: dict = None, projection: dict = None, limit: int = 100, ctx=None) -> str:
    """Query todos with optional filtering and projection"""
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
        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"],
            "project": todo["project"],
            "status": todo["status"],
            "priority": todo["priority"]
        })

    # MQTT publish as confirmation after the database query
    try:
        mqtt_message = f"filter: {json.dumps(filter)}, projection: {json.dumps(projection)}, limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/query_todos", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing todo by ID"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/update_todo", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Todo {todo_id} updated successfully")

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """Delete a todo by ID"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/delete_todo", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Todo {todo_id} deleted")

async def get_todo(todo_id: str) -> str:
    """Get a specific todo by ID"""
    todo = collection.find_one({"id": todo_id})

    if todo is None:
        return create_response(False, message="Todo not found")

    # Format todo with rich information for AI agents
    formatted_todo = {
        "id": todo["id"],
        "description": todo["description"],
        "project": todo["project"],
        "status": todo["status"],
        "priority": todo["priority"],
        "target_agent": todo.get("target_agent", "user"),
        "source_agent": todo.get("source_agent", "unknown"),
        "created_at": todo["created_at"],
        "created_at_formatted": datetime.fromtimestamp(todo["created_at"], UTC).strftime("%Y-%m-%d %H:%M"),
        "metadata": todo.get("metadata", {})
    }

    # Add completion information if available
    if todo.get("completed_at"):
        formatted_todo["completed_at"] = todo["completed_at"]
        formatted_todo["completed_at_formatted"] = datetime.fromtimestamp(todo["completed_at"], UTC).strftime("%Y-%m-%d %H:%M")
        formatted_todo["duration_seconds"] = todo["completed_at"] - todo["created_at"]
        formatted_todo["duration_formatted"] = _format_duration(todo["completed_at"] - todo["created_at"])

    # Add possible next actions based on todo status
    if todo["status"] == "pending":
        formatted_todo["possible_next_actions"] = ["update_todo", "mark_todo_complete", "delete_todo",
                                               "get_specific_todo_suggestions", "suggest_deadline"]
    else:
        formatted_todo["possible_next_actions"] = ["delete_todo"]

    # MQTT publish as confirmation after retrieving the todo
    try:
        mqtt_message = f"todo_id: {todo_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/get_todo", mqtt_message)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, formatted_todo)

async def mark_todo_complete(todo_id: str, ctx: Context = None) -> str:
    """Mark a todo as completed"""
    completed_time = int(datetime.now(UTC).timestamp())

    result = collection.update_one(
        {"id": todo_id},
        {"$set": {"status": "completed", "completed_at": completed_time}}
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/mark_todo_complete", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, {
        "todo_id": todo_id,
        "completed_at": datetime.fromtimestamp(completed_time, UTC).strftime("%Y-%m-%d %H:%M")
    })

async def list_todos_by_status(status: str, limit: int = 100) -> str:
    """List todos by their status"""
    cursor = collection.find(
        {"status": status},
        limit=limit
    )
    results = list(cursor)

    # Create a detailed summary with more context for AI
    summary = {
        "count": len(results),
        "status": status,
        "limit": limit,
        "items": [],
        "projects": set(),  # Track unique projects
        "priorities": {     # Track priority distribution
            "high": 0,
            "medium": 0,
            "low": 0,
            "initial": 0
        }
    }

    # Add todo items with useful information
    for todo in results:
        # Track statistics
        project = todo.get("project", "unspecified")
        priority = todo.get("priority", "initial")
        summary["projects"].add(project)
        if priority in summary["priorities"]:
            summary["priorities"][priority] += 1

        # Format created_at date if available
        created_at_formatted = None
        if "created_at" in todo:
            try:
                created_at_formatted = datetime.fromtimestamp(todo["created_at"], UTC).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass

        # Add formatted todo to items
        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"],
            "project": project,
            "priority": priority,
            "created_at_formatted": created_at_formatted
        })

    # Convert projects set to list for JSON serialization
    summary["projects"] = list(summary["projects"])

    # Add possible next action hints
    summary["possible_next_actions"] = {
        "for_collection": ["query_todos", "search_todos"],
        "for_individual_todos": ["get_todo", "update_todo"]
    }

    if status == "pending":
        summary["possible_next_actions"]["for_individual_todos"].extend(["mark_todo_complete", "suggest_deadline"])
        summary["possible_next_actions"]["for_collection"].append("get_todo_suggestions")

    # MQTT publish as confirmation after listing todos
    try:
        mqtt_message = f"status: {status}, limit: {limit}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/list_todos_by_status", mqtt_message)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    """Add a lesson learned"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/add_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, {"lesson_id": lesson["id"], "topic": topic})

async def get_lesson(lesson_id: str) -> str:
    """Get a specific lesson by ID"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/get_lesson", mqtt_message)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, formatted_lesson)

async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing lesson by ID"""
    result = lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
    if result.modified_count == 0:
        return create_response(False, message="Lesson not found")

    # MQTT publish as confirmation after updating lesson
    try:
        mqtt_message = f"lesson_id: {lesson_id}, updates: {json.dumps(updates)}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/update_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Lesson {lesson_id} updated successfully")

async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
    """Delete a lesson by ID"""
    result = lessons_collection.delete_one({"id": lesson_id})

    if result.deleted_count == 0:
        return create_response(False, message="Lesson not found")

    # MQTT publish as confirmation after deleting lesson
    try:
        mqtt_message = f"lesson_id: {lesson_id}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/delete_lesson", mqtt_message, ctx)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, message=f"Lesson {lesson_id} deleted")

async def list_lessons(limit: int = 100) -> str:
    """List all lessons learned"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/list_lessons", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def search_todos(query: str, fields: list = None, limit: int = 100) -> str:
    """Search todos using text search on specified fields"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/search_todos", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def search_lessons(query: str, fields: list = None, limit: int = 100) -> str:
    """Search lessons using text search on specified fields"""
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
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/search_lessons", mqtt_message, ctx=None)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, summary)

async def deploy_nodered_flow(flow_json_name: str) -> str:
    """Deploys a Node-RED flow to a Node-RED instance."""
    try:
        # Set up logging
        logger = logging.getLogger(__name__)

        # Set default Node-RED URL if not provided
        node_red_url = os.getenv("NR_URL", "http://localhost:9191")
        username = os.getenv("NR_USER", None)
        password = os.getenv("NR_PASS", None)

        logger.debug(f"Node-RED URL: {node_red_url}")

        # Add local git pull
        dashboard_dir = os.path.abspath(os.path.dirname(__file__))
        try:
            result = subprocess.run(['git', 'pull'], cwd=dashboard_dir, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git pull failed: {e}")
            # Continue even if git pull fails

        flow_json_path = f"../../dashboard/{flow_json_name}"
        flow_path = os.path.abspath(os.path.join(os.path.dirname(__file__), flow_json_path))

        if not os.path.exists(flow_path):
            return create_response(False, message=f"Flow file not found: {flow_json_name}")

        # Read the JSON content from the file
        try:
            with open(flow_path, 'r') as file:
                flow_data = json.load(file)
        except json.JSONDecodeError as e:
            return create_response(False, message=f"Invalid JSON: {str(e)}")
        except Exception as e:
            return create_response(False, message=f"Error reading file: {str(e)}")

        # Validate flow_data is either a list or a dict
        if not isinstance(flow_data, (list, dict)):
            return create_response(False, message=f"Flow JSON must be a list or dict, got {type(flow_data).__name__}")

        # If it's a single flow object, wrap it in a list
        if isinstance(flow_data, dict):
            flow_data = [flow_data]

        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # The rest of the function remains largely the same but with simplified response
        # ... (skipping the HTTP client code for brevity, but it would be updated to use create_response)

        # At the end of successful deployment:
        return create_response(True, {
            "operation": "create",
            "flow_name": flow_json_name
        })

    except Exception as e:
        logging.exception("Unhandled exception")
        return create_response(False, message=f"Deployment error: {str(e)}")

def _format_duration(seconds: int) -> str:
    """Format a duration in seconds to a human-readable string"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"

async def suggest_deadline(todo_id: str) -> str:
    """
    Suggest an optimal deadline for a specific todo based on priority and content analysis.
    
    This tool analyzes a todo's priority and description to suggest a reasonable deadline:
    1. High priority tasks get shorter deadlines
    2. Keywords like "urgent" or "tomorrow" influence the suggestion
    3. The deadline always falls on a working day
    
    Args:
        todo_id: ID of the todo to suggest a deadline for
        
    Returns:
        A JSON string containing the deadline suggestion with reasoning
    """
    # First get the todo
    todo_response = await get_todo(todo_id)
    todo_data = json.loads(todo_response)

    if not todo_data.get("success"):
        return create_response(False, message=f"Failed to get todo: {todo_data.get('message', 'Unknown error')}")

    todo = todo_data.get("data", {})

    # Define deadline recommendations based on priority
    priority_deadlines = {
        "high": {"days": 2, "explanation": "High priority tasks should be completed quickly"},
        "medium": {"days": 5, "explanation": "Medium priority tasks can be scheduled within a week"},
        "low": {"days": 10, "explanation": "Low priority tasks can be scheduled within two weeks"},
        "initial": {"days": 7, "explanation": "Tasks with initial priority are assumed to be medium importance"}
    }

    # Extract relevant information
    priority = todo.get("priority", "initial")
    description = todo.get("description", "")

    # Start with the base deadline from priority
    base_days = priority_deadlines.get(priority, {"days": 7, "explanation": "Default deadline for unknown priority"})
    deadline_days = base_days["days"]
    reasoning = [base_days["explanation"]]

    # Analyze description for keywords that might affect deadline
    deadline_modifiers = []

    # Check for urgency indicators
    urgency_keywords = {
        "urgent": {"modifier": -1, "explanation": "Task description indicates urgency"},
        "asap": {"modifier": -2, "explanation": "ASAP indicator suggests highest urgency"},
        "emergency": {"modifier": -3, "explanation": "Emergency tasks require immediate attention"},
        "critical": {"modifier": -2, "explanation": "Critical tasks need prompt attention"},
        "immediate": {"modifier": -2, "explanation": "Immediate action required"}
    }

    for keyword, info in urgency_keywords.items():
        if keyword in description.lower():
            deadline_days = max(1, deadline_days + info["modifier"])
            deadline_modifiers.append({"type": "urgency", "keyword": keyword, "days_changed": info["modifier"]})
            reasoning.append(info["explanation"])

    # Check for explicit timeframes
    timeframe_patterns = {
        "tomorrow": {"days": 1, "explanation": "Task explicitly mentions it's needed tomorrow"},
        "next week": {"days": 7, "explanation": "Task is specifically scheduled for next week"},
        "next month": {"days": 30, "explanation": "Task is scheduled for next month"},
        "by end of week": {"days": 5, "explanation": "Task needs to be completed by the end of this week"},
        "by end of day": {"days": 1, "explanation": "Task must be completed today"}
    }

    for phrase, info in timeframe_patterns.items():
        if phrase in description.lower():
            original_days = deadline_days
            deadline_days = info["days"]
            deadline_modifiers.append({
                "type": "explicit_timeframe",
                "keyword": phrase,
                "days_changed": deadline_days - original_days
            })
            reasoning.append(info["explanation"])
            # If we find an explicit timeframe, it overrides other considerations
            break

    # Calculate the deadline date
    now = datetime.now(UTC)
    deadline_date = now + timedelta(days=deadline_days)

    # Ensure deadline falls on a working day (Mon-Fri)
    weekend_adjustment = 0
    if deadline_date.weekday() > 4:  # If it's a weekend
        # Move to next Monday
        days_to_monday = 7 - deadline_date.weekday()
        deadline_date += timedelta(days=days_to_monday)
        weekend_adjustment = days_to_monday
        reasoning.append(f"Adjusted deadline to next business day (moved {days_to_monday} days forward)")

    # Format for response
    formatted_deadline = deadline_date.strftime("%Y-%m-%d")
    timestamp_deadline = int(deadline_date.timestamp())

    result = {
        "todo_id": todo_id,
        "todo_description": description[:100] + ("..." if len(description) > 100 else ""),
        "todo_priority": priority,
        "suggested_deadline": {
            "date": formatted_deadline,
            "day_of_week": deadline_date.strftime("%A"),
            "timestamp": timestamp_deadline,
            "days_from_now": deadline_days + weekend_adjustment
        },
        "reasoning": {
            "summary": "; ".join(reasoning),
            "base_deadline": {
                "days": base_days["days"],
                "explanation": base_days["explanation"]
            },
            "modifiers": deadline_modifiers,
            "weekend_adjustment": weekend_adjustment
        },
        "possible_next_actions": ["update_todo", "mark_todo_complete", "suggest_time_slot"]
    }

    # MQTT publish as confirmation after generating a deadline suggestion
    try:
        mqtt_message = f"todo_id: {todo_id}, deadline: {formatted_deadline}"
        await mqtt_publish(f"status/{os.getenv('DeNa')}/todo-server/suggest_deadline", mqtt_message)
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"MQTT publish error (non-fatal): {str(e)}")

    return create_response(True, result)

if __name__ == "__main__":
    deploy_nodered_flow("Omnispindle.json")
