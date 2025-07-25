import sys
import json
import logging
from .auth import verify_token  # Assuming verify_token can be adapted

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StdioServer:
    def __init__(self):
        self.authenticated = False
        self.user_info = None

    def send_response(self, data):
        """Sends a JSON response to stdout."""
        sys.stdout.write(json.dumps(data) + '\\n')
        sys.stdout.flush()

    def handle_command(self, command_data):
        """Dispatches commands to the appropriate handlers."""
        command = command_data.get('command')
        payload = command_data.get('payload')

        if not self.authenticated and command != 'authenticate':
            self.send_response({'status': 'error', 'message': 'Authentication required.'})
            return

        if command == 'authenticate':
            self.authenticate(payload)
        elif command == 'ping':
            self.ping()
        else:
            self.send_response({'status': 'error', 'message': f'Unknown command: {command}'})

    def authenticate(self, payload):
        """Handles the authentication command."""
        token = payload.get('token')
        if not token:
            self.send_response({'status': 'error', 'message': 'Token is required for authentication.'})
            return

        # This is a placeholder for the actual token verification logic.
        # We will need to adapt the verify_token function to work in this context.
        # For now, we'll just check if a token is present.
        if token:
            self.authenticated = True
            self.user_info = {'username': 'testuser'}  # Placeholder user info
            self.send_response({'status': 'ok', 'message': 'Authentication successful.'})
            logging.info(f"User authenticated: {self.user_info['username']}")
        else:
            self.send_response({'status': 'error', 'message': 'Authentication failed.'})


    def ping(self):
        """Handles the ping command."""
        self.send_response({'status': 'ok', 'message': 'pong'})

    def run(self):
        """Main loop to read and process commands."""
        logging.info("STDIO server started. Waiting for commands.")
        for line in sys.stdin:
            try:
                command_data = json.loads(line)
                self.handle_command(command_data)
            except json.JSONDecodeError:
                self.send_response({'status': 'error', 'message': 'Invalid JSON format.'})
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                self.send_response({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    server = StdioServer()
    server.run() 
