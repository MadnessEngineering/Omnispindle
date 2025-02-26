import asyncio
import logging
from server import server
from __init__ import run_server

logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    logger.info("Starting Todo Server")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Shutting down server")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
