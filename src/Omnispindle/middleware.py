from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp
import logging
import asyncio
import anyio
import inspect
import functools

logger = logging.getLogger(__name__)

class ConnectionErrorsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle various connection-related errors that occur when clients disconnect.
    This handles common exceptions from SSE connections and long-polling requests.
    """
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except RuntimeError as exc:
            if str(exc) == 'No response returned.' and await request.is_disconnected():
                logger.debug("Client disconnected with 'No response returned' error")
                return Response(status_code=204)
            raise
        except (anyio.WouldBlock, asyncio.exceptions.CancelledError) as exc:
            # These are common with SSE and WebSocket connections when clients disconnect
            if await request.is_disconnected():
                logger.debug(f"Handled {type(exc).__name__} for disconnected client")
                return Response(status_code=204)
            raise
        except ConnectionResetError as exc:
            logger.debug("Client connection was reset")
            return Response(status_code=204)
        except ConnectionAbortedError as exc:
            logger.debug("Client connection was aborted")
            return Response(status_code=204)

# Keep the old middleware for backward compatibility
SuppressNoResponseReturnedMiddleware = ConnectionErrorsMiddleware

class NoneTypeResponseMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle 'NoneType' object is not callable errors.
    This occurs when a route handler returns None instead of a proper response object.
    """
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            if response is None:
                # Log the path that returned None
                logger.debug(f"Route handler for {request.url.path} returned None instead of a response object")
                # Return a generic 204 No Content response
                return Response(status_code=204)
            return response
        except TypeError as exc:
            if "'NoneType' object is not callable" in str(exc):
                logger.debug(f"Caught NoneType error in {request.url.path}: {str(exc)}")
                return Response(
                    status_code=204,
                    headers=[(b"content-type", b"text/plain")]
                )
            raise

def create_asgi_error_handler(app):
    """
    Create a low-level ASGI wrapper that handles errors and provides fallbacks.
    
    This is a more aggressive approach that wraps the entire ASGI application 
    to handle errors at the lowest level of the stack.
    """
    @functools.wraps(app)
    async def error_handling_app(scope, receive, send):
        # Define a patched send function
        original_send = send
        
        async def patched_send(message):
            try:
                await original_send(message)
            except Exception as e:
                logger.debug(f"Error in send: {type(e).__name__}: {str(e)}")
                # Send a fallback response if possible
                if message.get("type") == "http.response.start":
                    try:
                        await original_send({
                            "type": "http.response.start",
                            "status": 204,
                            "headers": [(b"content-type", b"text/plain")]
                        })
                        await original_send({
                            "type": "http.response.body",
                            "body": b"",
                            "more_body": False
                        })
                    except Exception as e2:
                        logger.debug(f"Failed to send fallback response: {str(e2)}")
        
        try:
            # Run the main application
            await app(scope, receive, patched_send)
        except TypeError as e:
            if "'NoneType' object is not callable" in str(e):
                logger.debug(f"Caught NoneType error at ASGI level: {str(e)}")
                try:
                    # Send a fallback response
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
                except Exception as e2:
                    logger.debug(f"Failed to send fallback response after NoneType error: {str(e2)}")
            else:
                logger.warning(f"Unhandled TypeError: {str(e)}")
                # Try to send a 500 response
                try:
                    await send({
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"text/plain")]
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b"Internal Server Error",
                        "more_body": False
                    })
                except Exception:
                    pass  # We tried our best
        except (asyncio.exceptions.CancelledError, anyio.WouldBlock) as e:
            logger.debug(f"Connection error: {type(e).__name__}")
            # These are common with client disconnections, so we just log and don't try to respond
        except Exception as e:
            logger.warning(f"Unhandled exception in ASGI app: {type(e).__name__}: {str(e)}")
            # Try to send a 500 response
            try:
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain")]
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Internal Server Error",
                    "more_body": False
                })
            except Exception:
                pass  # We tried our best
    
    return error_handling_app
