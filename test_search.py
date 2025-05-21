#!/usr/bin/env python3

import asyncio
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the path
sys.path.insert(0, os.path.abspath('src'))

# Import the tools
from Omnispindle import query_todos_tool
from fastmcp import Context

async def test_search():
    """Test different search and query scenarios"""
    try:
        # Test project search
        logger.info('Test 1: Search with project: prefix')
        try:
            result = await query_todos_tool('project:regressiontestkit')
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Test 1 failed: {str(e)}")
        
        # Test regular search
        logger.info('\nTest 2: Regular text search')
        try:
            result = await query_todos_tool('test')
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Test 2 failed: {str(e)}")

        # Test filter
        logger.info('\nTest 3: Filter query')
        try:
            result = await query_todos_tool({'status': 'pending'})
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Test 3 failed: {str(e)}")
            
        # Test project search with fields
        logger.info('\nTest 4: Project search with fields')
        try:
            result = await query_todos_tool('project:omnispindle', ['all'])
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Test 4 failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Test suite failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_search()) 
