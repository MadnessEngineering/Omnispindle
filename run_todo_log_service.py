#!/usr/bin/env python3
"""
Standalone runner for the TodoLogService API

This script starts the TodoLogService for direct logging of todo actions.
It provides an API for logging and retrieving todo logs, without monitoring MongoDB changes.
"""

import asyncio
import logging
import os
import signal
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
from Omnispindle.todo_log_service import start_service, stop_service

async def run_service():
    """Run the TodoLogService and wait for shutdown signal"""
    service = await start_service()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(stop_service()))

    logger.info("Todo Log Service API running. Press Ctrl+C to stop.")

    # Keep the service running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

    logger.info("Todo Log Service shutting down")

if __name__ == "__main__":
    logger.info("Starting Todo Log Service API")
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
    logger.info("Todo Log Service shutdown complete")
