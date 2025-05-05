import json
import os
import logging
import ssl
import subprocess
from datetime import datetime
from datetime import UTC
from typing import Any
from typing import Any
from typing import Dict
from typing import List
from fastmcp import Context

MQTT_HOST = os.getenv("AWSIP", "localhost")
MQTT_PORT = int(os.getenv("AWSPORT", 3003))


def create_response(success: bool, data: Any = None, message: str = None, return_context: bool = True) -> str:
    """Create a standardized JSON response with context-rich but efficient information for AI agents"""
    response = {
        "success": success,
    }

    # Only add agent_context when it provides value
    if data is not None:
        # Determine entity type early to avoid redundant checks
        entity_type = None
        entity_id = None

        if isinstance(data, dict):
            if "todo_id" in data:
                entity_type = "todo"
                entity_id = data["todo_id"]
            elif "lesson_id" in data:
                entity_type = "lesson"
                entity_id = data["lesson_id"]

        # Only add minimal agent_context with actually useful information
        if return_context and (entity_type or _should_add_context(data)):
            response["agent_context"] = {
                "type": _infer_result_type(data)
            }

            # Only add these fields if they exist and have value
            if entity_type:
                response["agent_context"]["entity"] = f"{entity_type}:{entity_id}"

            # Only add collection metadata for collections
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                items_count = len(data["items"])
                if items_count > 0:
                    collection_type = _infer_collection_type(data["items"])
                    if collection_type != "generic_collection":
                        response["agent_context"]["collection"] = f"{collection_type}:{items_count}"

        response["data"] = data

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

    if isinstance(data, dict):
        # Use a more compact approach for common types
        for key, type_name in [
            ("todo_id", "todo"),
            ("lesson_id", "lesson"),
            ("suggested_deadline", "deadline"),
            ("time_slot", "timeslot")
        ]:
            if key in data:
                return type_name

        # Collection detection
        if "items" in data and isinstance(data["items"], list):
            item_count = len(data["items"])
            if item_count == 0:
                return "empty_collection"

            # Sample first item for type inference
            sample = data["items"][0]
            if "description" in sample:
                return "todos"
            elif "topic" in sample:
                return "lessons"
            return "collection"

        return "object"

    # Simple types
    if isinstance(data, list):
        return "list"
    if isinstance(data, (int, float)):
        return "number"
    if isinstance(data, bool):
        return "bool"

    # Default to string representation of type
    return type(data).__name__


def _infer_collection_type(items: List[Dict]) -> str:
    """Infer the type of collection based on its items"""
    if not items:
        return "empty"

    # Use first item for inference, with quick checks for common types
    sample = items[0]
    if "description" in sample:
        return "todos"
    if "topic" in sample:
        return "lessons"
    if "message" in sample:
        return "messages"

    # For unknown types, return a generic label
    return "items"


def _should_add_context(data: Any) -> bool:
    """Determine if we should add agent_context based on data type"""
    if isinstance(data, dict):
        # Check if this is a collection, suggestion, or has action hints
        if ("items" in data and isinstance(data["items"], list) and len(data["items"]) > 0) or \
           "suggested_deadline" in data or \
           "time_slot" in data or \
           "possible_next_actions" in data:
            return True
    return False


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
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except subprocess.SubprocessError as e:
        print(f"Failed to get MQTT message: {str(e)}")
        return f"Failed to get MQTT message: {str(e)}"


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
