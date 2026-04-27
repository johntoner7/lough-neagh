"""Initialise PostGIS extensions."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology;"))

    print("PostGIS extensions ensured.")


if __name__ == "__main__":
    main()
