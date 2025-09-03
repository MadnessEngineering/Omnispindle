#!/usr/bin/env python3
"""
Token Exchange utility for Omnispindle MCP authentication.

This module provides a simple way for users to authenticate with Omnispindle
using Auth0's Custom Token Exchange feature. It generates a local token,
exchanges it for an Auth0 token, and outputs the MCP configuration.
"""

import json
import os
import sys
import time
import uuid
from typing import Optional, Dict, Any
import hashlib
import httpx
from pathlib import Path

# Auth0 configuration
AUTH0_DOMAIN = "dev-eoi0koiaujjbib20.us.auth0.com"
AUTH0_CLIENT_ID = "U43kJwbd1xPcCzJsu3kZIIeNV1ygS7x1"
AUTH0_AUDIENCE = "https://madnessinteractive.cc/api"
SUBJECT_TOKEN_TYPE = "urn:omnispindle:local-auth"


def generate_local_token() -> str:
    """
    Generate a secure local token that can be exchanged for an Auth0 token.
    This token includes machine-specific information for security.
    """
    # Get machine-specific information
    machine_id = str(uuid.getnode())  # MAC address-based UUID
    timestamp = str(int(time.time()))
    user = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
    
    # Create a unique token combining machine info, timestamp, and random data
    token_data = f"{machine_id}:{user}:{timestamp}:{uuid.uuid4()}"
    
    # Hash it for a cleaner token
    token_hash = hashlib.sha256(token_data.encode()).hexdigest()
    
    # Create a structured token that our Custom Token Exchange can validate
    local_token = f"local.{user}.{timestamp}.{token_hash}"
    
    return local_token


def exchange_token(local_token: str) -> Optional[str]:
    """
    Exchange the local token for an Auth0 access token using Custom Token Exchange.
    
    Args:
        local_token: The locally generated token to exchange
        
    Returns:
        The Auth0 access token if successful, None otherwise
    """
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": local_token,
        "subject_token_type": SUBJECT_TOKEN_TYPE,
        "client_id": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE,
        "scope": "openid profile email"
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(token_url, data=payload)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get("access_token")
            
    except httpx.HTTPStatusError as e:
        print(f"Error exchanging token: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error during token exchange: {e}", file=sys.stderr)
        return None


def save_mcp_config(token: str) -> Path:
    """
    Save the MCP configuration with the Auth0 token to the appropriate location.
    
    Args:
        token: The Auth0 access token
        
    Returns:
        Path to the saved configuration file
    """
    # Determine the config path based on the platform
    if sys.platform == "darwin":  # macOS
        config_dir = Path.home() / "Library" / "Application Support" / "Claude"
    elif sys.platform == "win32":  # Windows
        config_dir = Path(os.environ.get("APPDATA", "")) / "Claude"
    else:  # Linux
        config_dir = Path.home() / ".config" / "claude"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "claude_desktop_config.json"
    
    # Load existing config or create new
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add or update the omnispindle server configuration
    omnispindle_root = Path(__file__).parent.parent.parent
    
    config["mcpServers"]["omnispindle"] = {
        "command": "python",
        "args": ["-m", "src.Omnispindle.stdio_server"],
        "cwd": str(omnispindle_root),
        "env": {
            "AUTH0_TOKEN": token,
            "OMNISPINDLE_TOOL_LOADOUT": "full"
        }
    }
    
    # Save the updated config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config_file


def main():
    """
    Main function that orchestrates the token exchange and configuration.
    """
    print("🔐 Omnispindle Authentication Setup", file=sys.stderr)
    print("=" * 40, file=sys.stderr)
    
    # Step 1: Generate local token
    print("1️⃣  Generating local authentication token...", file=sys.stderr)
    local_token = generate_local_token()
    
    # Step 2: Exchange for Auth0 token
    print("2️⃣  Exchanging for Auth0 access token...", file=sys.stderr)
    auth0_token = exchange_token(local_token)
    
    if not auth0_token:
        print("❌ Failed to obtain Auth0 token. Please check your connection and try again.", file=sys.stderr)
        sys.exit(1)
    
    print("✅ Successfully obtained Auth0 token!", file=sys.stderr)
    
    # Step 3: Save MCP configuration
    print("3️⃣  Updating MCP configuration...", file=sys.stderr)
    config_path = save_mcp_config(auth0_token)
    print(f"✅ Configuration saved to: {config_path}", file=sys.stderr)
    
    # Step 4: Output the token for use in scripts
    print(auth0_token)  # This goes to stdout for capture
    
    print("\n" + "=" * 40, file=sys.stderr)
    print("🎉 Setup complete! Restart Claude Desktop to use Omnispindle.", file=sys.stderr)
    print("\nTo use in other MCP clients, your Auth0 token is:", file=sys.stderr)
    print(f"  {auth0_token[:20]}...", file=sys.stderr)


if __name__ == "__main__":
    main() 
