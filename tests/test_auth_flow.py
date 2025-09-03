import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import time
import threading
from http.server import HTTPServer
from pathlib import Path
import requests

# Add src to path to allow direct import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from Omnispindle import auth_flow

class TestAuthFlow(unittest.TestCase):

    def setUp(self):
        """Set up the test environment"""
        self.test_domain = "test.auth0.com"
        self.test_client_id = "test_client_id_123"
        self.test_audience = "test_audience"
        self.test_token = "fake_access_token_for_testing"

        # Patch environment variables
        self.env_patcher = patch.dict(os.environ, {
            "AUTH0_DOMAIN": self.test_domain,
            "AUTH0_CLIENT_ID": self.test_client_id,
            "AUTH0_AUDIENCE": self.test_audience,
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up the test environment"""
        self.env_patcher.stop()

    @patch('webbrowser.open')
    @patch('src.Omnispindle.auth_flow.save_token_to_env')
    @patch('src.Omnispindle.auth_flow.start_callback_server')
    def test_full_authentication_flow(self, mock_start_server, mock_save_token, mock_webbrowser_open):
        """
        Test the full browser-based authentication flow from start to finish.
        """
        # --- Test Setup ---
        
        # Mock the server to prevent it from actually starting
        mock_server_instance = MagicMock()
        mock_server_instance.token = None
        mock_start_server.return_value = mock_server_instance
        
        def simulate_callback():
            time.sleep(0.5) # give the main thread a moment to start waiting
            mock_server_instance.token = self.test_token
            
        # --- Test Execution ---
        
        callback_thread = threading.Thread(target=simulate_callback)
        callback_thread.start()
        
        result_token = auth_flow.authenticate_user()
        
        # --- Assertions ---

        self.assertEqual(result_token, self.test_token)
        mock_webbrowser_open.assert_called_once()
        mock_save_token.assert_called_once_with(self.test_token)
        mock_server_instance.shutdown.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data='EXISTING_KEY=some_value\\n')
    @patch.dict(os.environ, {})
    def test_save_token_to_env_file(self, mock_file):
        """
        Test that the token is correctly saved to a .env file.
        """
        # --- Test Setup ---
        
        test_token = "newly_saved_token"
        
        # --- Test Execution ---

        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            auth_flow.save_token_to_env(test_token)

        # --- Assertions ---
        
        # Check that the file was opened for writing with the correct absolute path
        expected_path = Path(__file__).parent.parent / '.env'
        mock_file.assert_called_with(expected_path, 'w')
        
        handle = mock_file()
        
        # Get all writes and join them
        written_content = "".join(call[0][0] for call in handle.write.call_args_list)

        # Verify the new token is in the content and old content is preserved
        self.assertIn(f"AUTH0_TOKEN={test_token}\\n", written_content)
        self.assertIn("EXISTING_KEY=some_value\\n", written_content)
        
        # Verify the environment variable was set in the current process
        self.assertEqual(os.environ['AUTH0_TOKEN'], test_token)

    def test_missing_env_vars(self):
        """
        Test that the script raises an error if required env vars are not set.
        """
        # Unset the required env vars for this test
        self.env_patcher.stop()
        
        with self.assertRaises(TypeError):
            # The script will fail when trying to build the auth URL with None values
            auth_flow.open_auth0_login()
            
        # Restore patcher
        self.env_patcher.start()


if __name__ == '__main__':
    unittest.main() 
