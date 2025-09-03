import unittest
import asyncio
from unittest.mock import MagicMock

# Add src to path to allow direct import
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from Omnispindle import tools
from Omnispindle.context import Context

class TestAddTodoDirect(unittest.TestCase):

    def test_add_todo_directly(self):
        """
        Test that we can add a todo directly without the stdio_server.
        """
        async def run_test():
            # Mock the context object
            mock_ctx = Context(user={'email': 'test@test.com', 'sub': 'test|123'})
            
            # Call the add_todo tool directly
            result = await tools.add_todo(
                description="This is a direct test",
                project="Omnispindle",
                ctx=mock_ctx
            )
            
            print(f"Result from add_todo: {result}")
            self.assertIn("success", result)

        # Run the async test
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main() 
