#!/usr/bin/env python3
"""
Test script for the MCP device status tool.
This demonstrates how to use the update_device_status_tool to control the MQTT dashboard.
"""

import argparse
import asyncio
import json
import random
import sys
import time
from urllib.parse import urljoin
import aiohttp

# Default MCP server URL
DEFAULT_MCP_URL = "http://localhost:8000"

async def update_device_status(session, mcp_url, device_name, status):
    """
    Call the MCP update_device_status_tool to update device status
    """
    endpoint = urljoin(mcp_url, "/api/tool/update_device_status_tool")
    
    payload = {
        "device_name": device_name,
        "status": status
    }
    
    async with session.post(endpoint, json=payload) as response:
        if response.status != 200:
            print(f"Error updating device status: HTTP {response.status}")
            return None
        
        result = await response.json()
        return result

async def simulate_devices(mcp_url, devices, iterations=30, interval=5):
    """
    Simulate multiple devices changing status
    """
    async with aiohttp.ClientSession() as session:
        print(f"Starting device simulation with {len(devices)} devices")
        print(f"Will run for {iterations} iterations with {interval} seconds between updates")
        
        # Initial status - all devices online
        for device in devices:
            result = await update_device_status(session, mcp_url, device, True)
            if result:
                print(f"✅ Initialized {device}: {result}")
        
        # Run simulation for specified iterations
        for i in range(iterations):
            await asyncio.sleep(interval)
            
            # Pick a random device
            device = random.choice(devices)
            
            # Random status (80% chance of being online)
            status = random.random() > 0.2
            
            # Update the device status
            result = await update_device_status(session, mcp_url, device, status)
            if result:
                print(f"{'✅' if status else '❌'} Update {i+1}/{iterations}: {result}")
            
        # Final status - return all to online
        print("\nResetting all devices to online...")
        for device in devices:
            await update_device_status(session, mcp_url, device, True)
        
        print("Simulation complete!")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test MCP device status updates")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL,
                      help=f"MCP server URL (default: {DEFAULT_MCP_URL})")
    parser.add_argument("--devices", nargs="+", default=["device1", "sensor01", "gateway", "camera"],
                      help="Device names to simulate (default: device1 sensor01 gateway camera)")
    parser.add_argument("--iterations", type=int, default=30,
                      help="Number of status changes to simulate (default: 30)")
    parser.add_argument("--interval", type=int, default=5,
                      help="Seconds between status updates (default: 5)")
    
    return parser.parse_args()

async def main():
    """Main execution function"""
    args = parse_args()
    
    print(f"MCP Server: {args.mcp_url}")
    print(f"Devices: {args.devices}")
    
    await simulate_devices(
        args.mcp_url,
        args.devices,
        args.iterations,
        args.interval
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulation stopped by user")
        sys.exit(0) 
