import os
import subprocess
import shutil 
from typing import Optional, Any

from fastmcp import Context

# MQTT configuration from environment
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None

async def mqtt_publish(topic: str, message: str, ctx: Optional[Context] = None, retain: bool = False) -> bool:
    """
    Publish a message to an MQTT topic using mosquitto_pub
    
    Args:
        topic: MQTT topic to publish to
        message: Message content to publish
        ctx: Optional context for logging
        retain: Whether to set the retain flag
        
    Returns:
        True if publish successful, False otherwise
    """
    if not MOSQUITTO_PUB_AVAILABLE:
        print(f"MQTT publishing not available - would publish {message} to {topic} (retain={retain})")
        return False

    try:
        cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-m", str(message)]
        if retain:
            cmd.append("-r")
        subprocess.run(cmd, check=True)
        
        if ctx is not None:
            try:
                ctx.info(f"Published to MQTT topic: {topic}")
            except Exception:
                pass
                
        return True
    except subprocess.SubprocessError as e:
        error_msg = f"Failed to publish MQTT message: {str(e)}"
        print(error_msg)
        
        if ctx is not None:
            try:
                ctx.error(error_msg)
            except Exception:
                pass
                
        return False


async def mqtt_get(topic: str) -> Optional[str]:
    """
    Get the latest message from an MQTT topic
    
    Args:
        topic: MQTT topic to retrieve from
        
    Returns:
        The message content or None if retrieval failed
    """
    try:
        cmd = ["mosquitto_sub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic, "-C", "1"]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except subprocess.SubprocessError as e:
        error_msg = f"Failed to get MQTT message: {str(e)}"
        print(error_msg)
        return None 