"""
RepositoryFactory - Creates repository instances based on DB_BACKEND config

Reads DB_BACKEND environment variable and instantiates the appropriate
repository implementation (MongoDB or PostgreSQL).

Usage:
    repos = create_repositories(db_connection, user_context)
    todos = await repos['todos'].find({"status": "pending"})
"""

import os
from typing import Any, Dict

from .base import IRepository
from .mongo_repository import MongoRepository
# from .postgres_repository import PostgresRepository  # Phase 3

DB_BACKEND = os.getenv('DB_BACKEND', 'mongodb')

# Collection names used across the application
COLLECTIONS = [
    'todos',
    'lessons_learned',
    'projects',
    'chat_sessions',
    'tags_cache',
    'todo_logs',
    'session_tokens',
    'api_keys',
    'explanations',
    'user_preferences'
]


def create_repositories(db_connection: Any, scope: str = 'default') -> Dict[str, IRepository]:
    """
    Create repository instances for all collections.

    Args:
        db_connection: Database connection (pymongo Database or asyncpg Pool)
        scope: 'personal' or 'shared' (for logging/debugging)

    Returns:
        Dict with repository instances keyed by collection name

    Raises:
        ValueError: If db_connection is None or backend is unknown
    """
    if db_connection is None:
        raise ValueError(f"Cannot create repositories: {scope} database connection is None")

    backend = DB_BACKEND.lower()
    repos = {}

    if backend == 'mongodb':
        # Create MongoDB repository for each collection
        for collection_name in COLLECTIONS:
            repos[collection_name] = MongoRepository(db_connection, collection_name)

    elif backend in ('postgresql', 'postgres'):
        # Phase 3: Implement PostgreSQL repositories
        raise NotImplementedError('PostgreSQL backend not yet implemented (Phase 3)')
        # for collection_name in COLLECTIONS:
        #     repos[collection_name] = PostgresRepository(db_connection, collection_name)

    else:
        raise ValueError(f"Unknown DB_BACKEND: {backend}. Must be 'mongodb' or 'postgresql'")

    # Add metadata for debugging
    repos['_backend'] = backend
    repos['_scope'] = scope
    repos['_collection_names'] = COLLECTIONS

    return repos


def get_backend_type() -> str:
    """
    Get the current database backend type.

    Returns:
        'mongodb' or 'postgresql'
    """
    return DB_BACKEND.lower()
