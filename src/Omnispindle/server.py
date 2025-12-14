import logging
import os
import signal
import sys
import asyncio
import shutil
import subprocess
import anyio
import traceback
import threading
import warnings
import functools

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# logging.getLogger('pymongo').setLevel(logging.WARNING)
# logging.getLogger('asyncio').setLevel(logging.WARNING)
# logging.getLogger('uvicorn.access').addFilter(NotTypeErrorFilter())

# Filter out specific RuntimeWarnings about unawaited coroutines - moved after logging setup
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*send_log_message.*was never awaited.*")

# Detect if this module has already been initialized
if globals().get('_MODULE_INITIALIZED', False):
    logger.warning("WARNING: Omnispindle/server.py is being loaded AGAIN!")
    _REINITIALIZATION_COUNT = globals().get('_REINITIALIZATION_COUNT', 0) + 1
    logger.warning(f"Reinitialization count: {_REINITIALIZATION_COUNT}")
    logger.warning(f"Stack trace:\n{''.join(traceback.format_stack())}")
    globals()['_REINITIALIZATION_COUNT'] = _REINITIALIZATION_COUNT
else:
    logger.info("First time initializing Omnispindle/server.py module")
    _MODULE_INITIALIZED = True
    _REINITIALIZATION_COUNT = 0
    globals()['_MODULE_INITIALIZED'] = True
    globals()['_REINITIALIZATION_COUNT'] = 0

from typing import Callable, Dict, Any, Optional
import uvicorn
from uvicorn.config import LOGGING_CONFIG
import json
from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send
from .middleware import (
    ConnectionErrorsMiddleware,
    SuppressNoResponseReturnedMiddleware,
    NoneTypeResponseMiddleware,
    create_asgi_error_handler
)
# from .auth import get_current_user, get_current_user_from_query, AUTH_CONFIG  # Removed - old SSE server not used
from fastapi import Depends, Request
from .todo_log_service import start_service
from .database import db_connection
from .models.config import AuthConfig
# from .mcp_handler import mcp_handler
from .scheduler import scheduler

# Configure logger
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DEVICE_NAME = os.getenv("DeNa", os.uname().nodename)

# For debugging double initialization
_init_counter = 0
_init_stack_traces = []


def publish_mqtt_status(topic, message, retain=False):
    """
    Publish MQTT message using mosquitto_pub command line tool
    Falls back to logging if mosquitto_pub is not available
    
    Args:
        topic: MQTT topic to publish to
        message: Message to publish (will be converted to string)
        retain: Whether to set the retain flag
    """
    if not shutil.which("mosquitto_pub") is not None:
        print(f"MQTT publishing not available - would publish {message} to {topic} (retain={retain})")
        return False

    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False


class Omnispindle:
    def __init__(self, name: str = "todo-server", server_type: str = "mcp"):
        global _init_counter, _init_stack_traces
        _init_counter += 1
        current_thread = threading.current_thread().name
        # stack = traceback.format_stack()
        # _init_stack_traces.append((current_thread, stack))

        logger.warning(f"⚠️  Omnispindle initialization #{_init_counter} in thread {current_thread}")

        logger.info(f"Initializing Omnispindle server with name='{name}', server_type='{server_type}'")
        self.name = name
        self.server_type = server_type
        logger.debug("Omnispindle instance initialization complete")

    async def run_server(self) -> FastAPI:
        """
        Creates and configures the FastAPI application.
        
        Returns:
            A FastAPI application
        """
        logger.info("Starting FastAPI server")

        try:
            topic = f"status/{DEVICE_NAME}/alive"
            logger.debug(f"Publishing online status to topic: {topic}")
            publish_mqtt_status(topic, "1")

            def signal_handler(sig, frame):
                logger.info(f"Received signal {sig}, shutting down gracefully...")
                publish_mqtt_status(topic, "0", retain=True)
                logger.info("Published offline status, exiting")
                sys.exit(0)

            # Register signal handlers
            logger.debug("Registering signal handlers for SIGINT and SIGTERM")
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Create FastAPI app
            app = FastAPI(
                title="Omnispindle",
                description="A FastAPI server for managing todos and other tasks, with AI agent integration.",
                version="0.1.0",
            )

            # Add middleware
            app.add_middleware(ConnectionErrorsMiddleware)
            app.add_middleware(NoneTypeResponseMiddleware)

            # Add the new /api/mcp endpoint
            @app.post("/api/mcp")
            async def mcp_endpoint(request: Request, token: str = Depends(get_current_user_from_query)):
                from .mcp_handler import mcp_handler
                return await mcp_handler(request, lambda: get_current_user_from_query(token))

            # SSE endpoint for MCP connections
            @app.get("/api/mcp/sse")
            async def mcp_sse_endpoint(request: Request, user: dict = Depends(get_current_user)):
                from .sse_handler import sse_handler
                from .tools import handle_tool_call, ToolCall
                import json

                async def mcp_event_generator(request: Request):
                    """Generator for MCP tool calls over SSE"""
                    try:
                        # Send initial connection event
                        yield {
                            "event": "connected",
                            "data": json.dumps({
                                "status": "connected",
                                "user": user.get("email", "unknown"),
                                "timestamp": str(asyncio.get_event_loop().time())
                            })
                        }

                        # Keep connection alive and wait for tool calls
                        # In a real implementation, this would listen for incoming tool calls
                        # For now, we'll send a heartbeat every 30 seconds
                        while True:
                            if await request.is_disconnected():
                                break

                            yield {
                                "event": "heartbeat",
                                "data": json.dumps({
                                    "status": "alive",
                                    "timestamp": str(asyncio.get_event_loop().time())
                                })
                            }

                            await asyncio.sleep(30)

                    except asyncio.CancelledError:
                        logger.info("SSE connection cancelled")
                        break
                    except Exception as e:
                        logger.error(f"Error in SSE generator: {e}")
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": str(e)})
                        }

                return sse_handler.sse_response(request, mcp_event_generator, send_timeout=60)

            # Legacy SSE endpoint (deprecated - use /api/mcp/sse instead)
            @app.get("/sse")
            async def sse_endpoint(req: Request, user: dict = Depends(get_current_user)):
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"error": "SSE endpoint deprecated", "message": "Use /api/mcp/sse endpoint instead"},
                    status_code=410  # Gone
                )

            # Root endpoint - redirect to login
            @app.get("/")
            def read_root():
                from starlette.responses import RedirectResponse
                return RedirectResponse(url="/login", status_code=302)
            
            # Auth endpoints
            @app.get("/api/auth/login")
            def login():
                """Redirect users to Auth0 login"""
                auth_url = (
                    f"https://{AUTH_CONFIG.domain}/authorize"
                    f"?client_id={AUTH_CONFIG.client_id}"
                    f"&response_type=token"
                    f"&redirect_uri=https://madnessinteractive.cc/api/auth/callback"
                    f"&audience={AUTH_CONFIG.audience}"
                    f"&scope=openid profile"
                )
                return {"login_url": auth_url, "message": "Visit login_url to authenticate"}
            
            @app.get("/api/auth/callback")
            def auth_callback():
                """Handle Auth0 callback - extract token from URL fragment"""
                return {
                    "message": "Authentication successful! Extract the access_token from the URL fragment.",
                    "instructions": "The token will be in the URL after #access_token=... Use this token for MCP requests."
                }

            # OAuth discovery endpoints
            @app.get("/api/.well-known/oauth-protected-resource")
            def oauth_protected_resource():
                """OAuth 2.0 Protected Resource metadata"""
                return {
                    "resource": f"https://madnessinteractive.cc/api/mcp",
                    "authorization_servers": [f"https://{AUTH_CONFIG.domain}"]
                }

            @app.get("/api/.well-known/oauth-authorization-server")
            def oauth_authorization_server():
                """OAuth 2.0 Authorization Server metadata"""
                return {
                    "issuer": f"https://{AUTH_CONFIG.domain}",
                    "authorization_endpoint": f"https://{AUTH_CONFIG.domain}/authorize",
                    "token_endpoint": f"https://{AUTH_CONFIG.domain}/oauth/token",
                    "jwks_uri": f"https://{AUTH_CONFIG.domain}/.well-known/jwks.json"
                }

            @app.post("/api/register")
            def client_registration():
                """Dynamic client registration endpoint"""
                return {
                    "client_id": AUTH_CONFIG.client_id,
                    "message": "Use the provided client_id for authentication"
                }

            logger.info("Server startup complete, returning ASGI application")
            return app
        except Exception as e:
            logger.exception(f"Error in server: {str(e)}")
            # Publish offline status with retain flag in case of error
            try:
                hostname = os.getenv("HOSTNAME", os.uname().nodename)
                topic = f"status/{hostname}/alive"
                logger.info(f"Publishing offline status to {topic} (retained)")
                publish_mqtt_status(topic, "0", retain=True)
                logger.debug(f"Published offline status to {topic} (retained)")
            except Exception as ex:
                logger.error(f"Failed to publish offline status: {str(ex)}")
            logger.error("Server startup failed, re-raising exception")
            raise

    # Add method to register tools
    def register_tool(self, tool_func):
        """Register a single tool with the server"""
        tool_name = getattr(tool_func, "__name__", str(tool_func))
        logger.debug(f"Attempting to register tool: {tool_name}")

        if not hasattr(self, '_registered_tools'):
            logger.debug("Initializing _registered_tools set")
            self._registered_tools = set()

        if tool_func.__name__ not in self._registered_tools:
            # Use the original FastMCP tool registration method
            logger.info(f"Registering new tool: {tool_name}")
            self.tool()(tool_func)
            self._registered_tools.add(tool_func.__name__)
            logger.info(f"Successfully registered tool: {tool_name}")
        else:
            logger.debug(f"Tool {tool_name} already registered, skipping")

        return tool_func

    def register_tools(self, tool_registry: dict):
        """
        Register multiple tools from a dictionary.

        Args:
            tool_registry (dict): A dictionary mapping tool names to tool functions.
        """
        logger.info(f"Registering {len(tool_registry)} tools from registry.")
        for name, func in tool_registry.items():
            # Create a new function with the desired name to register
            # This is necessary because the decorator uses the function's __name__
            # and we want to control the exposed name.
            tool_func = func
            tool_func.__name__ = name
            self.register_tool(tool_func)
        logger.debug("All tools from registry have been processed.")

    def _register_default_tools(self):
        """Register the built-in tools for the server"""
        # Implementation of _register_default_tools method
        pass

# Create a singleton instance at the module level.
# This is simpler and sufficient now that the app structure is being centralized.
try:
    logger.info("Creating module-level singleton for Omnispindle server.")
    server = Omnispindle()
except Exception as e:
    logger.critical(f"Failed to create Omnispindle server instance: {e}", exc_info=True)
    server = None
