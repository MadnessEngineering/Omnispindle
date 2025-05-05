import asyncio
import logging
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def numbers(minimum, maximum):
    """Generate numbers from minimum to maximum with a delay."""
    for i in range(minimum, maximum + 1):
        await asyncio.sleep(0.9)
        logger.info(f"Sending number: {i}")
        yield dict(data=i)

async def endless_stream(request):
    """Stream that properly handles client disconnects."""
    async def event_generator():
        i = 0
        try:
            while True:
                i += 1
                yield dict(data=f"Event {i}")
                logger.info(f"Sent event {i}")
                await asyncio.sleep(1)
        except asyncio.CancelledError as e:
            logger.info(f"Client disconnected: {request.client}")
            # Do any cleanup needed here
            raise e
    
    return EventSourceResponse(event_generator())

async def sse(request):
    """Simple SSE endpoint."""
    generator = numbers(1, 5)
    return EventSourceResponse(generator)

routes = [
    Route("/", endpoint=sse),
    Route("/endless", endpoint=endless_stream)
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    port = 8001  # Use a different port to avoid conflicts
    logger.info(f"Starting SSE test server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level='info') 
