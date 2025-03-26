import asyncio
import json
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from starlette.testclient import TestClient
import logging

# Add src to path so we can import server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from fastmcp_todo_server.server import Omnispindle


class TestOmnispindle:
    """Test cases for the Omnispindle class"""

    @pytest.fixture
    def server(self):
        """Creates a test server instance"""
        return Omnispindle(name="test-server", server_type="sse")

    @pytest.fixture
    def mock_publish_status(self):
        """Creates a mock publish_mqtt_status function"""
        async def _mock_publish(topic, message, retain=False):
            return True
        return _mock_publish

    @pytest.mark.asyncio
    async def test_run_server_handles_none_return(self, server, mock_publish_status):
        """Test that run_server properly handles when run_sse_async returns None"""
        
        # Mock the run_sse_async method to return None
        with patch.object(server, 'run_sse_async', new_callable=AsyncMock) as mock_run_sse:
            mock_run_sse.return_value = None
            
            # Call run_server
            app = await server.run_server(mock_publish_status)
            
            # Verify run_sse_async was called
            mock_run_sse.assert_called_once()
            
            # Verify app is not None
            assert app is not None
            
            # Test that the dummy app is callable with ASGI signature
            async def receive():
                return {"type": "http.request"}
                
            async def send(message):
                # Verify message structure for response
                if message["type"] == "http.response.start":
                    assert message["status"] == 503
                    assert any(h[0] == b"content-type" for h in message["headers"])
                    assert any(h[0] == b"x-fallback-app" for h in message["headers"])
            
            # Simulate HTTP request to dummy app
            scope = {"type": "http", "path": "/test"}
            await app(scope, receive, send)

    @pytest.mark.asyncio
    async def test_dummy_app_lifespan_protocol(self, server, mock_publish_status):
        """Test that the dummy app properly handles lifespan protocol messages"""
        
        # Mock the run_sse_async method to return None
        with patch.object(server, 'run_sse_async', new_callable=AsyncMock) as mock_run_sse:
            mock_run_sse.return_value = None
            
            # Call run_server to get the dummy app
            app = await server.run_server(mock_publish_status)
            
            # Prepare mock functions for ASGI interface
            messages_received = []
            
            async def receive():
                # First return startup, then shutdown
                if not messages_received:
                    messages_received.append("startup")
                    return {"type": "lifespan.startup"}
                else:
                    return {"type": "lifespan.shutdown"}
                
            messages_sent = []
            async def send(message):
                messages_sent.append(message)
            
            # Test lifespan protocol
            scope = {"type": "lifespan"}
            await app(scope, receive, send)
            
            # Verify the correct responses were sent
            assert len(messages_sent) == 2
            assert messages_sent[0]["type"] == "lifespan.startup.complete"
            assert messages_sent[1]["type"] == "lifespan.shutdown.complete"

    @pytest.mark.asyncio
    async def test_dummy_app_websocket_protocol(self, server, mock_publish_status):
        """Test that the dummy app properly handles websocket protocol messages"""
        
        # Mock the run_sse_async method to return None
        with patch.object(server, 'run_sse_async', new_callable=AsyncMock) as mock_run_sse:
            mock_run_sse.return_value = None
            
            # Call run_server to get the dummy app
            app = await server.run_server(mock_publish_status)
            
            # Prepare mock functions for ASGI interface
            async def receive():
                return {"type": "websocket.connect"}
                
            messages_sent = []
            async def send(message):
                messages_sent.append(message)
            
            # Test websocket protocol
            scope = {"type": "websocket", "path": "/ws"}
            await app(scope, receive, send)
            
            # Verify the close message was sent with correct code
            assert len(messages_sent) == 1
            assert messages_sent[0]["type"] == "websocket.close"
            assert messages_sent[0]["code"] == 1013  # Try again later

    @pytest.mark.asyncio
    async def test_run_server_returns_app_when_run_sse_async_succeeds(self, server, mock_publish_status):
        """Test that run_server returns the app from run_sse_async when it's not None"""
        
        # Create a mock ASGI app
        async def mock_asgi_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"success"})
        
        # Mock the run_sse_async method to return the mock app
        with patch.object(server, 'run_sse_async', new_callable=AsyncMock) as mock_run_sse:
            mock_run_sse.return_value = mock_asgi_app
            
            # Call run_server
            app = await server.run_server(mock_publish_status)
            
            # Verify run_sse_async was called
            mock_run_sse.assert_called_once()
            
            # Verify app is the same as the mock app
            assert app is mock_asgi_app 
