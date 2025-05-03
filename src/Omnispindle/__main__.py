import asyncio
import logging
import sys
from .bootstrap import bootstrap, MOSQUITTO_PUB_AVAILABLE

logger = logging.getLogger(__name__)

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
        asyncio.run(bootstrap())
    except KeyboardInterrupt:
        # KeyboardInterrupt will now be handled by the signal handler in run_server
        print("Shutting down server")
    except Exception as e:
        print(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
