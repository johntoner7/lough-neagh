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
import pymannkendall as mk
from sqlalchemy import create_engine, text

from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.process.metrics import compute_rolling_means

logger = logging.getLogger(__name__)


def _engine(database_url: str):
    return create_engine(database_url)


def identify_new_readings(csv_path: str, engine) -> pd.DataFrame:
    """Load and clean the updated FOI CSV; return only readings not yet in the DB."""
    _, readings_df = load_and_clean_foi(csv_path)
    readings_df["reading_date"] = pd.to_datetime(readings_df["reading_date"])

    existing = pd.read_sql_query(
        "SELECT station_code::bigint AS station_code, reading_date FROM readings",
        engine,
    )
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

    columns = [
        "station_code", "reading_date", "p_sol_mg_l", "p_tot_mg_l",
        "no3_n_mg_l", "no2_n_mg_l", "below_detection", "sparse_year",
    ]
    insert_df = new_readings_df[columns].copy()
    insert_df["station_code"] = pd.to_numeric(
        insert_df["station_code"], errors="coerce"
    ).astype("Int64")
    insert_df["reading_date"] = pd.to_datetime(
        insert_df["reading_date"], errors="coerce"
    ).dt.date

    insert_df.to_sql(
        "readings", engine,
        if_exists="append", index=False,
        chunksize=10_000, method="multi",
    )

    affected_stations = sorted(
        int(s) for s in new_readings_df["station_code"].dropna().unique()
    )
    affected_years = sorted(
        int(y) for y in pd.to_datetime(new_readings_df["reading_date"]).dt.year.unique()
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
    station_list = ", ".join(str(int(s)) for s in affected_stations)

    annual_df = pd.read_sql_query(
        f"""
        SELECT
            station_code,
            DATE_PART('year', reading_date)::INTEGER AS year,
            AVG(p_sol_mg_l)                          AS annual_mean_p_sol,
            COUNT(*)                                  AS reading_count,
            COUNT(*) < 8                              AS sparse_year,
            AVG(p_sol_mg_l) <= 0.035                 AS wfd_compliant
        FROM readings
        WHERE p_sol_mg_l IS NOT NULL
          AND p_sol_mg_l > 0
          AND station_code IN ({station_list})
        GROUP BY station_code, year
        ORDER BY station_code, year
        """,
        engine,
    )

    annual_df = compute_rolling_means(annual_df)

    insert_df = annual_df[[
        "station_code", "year", "annual_mean_p_sol",
        "reading_count", "sparse_year", "wfd_compliant", "rolling_mean_5yr",
    ]].copy()
    insert_df["station_code"] = insert_df["station_code"].astype("Int64")
    insert_df["year"] = insert_df["year"].astype("int64")
    insert_df["annual_mean_p_sol"] = insert_df["annual_mean_p_sol"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["reading_count"] = insert_df["reading_count"].astype("Int64")
    insert_df["rolling_mean_5yr"] = insert_df["rolling_mean_5yr"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )

    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM annual_metrics WHERE station_code IN ({station_list})"))

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
    station_list = ", ".join(str(int(s)) for s in affected_stations)

    annual_data = pd.read_sql_query(
        f"""
        SELECT station_code, year, annual_mean_p_sol, sparse_year
        FROM annual_metrics
        WHERE year >= 2010
          AND station_code IN ({station_list})
        ORDER BY station_code, year
        """,
        engine,
    )

    results = []
    for station in annual_data["station_code"].unique():
        series = annual_data[annual_data["station_code"] == station].sort_values("year")
        valid = series[~series["sparse_year"]]

        if len(valid) >= 8:
            r = mk.original_test(valid["annual_mean_p_sol"].values)
            direction = r.trend if r.trend in ("increasing", "decreasing") else "no trend"
            results.append({
                "station_code": int(station),
                "trend_direction": direction,
                "p_value": float(r.p),
                "sens_slope": float(r.slope),
                "significant": bool(r.p < 0.05),
                "years_analysed": len(valid),
            })
        else:
            results.append({
                "station_code": int(station),
                "trend_direction": "insufficient data",
                "p_value": None,
                "sens_slope": None,
                "significant": False,
                "years_analysed": len(valid),
            })

    if not results:
        logger.info("No trend results to update.")
        return 0

    trend_df = pd.DataFrame(results)

    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM trend_results WHERE station_code IN ({station_list})"))

    trend_df.to_sql(
        "trend_results", engine,
        if_exists="append", index=False, method="multi",
    )

    logger.info("Updated trend results for %d stations.", len(results))
    return len(results)


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
    url = database_url or os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = _engine(url)

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
