"""
Hybrid tools module that can switch between API and local database modes.
Provides graceful degradation and performance comparison capabilities.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from datetime import datetime, timezone

from .context import Context
from .utils import create_response
from . import tools as local_tools
from . import api_tools
from .api_client import MadnessAPIClient

logger = logging.getLogger(__name__)

class OmnispindleMode(Enum):
    """Available operation modes for Omnispindle"""
    LOCAL = "local"      # Direct MongoDB access
    API = "api"          # HTTP API calls only
    HYBRID = "hybrid"    # Try API first, fallback to local
    AUTO = "auto"        # Automatically choose best mode

class HybridConfig:
    """Configuration for hybrid mode operations"""
    
    def __init__(self):
        self.mode = self._get_mode_from_env()
        self.api_timeout = float(os.getenv("OMNISPINDLE_API_TIMEOUT", "10.0"))
        self.fallback_enabled = os.getenv("OMNISPINDLE_FALLBACK_ENABLED", "true").lower() == "true"
        self.performance_logging = os.getenv("OMNISPINDLE_PERFORMANCE_LOGGING", "false").lower() == "true"
        
        # Performance thresholds
        self.api_failure_threshold = int(os.getenv("OMNISPINDLE_API_FAILURE_THRESHOLD", "3"))
        self.api_timeout_threshold = float(os.getenv("OMNISPINDLE_API_TIMEOUT_THRESHOLD", "5.0"))
        
        # Performance tracking
        self.api_failures = 0
        self.local_failures = 0
        self.api_response_times = []
        self.local_response_times = []
        
    def _get_mode_from_env(self) -> OmnispindleMode:
        """Get operation mode from environment variable"""
        mode_str = os.getenv("OMNISPINDLE_MODE", "hybrid").lower()
        try:
            return OmnispindleMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid OMNISPINDLE_MODE '{mode_str}', defaulting to hybrid")
            return OmnispindleMode.HYBRID
    
    def should_use_api(self) -> bool:
        """Determine if API should be used based on current state"""
        if self.mode == OmnispindleMode.LOCAL:
            return False
        elif self.mode == OmnispindleMode.API:
            return True
        elif self.mode in [OmnispindleMode.HYBRID, OmnispindleMode.AUTO]:
            # Use API unless it's consistently failing
            return self.api_failures < self.api_failure_threshold
        return True
    
    def record_api_success(self, response_time: float):
        """Record successful API operation"""
        self.api_failures = 0  # Reset failure count on success
        if self.performance_logging:
            self.api_response_times.append(response_time)
            # Keep only recent measurements
            if len(self.api_response_times) > 100:
                self.api_response_times = self.api_response_times[-50:]
    
    def record_api_failure(self):
        """Record failed API operation"""
        self.api_failures += 1
        logger.warning(f"API failure count: {self.api_failures}/{self.api_failure_threshold}")
    
    def record_local_success(self, response_time: float):
        """Record successful local operation"""
        self.local_failures = 0
        if self.performance_logging:
            self.local_response_times.append(response_time)
            if len(self.local_response_times) > 100:
                self.local_response_times = self.local_response_times[-50:]
    
    def record_local_failure(self):
        """Record failed local operation"""
        self.local_failures += 1
        logger.warning(f"Local failure count: {self.local_failures}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {
            "mode": self.mode.value,
            "api_failures": self.api_failures,
            "local_failures": self.local_failures,
            "should_use_api": self.should_use_api()
        }
        
        if self.api_response_times:
            stats["api_avg_response_time"] = sum(self.api_response_times) / len(self.api_response_times)
            stats["api_recent_calls"] = len(self.api_response_times)
        
        if self.local_response_times:
            stats["local_avg_response_time"] = sum(self.local_response_times) / len(self.local_response_times)
            stats["local_recent_calls"] = len(self.local_response_times)
            
        return stats

# Global configuration instance
_hybrid_config = HybridConfig()

def get_hybrid_config() -> HybridConfig:
    """Get the global hybrid configuration"""
    return _hybrid_config

async def _execute_with_fallback(operation_name: str, api_func, local_func, *args, ctx: Optional[Context] = None, **kwargs):
    """
    Execute a function with hybrid mode support - API first, fallback to local if needed.
    """
    config = get_hybrid_config()
    
    # Record start time for performance tracking
    start_time = datetime.now(timezone.utc)
    
    # Determine primary and fallback methods
    use_api_first = config.should_use_api()
    
    if use_api_first:
        primary_func = api_func
        fallback_func = local_func
        primary_name = "API"
        fallback_name = "Local"
    else:
        primary_func = local_func
        fallback_func = api_func
        primary_name = "Local"
        fallback_name = "API"
    
    # Try primary method
    try:
        logger.debug(f"Executing {operation_name} via {primary_name}")
        result = await primary_func(*args, ctx=ctx, **kwargs)
        
        # Record success
        response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        if use_api_first:
            config.record_api_success(response_time)
        else:
            config.record_local_success(response_time)
        
        # Check if result indicates failure
        if isinstance(result, str) and '"success": false' in result:
            raise Exception(f"{primary_name} returned failure response")
        
        logger.debug(f"{operation_name} succeeded via {primary_name} in {response_time:.2f}s")
        return result
        
    except Exception as primary_error:
        logger.warning(f"{operation_name} failed via {primary_name}: {str(primary_error)}")
        
        # Record failure
        if use_api_first:
            config.record_api_failure()
        else:
            config.record_local_failure()
        
        # Try fallback if enabled and in hybrid/auto mode
        if config.fallback_enabled and config.mode in [OmnispindleMode.HYBRID, OmnispindleMode.AUTO]:
            try:
                logger.info(f"Falling back to {fallback_name} for {operation_name}")
                fallback_start = datetime.now(timezone.utc)
                
                result = await fallback_func(*args, ctx=ctx, **kwargs)
                
                # Record fallback success
                response_time = (datetime.now(timezone.utc) - fallback_start).total_seconds()
                if not use_api_first:
                    config.record_api_success(response_time)
                else:
                    config.record_local_success(response_time)
                
                logger.info(f"{operation_name} succeeded via {fallback_name} fallback in {response_time:.2f}s")
                return result
                
            except Exception as fallback_error:
                logger.error(f"{operation_name} failed via both {primary_name} and {fallback_name}")
                logger.error(f"Primary error: {str(primary_error)}")
                logger.error(f"Fallback error: {str(fallback_error)}")
                
                # Record fallback failure
                if not use_api_first:
                    config.record_api_failure()
                else:
                    config.record_local_failure()
                
                return create_response(False, message=f"Both {primary_name} and {fallback_name} failed. Primary: {str(primary_error)}, Fallback: {str(fallback_error)}")
        else:
            # No fallback, return primary error
            return create_response(False, message=f"{primary_name} failed: {str(primary_error)}")

# Hybrid tool implementations

async def add_todo(description: str, project: str, priority: str = "Medium", 
                  target_agent: str = "user", metadata: Optional[Dict[str, Any]] = None, 
                  ctx: Optional[Context] = None) -> str:
    """Create a todo using hybrid mode"""
    return await _execute_with_fallback(
        "add_todo",
        api_tools.add_todo,
        local_tools.add_todo,
        description, project, priority, target_agent, metadata,
        ctx=ctx
    )

async def query_todos(filter: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, 
                     limit: int = 100, ctx: Optional[Context] = None) -> str:
    """Query todos using hybrid mode"""
    return await _execute_with_fallback(
        "query_todos",
        api_tools.query_todos,
        local_tools.query_todos,
        filter, projection, limit,
        ctx=ctx
    )

async def update_todo(todo_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """Update todo using hybrid mode"""
    return await _execute_with_fallback(
        "update_todo",
        api_tools.update_todo,
        local_tools.update_todo,
        todo_id, updates,
        ctx=ctx
    )

async def delete_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """Delete todo using hybrid mode"""
    return await _execute_with_fallback(
        "delete_todo",
        api_tools.delete_todo,
        local_tools.delete_todo,
        todo_id,
        ctx=ctx
    )

async def get_todo(todo_id: str, ctx: Optional[Context] = None) -> str:
    """Get todo using hybrid mode"""
    return await _execute_with_fallback(
        "get_todo",
        api_tools.get_todo,
        local_tools.get_todo,
        todo_id,
        ctx=ctx
    )

async def mark_todo_complete(todo_id: str, comment: Optional[str] = None, ctx: Optional[Context] = None) -> str:
    """Complete todo using hybrid mode"""
    return await _execute_with_fallback(
        "mark_todo_complete",
        api_tools.mark_todo_complete,
        local_tools.mark_todo_complete,
        todo_id, comment,
        ctx=ctx
    )

async def list_todos_by_status(status: str, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """List todos by status using hybrid mode"""
    return await _execute_with_fallback(
        "list_todos_by_status",
        api_tools.list_todos_by_status,
        local_tools.list_todos_by_status,
        status, limit,
        ctx=ctx
    )

async def search_todos(query: str, fields: Optional[list] = None, limit: int = 100, ctx: Optional[Context] = None) -> str:
    """Search todos using hybrid mode"""
    return await _execute_with_fallback(
        "search_todos",
        api_tools.search_todos,
        local_tools.search_todos,
        query, fields, limit,
        ctx=ctx
    )

async def list_project_todos(project: str, limit: int = 5, ctx: Optional[Context] = None) -> str:
    """List project todos using hybrid mode"""
    return await _execute_with_fallback(
        "list_project_todos",
        api_tools.list_project_todos,
        local_tools.list_project_todos,
        project, limit,
        ctx=ctx
    )

async def list_projects(include_details: Union[bool, str] = False, madness_root: str = "/Users/d.edens/lab/madness_interactive", ctx: Optional[Context] = None) -> str:
    """List projects using hybrid mode"""
    return await _execute_with_fallback(
        "list_projects",
        api_tools.list_projects,
        local_tools.list_projects,
        include_details, madness_root,
        ctx=ctx
    )

# For non-todo operations, prefer local mode since they're not yet available via API

async def add_lesson(language: str, topic: str, lesson_learned: str, tags: Optional[list] = None, ctx: Optional[Context] = None) -> str:
    """Add lesson - local only for now"""
    return await local_tools.add_lesson(language, topic, lesson_learned, tags, ctx=ctx)

async def get_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """Get lesson - local only for now"""
    return await local_tools.get_lesson(lesson_id, ctx=ctx)

async def update_lesson(lesson_id: str, updates: dict, ctx: Optional[Context] = None) -> str:
    """Update lesson - local only for now"""
    return await local_tools.update_lesson(lesson_id, updates, ctx=ctx)

async def delete_lesson(lesson_id: str, ctx: Optional[Context] = None) -> str:
    """Delete lesson - local only for now"""
    return await local_tools.delete_lesson(lesson_id, ctx=ctx)

async def search_lessons(query: str, fields: Optional[list] = None, limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """Search lessons - local only for now"""
    return await local_tools.search_lessons(query, fields, limit, brief, ctx=ctx)

async def grep_lessons(pattern: str, limit: int = 20, ctx: Optional[Context] = None) -> str:
    """Grep lessons - local only for now"""
    return await local_tools.grep_lessons(pattern, limit, ctx=ctx)

async def list_lessons(limit: int = 100, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """List lessons - local only for now"""
    return await local_tools.list_lessons(limit, brief, ctx=ctx)

async def query_todo_logs(filter_type: str = 'all', project: str = 'all',
                       page: int = 1, page_size: int = 20, ctx: Optional[Context] = None) -> str:
    """Query todo logs - local only for now"""
    return await local_tools.query_todo_logs(filter_type, project, page, page_size, ctx=ctx)

async def add_explanation(topic: str, content: str, kind: str = "concept", author: str = "system", ctx: Optional[Context] = None) -> str:
    """Add explanation - local only for now"""
    return await local_tools.add_explanation(topic, content, kind, author, ctx=ctx)

async def explain_tool(topic: str, brief: bool = False, ctx: Optional[Context] = None) -> str:
    """Explain tool - local only for now"""
    return await local_tools.explain_tool(topic, brief, ctx=ctx)

async def point_out_obvious(observation: str, sarcasm_level: int = 5, ctx: Optional[Context] = None) -> str:
    """Point out obvious - local only for now"""
    return await local_tools.point_out_obvious(observation, sarcasm_level, ctx=ctx)

async def bring_your_own(tool_name: str, code: str, runtime: str = "python", 
                         timeout: int = 30, args: Optional[Dict[str, Any]] = None,
                         persist: bool = False, ctx: Optional[Context] = None) -> str:
    """Bring your own tool - local only for now"""
    return await local_tools.bring_your_own(tool_name, code, runtime, timeout, args, persist, ctx=ctx)

# Utility functions for monitoring and configuration

async def get_hybrid_status(ctx: Optional[Context] = None) -> str:
    """Get current hybrid mode status and performance stats"""
    config = get_hybrid_config()
    stats = config.get_performance_stats()
    
    return create_response(True, {
        "hybrid_status": stats,
        "configuration": {
            "mode": config.mode.value,
            "api_timeout": config.api_timeout,
            "fallback_enabled": config.fallback_enabled,
            "performance_logging": config.performance_logging,
            "api_failure_threshold": config.api_failure_threshold
        }
    }, message=f"Hybrid mode: {config.mode.value}, API preferred: {config.should_use_api()}")

async def test_api_connectivity(ctx: Optional[Context] = None) -> str:
    """Test API connectivity and response times"""
    try:
        auth_token, api_key = api_tools._get_auth_from_context(ctx)
        
        start_time = datetime.now(timezone.utc)
        async with MadnessAPIClient(auth_token=auth_token, api_key=api_key) as client:
            health_response = await client.health_check()
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        if health_response.success:
            return create_response(True, {
                "api_status": "healthy",
                "response_time": response_time,
                "api_data": health_response.data
            }, message=f"API connectivity OK ({response_time:.2f}s)")
        else:
            return create_response(False, {
                "api_status": "unhealthy",
                "response_time": response_time,
                "error": health_response.error
            }, message=f"API connectivity failed: {health_response.error}")
            
    except Exception as e:
        return create_response(False, {
            "api_status": "error",
            "error": str(e)
        }, message=f"API connectivity test failed: {str(e)}")