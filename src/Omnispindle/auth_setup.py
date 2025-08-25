#!/usr/bin/env python3
"""
Auth0 CLI setup for Omnispindle MCP client configuration.

This module provides a command-line interface for users to authenticate with Auth0
and retrieve their credentials for MCP client setup (Claude Desktop, etc.).
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import webbrowser
from typing import Dict, Any, Optional
import logging

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Auth0CLISetup:
    """Handles Auth0 device flow authentication for MCP setup."""
    
    def __init__(self):
        # Use same Auth0 config as main application
        self.auth0_domain = "dev-eoi0koiaujjbib20.us.auth0.com"
        self.client_id = "U43kJwbd1xPcCzJsu3kZIIeNV1ygS7x1"
        self.audience = "https://madnessinteractive.cc/api"
    
    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge for secure auth flow."""
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def start_device_flow(self) -> Dict[str, Any]:
        """Initiate Auth0 device authorization flow."""
        device_code_url = f"https://{self.auth0_domain}/oauth/device/code"
        
        data = {
            "client_id": self.client_id,
            "scope": "openid profile email",
            "audience": self.audience
        }
        
        response = requests.post(device_code_url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    def poll_for_token(self, device_code: str, interval: int = 5) -> Dict[str, Any]:
        """Poll Auth0 for access token after user authorization."""
        token_url = f"https://{self.auth0_domain}/oauth/token"
        
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": self.client_id
        }
        
        while True:
            response = requests.post(token_url, data=data)
            
            if response.status_code == 200:
                return response.json()
            
            result = response.json()
            error = result.get("error")
            
            if error == "authorization_pending":
                print("⏳ Waiting for user authorization...")
                asyncio.sleep(interval)
                continue
            elif error == "slow_down":
                interval += 5
                asyncio.sleep(interval)
                continue
            elif error == "expired_token":
                raise Exception("❌ Authorization expired. Please run setup again.")
            elif error == "access_denied":
                raise Exception("❌ Access denied. User cancelled authorization.")
            else:
                raise Exception(f"❌ Token exchange failed: {error}")
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user profile information from Auth0."""
        userinfo_url = f"https://{self.auth0_domain}/userinfo"
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(userinfo_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def generate_mcp_config(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Claude Desktop MCP configuration."""
        omnispindle_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        
        config = {
            "mcpServers": {
                "omnispindle": {
                    "command": "python",
                    "args": ["stdio_main.py"],
                    "cwd": omnispindle_path,
                    "env": {
                        "MONGODB_URI": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
                        "MONGODB_DB": os.getenv("MONGODB_DB", "swarmonomicon"),
                        "OMNISPINDLE_TOOL_LOADOUT": "basic",
                        "MCP_USER_EMAIL": user_info.get("email"),
                        "MCP_USER_ID": user_info.get("sub")
                    }
                }
            }
        }
        
        return config
    
    def save_config(self, config: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Save MCP configuration to file."""
        if output_path is None:
            home_dir = os.path.expanduser("~")
            output_path = os.path.join(home_dir, "omnispindle_mcp_config.json")
        
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return output_path
    
    async def run_setup(self, save_config: bool = True) -> Dict[str, Any]:
        """Run the complete Auth0 setup flow."""
        print("🔐 Omnispindle Auth0 MCP Setup")
        print("=" * 40)
        print()
        
        try:
            # Start device flow
            print("📱 Starting Auth0 device authorization...")
            device_info = self.start_device_flow()
            
            # Show user instructions
            verification_uri = device_info["verification_uri_complete"]
            user_code = device_info["user_code"]
            
            print(f"🌐 Opening browser to: {verification_uri}")
            print(f"📝 Your code is: {user_code}")
            print()
            print("Please complete the authorization in your browser...")
            
            # Open browser
            webbrowser.open(verification_uri)
            
            # Poll for token
            print("⏳ Waiting for authorization...")
            token_info = self.poll_for_token(
                device_info["device_code"], 
                device_info.get("interval", 5)
            )
            
            # Get user info
            print("✅ Authorization successful! Getting user info...")
            user_info = self.get_user_info(token_info["access_token"])
            
            # Generate MCP config
            print("⚙️  Generating MCP configuration...")
            mcp_config = self.generate_mcp_config(user_info)
            
            # Display results
            print()
            print("🎉 Setup Complete!")
            print("=" * 40)
            print(f"👤 User: {user_info.get('email', 'Unknown')}")
            print(f"🆔 User ID: {user_info.get('sub', 'Unknown')}")
            print()
            
            if save_config:
                config_path = self.save_config(mcp_config)
                print(f"💾 Configuration saved to: {config_path}")
                print()
                print("📋 To use with Claude Desktop:")
                print(f"1. Copy the contents of {config_path}")
                print("2. Paste into your Claude Desktop settings")
                print("3. Restart Claude Desktop")
            else:
                print("📋 MCP Configuration:")
                print(json.dumps(mcp_config, indent=2))
            
            print()
            print("🚀 You're ready to use Omnispindle with MCP!")
            
            return {
                "user_info": user_info,
                "mcp_config": mcp_config,
                "config_path": config_path if save_config else None
            }
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            raise


async def main():
    """Main entry point for CLI setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup Auth0 authentication for Omnispindle MCP")
    parser.add_argument("--no-save", action="store_true", help="Don't save config file, just display")
    parser.add_argument("--output", "-o", help="Output path for config file")
    
    args = parser.parse_args()
    
    try:
        setup = Auth0CLISetup()
        result = await setup.run_setup(save_config=not args.no_save)
        
        if args.output and not args.no_save:
            setup.save_config(result["mcp_config"], args.output)
            print(f"💾 Config also saved to: {args.output}")
        
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())