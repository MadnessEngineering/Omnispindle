import logging
import inspect
import importlib
import functools
import asyncio
import sys
from typing import Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

def apply_patches():
    """
    Apply monkey patches to external libraries to fix common errors.
    """
    logger.info("Applying monkey patches to external libraries")
    
    # Patch Starlette routing - be more careful about checking first
    try:
        import starlette.routing
        
        # Check if Route.app exists before trying to patch it
        if hasattr(starlette.routing.Route, "app") and callable(starlette.routing.Route.app):
            # Save original functions
            original_app = starlette.routing.Route.app
            
            @functools.wraps(original_app)
            def patched_app(self, scope, receive, send):
                @functools.wraps(self.endpoint)
                async def safe_endpoint(request):
                    try:
                        response = await self.endpoint(request)
                        if response is None:
                            logger.warning(f"Route '{scope.get('path', 'unknown')}' returned None; returning 204 No Content")
                            from starlette.responses import Response
                            return Response(status_code=204)
                        return response
                    except Exception as e:
                        logger.exception(f"Error in endpoint: {str(e)}")
                        from starlette.responses import JSONResponse
                        return JSONResponse(
                            status_code=500,
                            content={"error": f"Internal server error: {str(e)}"}
                        )
                
                return starlette.routing.get_handle(safe_endpoint)(scope, receive, send)
            
            # Apply patches
            starlette.routing.Route.app = patched_app
            logger.info("Patched starlette.routing.Route.app")
        else:
            logger.info("starlette.routing.Route.app not found or not callable - skipping patch")
        
        # Patch Starlette's _exception_handler.py (which is causing the errors)
        import starlette._exception_handler
        
        original_wrapped_app = starlette._exception_handler.wrapped_app
        
        @functools.wraps(original_wrapped_app)
        async def patched_wrapped_app(app, conn, scope, receive, sender):
            try:
                return await original_wrapped_app(app, conn, scope, receive, sender)
            except TypeError as e:
                if "'NoneType' object is not callable" in str(e):
                    logger.warning(f"Caught NoneType error in _exception_handler: {str(e)}")
                    # Send a fallback response 
                    await sender({
                        "type": "http.response.start",
                        "status": 204,
                        "headers": [(b"content-type", b"text/plain")]
                    })
                    await sender({
                        "type": "http.response.body",
                        "body": b"",
                        "more_body": False
                    })
                else:
                    raise
            except Exception as e:
                logger.exception(f"Unhandled exception in patched wrapped_app: {str(e)}")
                raise
        
        # Replace wrapped_app with our patched version
        starlette._exception_handler.wrapped_app = patched_wrapped_app
        logger.info("Patched starlette._exception_handler.wrapped_app")
        
    except Exception as e:
        logger.error(f"Failed to apply Starlette patches: {str(e)}")
    
    # Patch MCP's SSE module to properly handle client disconnects
    try:
        import mcp.server.sse
        import sse_starlette
        from sse_starlette.sse import EventSourceResponse
        
        # The original EventSourceResponse function doesn't handle disconnects well
        # Let's patch the SseServerTransport to manage this better
        
        # Store original method
        original_connect_sse = mcp.server.sse.SseServerTransport.connect_sse
        
        # Patch the connect_sse method to handle disconnects better
        @asynccontextmanager
        async def patched_connect_sse(self, scope, receive, send):
            # Log the client connecting
            client = scope.get("client", ("unknown", 0))
            logger.debug(f"SSE client connected: {client[0]}:{client[1]}")
            
            # Add better error handling
            try:
                async with original_connect_sse(self, scope, receive, send) as result:
                    yield result
            except asyncio.CancelledError:
                logger.debug(f"SSE client disconnected (CancelledError): {client[0]}:{client[1]}")
                # Don't re-raise, just end gracefully
            except Exception as e:
                logger.warning(f"SSE client error: {client[0]}:{client[1]} - {type(e).__name__}: {str(e)}")
                # Still don't re-raise, exit gracefully
            
            logger.debug(f"SSE connection closed for {client[0]}:{client[1]}")
        
        # Apply the patch
        mcp.server.sse.SseServerTransport.connect_sse = patched_connect_sse
        logger.info("Patched mcp.server.sse.SseServerTransport.connect_sse")
        
        # Next, let's enhance the EventSourceResponse creation to handle disconnects better
        original_event_source_sse = sse_starlette.sse.EventSourceResponse
        
        class EnhancedEventSourceResponse(EventSourceResponse):
            """Enhanced version of EventSourceResponse that handles disconnections better"""
            
            async def __call__(self, scope, receive, send):
                """Override to add better client disconnect handling"""
                client = scope.get("client", ("unknown", 0))
                logger.debug(f"Starting SSE stream for client: {client[0]}:{client[1]}")
                
                try:
                    # Call original method with better error handling
                    return await super().__call__(scope, receive, send)
                except asyncio.CancelledError:
                    logger.debug(f"SSE stream cancelled for client: {client[0]}:{client[1]}")
                    # Don't raise, handle gracefully
                    return None
                except TypeError as e:
                    if "'NoneType' object is not callable" in str(e):
                        logger.debug(f"SSE NoneType error for client: {client[0]}:{client[1]}")
                        # Most common error when client disconnects, suppress it
                        return None
                    raise
                except Exception as e:
                    logger.warning(f"SSE error for client {client[0]}:{client[1]}: {type(e).__name__}: {str(e)}")
                    raise
                finally:
                    logger.debug(f"SSE stream closed for client: {client[0]}:{client[1]}")
        
        # Patch the original class
        sse_starlette.sse.EventSourceResponse = EnhancedEventSourceResponse
        
        # Also need to update the module's EventSourceResponse
        sys.modules['sse_starlette'].EventSourceResponse = EnhancedEventSourceResponse
        logger.info("Patched sse_starlette.sse.EventSourceResponse")
        
    except Exception as e:
        logger.error(f"Failed to apply MCP SSE patches: {str(e)}")
    
    logger.info("Finished applying monkey patches") 
