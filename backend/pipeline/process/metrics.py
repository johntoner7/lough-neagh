"""Compute derived metrics from raw readings."""

from __future__ import annotations

import pandas as pd
import pymannkendall as mk
from sqlalchemy import text


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
    Only computes where a complete ±2 year window with at least 3 non-sparse years exists.
    """
    annual_df = annual_df.copy()
    annual_df["rolling_mean_5yr"] = None

    for station in annual_df["station_code"].unique():
        station_data = annual_df[annual_df["station_code"] == station].copy()
        station_data = station_data.sort_values("year").reset_index(drop=True)

        for _, row in station_data.iterrows():
            year = row["year"]
            window = station_data[station_data["year"].isin(range(year - 2, year + 3))]

            if len(window) < 5:
                continue

            valid = window[~window["sparse_year"]]
            if len(valid) < 3:
                continue

            loc = annual_df[
                (annual_df["station_code"] == station) & (annual_df["year"] == year)
            ].index
            if not loc.empty:
                annual_df.loc[loc[0], "rolling_mean_5yr"] = float(valid["annual_mean_p_sol"].mean())

    return annual_df


def compute_trend_results(engine) -> pd.DataFrame:
    """
    For each station with at least 8 non-sparse annual means since 2010:
    run Mann-Kendall test and return trend direction, p-value, and Sen slope.
    """
    annual_data = pd.read_sql_query(
        """
        SELECT station_code, year, annual_mean_p_sol, sparse_year
        FROM annual_metrics
        WHERE year >= 2010
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
                "station_code": station,
                "trend_direction": direction,
                "p_value": r.p,
                "sens_slope": r.slope,
                "significant": r.p < 0.05,
                "years_analysed": len(valid),
            })
        else:
            results.append({
                "station_code": station,
                "trend_direction": "insufficient data",
                "p_value": None,
                "sens_slope": None,
                "significant": False,
                "years_analysed": len(valid),
            })

    return pd.DataFrame(results)


def insert_annual_metrics(annual_df: pd.DataFrame, engine) -> None:
    """Truncate and reload the annual_metrics table."""
    insert_df = annual_df[[
        "station_code", "year", "annual_mean_p_sol", "reading_count",
        "sparse_year", "wfd_compliant", "rolling_mean_5yr",
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
        conn.execute(text("TRUNCATE TABLE annual_metrics RESTART IDENTITY;"))

    insert_df.to_sql(
        "annual_metrics", engine,
        if_exists="append", index=False, chunksize=1000, method="multi",
    )


def insert_trend_results(trend_df: pd.DataFrame, engine) -> None:
    """Truncate and reload the trend_results table."""
    insert_df = trend_df[[
        "station_code", "trend_direction", "p_value", "sens_slope",
        "significant", "years_analysed",
    ]].copy()
    insert_df["station_code"] = insert_df["station_code"].astype("int64")
    insert_df["p_value"] = insert_df["p_value"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["sens_slope"] = insert_df["sens_slope"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["significant"] = insert_df["significant"].astype("bool")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE trend_results RESTART IDENTITY;"))

    insert_df.to_sql(
        "trend_results", engine,
        if_exists="append", index=False, method="multi",
    )
