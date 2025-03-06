import asyncio
# import logging
from server import server
from __init__ import run_server
import sys

# logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    # logger.info("Starting Todo Server")
    print("Starting Todo Server")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        # KeyboardInterrupt will now be handled by the signal handler in run_server
        print("Shutting down server")
    except Exception as e:
        print(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
