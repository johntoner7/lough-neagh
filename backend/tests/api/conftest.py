"""Shared fixtures for API tests."""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Entering as a context manager runs FastAPI's lifespan, which opens the
    # DB pool — without it get_conn() has nothing to yield from and every
    # request fails, which used to make every test in this suite skip silently.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def require_db(client: TestClient) -> None:
    """Skip entire test session if the database is unavailable."""
    r = client.get("/health")
    if r.status_code != 200 or r.json().get("database") != "connected":
        pytest.skip("Database unavailable — skipping API tests")
