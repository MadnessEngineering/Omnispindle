from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json

async def main():
    # Create server parameters
    server_params = StdioServerParameters(
        command="python",
        args=["__init__.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", tools)

            # Add a todo
            result = await session.call_tool(
                "add_todo",
                arguments={
                    "description": "Test todo item",
                    "priority": "high",
                    "target_agent": "tester"
                }
            )
            print("\nAdd todo result:", result)

            # Query todos
            result = await session.call_tool(
                "query_todos",
                arguments={}
            )
            print("\nQuery todos result:", result)

if __name__ == "__main__":
    asyncio.run(main())
