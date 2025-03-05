from fastmcp import Context
from pymongo import MongoClient
from datetime import datetime, UTC
import uuid
import os
from dotenv import load_dotenv
import json
# import logging
import asyncio
from aiohttp import web
import paho.mqtt.client as mqtt
import subprocess
import ssl
import aiohttp
import logging

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# MQTT configuration
MQTT_HOST = "3.134.3.199"
MQTT_PORT = 3003
MQTT_KEEPALIVE = 60

# Create MongoDB connection at module level
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
lessons_collection = db["lessons_learned"]

async def add_todo(description: str, priority: str = "initial", target_agent: str = "user", ctx: Context = None) -> dict:
    """Add a new todo item to the database"""
    todo = {
        "id": str(uuid.uuid4()),
        "description": description,
        "priority": priority,
        "source_agent": "mcp-server",
        "target_agent": target_agent,
        "status": "pending",
        "created_at": int(datetime.now(UTC).timestamp()),
        "completed_at": None
    }

    collection.insert_one(todo)
    return {"status": "success", "todo_id": todo["id"]}

async def query_todos(filter: dict = None, projection: dict = None, limit: int = 100) -> dict:
    """Query todos with optional filtering and projection"""
    cursor = collection.find(
        filter or {},
        projection=projection,
        limit=limit
    )
    results = list(cursor)

    return {
        "status": "success",
        "todos": results
    }

async def update_todo(todo_id: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing todo by ID"""
    result = collection.update_one({"id": todo_id}, {"$set": updates})
    if result.modified_count == 0:
        return json.dumps({"status": "error", "message": "Todo not found"})

    if ctx is not None:
        try:
            ctx.info(f"Updated todo {todo_id}")
        except ValueError:
            pass

    return json.dumps({"status": "success"})

async def mqtt_publish(topic: str, message: str, ctx: Context = None) -> str:
    """Publish a message to the specified MQTT topic"""
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)

    result = mqtt_client.publish(topic, message)
    result.wait_for_publish()

    mqtt_client.disconnect()

    if result.is_published():
        if ctx is not None:
            try:
                ctx.info(f"Published message to topic {topic}")
            except ValueError:
                pass

        return json.dumps({"status": "success"})
    else:
        return json.dumps({"status": "error", "message": "Message not published"})

async def delete_todo(todo_id: str, ctx: Context = None) -> str:
    """Delete a todo by ID"""
    result = collection.delete_one({"id": todo_id})
    if result.deleted_count == 0:
        return json.dumps({"status": "error", "message": "Todo not found"})

    if ctx is not None:
        try:
            ctx.info(f"Deleted todo {todo_id}")
        except ValueError:
            pass

    return json.dumps({"status": "success"})

async def get_todo(todo_id: str) -> str:
    """Get a specific todo by ID"""
    todo = collection.find_one({"id": todo_id})
    if todo is None:
        return json.dumps({"status": "error", "message": "Todo not found"})

    return json.dumps({"status": "success", "todo": todo}, default=str)

async def mark_todo_complete(todo_id: str, ctx: Context = None) -> str:
    """Mark a todo as completed"""
    result = collection.update_one(
        {"id": todo_id},
        {"$set": {"status": "completed", "completed_at": int(datetime.now(UTC).timestamp())}}
    )
    if result.modified_count == 0:
        return json.dumps({"status": "error", "message": "Todo not found"})

    if ctx is not None:
        try:
            ctx.info(f"Marked todo {todo_id} as completed")
        except ValueError:
            pass

    return json.dumps({"status": "success"})

async def list_todos_by_status(status: str, limit: int = 100) -> str:
    """List todos by their status"""
    cursor = collection.find(
        {"status": status},
        limit=limit
    )
    results = list(cursor)

    return json.dumps({
        "status": "success",
        "todos": results
    }, default=str)

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

    # Insert into MongoDB
    lessons_collection.insert_one(lesson)
    return json.dumps({"status": "success", "lesson_id": lesson["id"]})

async def get_lesson(lesson_id: str) -> str:
    """Get a specific lesson by ID"""
    lesson = lessons_collection.find_one({"id": lesson_id})
    if lesson is None:
        return json.dumps({"status": "error", "message": "Lesson not found"})

    return json.dumps({"status": "success", "lesson": lesson}, default=str)

async def update_lesson(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    """Update an existing lesson by ID"""
    result = lessons_collection.update_one({"id": lesson_id}, {"$set": updates})
    if result.modified_count == 0:
        return json.dumps({"status": "error", "message": "Lesson not found"})

    return json.dumps({"status": "success"})

async def delete_lesson(lesson_id: str, ctx: Context = None) -> str:
    """Delete a lesson by ID"""
    result = lessons_collection.delete_one({"id": lesson_id})
    if result.deleted_count == 0:
        return json.dumps({"status": "error", "message": "Lesson not found"})

    return json.dumps({"status": "success"})

async def list_lessons(limit: int = 100) -> str:
    """List all lessons learned"""
    cursor = lessons_collection.find(limit=limit)
    results = list(cursor)

    return json.dumps({
        "status": "success",
        "lessons": results
    }, default=str)

async def search_todos(query: str, fields: list = None, limit: int = 100) -> str:
    """Search todos using text search on specified fields
    
    Args:
        query: The text to search for
        fields: List of fields to search in (defaults to ['description'])
        limit: Maximum number of results to return
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

    return json.dumps({
        "status": "success",
        "count": len(results),
        "query": query,
        "todos": results
    }, default=str)

async def search_lessons(query: str, fields: list = None, limit: int = 100) -> str:
    """Search lessons using text search on specified fields
    
    Args:
        query: The text to search for
        fields: List of fields to search in (defaults to ['topic', 'lesson_learned'])
        limit: Maximum number of results to return
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

    return json.dumps({
        "status": "success",
        "count": len(results),
        "query": query,
        "lessons": results
    }, default=str)

async def deploy_nodered_flow(flow_json_name: str, ctx: Context = None) -> str:
    """
    Deploys a Node-RED flow to a Node-RED instance.
    
    Args:
        flow_json_name: The name of the flow JSON file in the dashboard directory
        
    Returns:
        Result of the deployment operation
    """
    # Set up logging
    logger = logging.getLogger(__name__)

    # Set default Node-RED URL if not provided
    node_red_url = os.getenv("NR_URL", "http://localhost:9191")
    username = os.getenv("NR_USER", None)
    password = os.getenv("NR_PASS", None)

    logger.debug(f"Node-RED URL: {node_red_url}")
    logger.debug(f"Username: {username}")
    logger.debug(f"Password length: {len(password) if password else 'None'}")

    # Add local git pull
    dashboard_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../dashboard"))
    result = ""
    try:
        result = subprocess.run(['git', 'pull'], cwd=dashboard_dir, check=True, capture_output=True, text=True)
        logger.debug(f"Git pull output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git pull failed: {e}")
        logger.warning(f"Git pull stderr: {e.stderr}")

    flow_json_path = f"../../dashboard/{flow_json_name}"
    flow_path = os.path.abspath(os.path.join(os.path.dirname(__file__), flow_json_path))

    if not os.path.exists(flow_path):
        return {"success": False, "error": f"Flow file not found: {flow_json_name}, {result}"}

    # Read the JSON content from the file
    try:
        with open(flow_path, 'r') as file:
            flow_data = json.load(file)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON in file {flow_json_name}: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Error reading file {flow_json_name}: {str(e)}"}

    # Validate flow_data is either a list or a dict
    if not isinstance(flow_data, (list, dict)):
        return {"success": False, "error": f"Flow JSON must be a list or dict, got {type(flow_data).__name__}"}

    # If it's a single flow object, wrap it in a list
    if isinstance(flow_data, dict):
        flow_data = [flow_data]

    # Create SSL context to handle potential SSL verification issues
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        # First, check authentication scheme
        try:
            async with session.get(f"{node_red_url}/auth/login", ssl=ssl_context) as login_response:
                logger.debug(f"Login endpoint response status: {login_response.status}")
                logger.debug(f"Login endpoint response headers: {login_response.headers}")
                try:
                    login_info = await login_response.json()
                    logger.debug(f"Login info: {login_info}")
                except Exception as e:
                    login_text = await login_response.text()
                    logger.debug(f"Login response text: {login_text}")
                    logger.debug(f"Login JSON parsing error: {e}")

            # If authentication is required, get a token
            if username and password:
                token_payload = {
                    "client_id": "node-red-admin",
                    "grant_type": "password",
                    "scope": "*",
                    "username": username,
                    "password": password
                }
                logger.debug(f"Token payload: {token_payload}")

                async with session.post(f"{node_red_url}/auth/token", data=token_payload, ssl=ssl_context) as token_response:
                    logger.debug(f"Token request status: {token_response.status}")
                    logger.debug(f"Token request headers: {token_response.headers}")

                    # Log the full response text for debugging
                    token_text = await token_response.text()
                    logger.debug(f"Token response text: {token_text}")

                    # Try to parse the response as JSON
                    try:
                        token_data = json.loads(token_text)
                        access_token = token_data.get('access_token')

                        # Use the access token for subsequent requests
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {access_token}"
                        }
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse token response: {token_text}")
                        return {"success": False, "error": f"Failed to parse token response: {token_text}"}

            # If authentication is not required, proceed without token
            else:
                headers = {
                    "Content-Type": "application/json"
                }

            # Get existing flows
            async with session.get(f"{node_red_url}/flows", headers=headers, ssl=ssl_context) as response:
                logger.debug(f"Flows check response status: {response.status}")

                if response.status == 200:
                    existing_flows = await response.json()
                else:
                    return {"success": False, "error": f"Cannot access flows. HTTP {response.status}"}

                # Determine flow ID and operation
                flow_id = None
                flow_label = None
                for node in flow_data:
                    if node.get("type") == "tab":
                        flow_id = node.get("id")
                        flow_label = node.get("label")
                        break

                # Check if flow exists
                flow_exists = any(f.get("id") == flow_id and f.get("type") == "tab" for f in existing_flows)

                # Determine operation and endpoint
                if flow_exists:
                    operation = "update"
                    endpoint = f"{node_red_url}/flow/{flow_id}"
                    method = session.put
                else:
                    operation = "create"
                    endpoint = f"{node_red_url}/flows"
                    method = session.post

                # Deploy the flow
                async with method(endpoint, headers=headers, json=flow_data, ssl=ssl_context) as deploy_response:
                    logger.debug(f"Deploy response status: {deploy_response.status}")
                    result = await deploy_response.text()
                    logger.debug(f"Deploy response body: {result}")

                    if deploy_response.status not in (200, 201, 204):
                        return {"success": False, "error": f"HTTP {deploy_response.status}: {result}", "operation": operation}

                    return {
                        "success": True,
                        "operation": operation,
                        "flow_id": flow_id,
                        "flow_label": flow_label,
                        "dashboard_url": f"{node_red_url}/ui"
                    }

        except Exception as e:
            logger.exception("Deployment error")
            return {"success": False, "error": str(e)}
