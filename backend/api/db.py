"""Database helpers for the API."""

from __future__ import annotations

import contextlib
import os
from typing import Generator

import psycopg2
import psycopg2.extras


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


@contextlib.contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(get_database_url())
    try:
        yield conn
    finally:
        conn.close()
