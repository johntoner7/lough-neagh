"""Compute derived metrics from raw readings."""

from __future__ import annotations

import pandas as pd
import pymannkendall as mk
from sqlalchemy import text

from backend.api.constants import WFD_THRESHOLD_MG_L


def compute_annual_means(engine) -> pd.DataFrame:
    """
    For each station-year with at least 1 non-outlier reading:
    - Compute mean P(SOL)
    - Count readings
    - Flag sparse years (reading_count < 8)
    - Compute WFD compliance (annual_mean <= WFD_THRESHOLD_MG_L)
    """
    query = text("""
        SELECT
            station_code,
            DATE_PART('year', reading_date)::INTEGER AS year,
            AVG(p_sol_mg_l)                          AS annual_mean_p_sol,
            COUNT(*)                                  AS reading_count,
            COUNT(*) < 8                              AS sparse_year,
            AVG(p_sol_mg_l) <= :threshold             AS wfd_compliant
        FROM readings
        WHERE p_sol_mg_l IS NOT NULL AND p_sol_mg_l > 0
        GROUP BY station_code, year
        ORDER BY station_code, year
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"threshold": WFD_THRESHOLD_MG_L})
        return pd.DataFrame(result.fetchall(), columns=list(result.keys()))


def compute_rolling_means(annual_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each station, compute centred 5-year rolling mean of annual_mean_p_sol.
    Only computes where a complete ±2 year window with at least 3 non-sparse years exists.
    """
    df = annual_df.copy()
    df["rolling_mean_5yr"] = None

    for _, group in df.groupby("station_code"):
        group = group.sort_values("year")

        for idx, row in group.iterrows():
            year = row["year"]
            window = group[group["year"].between(year - 2, year + 2)]

            if len(window) < 5:
                continue
            valid = window[~window["sparse_year"]]
            if len(valid) < 3:
                continue

            df.loc[idx, "rolling_mean_5yr"] = float(valid["annual_mean_p_sol"].mean())

    return df


def compute_trend_results(annual_data: pd.DataFrame) -> pd.DataFrame:
    """
    Pure: compute Mann-Kendall trend results from a DataFrame of annual metrics.

    Input DataFrame must have columns: station_code, year, annual_mean_p_sol, sparse_year.
    Typically filtered to year >= 2010 before calling.

    For each station with at least 8 non-sparse annual means, runs Mann-Kendall
    and returns trend direction, p-value, and Sen slope.
    """
    results: list[dict] = []

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

    return pd.DataFrame(results)


def load_annual_data_for_trends(engine) -> pd.DataFrame:
    """Load post-2010 annual metrics from the database for trend computation."""
    query = text("""
        SELECT station_code, year, annual_mean_p_sol, sparse_year
        FROM annual_metrics
        WHERE year >= 2010
        ORDER BY station_code, year
    """)
    with engine.connect() as conn:
        result = conn.execute(query)
        return pd.DataFrame(result.fetchall(), columns=list(result.keys()))


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
