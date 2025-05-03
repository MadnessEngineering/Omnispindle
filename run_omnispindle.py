#!/usr/bin/env python3
"""
Entrypoint script for Omnispindle server
Avoids circular imports by not importing from src.Omnispindle.__main__
"""

import asyncio
import logging
import os
import sys
import shutil
import subprocess
from src.Omnispindle.server import Omnispindle

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("omnispindle")

# Define constants that avoid circular imports
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None

def publish_mqtt_status(topic, message, retain=False):
    """
    Publish MQTT message using mosquitto_pub command line tool
    Falls back to logging if mosquitto_pub is not available
    """
    if not MOSQUITTO_PUB_AVAILABLE:
        print(f"MQTT publishing not available - would publish {message} to {topic} (retain={retain})")
        return False

    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False

async def main_async():
    # Create server instance directly
    server = Omnispindle()
    
    # Print a warning if mosquitto_pub is not available
    if not MOSQUITTO_PUB_AVAILABLE:
        print("WARNING: mosquitto_pub command not found. MQTT status publishing will be disabled.")
        print("  To enable MQTT status publishing, install the Mosquitto clients package:")
        print("  Ubuntu/Debian: sudo apt install mosquitto-clients")
        print("  macOS: brew install mosquitto")
        print("  Windows: Download from https://mosquitto.org/download/")
    
    # Run the server
    return await server.run_server(publish_mqtt_status)

def main():
    logger.info("Omnispindle beginning spin")
    
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Shutting down server")
    except Exception as e:
        print(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
