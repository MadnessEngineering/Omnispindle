#!/usr/bin/env python3
"""
Test script for the new Omnispindle tools: point_out_obvious and bring_your_own
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from Omnispindle import tools
from Omnispindle.context import Context


async def test_point_out_obvious():
    """Test the point_out_obvious tool with various sarcasm levels"""
    print("\n=== Testing point_out_obvious tool ===\n")
    
    ctx = Context(user={"sub": "test_user"})
    
    # Test different sarcasm levels
    test_cases = [
        ("water is wet", 1),
        ("the sky is blue", 5),
        ("computers need electricity", 8),
        ("AI models can't actually think", 10),
    ]
    
    for observation, sarcasm_level in test_cases:
        print(f"\nObservation: '{observation}' (Sarcasm Level: {sarcasm_level})")
        result = await tools.point_out_obvious(observation, sarcasm_level, ctx)
        result_dict = json.loads(result)
        
        if result_dict.get("success"):
            print(f"Response: {result_dict['data']['response']}")
            print(f"Obviousness Score: {result_dict['data']['meta']['obviousness_score']}")
        else:
            print(f"Error: {result_dict.get('message')}")


async def test_bring_your_own():
    """Test the bring_your_own tool with different runtime environments"""
    print("\n=== Testing bring_your_own tool ===\n")
    
    ctx = Context(user={"sub": "admin_test"})
    
    # Test 1: Python runtime
    print("\n1. Testing Python runtime:")
    python_code = """
async def main(name="World", count=1):
    result = []
    for i in range(count):
        result.append(f"Hello, {name}! (iteration {i+1})")
    return {"messages": result, "total": count}
"""
    
    result = await tools.bring_your_own(
        tool_name="hello_world",
        code=python_code,
        runtime="python",
        timeout=5,
        args={"name": "Omnispindle", "count": 3},
        persist=False,
        ctx=ctx
    )
    result_dict = json.loads(result)
    
    if result_dict.get("success"):
        print(f"Tool ID: {result_dict['data']['tool_id']}")
        print(f"Result: {result_dict['data']['result']}")
    else:
        print(f"Error: {result_dict.get('message')}")
    
    # Test 2: Bash runtime
    print("\n2. Testing Bash runtime:")
    bash_code = "echo 'System info:'; uname -a; echo 'Current directory:'; pwd"
    
    result = await tools.bring_your_own(
        tool_name="system_info",
        code=bash_code,
        runtime="bash",
        timeout=5,
        args=None,
        persist=False,
        ctx=ctx
    )
    result_dict = json.loads(result)
    
    if result_dict.get("success"):
        print(f"Tool ID: {result_dict['data']['tool_id']}")
        print(f"Result:\n{result_dict['data']['result']}")
    else:
        print(f"Error: {result_dict.get('message')}")
    
    # Test 3: JavaScript runtime (if Node.js is available)
    print("\n3. Testing JavaScript runtime:")
    js_code = """
function main(args) {
    const greeting = args.greeting || 'Hello';
    const target = args.target || 'World';
    return {
        message: `${greeting}, ${target}!`,
        timestamp: new Date().toISOString(),
        platform: 'Node.js'
    };
}
"""
    
    result = await tools.bring_your_own(
        tool_name="js_greeting",
        code=js_code,
        runtime="javascript",
        timeout=5,
        args={"greeting": "Greetings", "target": "MCP Server"},
        persist=False,
        ctx=ctx
    )
    result_dict = json.loads(result)
    
    if result_dict.get("success"):
        print(f"Tool ID: {result_dict['data']['tool_id']}")
        print(f"Result: {result_dict['data']['result']}")
    else:
        print(f"Error: {result_dict.get('message')}")
    
    # Test 4: Test with persistence
    print("\n4. Testing tool persistence:")
    persistent_code = """
async def main(message="Default message"):
    return f"Persistent tool says: {message}"
"""
    
    result = await tools.bring_your_own(
        tool_name="persistent_test",
        code=persistent_code,
        runtime="python",
        timeout=5,
        args={"message": "This tool was saved!"},
        persist=True,  # Save for future use
        ctx=ctx
    )
    result_dict = json.loads(result)
    
    if result_dict.get("success"):
        print(f"Tool ID: {result_dict['data']['tool_id']}")
        print(f"Result: {result_dict['data']['result']}")
        print(f"Persisted: {result_dict['data']['persisted']}")
    else:
        print(f"Error: {result_dict.get('message')}")
    
    # Test 5: Test rate limiting (for non-admin users)
    print("\n5. Testing rate limiting:")
    non_admin_ctx = Context(user={"sub": "regular_user"})
    
    for i in range(3):
        print(f"\nAttempt {i+1}:")
        result = await tools.bring_your_own(
            tool_name="rate_test",
            code="async def main(): return 'test'",
            runtime="python",
            timeout=5,
            ctx=non_admin_ctx
        )
        result_dict = json.loads(result)
        
        if result_dict.get("success"):
            print(f"Success: {result_dict['data']['result']}")
        else:
            print(f"Rate limited: {result_dict.get('message')}")
        
        if i < 2:
            await asyncio.sleep(1)  # Short delay between attempts


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing New Omnispindle Tools")
    print("=" * 60)
    
    try:
        await test_point_out_obvious()
        await test_bring_your_own()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 
