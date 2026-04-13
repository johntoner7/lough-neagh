"""Initialise the PostGIS database extensions."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(database_url)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology;"))

    print("PostGIS extensions ensured.")


if __name__ == "__main__":
    main()