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

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# logging.getLogger('pymongo').setLevel(logging.WARNING)
# logging.getLogger('asyncio').setLevel(logging.WARNING)
# logging.getLogger('uvicorn.access').addFilter(NotTypeErrorFilter())

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
from fastmcp.server import FastMCP
import uvicorn
import json
from starlette.responses import JSONResponse
from .middleware import (
    ConnectionErrorsMiddleware,
    SuppressNoResponseReturnedMiddleware,
    NoneTypeResponseMiddleware,
    create_asgi_error_handler
)

# Configure logger
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

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


class Omnispindle(FastMCP):
    def __init__(self, name: str = "todo-server", server_type: str = "sse"):
        global _init_counter, _init_stack_traces
        _init_counter += 1
        current_thread = threading.current_thread().name
        # stack = traceback.format_stack()
        # _init_stack_traces.append((current_thread, stack))

        logger.warning(f"⚠️  Omnispindle initialization #{_init_counter} in thread {current_thread}")

        logger.info(f"Initializing Omnispindle server with name='{name}', server_type='{server_type}'")
        super().__init__(name=name, server_type=server_type)
        logger.debug("Omnispindle instance initialization complete")

    async def run_server(self) -> Callable:
        """
        Run the FastMCP server and return an ASGI application.
        
        Args:
            publish_mqtt_status: Callable to publish MQTT status messages
            
        Returns:
            An ASGI application callable
        """
        logger.info("Starting FastMCP server")

        try:
            hostname = os.getenv("DeNa", os.uname().nodename)
            topic = f"status/{hostname}/todo-server/alive"
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

            # Custom exception handler to silence specific SSE-related errors
            original_excepthook = sys.excepthook

            def custom_excepthook(exctype, value, traceback):
                # Handle NoneType errors from Starlette more broadly
                if exctype is TypeError and "'NoneType' object is not callable" in str(value):
                    # Log minimally instead of full stack trace
                    logger.warning(f"Suppressed NoneType error: {str(value)}")
                    return
                # Handle AnyIO WouldBlock and asyncio CancelledError more gracefully
                if exctype is anyio.WouldBlock or exctype is asyncio.exceptions.CancelledError:
                    # These are common with SSE connections when clients disconnect
                    logger.debug(f"Suppressed expected client disconnect error: {exctype.__name__}")
                    return
                # For all other errors, use the original exception handler
                logger.debug(f"Unhandled exception passed to original excepthook: {exctype.__name__}: {value}")
                original_excepthook(exctype, value, traceback)

            # Replace the default exception handler
            logger.debug("Installing custom exception handler")
            sys.excepthook = custom_excepthook

            # Configure uvicorn to suppress specific access logs for /messages endpoint
            logger.debug("Configuring uvicorn logging")
            log_config = uvicorn.config.LOGGING_CONFIG
            if "formatters" in log_config:
                log_config["formatters"]["access"]["fmt"] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                logger.debug("Modified uvicorn access log format")

            # Configure logging instead
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            logger.debug("Configured root logger")

            # Adjust specific loggers
            # Set SSE-related loggers to less verbose levels
            # logging.getLogger('sse_starlette').setLevel(logging.INFO)
            # logging.getLogger('uvicorn.protocols.http').setLevel(logging.WARNING)
            # But keep our own SSE handler at DEBUG level
            # logging.getLogger('Omnispindle.sse_handler').setLevel(logging.DEBUG)

            # Run the server
            logger.info("Calling run_sse_async() to start the server")
            app = await self.run_sse_async()

            if app is None:
                logger.warning("run_sse_async returned None, using dummy fallback app")

                async def dummy_app(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
                    """
                    A robust fallback ASGI application that handles basic requests when the main app is unavailable.
                    
                    This dummy app provides proper error responses for all requests rather than just failing silently.
                    It logs details about incoming requests for debugging purposes.
                    """
                    logger.info(f"Dummy app received request: {scope['type']} {scope.get('path', 'unknown path')}")

                    if scope["type"] == "http":
                        # Wait for the request body
                        await receive()

                        # Create a JSON response
                        response = JSONResponse(
                            status_code=503,
                            content={
                                "error": "Service Temporarily Unavailable",
                                "message": "The FastMCP server application is currently unavailable. Please try again later.",
                                "path": scope.get("path", "unknown")
                            }
                        )

                        # Send response headers
                        logger.debug(f"Dummy app sending 503 response for {scope.get('path', 'unknown path')}")
                        await send({
                            "type": "http.response.start",
                            "status": response.status_code,
                            "headers": [
                                [b"content-type", b"application/json"],
                                [b"x-fallback-app", b"true"]
                            ]
                        })

                        # Send response body
                        await send({
                            "type": "http.response.body",
                            "body": json.dumps(response.body).encode("utf-8"),
                        })

                    elif scope["type"] == "websocket":
                        # Handle WebSocket connections
                        logger.debug(f"Dummy app closing WebSocket connection for {scope.get('path', 'unknown path')}")
                        await send({
                            "type": "websocket.close",
                            "code": 1013,  # Try again later
                        })

                    elif scope["type"] == "lifespan":
                        # Handle lifespan events (startup/shutdown)
                        logger.debug("Dummy app handling lifespan events")
                        while True:
                            message = await receive()
                            if message["type"] == "lifespan.startup":
                                logger.debug("Dummy app responding to lifespan.startup")
                                await send({"type": "lifespan.startup.complete"})
                            elif message["type"] == "lifespan.shutdown":
                                logger.debug("Dummy app responding to lifespan.shutdown")
                                await send({"type": "lifespan.shutdown.complete"})
                                break
                            else:
                                logger.warning(f"Dummy app received unknown lifespan message: {message['type']}")

                app = dummy_app
                logger.info("Fallback dummy app is now active")
            else:
                logger.info("ASGI application successfully obtained from run_sse_async()")

                # Add a delay wrapper to ensure initialization is complete before handling requests
                original_app = app

                async def initialization_delay_wrapper(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
                    """
                    Wrapper that adds a small delay to ensure server initialization is complete
                    before processing any requests.
                    """
                    if scope["type"] == "http" and scope.get("path", "") == "/sse":
                        logger.debug("Delaying SSE connection to ensure initialization is complete")
                        # Add a small delay to ensure initialization is complete
                        await asyncio.sleep(0.5)

                    # Handle the request with error catch for initialization issues
                    try:
                        await original_app(scope, receive, send)
                    except RuntimeError as e:
                        if "Received request before initialization was complete" in str(e):
                            logger.warning("Caught initialization error, returning 503 Service Unavailable")
                            # Create a JSON response
                            response = JSONResponse(
                                status_code=503,
                                content={
                                    "error": "Service Temporarily Unavailable",
                                    "message": "The server is still initializing. Please try again in a moment.",
                                    "path": scope.get("path", "unknown")
                                }
                            )
                            # Send response headers
                            await send({
                                "type": "http.response.start",
                                "status": response.status_code,
                                "headers": [
                                    [b"content-type", b"application/json"],
                                    [b"retry-after", b"2"]
                                ]
                            })
                            # Send response body
                            await send({
                                "type": "http.response.body",
                                "body": json.dumps(response.body).encode("utf-8"),
                            })
                        else:
                            # Re-raise any other runtime errors
                            raise
                    except (asyncio.exceptions.CancelledError, anyio.WouldBlock) as e:
                        # For SSE endpoints, these errors are expected when clients disconnect
                        if scope["type"] == "http" and scope.get("path", "") == "/sse":
                            logger.debug(f"Client disconnected from SSE, handling gracefully: {type(e).__name__}")
                            # Send a 204 response to properly close the connection
                            await send({
                                "type": "http.response.start",
                                "status": 204,
                                "headers": []
                            })
                            await send({
                                "type": "http.response.body",
                                "body": b"",
                                "more_body": False
                            })
                        else:
                            raise
                    except (ConnectionResetError, ConnectionAbortedError) as e:
                        # Connection was reset or aborted by the client
                        logger.debug(f"Client connection was terminated: {type(e).__name__}")
                        # No need to send a response as connection is already closed

                app = initialization_delay_wrapper
                logger.info("Added initialization delay wrapper to ASGI application")

                # Apply the middlewares to handle various errors - ORDER MATTERS!
                # First apply the NoneType middleware as it's the most common error and should be first
                app = NoneTypeResponseMiddleware(app)
                logger.info("Added NoneTypeResponseMiddleware to handle None response errors")

                # Apply the low-level ASGI error handler as a final safety net
                app = create_asgi_error_handler(app)
                logger.info("Added low-level ASGI error handler as final safety net")

                # Then apply the connection errors middleware last so it handles any remaining issues
                app = ConnectionErrorsMiddleware(app)
                logger.info("Added ConnectionErrorsMiddleware to handle disconnected requests")

            logger.info("Server startup complete, returning ASGI application")
            return app
        except Exception as e:
            logger.exception(f"Error in server: {str(e)}")
            # Publish offline status with retain flag in case of error
            try:
                hostname = os.getenv("HOSTNAME", os.uname().nodename)
                topic = f"status/{hostname}/todo-server/alive"
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

    def register_tools(self, tools_list):
        """Register multiple tools with the server"""
        logger.info(f"Registering {len(tools_list)} tools")
        for tool in tools_list:
            self.register_tool(tool)
        logger.debug("All tools registered successfully")

# Create a singleton instance
_instance = None
_instance_lock = threading.Lock()

def get_server_instance(name: str = "todo-server", server_type: str = "sse") -> Omnispindle:
    """
    Get the singleton instance of the Omnispindle server.
    This ensures we only ever have one server instance.
    """
    global _instance, _instance_lock

    # Thread-safe initialization with double-checking lock pattern
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                current_thread = threading.current_thread().name
                logger.warning(f"🔒 Creating new Omnispindle singleton instance in thread {current_thread}")
                # logger.warning(f"🔒 Call stack:\n{''.join(traceback.format_stack()[-10:])}")

                logger.info(f"Creating new Omnispindle singleton instance with name='{name}', server_type='{server_type}'")
                _instance = Omnispindle(name=name, server_type=server_type)
                logger.info("Omnispindle singleton instance created")
            else:
                logger.warning("Another thread created the instance while we were waiting for the lock")

    return _instance

# Export the server instance
logger.warning("🚀 About to create the server instance in module initialization")
server = get_server_instance()
logger.warning(f"🚀 Server instance created, init count = {_init_counter}")
