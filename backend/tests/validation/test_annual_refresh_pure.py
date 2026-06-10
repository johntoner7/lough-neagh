from __future__ import annotations

import pandas as pd

from backend.pipeline.process.annual_refresh import (
    build_annual_metrics_insert_df,
    build_trend_results_df,
    prepare_new_readings_for_insert,
)


def test_prepare_new_readings_for_insert_normalizes_dates_and_summaries() -> None:
    frame = pd.DataFrame(
        {
            "station_code": [10233, 10233, 10380],
            "reading_date": ["2024-01-15", "2024-02-20", "2023-11-01"],
            "p_sol_mg_l": [0.05, 0.04, 0.03],
            "p_tot_mg_l": [0.07, 0.05, 0.04],
            "no3_n_mg_l": [1.1, 1.2, 1.3],
            "no2_n_mg_l": [0.01, 0.02, 0.03],
            "below_detection": [False, False, True],
            "sparse_year": [False, False, True],
        }
    )

    insert_df, affected_stations, affected_years = prepare_new_readings_for_insert(frame)

    assert list(insert_df.columns) == [
        "station_code",
        "reading_date",
        "p_sol_mg_l",
        "p_tot_mg_l",
        "no3_n_mg_l",
        "no2_n_mg_l",
        "below_detection",
        "sparse_year",
    ]
    assert insert_df["reading_date"].tolist() == [
        pd.Timestamp("2024-01-15").date(),
        pd.Timestamp("2024-02-20").date(),
        pd.Timestamp("2023-11-01").date(),
    ]
    assert affected_stations == [10233, 10380]
    assert affected_years == [2023, 2024]


def test_build_annual_metrics_insert_df_preserves_expected_shape() -> None:
    frame = pd.DataFrame(
        {
            "station_code": [10233],
            "year": [2024],
            "annual_mean_p_sol": [0.041],
            "reading_count": [12],
            "sparse_year": [False],
            "wfd_compliant": [False],
            "rolling_mean_5yr": [0.039],
        }
    )

    insert_df = build_annual_metrics_insert_df(frame)

    assert list(insert_df.columns) == [
        "station_code",
        "year",
        "annual_mean_p_sol",
        "reading_count",
        "sparse_year",
        "wfd_compliant",
        "rolling_mean_5yr",
    ]
    assert insert_df.loc[0, "station_code"] == 10233
    assert insert_df.loc[0, "year"] == 2024
    assert insert_df.loc[0, "annual_mean_p_sol"] == 0.041
    assert insert_df.loc[0, "rolling_mean_5yr"] == 0.039


def test_build_trend_results_df_classifies_station_trends() -> None:
    increasing = pd.DataFrame(
        {
            "station_code": [10233] * 8,
            "year": list(range(2010, 2018)),
            "annual_mean_p_sol": [0.01 * (i + 1) for i in range(8)],
            "sparse_year": [False] * 8,
        }
    )
    insufficient = pd.DataFrame(
        {
            "station_code": [10380] * 7,
            "year": list(range(2010, 2017)),
            "annual_mean_p_sol": [0.02] * 7,
            "sparse_year": [False] * 7,
        }
    )

    trend_df = build_trend_results_df(pd.concat([increasing, insufficient], ignore_index=True))

    increasing_row = trend_df.loc[trend_df["station_code"] == 10233].iloc[0]
    insufficient_row = trend_df.loc[trend_df["station_code"] == 10380].iloc[0]

    assert increasing_row["trend_direction"] == "increasing"
    assert bool(increasing_row["significant"]) is True
    assert increasing_row["years_analysed"] == 8
    assert insufficient_row["trend_direction"] == "insufficient data"
    assert bool(insufficient_row["significant"]) is False
    assert insufficient_row["years_analysed"] == 7