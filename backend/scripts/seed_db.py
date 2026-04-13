"""Seed a fresh database with the full pipeline.

Run this once after `docker-compose up -d` to populate a new database.
On Railway, this is the first-deploy initialisation step.

Usage:
    python backend/scripts/seed_db.py

Required data files (place before running):
    data/raw/foi/annex_a.csv
    data/raw/wfd_sites/WFD_River_and_Lake_Monitoring_Sites_*.geojson
    data/raw/wfd_waterbodies/WFD_River_Water_Bodies_2016.shp
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def check_data_files() -> list[str]:
    """Return a list of missing required data files."""
    required = [
        Path("data/raw/foi/annex_a.csv"),
        Path("data/raw/wfd_waterbodies/WFD_River_Water_Bodies_2016.shp"),
    ]
    missing = [str(p) for p in required if not p.exists()]

    # WFD sites — accept any .geojson in the directory
    wfd_sites_dir = Path("data/raw/wfd_sites")
    if not any(wfd_sites_dir.glob("*.geojson")):
        missing.append("data/raw/wfd_sites/*.geojson (no GeoJSON found)")

    return missing


def main() -> None:
    missing = check_data_files()
    if missing:
        print("ERROR: Required data files are missing:")
        for f in missing:
            print(f"  - {f}")
        print("\nDownload the data files and place them in the paths above.")
        print("See README.md for download links.")
        sys.exit(1)

    print("=== Step 1/3: Initialise PostGIS extensions ===")
    from backend.scripts.init_db import main as init_db
    init_db()

    print("\n=== Step 2/3: Create tables ===")
    from backend.scripts.create_tables import main as create_tables
    create_tables()

    print("\n=== Step 3/3: Run full pipeline ===")
    from backend.pipeline.flows.full_pipeline import run_full_pipeline
    summary = run_full_pipeline()

    print("\n=== Seed complete ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
