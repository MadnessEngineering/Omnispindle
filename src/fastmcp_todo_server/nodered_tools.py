import os
import json
import logging
import subprocess
import ssl
import aiohttp
from fastmcp import FastMCP, Context

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def deploy_nodered_flow(flow_json_name: str, ctx: Context = None) -> str:
    """
    Deploys a Node-RED flow to a Node-RED instance.
    
    Args:
        flow_json_name: The name of the flow JSON file in the dashboard directory
        
    Returns:
        Result of the deployment operation
    """
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
