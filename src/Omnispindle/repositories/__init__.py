"""
Repository abstraction layer for database operations.

Provides a unified interface for MongoDB and PostgreSQL backends.
"""

from .base import IRepository
from .mongo_repository import MongoRepository
from .factory import create_repositories, get_backend_type, COLLECTIONS

__all__ = [
    'IRepository',
    'MongoRepository',
    'create_repositories',
    'get_backend_type',
    'COLLECTIONS'
]
