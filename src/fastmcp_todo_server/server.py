import logging
import os
import signal
import sys
from typing import Callable
from fastmcp.server import FastMCP
import uvicorn


class Omnispindle(FastMCP):
    def __init__(self, name: str = "todo-server", server_type: str = "sse"):
        super().__init__(name, server_type)
        # We don't need to create another server instance since we inherit from FastMCP

    async def run_server(self, publish_mqtt_status: Callable):
        print("Starting FastMCP server")

        try:
            hostname = os.getenv("DeNa", os.uname().nodename)
            topic = f"status/{hostname}-mcp/alive"
            publish_mqtt_status(topic, "1")

            def signal_handler(sig, frame):
                print(f"Received signal {sig}, shutting down gracefully...")
                publish_mqtt_status(topic, "0", retain=True)
                sys.exit(0)

            # Register signal handlers
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Custom exception handler to silence specific SSE-related errors
            original_excepthook = sys.excepthook

            def custom_excepthook(exctype, value, traceback):
                # Handle NoneType errors from Starlette more broadly
                if exctype is TypeError and "'NoneType' object is not callable" in str(value):
                    # Log minimally instead of full stack trace
                    print(f"Suppressed NoneType error: {str(value)}")
                    return
                # For all other errors, use the original exception handler
                original_excepthook(exctype, value, traceback)

            # Replace the default exception handler
            sys.excepthook = custom_excepthook

            # Configure uvicorn to suppress specific access logs for /messages endpoint
            log_config = uvicorn.config.LOGGING_CONFIG
            if "formatters" in log_config:
                log_config["formatters"]["access"]["fmt"] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

            # Configure logging instead
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            # Run the server
            await self.run_sse_async()  # Use self instead of server
        except Exception as e:
            print(f"Error in server: {str(e)}")
            # Publish offline status with retain flag in case of error
            try:
                hostname = os.getenv("HOSTNAME", os.uname().nodename)
                topic = f"status/{hostname}/alive"
                publish_mqtt_status(topic, "0", retain=True)
                print(f"Published offline status to {topic} (retained)")
            except Exception as ex:
                print(f"Failed to publish offline status: {str(ex)}")
            raise

    # Add method to register tools
    def register_tool(self, tool_func):
        """Register a single tool with the server"""
        if not hasattr(self, '_registered_tools'):
            self._registered_tools = set()

        if tool_func.__name__ not in self._registered_tools:
            # Use the original FastMCP tool registration method
            self.tool()(tool_func)
            self._registered_tools.add(tool_func.__name__)
            print(f"Registered tool: {tool_func.__name__}")
        return tool_func

    def register_tools(self, tools_list):
        """Register multiple tools with the server"""
        for tool in tools_list:
            self.register_tool(tool)

# Create a singleton instance
server = Omnispindle()
