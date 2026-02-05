"""
IRepository - Abstract base class for database operations

Defines the contract that both MongoDB and PostgreSQL implementations must follow.
All methods use MongoDB-style filter dicts as the canonical query format.

Filter format examples:
    {"status": "pending"}
    {"project": "inventorium", "priority": {"$in": ["High", "Critical"]}}
    {"metadata.tags": {"$all": ["bug", "urgent"]}}
    {"created_at": {"$gte": 1704067200}}
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IRepository(ABC):
    """Abstract repository interface for database operations."""

    def __init__(self, collection_name: str):
        """
        Initialize repository.

        Args:
            collection_name: Name of the collection/table
        """
        self.collection_name = collection_name

    @abstractmethod
    async def find_one(self, filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a single document matching the filter.

        Args:
            filter: MongoDB-style filter dict

        Returns:
            Document dict or None if not found
        """
        pass

    @abstractmethod
    async def find(
        self,
        filter: Dict[str, Any] = None,
        limit: int = 100,
        offset: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find multiple documents matching the filter.

        Args:
            filter: MongoDB-style filter dict
            limit: Max results to return (default: 100)
            offset: Number of results to skip (default: 0)
            sort: Sort specification as list of (field, direction) tuples
                  e.g., [("created_at", -1)] for descending

        Returns:
            List of matching documents
        """
        pass

    @abstractmethod
    async def insert_one(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a single document.

        Args:
            document: Document to insert

        Returns:
            Inserted document with generated id
        """
        pass

    @abstractmethod
    async def update_one(
        self,
        filter: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Update a single document matching the filter.

        Args:
            filter: MongoDB-style filter dict
            updates: Update operations (supports $set, $push, $pull, $inc)

        Returns:
            Dict with matchedCount and modifiedCount
        """
        pass

    @abstractmethod
    async def delete_one(self, filter: Dict[str, Any]) -> Dict[str, int]:
        """
        Delete a single document matching the filter.

        Args:
            filter: MongoDB-style filter dict

        Returns:
            Dict with deletedCount
        """
        pass

    @abstractmethod
    async def count(self, filter: Dict[str, Any] = None) -> int:
        """
        Count documents matching the filter.

        Args:
            filter: MongoDB-style filter dict

        Returns:
            Count of matching documents
        """
        pass

    @abstractmethod
    async def distinct(
        self,
        field: str,
        filter: Dict[str, Any] = None
    ) -> List[Any]:
        """
        Get distinct values for a field.

        Args:
            field: Field name (supports dot notation for nested fields)
            filter: MongoDB-style filter dict

        Returns:
            List of distinct values
        """
        pass

    # Note: aggregate() is intentionally omitted from base interface
    # MongoDB aggregation pipelines are complex and may not map cleanly to SQL
    # Implementations can provide their own aggregate methods if needed
