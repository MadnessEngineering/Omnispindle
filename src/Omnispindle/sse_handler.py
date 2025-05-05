import asyncio
import logging
import json
from typing import AsyncGenerator, Dict, Any, Callable, Optional
from starlette.requests import Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

logger = logging.getLogger(__name__)

class OmnispindleSSE:
    """
    A helper class for Server-Sent Events handling in Omnispindle.
    This class provides a cleaner interface for SSE events and handles
    client disconnections gracefully.
    """

    def __init__(self, ping_interval: int = 15):
        """
        Initialize the SSE handler.
        
        Args:
            ping_interval: How often to send ping events in seconds
        """
        self.ping_interval = ping_interval

    async def event_generator(self,
                              request: Request,
                              data_generator: Callable[[Request], AsyncGenerator[Dict[str, Any], None]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Create an event generator that handles client disconnections.
        
        Args:
            request: The Starlette request object
            data_generator: A function that generates event data
            
        Yields:
            Event data dictionaries suitable for EventSourceResponse
        """
        generator = data_generator(request)
        try:
            async for event_data in generator:
                # Check if client is still connected before yielding
                if await request.is_disconnected():
                    logger.info(f"Client disconnected: {request.client}")
                    break

                yield event_data

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled, client disconnected: {request.client}")
            # Allow CancelledError to propagate to properly clean up resources
            raise

        except Exception as e:
            logger.exception(f"Error in event generator: {str(e)}")
            # Include error in the event stream if still connected
            if not await request.is_disconnected():
                yield {"event": "error", "data": str(e)}
            raise

        finally:
            # Allow for cleanup when the generator is done
            if hasattr(generator, 'aclose'):
                await generator.aclose()
            logger.debug("Event generator closed successfully")

    def sse_response(self,
                    request: Request,
                    data_generator: Callable[[Request], AsyncGenerator[Dict[str, Any], None]],
                    send_timeout: Optional[int] = None) -> EventSourceResponse:
        """
        Create an SSE response.
        
        Args:
            request: The Starlette request object
            data_generator: A function that generates event data
            send_timeout: Optional timeout for sending events (prevents hanging connections)
            
        Returns:
            An EventSourceResponse object
        """
        event_generator = self.event_generator(request, data_generator)

        return EventSourceResponse(
            event_generator,
            ping=self.ping_interval,
            send_timeout=send_timeout,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-SSE-Handler": "OmnispindleSSE"
            }
        )

# Create a singleton instance for convenience
sse_handler = OmnispindleSSE()

# Helper function for easier usage
def sse_endpoint(data_generator: Callable[[Request], AsyncGenerator[Dict[str, Any], None]],
                 send_timeout: Optional[int] = None) -> Callable[[Request], EventSourceResponse]:
    """
    Create an SSE endpoint function with proper error handling.
    
    Args:
        data_generator: A function that generates event data
        send_timeout: Optional timeout for sending events
        
    Returns:
        A function that takes a Request and returns an EventSourceResponse
    """
    def endpoint(request: Request) -> EventSourceResponse:
        return sse_handler.sse_response(request, data_generator, send_timeout)

    return endpoint
