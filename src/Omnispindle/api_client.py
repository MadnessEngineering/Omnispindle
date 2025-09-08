import os
import json
import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Structured response from API calls"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: Optional[int] = None

class MadnessAPIClient:
    """
    HTTP client for madnessinteractive.cc/api endpoints.
    Handles authentication, retries, and response parsing for MCP tools.
    """
    
    def __init__(self, base_url: str = None, auth_token: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("MADNESS_API_URL", "https://madnessinteractive.cc/api")
        self.auth_token = auth_token or os.getenv("MADNESS_AUTH_TOKEN")
        self.api_key = api_key or os.getenv("MADNESS_API_KEY")
        self.session: Optional[aiohttp.ClientSession] = None
        self.max_retries = 3
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        # Authentication priority: JWT token > API key
        self.auth_headers = {}
        if self.auth_token:
            self.auth_headers["Authorization"] = f"Bearer {self.auth_token}"
            logger.info("Using JWT token authentication")
        elif self.api_key:
            self.auth_headers["Authorization"] = f"Bearer {self.api_key}"
            logger.info("Using API key authentication")
        else:
            logger.warning("No authentication configured - API calls may fail")

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session is created"""
        if not self.session:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                headers={"User-Agent": "Omnispindle-MCP/1.0"}
            )

    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> APIResponse:
        """
        Make HTTP request with retries and error handling
        """
        await self._ensure_session()
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Merge auth headers with any provided headers
        headers = {**self.auth_headers}
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        # Add Content-Type for requests with data
        if method.upper() in ['POST', 'PUT', 'PATCH'] and 'json' in kwargs:
            headers.setdefault('Content-Type', 'application/json')

        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"API {method.upper()} {url} (attempt {attempt + 1})")
                
                async with self.session.request(method, url, **kwargs) as response:
                    response_text = await response.text()
                    
                    # Log response details
                    logger.debug(f"API Response: {response.status} {len(response_text)} bytes")
                    
                    # Try to parse JSON response
                    try:
                        response_data = json.loads(response_text) if response_text else {}
                    except json.JSONDecodeError:
                        response_data = {"raw_response": response_text}
                    
                    # Handle HTTP status codes
                    if response.status == 200 or response.status == 201:
                        return APIResponse(
                            success=True,
                            data=response_data,
                            status_code=response.status
                        )
                    elif response.status == 401:
                        error_msg = f"Authentication failed (401): {response_data.get('message', 'Invalid credentials')}"
                        logger.error(error_msg)
                        return APIResponse(
                            success=False,
                            error=error_msg,
                            status_code=response.status
                        )
                    elif response.status == 403:
                        error_msg = f"Access forbidden (403): {response_data.get('message', 'Insufficient permissions')}"
                        logger.error(error_msg)
                        return APIResponse(
                            success=False,
                            error=error_msg,
                            status_code=response.status
                        )
                    elif response.status == 404:
                        error_msg = f"Resource not found (404): {response_data.get('message', 'Not found')}"
                        return APIResponse(
                            success=False,
                            error=error_msg,
                            status_code=response.status
                        )
                    elif 400 <= response.status < 500:
                        # Client error - don't retry
                        error_msg = f"Client error ({response.status}): {response_data.get('message', 'Bad request')}"
                        logger.error(error_msg)
                        return APIResponse(
                            success=False,
                            error=error_msg,
                            status_code=response.status
                        )
                    elif response.status >= 500:
                        # Server error - retry
                        error_msg = f"Server error ({response.status}): {response_data.get('message', 'Internal server error')}"
                        logger.warning(f"{error_msg} - will retry")
                        last_error = error_msg
                        
                        if attempt < self.max_retries:
                            # Exponential backoff
                            wait_time = 2 ** attempt
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            return APIResponse(
                                success=False,
                                error=error_msg,
                                status_code=response.status
                            )
                    
            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                logger.warning(f"{error_msg} - attempt {attempt + 1}")
                last_error = error_msg
                
                if attempt < self.max_retries:
                    # Exponential backoff for network errors
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return APIResponse(
                        success=False,
                        error=error_msg,
                        status_code=None
                    )
            
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                return APIResponse(
                    success=False,
                    error=error_msg,
                    status_code=None
                )
        
        # Should not reach here, but just in case
        return APIResponse(
            success=False,
            error=last_error or "Unknown error after retries",
            status_code=None
        )

    # Health check
    async def health_check(self) -> APIResponse:
        """Check API health and connectivity"""
        return await self._make_request("GET", "/health")

    # Todo operations
    async def get_todos(self, project: str = None, status: str = None, priority: str = None, limit: int = 100) -> APIResponse:
        """Get todos with optional filtering"""
        params = {}
        if project:
            params["project"] = project
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if limit:
            params["limit"] = limit
            
        return await self._make_request("GET", "/todos", params=params)

    async def get_todo(self, todo_id: str) -> APIResponse:
        """Get a specific todo by ID"""
        return await self._make_request("GET", f"/todos/{todo_id}")

    async def create_todo(self, description: str, project: str, priority: str = "Medium", metadata: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Create a new todo"""
        payload = {
            "description": description,
            "project": project,
            "priority": priority
        }
        if metadata:
            payload["metadata"] = metadata
            
        return await self._make_request("POST", "/todos", json=payload)

    async def update_todo(self, todo_id: str, updates: Dict[str, Any]) -> APIResponse:
        """Update an existing todo"""
        return await self._make_request("PUT", f"/todos/{todo_id}", json=updates)

    async def delete_todo(self, todo_id: str) -> APIResponse:
        """Delete a todo"""
        return await self._make_request("DELETE", f"/todos/{todo_id}")

    async def complete_todo(self, todo_id: str, comment: str = None) -> APIResponse:
        """Mark a todo as complete"""
        payload = {}
        if comment:
            payload["comment"] = comment
            
        return await self._make_request("POST", f"/todos/{todo_id}/complete", json=payload)

    async def get_todo_stats(self, project: str = None) -> APIResponse:
        """Get todo statistics"""
        params = {}
        if project:
            params["project"] = project
            
        return await self._make_request("GET", "/todos/stats", params=params)

    async def get_projects(self) -> APIResponse:
        """Get available projects"""
        return await self._make_request("GET", "/projects")

# Factory function for creating API client instances
def create_api_client(auth_token: str = None, api_key: str = None) -> MadnessAPIClient:
    """Factory function to create API client with authentication"""
    return MadnessAPIClient(auth_token=auth_token, api_key=api_key)

# Singleton instance for module-level usage
_default_client: Optional[MadnessAPIClient] = None

async def get_default_client() -> MadnessAPIClient:
    """Get or create default API client instance"""
    global _default_client
    if not _default_client:
        _default_client = create_api_client()
    return _default_client