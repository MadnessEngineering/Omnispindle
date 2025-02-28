from fastmcp.server import FastMCP
# from starlette.applications import Starlette
# from starlette.routing import Route
# from starlette.responses import Response
# from starlette.requests import Request
# import uvicorn
# from uuid import UUID
# from fastmcp.tools import ToolManager
# from mcp.types import Tool as MCPTool

# Import the tool functions from the tools module
# from fastmcp_todo_server.tools import (
#     add_todo,
#     query_todos,
#     update_todo,
#     mqtt_publish,
#     delete_todo,
#     get_todo,
#     mark_todo_complete,
#     list_todos_by_status,
#     add_lesson,
#     get_lesson,
#     update_lesson,
#     delete_lesson,
#     list_lessons,
# )

# # Create a minimally patched version of FastMCP
# class MinimallyPatchedFastMCP(FastMCP):
#     """A minimally patched version of FastMCP that fixes the SSE handler issue."""

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         # Initialize a ToolManager
#         self._tool_manager = ToolManager()

#         # Register the tool functions
#         self._tool_manager.add_tool(add_todo)
#         self._tool_manager.add_tool(query_todos)
#         self._tool_manager.add_tool(update_todo)
#         self._tool_manager.add_tool(mqtt_publish)
#         self._tool_manager.add_tool(delete_todo)
#         self._tool_manager.add_tool(get_todo)
#         self._tool_manager.add_tool(mark_todo_complete)
#         self._tool_manager.add_tool(list_todos_by_status)
#         self._tool_manager.add_tool(add_lesson)
#         self._tool_manager.add_tool(get_lesson)
#         self._tool_manager.add_tool(update_lesson)
#         self._tool_manager.add_tool(delete_lesson)
#         self._tool_manager.add_tool(list_lessons)

#         # Register the list_tools method as a handler
#         self._mcp_server.list_tools()(self.list_tools)

#     async def list_tools(self) -> list[MCPTool]:
#         """List all available tools."""
#         tools = self._tool_manager.list_tools()
#         return [
#             MCPTool(
#                 name=info.name,
#                 description=info.description,
#                 inputSchema=info.parameters,
#             )
#             for info in tools
#         ]

#     async def run_sse_async(self) -> None:
#         """Run the server using SSE transport with proper response handling."""
#         from mcp.server.sse import SseServerTransport

#         sse = SseServerTransport("/messages")

#         async def handle_sse(request):
#             # Handle SSE connection
#             async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
#                 # The SSE connection is now set up
#                 # We can use read_stream and write_stream to communicate with the client
#                 return Response(status_code=200)

#         async def handle_messages(request: Request):
#             # Handle messages to SSE clients
#             session_id_param = request.query_params.get("session_id")
#             if session_id_param is None:
#                 return Response("session_id is required", status_code=400)

#             try:
#                 session_id = UUID(hex=session_id_param)
#             except ValueError:
#                 return Response("Invalid session ID", status_code=400)

#             writer = sse._read_stream_writers.get(session_id)
#             if not writer:
#                 return Response("Could not find session", status_code=404)

#             data = await request.json()
#             await writer.send(data)
#             return Response(status_code=202)

#         # Create Starlette app with routes
#         starlette_app = Starlette(
#             debug=self.settings.debug,
#             routes=[
#                 Route("/sse", endpoint=handle_sse),
#                 Route("/messages", endpoint=handle_messages, methods=["POST"]),
#             ],
#         )

#         # Start server
#         config = uvicorn.Config(
#             starlette_app,
#             host=self.settings.host,
#             port=self.settings.port,
#             log_level=self.settings.log_level.lower(),
#         )
#         server = uvicorn.Server(config)
#         await server.serve()

# Create the patched FastMCP instance
# server = MinimallyPatchedFastMCP("todo_server")
server = FastMCP("todo_server")
