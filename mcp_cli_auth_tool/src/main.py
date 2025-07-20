import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# This should be a secret and loaded from environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]

# Path to the client secrets file.
CLIENT_SECRETS_FILE = "client_secrets.json"

# Create a client secrets file if it doesn't exist
if not os.path.exists(CLIENT_SECRETS_FILE):
    client_secrets = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    with open(CLIENT_SECRETS_FILE, "w") as f:
        json.dump(client_secrets, f)


@app.get("/")
async def root():
    return HTMLResponse('<body><a href="/login">Login with Google</a></body>')


@app.get("/login")
async def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    return RedirectResponse(authorization_url)


@app.get("/callback")
async def callback(request: Request):
    state = request.query_params.get("state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI,
    )
    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    id_token = credentials.id_token

    # Here you would typically save the token or user info
    # For this tool, we will print it and then update the mcp.json

    print("ID Token:", id_token)

    # Now, let's find and update mcp.json
    # This is a placeholder for the logic to find and update the file.
    # We'll need to search for the file in common locations.
    mcp_json_path = find_mcp_json()
    if mcp_json_path:
        update_mcp_json(mcp_json_path, id_token)
        return HTMLResponse(f"""
            <h1>Authentication Successful!</h1>
            <p>Your token has been retrieved and mcp.json has been updated.</p>
            <p>ID Token: {id_token}</p>
        """)
    else:
        return HTMLResponse(f"""
            <h1>Authentication Successful!</h1>
            <p>Could not find mcp.json. Please configure it manually.</p>
            <p>ID Token: {id_token}</p>
        """)


def find_mcp_json():
    # Placeholder: Search for mcp.json in likely locations
    # e.g., ~/.cursor/mcp.json
    home = os.path.expanduser("~")
    cursor_path = os.path.join(home, ".cursor", "mcp.json")
    if os.path.exists(cursor_path):
        return cursor_path
    return None


def update_mcp_json(file_path, token):
    # Placeholder: Update the mcp.json file
    with open(file_path, "r+") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
        # This assumes a specific structure for mcp.json
        # We might need to adjust this based on the actual structure
        data["auth_token"] = token
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
    print(f"Updated {file_path}")


if __name__ == "__main__":
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in a .env file")
    uvicorn.run(app, host="localhost", port=8000)