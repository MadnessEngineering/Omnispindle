#!/usr/bin/env python3
"""
Deploys the MQTT Status Dashboard to Node-RED using the MCP deploy_nodered_flow_tool
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urljoin
import aiohttp

# Default MCP server URL
DEFAULT_MCP_URL = "http://localhost:8000"
DEFAULT_NODERED_URL = "http://localhost:1880"

async def deploy_flow_via_mcp(session, mcp_url, flow_json, node_red_url, username=None, password=None):
    """
    Call the MCP deploy_nodered_flow_tool to deploy a flow
    """
    endpoint = urljoin(mcp_url, "/api/tool/deploy_nodered_flow_tool")
    
    payload = {
        "flow_json": flow_json,
        "node_red_url": node_red_url
    }
    
    if username:
        payload["username"] = username
    
    if password:
        payload["password"] = password
    
    async with session.post(endpoint, json=payload) as response:
        if response.status != 200:
            print(f"Error deploying flow: HTTP {response.status}")
            try:
                error_text = await response.text()
                print(f"Error details: {error_text}")
            except:
                pass
            return None
        
        result = await response.json()
        return result

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Deploy Node-RED flow via MCP")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL,
                      help=f"MCP server URL (default: {DEFAULT_MCP_URL})")
    parser.add_argument("--node-red-url", default=DEFAULT_NODERED_URL,
                      help=f"Node-RED URL (default: {DEFAULT_NODERED_URL})")
    parser.add_argument("--flow-file", default="mqtt_status_lights.json",
                      help="JSON file containing the flow definition (default: mqtt_status_lights.json)")
    parser.add_argument("--username", help="Username for Node-RED authentication")
    parser.add_argument("--password", help="Password for Node-RED authentication")
    
    return parser.parse_args()

async def main():
    """Main execution function"""
    args = parse_args()
    
    # Get the path to the flow file
    script_dir = Path(__file__).parent.absolute()
    flow_file = script_dir / args.flow_file
    
    if not flow_file.exists():
        print(f"Error: Flow file {flow_file} not found")
        sys.exit(1)
    
    # Load the flow JSON
    try:
        with open(flow_file, 'r') as f:
            flow_json = json.load(f)
    except Exception as e:
        print(f"Error loading flow file: {e}")
        sys.exit(1)
    
    print(f"Deploying flow from {flow_file} to Node-RED at {args.node_red_url} via MCP at {args.mcp_url}")
    
    async with aiohttp.ClientSession() as session:
        result = await deploy_flow_via_mcp(
            session, 
            args.mcp_url, 
            flow_json, 
            args.node_red_url,
            args.username,
            args.password
        )
        
        if result:
            if result.get("success"):
                print(f"✅ Flow deployed successfully! Operation: {result.get('operation')}")
                print(f"   Flow ID: {result.get('flow_id')}")
                print(f"   Flow Label: {result.get('flow_label')}")
                print(f"   Dashboard URL: {result.get('dashboard_url')}")
            else:
                print(f"❌ Flow deployment failed: {result.get('error')}")
        else:
            print("❌ Failed to get a response from MCP")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation canceled by user")
        sys.exit(0) 
