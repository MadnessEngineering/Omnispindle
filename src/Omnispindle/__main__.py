import asyncio
import logging
import os
import uvicorn
from . import run_server

import sys
import shutil
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None

def main():
    logger.info("Omnispindle beginning spin")

    # Print a warning if mosquitto_pub is not available
    if not MOSQUITTO_PUB_AVAILABLE:
        print("WARNING: mosquitto_pub command not found. MQTT status publishing will be disabled.")
        print("  To enable MQTT status publishing, install the Mosquitto clients package:")
        print("  Ubuntu/Debian: sudo apt install mosquitto-clients")
        print("  macOS: brew install mosquitto")
        print("  Windows: Download from https://mosquitto.org/download/")

    try:
        # Get host and port from environment variables with proper defaults for containerization
        # Force host to 0.0.0.0 for Docker compatibility - overriding any existing variables
        host = "0.0.0.0"  # Force binding to all interfaces
        port = int(os.getenv("PORT", 8000))

        # Print binding information for debugging
        logger.info(f"Starting Uvicorn server on {host}:{port}")

        # Ensure we use asyncio to start the server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Get the ASGI app by running the server in the event loop
        app = loop.run_until_complete(run_server())

        # Run Uvicorn with the ASGI app
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            proxy_headers=True,  # Important for proper header handling in Docker
            forwarded_allow_ips="*"  # Accept X-Forwarded-* headers from any IP
        )
    except Exception as e:
        logger.exception(f"Error starting Omnispindle: {str(e)}")
        raise
    finally:
        loop.close()

if __name__ == "__main__":
    main()
