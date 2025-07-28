#!/usr/bin/env python3
"""
Entry point for the stdio-based MCP server.

This allows running the Omnispindle MCP server with stdio transport:
    python stdio_main.py

Or as a module:
    python -m stdio_main
"""

import asyncio
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.Omnispindle.stdio_server import main

if __name__ == "__main__":
    asyncio.run(main())