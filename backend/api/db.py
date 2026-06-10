"""Database connection pool for the API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

import psycopg
from psycopg_pool import AsyncConnectionPool

if TYPE_CHECKING:
    from api.config import Settings

_pool: AsyncConnectionPool | None = None


async def init_pool(settings: Settings) -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    assert _pool is not None, "Connection pool not initialised — call init_pool() first"
    async with _pool.connection() as conn:
        yield conn
