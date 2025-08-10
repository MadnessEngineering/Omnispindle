
import asyncio
import json
import logging
from typing import AsyncGenerator, Coroutine, Any, Callable

from starlette.requests import Request
from starlette.responses import StreamingResponse

from .tools import ToolCall, handle_tool_call

logger = logging.getLogger(__name__)


async def mcp_handler(request: Request, get_current_user: Callable[[], Coroutine[Any, Any, Any]]) -> StreamingResponse:
    user = await get_current_user()
    if not user:
        return StreamingResponse(content="Unauthorized", status_code=401)

    async def event_generator() -> AsyncGenerator[str, None]:
        buffer = ""
        while True:
            try:
                # Read data from the request body stream
                chunk = await request.stream().read()
                if not chunk:
                    await asyncio.sleep(0.1)
                    continue

                buffer += chunk.decode('utf-8')
                logger.debug(f"Received chunk: {chunk.decode('utf-8')}")
                logger.debug(f"Buffer content: {buffer}")

                # Process buffer for complete JSON objects
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        logger.debug(f"Processing line: {line}")
                        try:
                            data = json.loads(line)
                            tool_call = ToolCall.parse_obj(data)
                            response = await handle_tool_call(tool_call)
                            response_json = json.dumps(response.dict())
                            logger.debug(f"Sending response: {response_json}")
                            yield f"{response_json}\n"
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e} for line: {line}")
                        except Exception as e:
                            logger.error(f"Error processing tool call: {e}")
                            error_response = {"status": "error", "message": str(e)}
                            yield f"{json.dumps(error_response)}\n"

            except asyncio.CancelledError:
                logger.info("Client disconnected.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                break

    return StreamingResponse(event_generator(), media_type="application/json") 
