"""Pure data-shaping helpers for the annual refresh flow."""

from __future__ import annotations

import pandas as pd


def prepare_new_readings_for_insert(new_readings_df: pd.DataFrame) -> tuple[pd.DataFrame, list[int], list[int]]:
    """Normalize new readings and derive the affected station/year lists."""
    columns = [
        "station_code",
        "reading_date",
        "p_sol_mg_l",
        "p_tot_mg_l",
        "no3_n_mg_l",
        "no2_n_mg_l",
        "below_detection",
        "sparse_year",
    ]

    insert_df = new_readings_df[columns].copy()
    insert_df["station_code"] = pd.to_numeric(insert_df["station_code"], errors="coerce").astype("Int64")
    insert_df["reading_date"] = pd.to_datetime(insert_df["reading_date"], errors="coerce").dt.date

    affected_stations = sorted(int(s) for s in new_readings_df["station_code"].dropna().unique())
    affected_years = sorted(
        int(y)
        for y in pd.to_datetime(new_readings_df["reading_date"], errors="coerce").dt.year.dropna().unique()
    )

    return insert_df, affected_stations, affected_years


def build_annual_metrics_insert_df(annual_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare annual metrics for database insertion."""
    insert_df = annual_df[
        [
            "station_code",
            "year",
            "annual_mean_p_sol",
            "reading_count",
            "sparse_year",
            "wfd_compliant",
            "rolling_mean_5yr",
        ]
    ].copy()
    insert_df["station_code"] = insert_df["station_code"].astype("Int64")
    insert_df["year"] = insert_df["year"].astype("int64")
    insert_df["annual_mean_p_sol"] = insert_df["annual_mean_p_sol"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["reading_count"] = insert_df["reading_count"].astype("Int64")
    insert_df["rolling_mean_5yr"] = insert_df["rolling_mean_5yr"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    return insert_df