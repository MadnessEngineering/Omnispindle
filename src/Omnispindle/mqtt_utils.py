import os
import subprocess
from typing import Optional
from fastmcp import Context

MQTT_HOST = os.getenv("AWSIP", "localhost")
MQTT_PORT = int(os.getenv("AWSPORT", 3003))

async def mqtt_publish(topic: str, message: str, ctx: Context = None, retain: bool = False) -> bool:
    """Publish a message to the specified MQTT topic"""
    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Failed to publish MQTT message: {str(e)}")
        return False

async def mqtt_get(topic: str) -> str:
    """Get a message from the specified MQTT topic"""
    try:
        cmd = ["mosquitto_sub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-C", "1"]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except subprocess.SubprocessError as e:
        print(f"Failed to get MQTT message: {str(e)}")
        return f"Failed to get MQTT message: {str(e)}" 
