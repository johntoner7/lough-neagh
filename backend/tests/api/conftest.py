"""Shared fixtures for API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def require_db(client: TestClient) -> None:
    """Skip entire test session if the database is unavailable."""
    r = client.get("/health")
    if r.status_code != 200 or r.json().get("database") != "connected":
        pytest.skip("Database unavailable — skipping API tests")
