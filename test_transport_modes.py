#!/usr/bin/env python3
"""
Test script to compare HTTP vs SSE transport modes for MCP timeout issues.
Run this to test which transport works better for your use case.
"""

import os
import asyncio
import time
from src.Omnispindle.tools import add_todo_tool

async def test_transport_mode(mode: str, timeout: int = 60):
    """Test a specific transport mode with given timeout"""
    print(f"\n=== Testing {mode.upper()} Transport Mode ===")
    
    # Set environment variables
    os.environ["MCP_TRANSPORT_MODE"] = mode
    os.environ["MCP_TOOL_TIMEOUT"] = str(timeout)
    
    try:
        from src.Omnispindle import run_server
        
        print(f"✓ Successfully imported server with {mode} transport")
        print(f"✓ Timeout set to {timeout} seconds")
        
        # Test a simple operation
        start_time = time.time()
        
        # Simulate a tool call that might take some time
        result = await add_todo_tool(
            description=f"Test todo for {mode} transport - {int(start_time)}",
            project="omnispindle",
            priority="medium"
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"✓ Tool call completed in {elapsed:.2f} seconds")
        print(f"✓ Result: {result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing {mode} transport: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🔧 MCP Transport Mode Timeout Test")
    print("=" * 50)
    
    # Test HTTP mode (recommended)
    http_success = await test_transport_mode("http", 60)
    
    # Test SSE mode (your current setup)
    sse_success = await test_transport_mode("sse", 60)
    
    print("\n" + "=" * 50)
    print("📊 RESULTS SUMMARY")
    print("=" * 50)
    print(f"HTTP Transport: {'✓ SUCCESS' if http_success else '✗ FAILED'}")
    print(f"SSE Transport:  {'✓ SUCCESS' if sse_success else '✗ FAILED'}")
    
    if http_success and not sse_success:
        print("\n💡 RECOMMENDATION: Switch to HTTP transport mode")
        print("   Add this to your .env file: MCP_TRANSPORT_MODE=http")
    elif not http_success and sse_success:
        print("\n💡 RECOMMENDATION: Keep SSE transport mode")
        print("   Your SSE setup is working correctly")
    elif http_success and sse_success:
        print("\n💡 RECOMMENDATION: Both modes work")
        print("   Consider HTTP for better scalability")
    else:
        print("\n⚠️  ISSUE: Both transports failed")
        print("   Check your server configuration and dependencies")

if __name__ == "__main__":
    asyncio.run(main()) 