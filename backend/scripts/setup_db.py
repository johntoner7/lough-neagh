"""One-time database initialisation script.

Runs the three setup steps that must complete before the API can serve traffic:
  1. init_db      — creates PostGIS extensions
  2. create_tables — creates all tables, adds columns, builds spatial indexes,
                     and runs geometry-transform UPDATE statements
  3. backfill_farm_census_catchments — assigns catchment_name to farm census
                                       ward rows via a spatial join

This script is intentionally NOT called during API startup. Run it once before
the first deploy, or as a Railway pre-deploy / one-off command:

    uv run python -m scripts.setup_db

    # Against a specific database URL:
    DATABASE_URL=<url> uv run python -m scripts.setup_db

    # Against a remote host (requires explicit --production flag):
    DATABASE_URL=<railway-url> uv run python -m scripts.setup_db --production
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text


def is_production_url(url: str) -> bool:
    return "localhost" not in url and "127.0.0.1" not in url


def check_db(database_url: str) -> bool:
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  OK       database reachable")
        return True
    except Exception as exc:
        print(f"  FAIL     database: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--production",
        action="store_true",
        help="Required when DATABASE_URL points to a remote host",
    )
    parser.add_argument(
        "--db-url",
        metavar="URL",
        help="Override DATABASE_URL",
    )
    args = parser.parse_args()

    database_url = (
        args.db_url
        or os.environ.get("DATABASE_PUBLIC_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql://user:password@localhost:5433/phosphorus_db"
    )

    print("\n=== Database connectivity check ===\n")
    if not check_db(database_url):
        sys.exit(1)

    if is_production_url(database_url) and not args.production:
        print(
            "\n✗  DATABASE_URL points to a remote host but --production was not passed.\n"
            "   Add --production to confirm you intend to initialise the hosted database."
        )
        sys.exit(1)

    if is_production_url(database_url):
        print(
            "\n⚠  You are about to run database initialisation against PRODUCTION.\n"
            "   Existing tables will NOT be dropped, but ALTER TABLE and UPDATE\n"
            "   statements will run and may take several minutes.\n"
        )
        confirm = input("   Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    # ── Step 1: PostGIS extensions ────────────────────────────────────────────
    print("\n=== Step 1/3: PostGIS extensions ===\n")
    from scripts.init_db import main as init_db
    init_db(database_url)

    # ── Step 2: Tables, columns, indexes, geometry transforms ─────────────────
    print("\n=== Step 2/3: Tables and indexes ===\n")
    from scripts.create_tables import main as create_tables
    create_tables(database_url)

    # ── Step 3: Backfill farm census catchment names ──────────────────────────
    print("\n=== Step 3/3: Backfill farm census catchments ===\n")
    from pipeline.ingest.farm_census import backfill_farm_census_catchments
    count = backfill_farm_census_catchments(database_url)
    print(f"Backfilled catchment_name for {count:,} farm census ward rows.")

    print("\n✓  Database initialisation complete.\n")


if __name__ == "__main__":
    main()
