"""Backfill farm census ward catchments from station-derived catchment geometry."""

from __future__ import annotations

import argparse
import os

from pipeline.ingest.farm_census import backfill_farm_census_catchments


def main(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    count = backfill_farm_census_catchments(url)
    print(f"Backfilled catchment_name for {count:,} farm census ward rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", dest="database_url", help="Database URL to backfill")
    args = parser.parse_args()
    main(args.database_url)
