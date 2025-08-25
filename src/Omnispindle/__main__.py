import asyncio
import logging
import os
import uvicorn
from .server import Omnispindle

import sys
import shutil
import subprocess
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MOSQUITTO_PUB_AVAILABLE = shutil.which("mosquitto_pub") is not None

def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="Omnispindle MCP Server Management",
        prog="python -m src.Omnispindle"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Authentication setup")
    auth_parser.add_argument("--setup", action="store_true", help="Run Auth0 setup flow")
    auth_parser.add_argument("--no-save", action="store_true", help="Don't save config file")
    auth_parser.add_argument("--output", "-o", help="Output path for config file")
    
    # Server command (default behavior)
    server_parser = subparsers.add_parser("server", help="Run the web server (default)")
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command == "auth":
        if args.setup:
            asyncio.run(run_auth_setup(args))
        else:
            auth_parser.print_help()
        return
    
    # Default behavior or explicit server command - run the web server
    run_web_server()


def run_auth_setup(args):
    """Run the Auth0 setup flow."""
    async def setup():
        try:
            from .auth_setup import Auth0CLISetup
            
            setup_handler = Auth0CLISetup()
            result = await setup_handler.run_setup(save_config=not args.no_save)
            
            if args.output and not args.no_save:
                setup_handler.save_config(result["mcp_config"], args.output)
                print(f"💾 Config also saved to: {args.output}")
                
        except ImportError as e:
            print(f"❌ Auth setup requires additional dependencies: {e}")
            print("💡 Try: pip install requests")
        except KeyboardInterrupt:
            print("\n❌ Setup cancelled by user")
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)
    
    return setup()


def run_web_server():
    """Run the web server (original main functionality)."""
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
        server = Omnispindle()
        app = loop.run_until_complete(server.run_server())

        # Run Uvicorn with the ASGI app
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            proxy_headers=True,  # Important for proper header handling in Docker
            forwarded_allow_ips="*",  # Accept X-Forwarded-* headers from any IP
            interface="asgi3"  # Force use of the newer ASGI interface
        )
    except Exception as e:
        logger.exception(f"Error starting Omnispindle: {str(e)}")
        raise
    finally:
        loop.close()

if __name__ == "__main__":
    main()
