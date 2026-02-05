"""
MongoRepository - MongoDB implementation of IRepository

Wraps pymongo operations, preserving existing behavior while conforming
to the IRepository interface.
"""

from typing import Any, Dict, List, Optional
from pymongo.collection import Collection

from .base import IRepository


class MongoRepository(IRepository):
    """MongoDB implementation of the repository interface."""

    def __init__(self, db, collection_name: str):
        """
        Initialize MongoDB repository.

        Args:
            db: pymongo Database instance
            collection_name: Name of the collection
        """
        super().__init__(collection_name)
        self.db = db
        self.collection: Collection = db[collection_name]

    async def find_one(self, filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single document matching the filter."""
        # Note: pymongo's find_one is synchronous, but we keep async signature
        # for interface consistency (PostgreSQL implementation will be async)
        return self.collection.find_one(filter)

    async def find(
        self,
        filter: Dict[str, Any] = None,
        limit: int = 100,
        offset: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple documents matching the filter."""
        if filter is None:
            filter = {}

        cursor = self.collection.find(filter)

        if sort:
            cursor = cursor.sort(sort)

        if offset > 0:
            cursor = cursor.skip(offset)

        if limit > 0:
            cursor = cursor.limit(limit)

        return list(cursor)

    async def insert_one(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a single document."""
        result = self.collection.insert_one(document)
        # Return the inserted document with the generated _id
        return {**document, "_id": result.inserted_id}

    async def update_one(
        self,
        filter: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> Dict[str, int]:
        """Update a single document matching the filter."""
        result = self.collection.update_one(filter, updates)
        return {
            "matchedCount": result.matched_count,
            "modifiedCount": result.modified_count
        }

    async def delete_one(self, filter: Dict[str, Any]) -> Dict[str, int]:
        """Delete a single document matching the filter."""
        result = self.collection.delete_one(filter)
        return {"deletedCount": result.deleted_count}

    async def count(self, filter: Dict[str, Any] = None) -> int:
        """Count documents matching the filter."""
        if filter is None:
            filter = {}
        return self.collection.count_documents(filter)

    async def distinct(
        self,
        field: str,
        filter: Dict[str, Any] = None
    ) -> List[Any]:
        """Get distinct values for a field."""
        if filter is None:
            filter = {}
        return self.collection.distinct(field, filter)

    def get_raw_collection(self) -> Collection:
        """
        Expose raw collection for advanced operations not in IRepository.
        Use sparingly - prefer adding methods to IRepository when possible.
        """
        return self.collection
