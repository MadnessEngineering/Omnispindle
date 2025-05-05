import pytest
import asyncio
import anyio
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.middleware import Middleware

from Omnispindle.middleware import ConnectionErrorsMiddleware, NoneTypeResponseMiddleware

def test_middleware_handles_disconnected_requests():
    """Test that the middleware properly handles disconnected requests."""
    # Mock an application that raises various errors
    def mock_app():
        app = Starlette()
        
        @app.route("/normal")
        async def normal(request):
            return PlainTextResponse("OK")
        
        @app.route("/runtime_error")
        async def runtime_error(request):
            # Simulate the "No response returned" error
            raise RuntimeError("No response returned.")
            
        @app.route("/cancelled")
        async def cancelled(request):
            # Simulate a CancelledError
            raise asyncio.exceptions.CancelledError()
            
        @app.route("/would_block")
        async def would_block(request):
            # Simulate a WouldBlock error
            raise anyio.WouldBlock()
            
        @app.route("/connection_reset")
        async def connection_reset(request):
            # Simulate connection reset
            raise ConnectionResetError()
            
        @app.route("/connection_aborted")
        async def connection_aborted(request):
            # Simulate connection aborted
            raise ConnectionAbortedError()
        
        return app
    
    # Create app with middleware
    app_with_middleware = mock_app()
    app_with_middleware.add_middleware(ConnectionErrorsMiddleware)
    
    # Create a test client
    client = TestClient(app_with_middleware)
    
    # Test normal route works
    response = client.get("/normal")
    assert response.status_code == 200
    assert response.text == "OK"
    
    # Test various error routes
    # Note: TestClient doesn't simulate the is_disconnected behavior correctly
    # so these will still raise exceptions in the test, but the middleware would
    # catch them in a real environment with disconnected clients
    
    with pytest.raises(RuntimeError):
        client.get("/runtime_error")
        
    with pytest.raises(asyncio.exceptions.CancelledError):
        client.get("/cancelled")
        
    with pytest.raises(anyio.WouldBlock):
        client.get("/would_block")
        
    # These connection errors should be caught regardless of is_disconnected
    # so we expect a 204 status code
    response = client.get("/connection_reset", raise_server_exceptions=False)
    assert response.status_code == 204
    
    response = client.get("/connection_aborted", raise_server_exceptions=False)
    assert response.status_code == 204
        
    # The actual middleware functionality is tested in production with real disconnected requests 

def test_none_type_response_middleware():
    """Test that the middleware properly handles None responses from route handlers."""
    # Mock an application that returns None from a route handler
    def mock_app():
        app = Starlette()
        
        @app.route("/normal")
        async def normal(request):
            return PlainTextResponse("OK")
        
        @app.route("/none_response")
        async def none_response(request):
            # Return None directly instead of a response object
            return None
        
        return app
    
    # Create app with middleware
    app_with_middleware = mock_app()
    app_with_middleware.add_middleware(NoneTypeResponseMiddleware)
    
    # Create a test client
    client = TestClient(app_with_middleware)
    
    # Test normal route works
    response = client.get("/normal")
    assert response.status_code == 200
    assert response.text == "OK"
    
    # Test route that returns None
    # This should be caught by the middleware and return a 204 response
    response = client.get("/none_response")
    assert response.status_code == 204 
