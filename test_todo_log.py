#!/usr/bin/env python3
"""
Test script for the Todo Log Service

This script tests the direct logging functionality of the TodoLogService.
"""

import asyncio
import logging
from src.Omnispindle.todo_log_service import (
    get_service_instance, 
    start_service, 
    log_todo_create,
    log_todo_update,
    log_todo_complete,
    log_todo_delete
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_todo_logging():
    """Test all logging operations"""
    logger.info("Starting Todo Log Service test")
    
    # Get and start the service
    service = get_service_instance()
    await start_service()
    
    # Test todo ID and info
    todo_id = "test-todo-123"
    description = "Test Todo Item"
    project = "omnispindle"
    user_agent = "Test Script"
    
    # Test logging a create operation
    logger.info("Testing log_todo_create")
    success = await log_todo_create(todo_id, description, project, user_agent)
    logger.info(f"Create log success: {success}")
    
    # Test logging an update operation
    logger.info("Testing log_todo_update")
    changes = [
        {"field": "description", "oldValue": description, "newValue": "Updated Description"},
        {"field": "priority", "oldValue": "Medium", "newValue": "High"}
    ]
    success = await log_todo_update(todo_id, "Updated Description", project, changes, user_agent)
    logger.info(f"Update log success: {success}")
    
    # Test logging a complete operation
    logger.info("Testing log_todo_complete")
    success = await log_todo_complete(todo_id, "Updated Description", project, user_agent)
    logger.info(f"Complete log success: {success}")
    
    # Test logging a delete operation
    logger.info("Testing log_todo_delete")
    success = await log_todo_delete(todo_id, "Updated Description", project, user_agent)
    logger.info(f"Delete log success: {success}")
    
    # Test retrieving logs
    logger.info("Testing get_logs")
    logs = await service.get_logs()
    logger.info(f"Retrieved {len(logs.get('logEntries', []))} log entries")
    
    logger.info("Todo Log Service test completed successfully")

if __name__ == "__main__":
    asyncio.run(test_todo_logging()) 
