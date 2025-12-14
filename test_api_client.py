#!/usr/bin/env python3
"""
Test script for the new API client functionality.
Tests both direct API calls and hybrid mode operations.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.Omnispindle.api_client import MadnessAPIClient
from src.Omnispindle import hybrid_tools
from src.Omnispindle.context import Context

async def test_api_client_direct():
    """Test direct API client functionality"""
    print("=== Testing Direct API Client ===")
    
    # Use environment variables or defaults for testing
    api_url = os.getenv("MADNESS_API_URL", "https://madnessinteractive.cc/api")
    auth_token = os.getenv("MADNESS_AUTH_TOKEN")
    api_key = os.getenv("MADNESS_API_KEY")
    
    print(f"Testing API at: {api_url}")
    print(f"Auth token: {'Present' if auth_token else 'Not set'}")
    print(f"API key: {'Present' if api_key else 'Not set'}")
    
    async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
        # Test 1: Health check
        print("\n1. Testing health check...")
        health_response = await client.health_check()
        print(f"Health check result: {health_response.success}")
        if health_response.success:
            print(f"Health data: {health_response.data}")
        else:
            print(f"Health check error: {health_response.error}")
        
        # Test 2: Get todos
        print("\n2. Testing get todos...")
        todos_response = await client.get_todos(limit=5)
        print(f"Get todos result: {todos_response.success}")
        if todos_response.success and todos_response.data:
            todos_data = todos_response.data
            if isinstance(todos_data, dict) and 'todos' in todos_data:
                todo_count = len(todos_data['todos'])
                print(f"Found {todo_count} todos")
                if todo_count > 0:
                    print(f"First todo: {todos_data['todos'][0].get('description', 'No description')}")
            else:
                print(f"Unexpected todos data format: {type(todos_data)}")
        else:
            print(f"Get todos error: {todos_response.error}")
        
        # Test 3: Create a test todo (only if we have write access)
        if auth_token or api_key:
            print("\n3. Testing create todo...")
            create_response = await client.create_todo(
                description="API Client Test Todo",
                project="omnispindle",
                priority="Low",
                metadata={"test": True, "source": "api_client_test"}
            )
            print(f"Create todo result: {create_response.success}")
            if create_response.success:
                print(f"Created todo data: {create_response.data}")
                
                # Test 4: Get the created todo
                if isinstance(create_response.data, dict):
                    todo_data = create_response.data.get('todo', create_response.data.get('data'))
                    if todo_data and 'id' in todo_data:
                        todo_id = todo_data['id']
                        print(f"\n4. Testing get specific todo: {todo_id}")
                        get_response = await client.get_todo(todo_id)
                        print(f"Get specific todo result: {get_response.success}")
                        if get_response.success:
                            print(f"Retrieved todo: {get_response.data.get('description')}")
                        else:
                            print(f"Get specific todo error: {get_response.error}")
                        
                        # Test 5: Complete the todo
                        print(f"\n5. Testing complete todo: {todo_id}")
                        complete_response = await client.complete_todo(todo_id, "Test completion via API client")
                        print(f"Complete todo result: {complete_response.success}")
                        if not complete_response.success:
                            print(f"Complete todo error: {complete_response.error}")
            else:
                print(f"Create todo error: {create_response.error}")
        else:
            print("\n3-5. Skipping write operations (no authentication)")

async def test_hybrid_mode():
    """Test hybrid mode functionality"""
    print("\n\n=== Testing Hybrid Mode ===")
    
    # Create a test context
    test_user = {"sub": "test_user", "email": "test@example.com"}
    if os.getenv("MADNESS_AUTH_TOKEN"):
        test_user["access_token"] = os.getenv("MADNESS_AUTH_TOKEN")
    if os.getenv("MADNESS_API_KEY"):
        test_user["api_key"] = os.getenv("MADNESS_API_KEY")
    
    ctx = Context(user=test_user)
    
    # Test 1: Get hybrid status
    print("\n1. Testing get hybrid status...")
    status_result = await hybrid_tools.get_hybrid_status(ctx=ctx)
    print(f"Hybrid status result: {status_result}")
    
    # Test 2: Test API connectivity
    print("\n2. Testing API connectivity...")
    connectivity_result = await hybrid_tools.test_api_connectivity(ctx=ctx)
    print(f"API connectivity result: {connectivity_result}")
    
    # Test 3: Query todos via hybrid mode
    print("\n3. Testing hybrid query todos...")
    query_result = await hybrid_tools.query_todos(limit=3, ctx=ctx)
    print(f"Hybrid query todos result: {'Success' if 'success' in query_result and json.loads(query_result)['success'] else 'Failed'}")
    
    # Test 4: Create a todo via hybrid mode (if authenticated)
    if test_user.get("access_token") or test_user.get("api_key"):
        print("\n4. Testing hybrid add todo...")
        add_result = await hybrid_tools.add_todo(
            description="Hybrid Mode Test Todo",
            project="omnispindle", 
            priority="Low",
            metadata={"test": True, "source": "hybrid_test"},
            ctx=ctx
        )
        print(f"Hybrid add todo result: {'Success' if 'success' in add_result else 'Failed'}")
        print(f"Add result details: {add_result[:200]}...")
    else:
        print("\n4. Skipping hybrid add todo (no authentication)")

async def main():
    """Main test function"""
    print("Starting Omnispindle API Client Tests")
    print("=" * 50)
    
    try:
        await test_api_client_direct()
        await test_hybrid_mode()
        
        print("\n" + "=" * 50)
        print("Tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    import json
    exit_code = asyncio.run(main())
    sys.exit(exit_code)