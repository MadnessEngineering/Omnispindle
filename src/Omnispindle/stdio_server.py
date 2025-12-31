#!/usr/bin/env python3
"""
Stdio-based MCP server for Omnispindle using FastMCP.

This module provides a standard input/output transport layer for the MCP protocol,
allowing the Omnispindle tools to be used by Claude Desktop and other MCP clients
that expect stdio communication.

Usage:
    python -m src.Omnispindle.stdio_server
"""

import asyncio
import logging
import os
import sys
import time
import hashlib
from typing import Dict, Any, Optional, Annotated

from pydantic import Field
from jose import jwt
from jose.exceptions import JWTError

from .auth_flow import ensure_authenticated, run_async_in_thread
from .auth_utils import verify_auth0_token, get_jwks, AUTH_CONFIG
from fastmcp import FastMCP
from .context import Context
from . import tools
from .documentation_manager import get_tool_doc, build_tool_docstring

# Configure logging to stderr so it doesn't interfere with stdio protocol
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Auth result caching to avoid thread blocking on every tool call
# Cache format: {token_hash: (payload, expiry_time)}
_auth_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
_auth_cache_ttl = 300  # 5 minutes TTL for auth results

# Tool loadout configurations - same as FastAPI server
# Import shared loadout definitions
from .tool_loadouts import get_loadout, get_all_loadouts


async def verify_auth0_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies an Auth0 token and returns the payload."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = get_jwks()
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            logger.error("Unable to find appropriate key in JWKS")
            return None

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH_CONFIG.audience,
            issuer=f"https://{AUTH_CONFIG.domain}/",
        )
        return payload

    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during token verification: {e}")
        return None


def _create_context() -> Context:
    """Create a context object with REQUIRED environment-based user information."""
    # Priority 1: Auth0 Token
    auth0_token = os.getenv("AUTH0_TOKEN")

    # If no token, trigger browser-based authentication
    if not auth0_token:
        logger.info("No AUTH0_TOKEN found, initiating browser-based authentication...")
        try:
            # Use run_async_in_thread to handle the async ensure_authenticated call
            def sync_ensure_auth():
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(ensure_authenticated())

            auth0_token = sync_ensure_auth()
            logger.info("✅ Browser authentication successful!")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            # Fall back to other methods
            pass

    if auth0_token:
        # Performance optimization: Cache auth results to avoid thread blocking on every call
        token_hash = hashlib.sha256(auth0_token.encode()).hexdigest()
        now = time.time()

        # Check cache first
        if token_hash in _auth_cache:
            cached_payload, expiry_time = _auth_cache[token_hash]
            if now < expiry_time:
                cache_age = now - (expiry_time - _auth_cache_ttl)
                logger.debug(f"⚡ Using cached auth result (age: {cache_age:.1f}s)")
                cached_payload["auth_method"] = "auth0"
                cached_payload["access_token"] = auth0_token
                return Context(user=cached_payload)
            else:
                logger.debug("🔄 Auth cache expired, re-verifying token")

        # Cache miss or expired - verify token
        logger.info("🔐 Found AUTH0_TOKEN, attempting verification...")
        user_payload = {}

        async def verify_token_async():
            nonlocal user_payload
            payload = await verify_auth0_token(auth0_token)
            if payload:
                user_payload.update(payload)

        start_time = time.time()
        run_async_in_thread(verify_token_async())
        verify_time = time.time() - start_time

        if user_payload:
            # Cache the result
            expiry_time = now + _auth_cache_ttl
            _auth_cache[token_hash] = (user_payload.copy(), expiry_time)
            logger.info(f"✅ Auth0 verified in {verify_time:.3f}s, cached for {_auth_cache_ttl}s: {user_payload.get('sub')}")

            user_payload["auth_method"] = "auth0"
            user_payload["access_token"] = auth0_token
            return Context(user=user_payload)
        else:
            logger.error("Auth0 token verification failed. Falling back.")

    # Check for API key first, then fall back to email/user_id
    api_key = os.getenv("MCP_API_KEY")
    user_email = os.getenv("MCP_USER_EMAIL")
    user_id = os.getenv("MCP_USER_ID")

    if api_key:
        # Use API key authentication - we'll trust the API key format validation
        # This allows using API keys from the Inventorium dashboard
        logger.info(f"🔐 Using API key authentication: {api_key[:12]}...")
        user = {
            "email": "api-key-user",  # Placeholder - real validation would happen server-side
            "sub": api_key[:16],  # Use key prefix as identifier
            "auth_method": "api_key",
            "api_key": api_key
        }
        return Context(user=user)

    if not user_email and not user_id:
        logger.error("❌ Authentication required for STDIO MCP server")
        logger.error("💡 Setup authentication with: python -m src.Omnispindle auth --setup")
        logger.error("🔑 Or manually set: MCP_USER_EMAIL, MCP_USER_ID, or MCP_API_KEY environment variables")
        logger.error("🔑 Alternatively, provide an AUTH0_TOKEN for secure authentication.")
        raise ValueError(
            "Authentication required: MCP_USER_EMAIL, MCP_USER_ID, or MCP_API_KEY must be set. "
            "Run 'python -m src.Omnispindle auth --setup' to configure authentication."
        )

    user = {
        "email": user_email,
        "sub": user_id or user_email,  # Use email as fallback ID
        "auth_method": "environment"
    }
    logger.info(f"🔐 Authenticated user: {user_email or user_id}")

    return Context(user=user)


class OmniSpindleStdioServer:
    """Stdio-based MCP server for Omnispindle tools using FastMCP."""

    def __init__(self):
        self.server = FastMCP(name="omnispindle")
        self._register_tools()
        logger.info("OmniSpindleStdioServer initialized with FastMCP")

    def _register_tools(self):
        """Register tools based on OMNISPINDLE_TOOL_LOADOUT env var."""

        loadout = os.getenv("OMNISPINDLE_TOOL_LOADOUT", "full").lower()
        # Validate loadout (get_loadout handles invalid names by defaulting to 'full')
        enabled = get_loadout(loadout, mode="local")
        logger.info(f"Loading '{loadout}' loadout (local mode, {len(enabled)} tools): {enabled}")

        # Tool registry with loadout-aware documentation
        tool_registry = {
            "add_todo": {
                "func": tools.add_todo,
                "doc": get_tool_doc("add_todo")
            },
            "query_todos": {
                "func": tools.query_todos,
                "doc": get_tool_doc("query_todos")
            },
            "update_todo": {
                "func": tools.update_todo,
                "doc": get_tool_doc("update_todo")
            },
            "delete_todo": {
                "func": tools.delete_todo,
                "doc": get_tool_doc("delete_todo")
            },
            "get_todo": {
                "func": tools.get_todo,
                "doc": get_tool_doc("get_todo")
            },
            "mark_todo_complete": {
                "func": tools.mark_todo_complete,
                "doc": get_tool_doc("mark_todo_complete")
            },
            "list_todos_by_status": {
                "func": tools.list_todos_by_status,
                "doc": get_tool_doc("list_todos_by_status")
            },
            "search_todos": {
                "func": tools.search_todos,
                "doc": get_tool_doc("search_todos")
            },
            "list_project_todos": {
                "func": tools.list_project_todos,
                "doc": get_tool_doc("list_project_todos")
            },
            "add_lesson": {
                "func": tools.add_lesson,
                "doc": get_tool_doc("add_lesson")
            },
            "get_lesson": {
                "func": tools.get_lesson,
                "doc": get_tool_doc("get_lesson")
            },
            "update_lesson": {
                "func": tools.update_lesson,
                "doc": get_tool_doc("update_lesson")
            },
            "delete_lesson": {
                "func": tools.delete_lesson,
                "doc": get_tool_doc("delete_lesson")
            },
            "search_lessons": {
                "func": tools.search_lessons,
                "doc": get_tool_doc("search_lessons")
            },
            "grep_lessons": {
                "func": tools.grep_lessons,
                "doc": get_tool_doc("grep_lessons")
            },
            "list_lessons": {
                "func": tools.list_lessons,
                "doc": get_tool_doc("list_lessons")
            },
            "query_todo_logs": {
                "func": tools.query_todo_logs,
                "doc": get_tool_doc("query_todo_logs")
            },
            "list_projects": {
                "func": tools.list_projects,
                "doc": get_tool_doc("list_projects")
            },
            "explain": {
                "func": tools.explain_tool,
                "doc": get_tool_doc("explain")
            },
            "add_explanation": {
                "func": tools.add_explanation,
                "doc": get_tool_doc("add_explanation")
            },
            "point_out_obvious": {
                "func": tools.point_out_obvious,
                "doc": get_tool_doc("point_out_obvious")
            },
            "bring_your_own": {
                "func": tools.bring_your_own,
                "doc": get_tool_doc("bring_your_own")
            },
            "inventorium_sessions_list": {
                "func": tools.inventorium_sessions_list,
                "doc": get_tool_doc("inventorium_sessions_list")
            },
            "inventorium_sessions_get": {
                "func": tools.inventorium_sessions_get,
                "doc": get_tool_doc("inventorium_sessions_get")
            },
            "inventorium_sessions_create": {
                "func": tools.inventorium_sessions_create,
                "doc": get_tool_doc("inventorium_sessions_create")
            },
            "inventorium_sessions_spawn": {
                "func": tools.inventorium_sessions_spawn,
                "doc": get_tool_doc("inventorium_sessions_spawn")
            },
            "inventorium_todos_link_session": {
                "func": tools.inventorium_todos_link_session,
                "doc": get_tool_doc("inventorium_todos_link_session")
            },
            "inventorium_sessions_fork": {
                "func": tools.inventorium_sessions_fork,
                "doc": get_tool_doc("inventorium_sessions_fork")
            },
            "inventorium_sessions_genealogy": {
                "func": tools.inventorium_sessions_genealogy,
                "doc": get_tool_doc("inventorium_sessions_genealogy")
            },
            "inventorium_sessions_tree": {
                "func": tools.inventorium_sessions_tree,
                "doc": get_tool_doc("inventorium_sessions_tree")
            }
        }

        # Register enabled tools dynamically
        for tool_name in enabled:
            if tool_name in tool_registry:
                tool_info = tool_registry[tool_name]

                # Create dynamic tool function with proper signature
                def make_tool(name, func, docstring):
                    def create_wrapper():
                        if name == "add_todo":
                            @self.server.tool()
                            async def add_todo(
                                description: Annotated[str, Field(description="Task description")],
                                project: Annotated[str, Field(description="Project name")],
                                priority: Annotated[str, Field(description="Critical|High|Medium|Low")] = "Medium",
                                target_agent: Annotated[str, Field(description="user|AI name")] = "user",
                                metadata: Annotated[Optional[Dict[str, Any]], Field(description="{key: value} pairs")] = None
                            ) -> str:
                                """Create task. Returns ID and project stats."""
                                ctx = _create_context()
                                return await func(description, project, priority, target_agent, metadata, ctx=ctx)
                            return add_todo

                        elif name == "query_todos":
                            @self.server.tool()
                            async def query_todos(
                                filter: Annotated[Optional[Dict[str, Any]], Field(description="{status: 'pending', project: 'name'}")] = None,
                                projection: Annotated[Optional[Dict[str, Any]], Field(description="{field: 1} to include")] = None,
                                limit: Annotated[int, Field(description="Max results")] = 100,
                                ctx: Annotated[Optional[str], Field(description="Additional context")] = None
                            ) -> str:
                                """Query with MongoDB filters. Ex: {status: 'pending', project: 'name'}"""
                                context = _create_context()
                                return await func(filter, projection, limit, ctx=context)
                            return query_todos

                        elif name == "update_todo":
                            @self.server.tool()
                            async def update_todo(
                                todo_id: Annotated[str, Field(description="Todo ID")],
                                updates: Annotated[dict, Field(description="{field: new_value}")]
                            ) -> str:
                                """Update todo. Fields: description, priority, status, metadata."""
                                ctx = _create_context()
                                return await func(todo_id, updates, ctx=ctx)
                            return update_todo

                        elif name == "delete_todo":
                            @self.server.tool()
                            async def delete_todo(
                                todo_id: Annotated[str, Field(description="Todo ID")]
                            ) -> str:
                                """Delete todo by ID"""
                                ctx = _create_context()
                                return await func(todo_id, ctx=ctx)
                            return delete_todo

                        elif name == "get_todo":
                            @self.server.tool()
                            async def get_todo(
                                todo_id: Annotated[str, Field(description="Todo ID")]
                            ) -> str:
                                """Get todo by ID"""
                                ctx = _create_context()
                                return await func(todo_id, ctx=ctx)
                            return get_todo

                        elif name == "mark_todo_complete":
                            @self.server.tool()
                            async def mark_todo_complete(
                                todo_id: Annotated[str, Field(description="Todo ID")],
                                comment: Annotated[Optional[str], Field(description="Optional completion comment")] = None
                            ) -> str:
                                """Mark completed. Optional comment."""
                                ctx = _create_context()
                                return await func(todo_id, comment, ctx=ctx)
                            return mark_todo_complete

                        elif name == "list_todos_by_status":
                            @self.server.tool()
                            async def list_todos_by_status(
                                status: Annotated[str, Field(description="pending|completed|initial|blocked|in_progress")],
                                limit: Annotated[int, Field(description="Max results")] = 100
                            ) -> str:
                                """List by status: pending|completed|initial|blocked|in_progress"""
                                ctx = _create_context()
                                return await func(status, limit, ctx=ctx)
                            return list_todos_by_status

                        elif name == "search_todos":
                            @self.server.tool()
                            async def search_todos(
                                query: Annotated[str, Field(description="Search text. Use 'project:Name' for project filter")],
                                fields: Annotated[Optional[list], Field(description="Fields to search")] = None,
                                limit: Annotated[int, Field(description="Max results")] = 100,
                                ctx: Annotated[Optional[str], Field(description="Additional context")] = None
                            ) -> str:
                                """Text search across fields. Use 'project:Name' for project filter."""
                                context = _create_context()
                                return await func(query, fields, limit, ctx=context)
                            return search_todos

                        elif name == "list_project_todos":
                            @self.server.tool()
                            async def list_project_todos(
                                project: Annotated[str, Field(description="Project name")],
                                limit: Annotated[int, Field(description="Max results")] = 5
                            ) -> str:
                                """List recent pending todos for project"""
                                ctx = _create_context()
                                return await func(project, limit, ctx=ctx)
                            return list_project_todos

                        elif name == "add_lesson":
                            @self.server.tool()
                            async def add_lesson(
                                language: Annotated[str, Field(description="Programming language")],
                                topic: Annotated[str, Field(description="Topic/category")],
                                lesson_learned: Annotated[str, Field(description="Lesson content")],
                                tags: Annotated[Optional[list], Field(description="Tags (optional)")] = None
                            ) -> str:
                                """Add lesson to knowledge base"""
                                ctx = _create_context()
                                return await func(language, topic, lesson_learned, tags, ctx=ctx)
                            return add_lesson

                        elif name == "get_lesson":
                            @self.server.tool()
                            async def get_lesson(
                                lesson_id: Annotated[str, Field(description="Lesson ID")]
                            ) -> str:
                                """Get lesson by ID"""
                                ctx = _create_context()
                                return await func(lesson_id, ctx=ctx)
                            return get_lesson

                        elif name == "update_lesson":
                            @self.server.tool()
                            async def update_lesson(
                                lesson_id: Annotated[str, Field(description="Lesson ID")],
                                updates: Annotated[dict, Field(description="{field: new_value}")]
                            ) -> str:
                                """Update lesson by ID"""
                                ctx = _create_context()
                                return await func(lesson_id, updates, ctx=ctx)
                            return update_lesson

                        elif name == "delete_lesson":
                            @self.server.tool()
                            async def delete_lesson(
                                lesson_id: Annotated[str, Field(description="Lesson ID")]
                            ) -> str:
                                """Delete lesson by ID"""
                                ctx = _create_context()
                                return await func(lesson_id, ctx=ctx)
                            return delete_lesson

                        elif name == "search_lessons":
                            @self.server.tool()
                            async def search_lessons(
                                query: Annotated[str, Field(description="Search text")],
                                fields: Annotated[Optional[list], Field(description="Fields to search")] = None,
                                limit: Annotated[int, Field(description="Max results")] = 100
                            ) -> str:
                                """Text search lessons"""
                                ctx = _create_context()
                                return await func(query, fields, limit, ctx=ctx)
                            return search_lessons

                        elif name == "grep_lessons":
                            @self.server.tool()
                            async def grep_lessons(
                                pattern: Annotated[str, Field(description="Regex pattern")],
                                limit: Annotated[int, Field(description="Max results")] = 20
                            ) -> str:
                                """Pattern match across topic and content"""
                                ctx = _create_context()
                                return await func(pattern, limit, ctx=ctx)
                            return grep_lessons

                        elif name == "list_lessons":
                            @self.server.tool()
                            async def list_lessons(
                                limit: Annotated[int, Field(description="Max results")] = 100
                            ) -> str:
                                """List all lessons (newest first)"""
                                ctx = _create_context()
                                return await func(limit, ctx=ctx)
                            return list_lessons

                        elif name == "query_todo_logs":
                            @self.server.tool()
                            async def query_todo_logs(
                                filter_type: Annotated[str, Field(description="all|create|update|delete|complete")] = 'all',
                                project: Annotated[str, Field(description="Project name or 'all'")] = 'all',
                                page: Annotated[int, Field(description="Page number")] = 1,
                                page_size: Annotated[int, Field(description="Results per page")] = 20
                            ) -> str:
                                """Query audit logs with filtering"""
                                ctx = _create_context()
                                return await func(filter_type, project, page, page_size, ctx=ctx)
                            return query_todo_logs

                        elif name == "list_projects":
                            @self.server.tool()
                            async def list_projects(
                                include_details: Annotated[bool, Field(description="Include metadata")] = False,
                                madness_root: Annotated[str, Field(description="Madness root path")] = "/Users/d.edens/lab/madness_interactive"
                            ) -> str:
                                """List all valid projects"""
                                ctx = _create_context()
                                return await func(include_details, madness_root, ctx=ctx)
                            return list_projects

                        elif name == "explain":
                            @self.server.tool()
                            async def explain(
                                topic: Annotated[str, Field(description="Topic/project name")]
                            ) -> str:
                                """Explain project or concept"""
                                ctx = _create_context()
                                return await func(topic, ctx=ctx)
                            return explain

                        elif name == "add_explanation":
                            @self.server.tool()
                            async def add_explanation(
                                topic: Annotated[str, Field(description="Topic name")],
                                content: Annotated[str, Field(description="Explanation content")],
                                kind: Annotated[str, Field(description="Type (concept|project)")] = "concept",
                                author: Annotated[str, Field(description="Author name")] = "system"
                            ) -> str:
                                """Add static explanation to knowledge base"""
                                ctx = _create_context()
                                return await func(topic, content, kind, author, ctx=ctx)
                            return add_explanation

                        elif name == "point_out_obvious":
                            @self.server.tool()
                            async def point_out_obvious(
                                observation: Annotated[str, Field(description="Obvious observation")],
                                sarcasm_level: Annotated[int, Field(description="Sarcasm level (1-10)")] = 5
                            ) -> str:
                                """Point out obvious with humor"""
                                ctx = _create_context()
                                return await func(observation, sarcasm_level, ctx=ctx)
                            return point_out_obvious

                        elif name == "bring_your_own":
                            @self.server.tool()
                            async def bring_your_own(
                                tool_name: Annotated[str, Field(description="Tool name")],
                                code: Annotated[str, Field(description="Code to execute")],
                                runtime: Annotated[str, Field(description="python|javascript|bash")] = "python",
                                timeout: Annotated[int, Field(description="Timeout in seconds")] = 30,
                                args: Annotated[Optional[Dict[str, Any]], Field(description="Arguments dict")] = None,
                                persist: Annotated[bool, Field(description="Persist tool")] = False
                            ) -> str:
                                """Run custom code (Python|JS|Bash)"""
                                ctx = _create_context()
                                return await func(tool_name, code, runtime, timeout, args, persist, ctx=ctx)
                            return bring_your_own


                        elif name == "inventorium_sessions_list":
                            @self.server.tool()
                            async def inventorium_sessions_list(
                                project: Annotated[Optional[str], Field(description="Project filter (optional)")] = None,
                                limit: Annotated[int, Field(description="Max results")] = 50
                            ) -> str:
                                """List chat sessions. Filter by project."""
                                ctx = _create_context()
                                return await func(project, limit, ctx=ctx)
                            return inventorium_sessions_list

                        elif name == "inventorium_sessions_get":
                            @self.server.tool()
                            async def inventorium_sessions_get(
                                session_id: Annotated[str, Field(description="Session ID")]
                            ) -> str:
                                """Get session details by ID"""
                                ctx = _create_context()
                                return await func(session_id, ctx=ctx)
                            return inventorium_sessions_get

                        elif name == "inventorium_sessions_create":
                            @self.server.tool()
                            async def inventorium_sessions_create(
                                project: Annotated[str, Field(description="Project name")],
                                title: Annotated[Optional[str], Field(description="Session title (optional)")] = None,
                                initial_prompt: Annotated[Optional[str], Field(description="First message (optional)")] = None,
                                agentic_tool: Annotated[str, Field(description="Agent tool name")] = "claude-code"
                            ) -> str:
                                """Create chat session for project"""
                                ctx = _create_context()
                                return await func(project, title, initial_prompt, agentic_tool, ctx=ctx)
                            return inventorium_sessions_create

                        elif name == "inventorium_sessions_spawn":
                            @self.server.tool()
                            async def inventorium_sessions_spawn(
                                parent_session_id: Annotated[str, Field(description="Parent session ID")],
                                prompt: Annotated[str, Field(description="Initial prompt")],
                                todo_id: Annotated[Optional[str], Field(description="Todo ID to link (optional)")] = None,
                                title: Annotated[Optional[str], Field(description="Session title (optional)")] = None
                            ) -> str:
                                """Spawn child session from parent with prompt"""
                                ctx = _create_context()
                                return await func(parent_session_id, prompt, todo_id, title, ctx=ctx)
                            return inventorium_sessions_spawn

                        elif name == "inventorium_todos_link_session":
                            @self.server.tool()
                            async def inventorium_todos_link_session(
                                todo_id: Annotated[str, Field(description="Todo ID")],
                                session_id: Annotated[str, Field(description="Session ID")]
                            ) -> str:
                                """Link todo to session (idempotent)"""
                                ctx = _create_context()
                                return await func(todo_id, session_id, ctx=ctx)
                            return inventorium_todos_link_session

                        elif name == "inventorium_sessions_fork":
                            @self.server.tool()
                            async def inventorium_sessions_fork(
                                session_id: Annotated[str, Field(description="Session ID to fork")],
                                title: Annotated[Optional[str], Field(description="New session title (optional)")] = None,
                                include_messages: Annotated[bool, Field(description="Copy message history")] = True,
                                inherit_todos: Annotated[bool, Field(description="Inherit todos")] = True,
                                initial_status: Annotated[Optional[str], Field(description="Initial status (optional)")] = None
                            ) -> str:
                                """Clone session (optional: copy history/todos)"""
                                ctx = _create_context()
                                return await func(session_id, title, include_messages, inherit_todos, initial_status, ctx=ctx)
                            return inventorium_sessions_fork

                        elif name == "inventorium_sessions_genealogy":
                            @self.server.tool()
                            async def inventorium_sessions_genealogy(
                                session_id: Annotated[str, Field(description="Session ID")]
                            ) -> str:
                                """Get parents and children for session"""
                                ctx = _create_context()
                                return await func(session_id, ctx=ctx)
                            return inventorium_sessions_genealogy

                        elif name == "inventorium_sessions_tree":
                            @self.server.tool()
                            async def inventorium_sessions_tree(
                                project: Annotated[Optional[str], Field(description="Project filter (optional)")] = None,
                                limit: Annotated[int, Field(description="Max sessions")] = 200
                            ) -> str:
                                """Get full session tree for project"""
                                ctx = _create_context()
                                return await func(project, limit, ctx=ctx)
                            return inventorium_sessions_tree

                    return create_wrapper()

                make_tool(tool_name, tool_info["func"], tool_info["doc"])

    async def run(self):
        """Run the stdio server."""
        logger.info("Starting Omnispindle stdio MCP server with FastMCP")
        await self.server.run_stdio_async()


async def main():
    """Main entry point for stdio server."""
    server = OmniSpindleStdioServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
