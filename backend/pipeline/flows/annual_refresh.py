"""Annual refresh flow.

Re-ingests updated DAERA FOI data and recomputes metrics only for stations
that received new readings. Safe to run multiple times on the same file —
new readings are identified by (station_code, reading_date) and inserted once.

Usage:
    uv run python -m backend.pipeline.flows.annual_refresh
    uv run python -m backend.pipeline.flows.annual_refresh --csv-path data/raw/foi/annex_a.csv

Schedule: run each February after DAERA publishes the annual data update.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

from api.constants import WFD_THRESHOLD_MG_L
from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.process.annual_refresh import (
    build_annual_metrics_insert_df,
    prepare_new_readings_for_insert,
)
from backend.pipeline.process.metrics import compute_rolling_means, compute_trend_results

logger = logging.getLogger(__name__)


def identify_new_readings(csv_path: str, engine) -> pd.DataFrame:
    """Load and clean the updated FOI CSV; return only readings not yet in the DB."""
    _, readings_df = load_and_clean_foi(csv_path)
    readings_df["reading_date"] = pd.to_datetime(readings_df["reading_date"])

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT station_code::bigint AS station_code, reading_date FROM readings")
        )
        existing = pd.DataFrame(result.fetchall(), columns=["station_code", "reading_date"])
    existing["reading_date"] = pd.to_datetime(existing["reading_date"])

    merged = readings_df.merge(
        existing[["station_code", "reading_date"]],
        on=["station_code", "reading_date"],
        how="left",
        indicator=True,
    )
    new_readings = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

    logger.info(
        "CSV contains %d readings. %d are new (not yet in database).",
        len(readings_df),
        len(new_readings),
    )
    return new_readings


def insert_new_readings(new_readings_df: pd.DataFrame, engine) -> dict[str, Any]:
    """Append new readings to the readings table. Returns affected stations and years."""
    if new_readings_df.empty:
        logger.info("No new readings to insert — database is already up to date.")
        return {"new_readings": 0, "affected_stations": [], "affected_years": []}

    insert_df, affected_stations, affected_years = prepare_new_readings_for_insert(new_readings_df)

    insert_df.to_sql(
        "readings", engine,
        if_exists="append", index=False,
        chunksize=10_000, method="multi",
    )

    logger.info(
        "Inserted %d new readings across %d stations, years %s.",
        len(insert_df),
        len(affected_stations),
        affected_years,
    )
    return {
        "new_readings": len(insert_df),
        "affected_stations": affected_stations,
        "affected_years": affected_years,
    }


def recompute_annual_metrics(affected_stations: list[int], engine) -> int:
    """Delete and recompute annual_metrics + rolling means for affected stations."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT
                    station_code,
                    DATE_PART('year', reading_date)::INTEGER AS year,
                    AVG(p_sol_mg_l)                          AS annual_mean_p_sol,
                    COUNT(*)                                  AS reading_count,
                    COUNT(*) < 8                              AS sparse_year,
                    AVG(p_sol_mg_l) <= :threshold             AS wfd_compliant
                FROM readings
                WHERE p_sol_mg_l IS NOT NULL
                  AND p_sol_mg_l > 0
                  AND station_code = ANY(:codes)
                GROUP BY station_code, year
                ORDER BY station_code, year
            """),
            {"threshold": WFD_THRESHOLD_MG_L, "codes": affected_stations},
        )
        annual_df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))

    annual_df = compute_rolling_means(annual_df)
    insert_df = build_annual_metrics_insert_df(annual_df)

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM annual_metrics WHERE station_code = ANY(:codes)"),
            {"codes": affected_stations},
        )

    insert_df.to_sql(
        "annual_metrics", engine,
        if_exists="append", index=False,
        chunksize=1000, method="multi",
    )

    logger.info(
        "Recomputed %d station-year metric rows for %d stations.",
        len(insert_df),
        len(affected_stations),
    )
    return len(insert_df)


def recompute_trend_results(affected_stations: list[int], engine) -> int:
    """Recompute Mann-Kendall trend results for affected stations."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT station_code, year, annual_mean_p_sol, sparse_year
                FROM annual_metrics
                WHERE year >= 2010
                  AND station_code = ANY(:codes)
                ORDER BY station_code, year
            """),
            {"codes": affected_stations},
        )
        annual_data = pd.DataFrame(result.fetchall(), columns=list(result.keys()))

    trend_df = compute_trend_results(annual_data)

    if trend_df.empty:
        logger.info("No trend results to update.")
        return 0

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM trend_results WHERE station_code = ANY(:codes)"),
            {"codes": affected_stations},
        )

    trend_df.to_sql(
        "trend_results", engine,
        if_exists="append", index=False, method="multi",
    )

    logger.info("Updated trend results for %d stations.", len(trend_df))
    return len(trend_df)


def annual_refresh(
    csv_path: str = "data/raw/foi/annex_a.csv",
    database_url: str | None = None,
) -> dict[str, Any]:
    """
    Incrementally update the database with new FOI readings.

    1. Load and clean the updated FOI CSV.
    2. Identify readings not already in the database (by station_code + reading_date).
    3. Insert only new readings — safe to re-run on the same file.
    4. Recompute annual_metrics and 5-year rolling means for affected stations only.
    5. Recompute Mann-Kendall trend results for affected stations only.
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    engine = create_engine(url)

    new_readings = identify_new_readings(csv_path, engine)
    summary = insert_new_readings(new_readings, engine)

    if not summary["affected_stations"]:
        return {**summary, "station_years_updated": 0, "trends_recomputed": 0}

    station_years_updated = recompute_annual_metrics(summary["affected_stations"], engine)
    trends_recomputed = recompute_trend_results(summary["affected_stations"], engine)

    return {
        **summary,
        "station_years_updated": station_years_updated,
        "trends_recomputed": trends_recomputed,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run the annual phosphorus data refresh.")
    parser.add_argument(
        "--csv-path",
        default="data/raw/foi/annex_a.csv",
        help="Path to updated DAERA FOI CSV (default: data/raw/foi/annex_a.csv)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection string (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    result = annual_refresh(csv_path=args.csv_path, database_url=args.database_url)
    print("\nRefresh complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    sys.exit(0)
