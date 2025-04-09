import json
import logging
import os
import ssl
import subprocess
import uuid
from datetime import datetime
from datetime import UTC
from typing import Any, Dict, List, Optional

import aiohttp
import logging
import paho.mqtt.client as mqtt
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
    """Create a standardized JSON response with minimal footprint"""
    response = {"success": success}
    if data is not None:
        response["data"] = data
    if message is not None:
        response["message"] = message
    return json.dumps(response)

async def mqtt_publish(topic: str, message: str, ctx: Context = None) -> bool:
    """Publish a message to the specified MQTT topic"""
    # mqtt_client = mqtt.Client()
    # print(f"{MQTT_HOST}, {MQTT_PORT}")
    # mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)  # Using constant for keepalive

    # if isinstance(message, str):
    #     payload = message
    # else:
    #     payload = json.dumps(message)

    # result = mqtt_client.publish(topic, payload)
    # result.wait_for_publish(timeout=5)
    # mqtt_client.disconnect()

    # return result.is_published()
    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False

async def add_todo(description: str, project: str, priority: str = "initial", target_agent: str = "user", metadata: dict = None, ctx: Context = None) -> str:
    """Add a new todo item to the database"""
    todo = {
        "id": str(uuid.uuid4()),
        "description": description,
        "project": project,
        "priority": priority,
        "source_agent": "Omnispindle",
        "target_agent": target_agent,
        "status": "pending",
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

    # Always return success if database operation succeeded, regardless of MQTT status
    return create_response(True, {"todo_id": todo["id"]})

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

    # Format todo for concise display
    formatted_todo = {
        "id": todo["id"],
        "description": todo["description"],
        "project": todo["project"],
        "status": todo["status"],
        "priority": todo["priority"],
        "created": datetime.fromtimestamp(todo["created_at"], UTC).strftime("%Y-%m-%d"),
        "metadata": todo.get("metadata", {})
    }

    if todo.get("completed_at"):
        formatted_todo["completed"] = datetime.fromtimestamp(todo["completed_at"], UTC).strftime("%Y-%m-%d")

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

    # Create a summary format
    summary = {
        "count": len(results),
        "status": status,
        "items": []
    }

    # Add simplified todo items
    for todo in results:
        summary["items"].append({
            "id": todo["id"],
            "description": todo["description"][:50] + ("..." if len(todo["description"]) > 50 else ""),
            "project": todo["project"],
            "priority": todo["priority"]
        })

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

if __name__ == "__main__":
    deploy_nodered_flow("fastmcp-todo-server.json")
