#!/usr/bin/env python3
"""
Standalone runner for the TodoLogService

This script runs the TodoLogService as a standalone process, separate from Node-RED.
It monitors MongoDB for changes to todos and records them in the todo_logs collection.
"""

import asyncio
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('todo_log_service.log')
    ]
)
logger = logging.getLogger("todo_log_service")

# Add the src directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the service module
from Omnispindle.todo_log_service import start_service

if __name__ == "__main__":
    logger.info("Starting Todo Log Service")
    try:
        asyncio.run(start_service())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
    logger.info("Todo Log Service shutdown complete") 
