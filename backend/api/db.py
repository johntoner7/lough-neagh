"""Database connection pool for the API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(conninfo=_database_url(), min_size=2, max_size=20, open=False)
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    assert _pool is not None, "Pool not initialised"
    async with _pool.connection() as conn:
        yield conn
