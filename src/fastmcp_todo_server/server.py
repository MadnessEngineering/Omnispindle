import logging
import os
import signal
import sys
from typing import Callable, Dict, Any, Optional
from fastmcp.server import FastMCP
import uvicorn
import json
from starlette.responses import JSONResponse

# Configure logger
logger = logging.getLogger(__name__)

class Omnispindle(FastMCP):
    def __init__(self, name: str = "todo-server", server_type: str = "sse"):
        logger.info(f"Initializing Omnispindle server with name='{name}', server_type='{server_type}'")
        super().__init__(name=name, server_type=server_type)
        logger.debug("Omnispindle instance initialization complete")
        # We don't need to create another server instance since we inherit from FastMCP

    async def run_server(self, publish_mqtt_status: Callable) -> Callable:
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
            topic = f"status/{hostname}-mcp/alive"
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

    def register_tools(self, tools_list):
        """Register multiple tools with the server"""
        logger.info(f"Registering {len(tools_list)} tools")
        for tool in tools_list:
            self.register_tool(tool)
        logger.debug("All tools registered successfully")

# Create a singleton instance
logger.info("Creating Omnispindle singleton instance")
server = Omnispindle()
logger.debug("Omnispindle singleton instance created")
