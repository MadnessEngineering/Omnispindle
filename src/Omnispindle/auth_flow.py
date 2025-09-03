import asyncio
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# Auth0 configuration - Reads from environment variables
CALLBACK_PORT = 8765

logger = logging.getLogger(__name__)


def run_async_in_thread(coro):
    """
    Run an async coroutine in a separate thread, managing the event loop.
    """
    def thread_target():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)

    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join()


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for Auth0 callback"""

    def do_GET(self):
        """Handle the OAuth callback from Auth0"""
        if self.path.startswith('/callback'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            success_html = """
            <!DOCTYPE html><html><head><title>Success</title>
            <script>
                const hash = window.location.hash.substring(1);
                const params = new URLSearchParams(hash);
                const token = params.get('access_token');
                if (token) {
                    fetch('/token', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({access_token: token})
                    }).then(() => setTimeout(() => window.close(), 1000));
                }
            </script>
            </head><body><h1>Authenticated!</h1><p>You can close this window.</p></body></html>
            """
            self.wfile.write(success_html.encode())

    def do_POST(self):
        """Handle token submission from JavaScript"""
        if self.path == '/token':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            self.server.token = data.get('access_token')
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        pass

class AuthCallbackServer(HTTPServer):
    """Extended HTTPServer that can store the received token"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None

def start_callback_server() -> AuthCallbackServer:
    """Start a local HTTP server to handle the Auth0 callback"""
    server = AuthCallbackServer(('localhost', CALLBACK_PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

def open_auth0_login():
    """Open the Auth0 login page in the user's browser"""
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_client_id = os.getenv("AUTH0_CLIENT_ID")
    auth0_audience = os.getenv("AUTH0_AUDIENCE", "https://madnessinteractive.cc/api")

    auth_url = (
        f"https://{auth0_domain}/authorize"
        f"?client_id={auth0_client_id}"
        f"&response_type=token"
        f"&redirect_uri=http://localhost:{CALLBACK_PORT}/callback"
        f"&audience={auth0_audience}"
        f"&scope=openid%20profile%20email"  # URL Encoded scope
    )

    print(f"Opening browser to: {auth_url}", file=sys.stderr)
    webbrowser.open(auth_url)

def save_token_to_env(token: str) -> Path:
    """Save the Auth0 token to a .env file"""
    env_path = Path(__file__).parent.parent.parent / '.env'

    env_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_lines = f.readlines()

    token_line = f"AUTH0_TOKEN={token}\n"
    token_found = False

    for i, line in enumerate(env_lines):
        if line.startswith('AUTH0_TOKEN='):
            env_lines[i] = token_line
            token_found = True
            break

    if not token_found:
        env_lines.append(token_line)

    with open(env_path, 'w') as f:
        f.writelines(env_lines)

    os.environ['AUTH0_TOKEN'] = token
    return env_path

async def authenticate_user() -> Optional[str]:
    """Perform browser-based authentication flow."""
    existing_token = os.environ.get('AUTH0_TOKEN')
    if existing_token:
        return existing_token
    
    server = start_callback_server()
    open_auth0_login()
    
    timeout = 120
    start_time = time.time()
    
    while server.token is None and (time.time() - start_time) < timeout:
        await asyncio.sleep(0.5)
    
    server.shutdown()
    
    if server.token:
        save_token_to_env(server.token)
        return server.token
    else:
        return None

async def ensure_authenticated() -> str:
    """Ensure the user is authenticated, prompting for login if needed."""
    token = await authenticate_user()
    if not token:
        raise RuntimeError("Authentication failed.")
    return token

if __name__ == "__main__":
    try:
        token = asyncio.run(ensure_authenticated())
        print(f"Token: {token}")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
