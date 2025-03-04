#!/usr/bin/env python3
"""
MCP Server Integration for Node-RED MQTT Status Dashboard
This script helps deploy the MQTT Status Dashboard to a Node-RED instance
and integrates it with the MCP system.
"""

import os
import sys
import json
import argparse
import subprocess
import requests
from pathlib import Path

# Default values
DEFAULT_NODERED_URL = "http://localhost:1880"
DEFAULT_MCP_URL = "http://localhost:8000"

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Deploy MQTT Status Dashboard to Node-RED")
    parser.add_argument("--node-red-url", default=DEFAULT_NODERED_URL,
                      help=f"Node-RED server URL (default: {DEFAULT_NODERED_URL})")
    parser.add_argument("--username", help="Node-RED username (if authentication is enabled)")
    parser.add_argument("--password", help="Node-RED password (if authentication is enabled)")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL,
                      help=f"MCP server URL (default: {DEFAULT_MCP_URL})")
    parser.add_argument("--mcp-api-key", help="MCP API key (if required)")
    parser.add_argument("--skip-mcp", action="store_true",
                      help="Skip MCP integration and only deploy to Node-RED")

    return parser.parse_args()

def deploy_to_nodered(node_red_url, username=None, password=None):
    """Deploy the MQTT Status Dashboard to Node-RED"""
    # Get the directory of this script
    script_dir = Path(__file__).parent.absolute()

    # Path to the deployment script
    deploy_script = script_dir / "deploy_to_nodered.sh"

    # Ensure the script is executable
    os.chmod(deploy_script, 0o755)

    # Build the command
    cmd = [str(deploy_script)]

    # Add parameters
    cmd.append(node_red_url)
    if username and password:
        cmd.append(username)
        cmd.append(password)

    # Execute the deployment script
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error deploying to Node-RED: {e}", file=sys.stderr)
        print(e.stdout)
        print(e.stderr)
        return False

def register_with_mcp(mcp_url, api_key=None, node_red_url=DEFAULT_NODERED_URL):
    """Register the dashboard with the MCP server"""
    headers = {"Content-Type": "application/json"}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Dashboard information
    dashboard_data = {
        "name": "MQTT Device Status Dashboard",
        "description": "Dashboard showing status lights for device availability",
        "url": f"{node_red_url}/ui",
        "type": "node-red-dashboard",
        "tags": ["mqtt", "status", "dashboard"]
    }

    try:
        # Check if MCP API has a dashboard registration endpoint
        # This is an example - adjust to your actual MCP API structure
        response = requests.post(
            f"{mcp_url}/api/dashboards",
            headers=headers,
            json=dashboard_data
        )

        if response.status_code in (200, 201):
            print(f"Successfully registered dashboard with MCP: {response.json()}")
            return True
        else:
            print(f"Failed to register with MCP: {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        print(f"Error connecting to MCP server: {e}")
        return False

def main():
    """Main function"""
    args = parse_args()

    # Deploy to Node-RED
    print(f"Deploying to Node-RED at {args.node_red_url}...")
    deploy_success = deploy_to_nodered(
        args.node_red_url,
        args.username,
        args.password
    )

    if not deploy_success:
        print("Failed to deploy to Node-RED")
        sys.exit(1)

    # Register with MCP if not skipped
    if not args.skip_mcp:
        print(f"Registering with MCP server at {args.mcp_url}...")
        mcp_success = register_with_mcp(
            args.mcp_url,
            args.mcp_api_key,
            args.node_red_url
        )

        if not mcp_success:
            print("Warning: Failed to register with MCP server")

    print("\nSetup complete!")
    print(f"Access the dashboard at: {args.node_red_url}/ui")

if __name__ == "__main__":
    main()
