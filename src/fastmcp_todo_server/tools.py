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
