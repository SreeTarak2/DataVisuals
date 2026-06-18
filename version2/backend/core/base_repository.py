"""
Base repository — common contract for all data access objects.

Provides CRUD scaffolding, pagination helpers, and consistent error
wrapping so every repository follows the same patterns.
"""

from __future__ import annotations

import logging
from typing import Any, Generic, TypeVar

from core.exceptions import NotFoundError

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Shared base for all data repositories.

    Subclasses override:
    - _collection_name()  → label used in log messages
    - find(), find_one(), insert_one(), update_one(), delete_one()
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self._collection_name)

    @property
    def _collection_name(self) -> str:
        return self.__class__.__name__

    # ── CRUD scaffold (override in subclasses) ─────────────────────────────

    async def find(self, filters: dict[str, Any] | None = None, **kwargs: Any) -> list[T]:
        raise NotImplementedError

    async def find_one(self, filters: dict[str, Any]) -> T | None:
        raise NotImplementedError

    async def find_by_id(self, id: str) -> T | None:
        return await self.find_one({"_id": id})

    async def find_one_or_raise(self, filters: dict[str, Any]) -> T:
        result = await self.find_one(filters)
        if result is None:
            raise NotFoundError(
                f"{self._collection_name} not found",
                code=f"{self._collection_name}.NotFound",
            )
        return result

    async def insert_one(self, document: T) -> T:
        raise NotImplementedError

    async def update_one(self, filters: dict[str, Any], update: dict[str, Any]) -> T | None:
        raise NotImplementedError

    async def delete_one(self, filters: dict[str, Any]) -> bool:
        raise NotImplementedError

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        raise NotImplementedError

    # ── Pagination ─────────────────────────────────────────────────────────

    async def paginate(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: list[tuple[str, int]] | None = None,
    ) -> tuple[list[T], int]:
        """Returns (items, total_count)."""
        total = await self.count(filters)
        skip = (page - 1) * page_size
        items = await self.find(filters=filters, skip=skip, limit=page_size, sort=sort)
        return items, total
