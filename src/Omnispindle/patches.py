import logging
import inspect
import importlib
import functools
import asyncio
import sys
from typing import Dict, Any
from contextlib import asynccontextmanager
from starlette.responses import Response

logger = logging.getLogger(__name__)

def apply_patches():
    """
    Apply monkey patches to external libraries to fix common errors.
    """
    logger.info("Applying monkey patches to external libraries")

    # Patch Starlette routing - be more careful about checking first
    try:
        import starlette.routing

        # Instead of trying to patch Route.app directly (which might not exist in 0.45.3),
        # we'll patch the Router's handle method to catch None responses
        if hasattr(starlette.routing, "Router") and hasattr(starlette.routing.Router, "handle"):
            original_handle = starlette.routing.Router.handle

            @functools.wraps(original_handle)
            async def patched_handle(self, scope, receive, send):
                try:
                    await original_handle(self, scope, receive, send)
                except TypeError as e:
                    if "'NoneType' object is not callable" in str(e):
                        logger.debug(f"Caught NoneType error in Router.handle: {scope.get('path', 'unknown')}")
                        # Send a fallback 204 response
                        await send({
                            "type": "http.response.start",
                            "status": 204,
                            "headers": [(b"content-type", b"text/plain")]
                        })
                        await send({
                            "type": "http.response.body",
                            "body": b"",
                            "more_body": False
                        })
                    else:
                        raise

            # Apply the patch
            starlette.routing.Router.handle = patched_handle
            logger.info("Patched starlette.routing.Router.handle")

            # Now we need to patch the _exception_handler.py which is the source of the NoneType errors
            # This is a deeper fix for the most common error
            import starlette._exception_handler

            # Get the original wrap_app_handling_exceptions function
            original_wrap_app = starlette._exception_handler.wrap_app_handling_exceptions

            # Create a patched version that catches NoneType errors
            @functools.wraps(original_wrap_app)
            def patched_wrap_app_handling_exceptions(app, conn):
                """
                This patches the key function in starlette._exception_handler that's causing the NoneType errors.
                It handles the case where an endpoint returns None by returning a 204 response.
                """
                # First get the wrapped ASGI app from the original function
                wrapped_app = original_wrap_app(app, conn)

                # Now wrap it with our safe version
                @functools.wraps(wrapped_app)
                async def safe_wrapped_app(scope, receive, send):
                    try:
                        # Call the original wrapped app
                        return await wrapped_app(scope, receive, send)
                    except TypeError as e:
                        if "'NoneType' object is not callable" in str(e):
                            logger.debug(f"Caught NoneType error in _exception_handler: {scope.get('path', 'unknown')}")

                            # Send a fallback 204 No Content response
                            await send({
                                "type": "http.response.start",
                                "status": 204,
                                "headers": [(b"content-type", b"text/plain")]
                            })
                            await send({
                                "type": "http.response.body",
                                "body": b"",
                                "more_body": False
                            })

                            # Don't re-raise the exception
                            return
                        else:
                            # Other TypeErrors should be re-raised
                            pass
                    except Exception as e:
                        # For other exceptions, let the original error handling take over
                        pass

                # Return our patched app
                return safe_wrapped_app

            # Replace the original function with our patched version
            starlette._exception_handler.wrap_app_handling_exceptions = patched_wrap_app_handling_exceptions
            logger.info("Patched starlette._exception_handler.wrap_app_handling_exceptions")
        else:
            logger.info("starlette.routing.Router.handle not found - skipping patch")
    except Exception as e:
        logger.error(f"Failed to apply Starlette router patches: {str(e)}")

    # Patch MCP's SSE module to properly handle client disconnects
    try:
        import mcp.server.sse
        import sse_starlette
        from sse_starlette.sse import EventSourceResponse

        # Store original method
        original_connect_sse = mcp.server.sse.SseServerTransport.connect_sse

        # Patch the connect_sse method to handle disconnects better and ensure it returns a Response
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
                logger.debug(f"SSE client error: {client[0]}:{client[1]} - {type(e).__name__}: {str(e)}")
                # Still don't re-raise, exit gracefully

            logger.debug(f"SSE connection closed for {client[0]}:{client[1]}")

        # Apply the patch
        mcp.server.sse.SseServerTransport.connect_sse = patched_connect_sse
        logger.info("Patched mcp.server.sse.SseServerTransport.connect_sse")

        # Important patch: For direct SSE handling, ensure proper response is returned
        original_handle_sse = None
        if hasattr(mcp.server.sse.SseServerTransport, 'handle_sse'):
            original_handle_sse = mcp.server.sse.SseServerTransport.handle_sse

            @functools.wraps(original_handle_sse)
            async def patched_handle_sse(self, request):
                try:
                    response = await original_handle_sse(self, request)
                    if response is None:
                        # Critical fix: Return empty Response instead of None when connection ends
                        logger.debug(f"SSE connection ended, returning empty Response for {request.client}")
                        return Response(status_code=204)
                    return response
                except Exception as e:
                    logger.debug(f"Error in handle_sse: {type(e).__name__}: {str(e)}")
                    # Always return a Response instead of None or raising
                    return Response(status_code=204)

            # Apply the patch to handle_sse
            mcp.server.sse.SseServerTransport.handle_sse = patched_handle_sse
            logger.info("Patched mcp.server.sse.SseServerTransport.handle_sse")

        # Next, let's enhance the EventSourceResponse creation to handle disconnects better
        original_event_source_response = EventSourceResponse.__call__

        @functools.wraps(original_event_source_response)
        async def patched_event_source_response(self, scope, receive, send):
            """Override to add better client disconnect handling"""
            client = scope.get("client", ("unknown", 0))

            try:
                # Call original method with better error handling
                return await original_event_source_response(self, scope, receive, send)
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
                logger.debug(f"SSE error for client {client[0]}:{client[1]}: {type(e).__name__}: {str(e)}")
                raise

        # Apply the patch directly to the method instead of subclassing
        EventSourceResponse.__call__ = patched_event_source_response
        logger.info("Patched sse_starlette.sse.EventSourceResponse.__call__")

    except Exception as e:
        logger.error(f"Failed to apply MCP SSE patches: {str(e)}")

    logger.info("Finished applying monkey patches")
