"""Safe pipeline runner with pre-flight checks and production confirmation gate.

Usage:
    # Dry-run: validate files and DB connection, print row counts, no writes
    uv run python -m backend.scripts.run_pipeline --dry-run

    # Run against local DB
    uv run python -m backend.scripts.run_pipeline

    # Run against production (requires explicit flag)
    DATABASE_URL=<railway-url> uv run python -m backend.scripts.run_pipeline --production

    # Run against production non-interactively (e.g. in CI)
    DATABASE_URL=<railway-url> uv run python -m backend.scripts.run_pipeline --production --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


# ─── Required source files ────────────────────────────────────────────────────

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"

REQUIRED_FILES = {
    "FOI readings":    DATA_ROOT / "foi" / "annex_a.csv",
    "WFD waterbodies": DATA_ROOT / "wfd_waterbodies" / "WFD_River_Water_Bodies_2016.shp",
    "Lake polygons":   DATA_ROOT / "lakes" / "Lake_Polygon_Classification_Ecological_Status_2024.geojson",
    "Ward boundaries": DATA_ROOT / "farms" / "osni_open_data_largescale_boundaries_wards_2012.geojson",
}

REQUIRED_DIR_GLOBS = {
    "WFD monitoring sites": (DATA_ROOT / "wfd_sites", "*.geojson"),
    "Farm census CSV":      (DATA_ROOT / "farms", "FCWARD.*.csv"),
}


def check_files() -> list[str]:
    missing = []
    for label, path in REQUIRED_FILES.items():
        if not path.exists():
            missing.append(f"  MISSING  {label}: {path}")
        else:
            print(f"  OK       {label}")

    for label, (directory, pattern) in REQUIRED_DIR_GLOBS.items():
        matches = list(directory.glob(pattern)) if directory.exists() else []
        if not matches:
            missing.append(f"  MISSING  {label}: {directory / pattern}")
        else:
            print(f"  OK       {label} ({matches[0].name})")

    return missing


def check_db(database_url: str) -> bool:
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  OK       database reachable")
        return True
    except Exception as e:
        print(f"  FAIL     database: {e}")
        return False


def normalize_database_url(url: str) -> str:
    """Normalize common non-SQLAlchemy Postgres URL forms."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def current_row_counts(database_url: str) -> dict[str, int]:
    tables = ["stations", "readings", "annual_metrics", "trend_results",
              "waterbodies", "lakes", "farm_census_wards"]
    engine = create_engine(database_url)
    counts = {}
    for table in tables:
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = result.scalar()
        except Exception:
            counts[table] = -1  # table doesn't exist yet
    return counts


def is_production_url(url: str) -> bool:
    return "localhost" not in url and "127.0.0.1" not in url


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the phosphorus data pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate files and DB only — no writes")
    parser.add_argument("--production", action="store_true",
                        help="Required when targeting a remote host")
    parser.add_argument("--db-url", metavar="URL",
                        help="Override DATABASE_URL (useful when the injected URL is internal-only)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip interactive confirmation (for CI/non-interactive environments)")
    args = parser.parse_args()

    database_url = (
        args.db_url
        or os.environ.get("DATABASE_PUBLIC_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql://user:password@localhost:5433/phosphorus_db"
    )
    database_url = normalize_database_url(database_url)

    print("\n=== Pre-flight checks ===\n")

    print("Source files:")
    missing = check_files()

    print("\nDatabase:")
    db_ok = check_db(database_url)

    if missing or not db_ok:
        print("\n✗ Pre-flight failed:")
        for m in missing:
            print(m)
        if not db_ok:
            print("  Database unreachable")
        sys.exit(1)

    print("\n✓ All checks passed\n")

    # ── Show current state ────────────────────────────────────────────────────
    counts = current_row_counts(database_url)
    print("Current row counts:")
    for table, n in counts.items():
        label = "(table not yet created)" if n == -1 else f"{n:,} rows"
        print(f"  {table:<25} {label}")

    if args.dry_run:
        print("\nDry-run complete — no changes made.")
        sys.exit(0)

    # ── Production gate ───────────────────────────────────────────────────────
    if is_production_url(database_url) and not args.production:
        print(
            "\n✗  DATABASE_URL points to a remote host but --production was not passed.\n"
            "   Add --production to confirm you intend to write to the hosted database."
        )
        sys.exit(1)

    if is_production_url(database_url):
        print(
            "\n⚠  You are about to overwrite the PRODUCTION database.\n"
            "   All tables will be truncated and reloaded from local data files.\n"
        )
        if args.yes:
            print("   --yes flag set, skipping confirmation.")
        else:
            confirm = input("   Type 'yes' to continue: ").strip().lower()
            if confirm != "yes":
                print("Aborted.")
                sys.exit(0)

    # ── Initialise schema ─────────────────────────────────────────────────────
    print("\n=== Initialising schema ===\n")

    from backend.scripts.init_db import main as init_db
    init_db(database_url)

    from backend.scripts.create_tables import main as create_tables
    create_tables(database_url)

    # ── Run pipeline ──────────────────────────────────────────────────────────
    print("\n=== Running pipeline ===\n")

    from backend.pipeline.flows.full_pipeline import run_full_pipeline
    summary = run_full_pipeline(database_url=database_url)

    print("\n=== Pipeline complete ===\n")
    for key, value in summary.items():
        print(f"  {key:<25} {value:,}")

    print("\nNew row counts:")
    new_counts = current_row_counts(database_url)
    for table, n in new_counts.items():
        label = "(table not yet created)" if n == -1 else f"{n:,} rows"
        print(f"  {table:<25} {label}")


if __name__ == "__main__":
    main()
