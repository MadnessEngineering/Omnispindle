from fastmcp import FastMCP, Context
from pymongo import MongoClient
from datetime import datetime, UTC
import uuid
import os
from dotenv import load_dotenv
import json
import logging
import asyncio
from aiohttp import web
import paho.mqtt.client as mqtt

# Import the tool functions from the tools module
from fastmcp_todo_server.tools import (
    add_todo,
    query_todos,
    update_todo,
    mqtt_publish,
    delete_todo,
    get_todo,
    mark_todo_complete,
    list_todos_by_status,
    add_lesson,
    get_lesson,
    update_lesson,
    delete_lesson,
    list_lessons,
)

# Configure logging - set to DEBUG level for maximum visibility
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable debug logging for FastMCP
logging.getLogger('fastmcp').setLevel(logging.DEBUG)
logging.getLogger('mcp').setLevel(logging.DEBUG)

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

# Cursor MCP configuration
# CURSOR_MCP_URL = os.getenv("CURSOR_MCP_URL", "http://localhost:8000")
# CURSOR_MCP_SSE_ENDPOINT = os.getenv("CURSOR_MCP_SSE_ENDPOINT", "/sse")

# Import the server instance from our server module
from fastmcp_todo_server.server import server

# Create MongoDB connection at module level
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]
lessons_collection = db["lessons_learned"]

# Register tools using the FastMCP decorator syntax
@server.tool()
async def add_todo_tool(description: str, priority: str = "initial", target_agent: str = "user", ctx: Context = None) -> dict:
    return await add_todo(description, priority, target_agent, ctx)

@server.tool()
async def query_todos_tool(filter: dict = None, projection: dict = None, limit: int = 100) -> dict:
    return await query_todos(filter, projection, limit)

@server.tool()
async def update_todo_tool(todo_id: str, updates: dict, ctx: Context = None) -> str:
    return await update_todo(todo_id, updates, ctx)

@server.tool()
async def mqtt_publish_tool(topic: str, message: str, ctx: Context = None) -> str:
    return await mqtt_publish(topic, message, ctx)

@server.tool()
async def delete_todo_tool(todo_id: str, ctx: Context = None) -> str:
    return await delete_todo(todo_id, ctx)

@server.tool()
async def get_todo_tool(todo_id: str) -> str:
    return await get_todo(todo_id)

@server.tool()
async def mark_todo_complete_tool(todo_id: str, ctx: Context = None) -> str:
    return await mark_todo_complete(todo_id, ctx)

@server.tool()
async def list_todos_by_status_tool(status: str, limit: int = 100) -> str:
    return await list_todos_by_status(status, limit)

@server.tool()
async def add_lesson_tool(language: str, topic: str, lesson_learned: str, tags: list = None, ctx: Context = None) -> str:
    return await add_lesson(language, topic, lesson_learned, tags, ctx)

@server.tool()
async def get_lesson_tool(lesson_id: str) -> str:
    return await get_lesson(lesson_id)

@server.tool()
async def update_lesson_tool(lesson_id: str, updates: dict, ctx: Context = None) -> str:
    return await update_lesson(lesson_id, updates, ctx)

@server.tool()
async def delete_lesson_tool(lesson_id: str, ctx: Context = None) -> str:
    return await delete_lesson(lesson_id, ctx)

@server.tool()
async def list_lessons_tool(limit: int = 100) -> str:
    return await list_lessons(limit)

async def run_server():
    """Run the FastMCP server"""
    logger.info("Starting FastMCP server")
    try:
        await server.run_sse_async()  # Use run_stdio_async directly
    except Exception as e:
        logger.error(f"Error in server: {str(e)}", exc_info=True)
        raise
