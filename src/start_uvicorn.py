#!/usr/bin/env python3
"""
Simple Uvicorn starter script to test binding to 0.0.0.0
"""
import uvicorn
import os
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

# Create a simple Starlette application for testing
async def homepage(request):
    return JSONResponse({
        "message": "Omnispindle SSE Test Server",
        "status": "ok",
        "version": "0.1.0"
    })

async def sse_test(request):
    return JSONResponse({
        "message": "SSE endpoint test - this would normally be an SSE connection",
        "status": "working"
    })

routes = [
    Route("/", homepage),
    Route("/sse", sse_test),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    # Ensure we bind to all interfaces
    host = "0.0.0.0"
    port = int(os.getenv("PORT", 8000))
    
    print(f"Starting Uvicorn on {host}:{port}")
    
    # Run Uvicorn directly
    uvicorn.run(
        app, 
        host=host,
        port=port,
        log_level="info"
    ) 
