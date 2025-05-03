import asyncio
import logging
import os
import shutil
import sys
import subprocess

logger = logging.getLogger(__name__)

# Define MOSQUITTO_PUB_AVAILABLE here so it's not imported from __init__
MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None

async def bootstrap():
    """Bootstrap function to start the Omnispindle server"""
    # Print a warning if mosquitto_pub is not available
    if not MOSQUITTO_PUB_AVAILABLE:
        print("WARNING: mosquitto_pub command not found. MQTT status publishing will be disabled.")
        print("  To enable MQTT status publishing, install the Mosquitto clients package:")
        print("  Ubuntu/Debian: sudo apt install mosquitto-clients")
        print("  macOS: brew install mosquitto")
        print("  Windows: Download from https://mosquitto.org/download/")
    
    # Import server here to avoid circular imports
    from .server import server
    
    # Create publish_mqtt_status function for the server
    def publish_mqtt_status(topic, message, retain=False):
        if not MOSQUITTO_PUB_AVAILABLE:
            print(f"MQTT publishing not available - would publish {message} to {topic} (retain={retain})")
            return False

        try:
            MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
            MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
            cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
            if retain:
                cmd.append("-r")
            subprocess.run(cmd, check=True)
            return True
        except subprocess.SubprocessError as e:
            print(f"Failed to publish MQTT message: {str(e)}")
            return False
    
    return await server.run_server(publish_mqtt_status) 
