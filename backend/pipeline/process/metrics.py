"""Pure metric computation functions — no database I/O."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pymannkendall as mk

logger = logging.getLogger(__name__)


def compute_rolling_means(annual_df: pd.DataFrame) -> pd.DataFrame:
    """Compute centred 5-year rolling mean of annual_mean_p_sol per station.

    A value is only written when the ±2-year window contains all 5 years and
    at least 3 of them are non-sparse.
    """
    df = annual_df.copy()
    df["rolling_mean_5yr"] = np.nan

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

    computed = int(df["rolling_mean_5yr"].notna().sum())
    logger.info("compute_rolling_means: %d/%d rows received a rolling mean", computed, len(df))
    return df


def compute_trend_results(annual_data: pd.DataFrame) -> pd.DataFrame:
    """Compute Mann-Kendall trend results from a DataFrame of annual metrics.

    Expects columns: station_code, year, annual_mean_p_sol, sparse_year.
    Typically pre-filtered to year >= 2010 by the caller.
    Requires at least 8 non-sparse years per station to produce a trend.
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

    result_df = pd.DataFrame(results)
    logger.info(
        "compute_trend_results: %d stations — %d with trends, %d insufficient data",
        len(result_df),
        int((result_df["trend_direction"] != "insufficient data").sum()),
        int((result_df["trend_direction"] == "insufficient data").sum()),
    )
    return result_df
