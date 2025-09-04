#!/usr/bin/env python3
"""
HTTP wrapper for stdio MCP server.
Provides HTTP endpoint that proxies to the stdio-based MCP server.
"""

import asyncio
import json
import logging
from typing import Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from .stdio_server import OmniSpindleStdioServer

logger = logging.getLogger(__name__)

app = FastAPI(title="Omnispindle MCP HTTP Server")

# Global stdio server instance
stdio_server = None

@app.on_event("startup")
async def startup():
    """Initialize the stdio server"""
    global stdio_server
    stdio_server = OmniSpindleStdioServer()
    logger.info("Stdio MCP server initialized")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "server": "omnispindle-stdio"}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP endpoint that accepts JSON-RPC over HTTP.
    This proxies requests to the stdio server.
    """
    if not stdio_server:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    try:
        # Get the JSON-RPC request
        json_rpc = await request.json()
        
        # Process through stdio server (this would need adaptation)
        # For now, return a placeholder response
        return {
            "jsonrpc": "2.0",
            "id": json_rpc.get("id"),
            "error": {
                "code": -32601,
                "message": "Method not implemented - stdio server needs HTTP adaptation"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import os
    host = "0.0.0.0"
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "src.Omnispindle.stdio_http_server:app",
        host=host,
        port=port,
        log_level="info"
    )