"""Compute derived metrics from raw readings."""

from __future__ import annotations

import os

import pandas as pd
import pymannkendall as mk
from sqlalchemy import create_engine, text


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


def compute_annual_means(engine) -> pd.DataFrame:
    """
    For each station-year with at least 1 non-outlier reading:
    - Compute mean P(SOL)
    - Count readings
    - Flag sparse years (reading_count < 8)
    - Compute WFD compliance (annual_mean <= 0.035 mg/l)
    """
    query = """
    SELECT
        station_code,
        DATE_PART('year', reading_date)::INTEGER as year,
        AVG(p_sol_mg_l) as annual_mean_p_sol,
        COUNT(*) as reading_count,
        COUNT(*) < 8 as sparse_year,
        AVG(p_sol_mg_l) <= 0.035 as wfd_compliant
    FROM readings
    WHERE p_sol_mg_l IS NOT NULL AND p_sol_mg_l > 0
    GROUP BY station_code, year
    ORDER BY station_code, year
    """
    return pd.read_sql_query(query, engine)


def compute_rolling_means(annual_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each station, compute centred 5-year rolling mean of annual_mean_p_sol.
    Only compute rolling mean for years where we have a complete ±2 year window with data.
    """
    annual_df = annual_df.copy()
    annual_df["rolling_mean_5yr"] = None

    for station in annual_df["station_code"].unique():
        station_data = annual_df[annual_df["station_code"] == station].copy()
        station_data = station_data.sort_values("year").reset_index(drop=True)

        for idx, row in station_data.iterrows():
            year = row["year"]
            window_years = [year - 2, year - 1, year, year + 1, year + 2]

            # Check if we can form a complete window (all 5 years should exist in data)
            window_data = station_data[station_data["year"].isin(window_years)].copy()

            # Only compute rolling mean if we have all 5 years in the window
            if len(window_data) < 5:
                continue

            valid_data = window_data[~window_data["sparse_year"]]

            # Require at least 3 valid (non-sparse) years
            if len(valid_data) >= 3:
                rolling_mean = float(valid_data["annual_mean_p_sol"].mean())
                loc = annual_df[
                    (annual_df["station_code"] == station) & (annual_df["year"] == year)
                ].index
                if not loc.empty:
                    annual_df.loc[loc[0], "rolling_mean_5yr"] = rolling_mean

    return annual_df


def compute_trend_results(engine) -> pd.DataFrame:
    """
    For each station with at least 8 annual means in post-2010 period:
    - Run Mann-Kendall test
    - Store trend direction, p-value, Sen slope, significance
    """
    annual_query = """
    SELECT station_code, year, annual_mean_p_sol, sparse_year
    FROM annual_metrics
    WHERE year >= 2010
    ORDER BY station_code, year
    """
    annual_data = pd.read_sql_query(annual_query, engine)

    results = []

    for station in annual_data["station_code"].unique():
        station_series = annual_data[annual_data["station_code"] == station].copy()
        station_series = station_series.sort_values("year")

        valid_series = station_series[~station_series["sparse_year"]]

        if len(valid_series) >= 8:
            y = valid_series["annual_mean_p_sol"].values
            result = mk.original_test(y)

            trend_direction = "increasing" if result.trend == "increasing" else "no trend"
            if result.trend == "decreasing":
                trend_direction = "decreasing"

            results.append(
                {
                    "station_code": station,
                    "trend_direction": trend_direction,
                    "p_value": result.p,
                    "sens_slope": result.slope,
                    "significant": result.p < 0.05,
                    "years_analysed": len(valid_series),
                }
            )
        else:
            results.append(
                {
                    "station_code": station,
                    "trend_direction": "insufficient data",
                    "p_value": None,
                    "sens_slope": None,
                    "significant": False,
                    "years_analysed": len(valid_series),
                }
            )

    return pd.DataFrame(results)


def insert_annual_metrics(annual_df: pd.DataFrame, engine) -> None:
    """Insert computed annual metrics into PostGIS."""
    insert_df = annual_df[[
        "station_code", "year", "annual_mean_p_sol", "reading_count",
        "sparse_year", "wfd_compliant", "rolling_mean_5yr"
    ]].copy()

    # Convert numpy types to Python native types
    insert_df["station_code"] = insert_df["station_code"].astype("Int64")
    insert_df["year"] = insert_df["year"].astype("int64")
    insert_df["annual_mean_p_sol"] = insert_df["annual_mean_p_sol"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["reading_count"] = insert_df["reading_count"].astype("Int64")
    insert_df["rolling_mean_5yr"] = insert_df["rolling_mean_5yr"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )

    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE annual_metrics RESTART IDENTITY;"))

    insert_df.to_sql("annual_metrics", engine, if_exists="append", index=False, chunksize=1000, method="multi")


def insert_trend_results(trend_df: pd.DataFrame, engine) -> None:
    """Insert trend analysis results into PostGIS."""
    insert_df = trend_df[[
        "station_code", "trend_direction", "p_value", "sens_slope", "significant", "years_analysed"
    ]].copy()

    # Convert numpy types to Python native types
    insert_df["station_code"] = insert_df["station_code"].astype("int64")
    insert_df["p_value"] = insert_df["p_value"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["sens_slope"] = insert_df["sens_slope"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["significant"] = insert_df["significant"].astype("bool")

    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE trend_results RESTART IDENTITY;"))

    insert_df.to_sql("trend_results", engine, if_exists="append", index=False, method="multi")