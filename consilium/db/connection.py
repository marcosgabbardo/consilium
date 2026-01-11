"""Async MySQL connection pool management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

import aiomysql

from consilium.config import Settings, get_settings
from consilium.core.exceptions import DatabaseError


class DatabasePool:
    """Async MySQL connection pool manager."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: aiomysql.Pool | None = None

    @property
    def is_connected(self) -> bool:
        """Check if pool is initialized."""
        return self._pool is not None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return

        try:
            self._pool = await aiomysql.create_pool(
                host=self._settings.database.host,
                port=self._settings.database.port,
                user=self._settings.database.user,
                password=self._settings.database.password,
                db=self._settings.database.name,
                minsize=1,
                maxsize=self._settings.database.pool_size,
                pool_recycle=self._settings.database.pool_recycle,
                autocommit=True,
                charset="utf8mb4",
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to create database pool: {e}",
                operation="connect",
                details={"host": self._settings.database.host},
            ) from e

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[aiomysql.Connection, None]:
        """Acquire a connection from the pool."""
        if self._pool is None:
            await self.connect()

        assert self._pool is not None

        async with self._pool.acquire() as conn:
            yield conn

    async def execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> tuple[int, int]:
        """Execute a query and return (affected_rows, last_insert_id)."""
        async with self.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount, cur.lastrowid

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Execute a query and fetch one row as dict."""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and fetch all rows as dicts."""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            result = await self.fetch_one("SELECT 1 as health")
            return result is not None and result.get("health") == 1
        except Exception:
            return False


# Global pool instance
_pool: DatabasePool | None = None


async def get_pool() -> DatabasePool:
    """Get or create the global database pool."""
    global _pool
    if _pool is None:
        _pool = DatabasePool()
        await _pool.connect()
    return _pool


async def close_pool() -> None:
    """Close the global database pool."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
