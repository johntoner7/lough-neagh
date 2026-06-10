"""Application settings loaded from environment variables.

Usage:
    from api.config import get_settings
    settings = get_settings()

Schema is validated on first call; a missing DATABASE_URL raises immediately
rather than producing a confusing connection error later.

Schema creation and data migrations are NOT run by this module.
Run them explicitly before starting the API:
    uv run python -m scripts.init_db
    uv run python -m scripts.create_tables
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_settings: Settings | None = None


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_format: str
    log_level: str
    pool_min_size: int
    pool_max_size: int

    @classmethod
    def from_env(cls) -> Settings:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is required. "
                "Set it before starting the API."
            )
        return cls(
            database_url=db_url,
            log_format=os.environ.get("LOG_FORMAT", "text"),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            pool_min_size=int(os.environ.get("POOL_MIN_SIZE", "2")),
            pool_max_size=int(os.environ.get("POOL_MAX_SIZE", "20")),
        )


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
