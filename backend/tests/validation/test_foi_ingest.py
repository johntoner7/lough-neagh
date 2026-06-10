"""Validation tests for FOI ingestion (TEST 1).

Requires: data/raw/foi/annex_a.csv
Skipped automatically when the file is absent.
"""

from __future__ import annotations

import pandas as pd
import pytest

from .conftest import KEY_STATIONS

EXPECTED_STATIONS = 1201
EXPECTED_DATE_MIN = pd.Timestamp("1990-01-02")
EXPECTED_DATE_MAX = pd.Timestamp("2024-12-11")


@pytest.fixture(scope="module")
def stations_df(foi_data):
    return foi_data[0]


@pytest.fixture(scope="module")
def readings_df(foi_data):
    return foi_data[1]


def test_station_count(readings_df):
    assert readings_df["station_code"].nunique(dropna=True) == EXPECTED_STATIONS


def test_date_range(readings_df):
    assert readings_df["reading_date"].min() == EXPECTED_DATE_MIN
    assert readings_df["reading_date"].max() == EXPECTED_DATE_MAX


def test_row_count(readings_df):
    assert 165_000 <= len(readings_df) <= 175_000


def test_below_detection_count(readings_df):
    count = int(readings_df["below_detection"].sum())
    assert 20_000 <= count <= 35_000


def test_below_detection_not_clustered_in_one_year(readings_df):
    below = readings_df.loc[readings_df["below_detection"], "year"]
    total = int(readings_df["below_detection"].sum())
    top_year_share = (int(below.value_counts().max()) / total) * 100
    assert top_year_share <= 40, f"below_detection concentrated in one year: {top_year_share:.1f}%"


def test_below_detection_key_stations_not_excessive(readings_df):
    key_codes = list(KEY_STATIONS.keys())
    count = int(
        readings_df.loc[
            readings_df["below_detection"] & readings_df["station_code"].isin(key_codes)
        ].shape[0]
    )
    assert count <= 500


def test_moyola_sparse_years(readings_df):
    sparse = (
        readings_df.loc[readings_df["sparse_year"], ["station_code", "year"]]
        .drop_duplicates()
    )
    moyola_sparse = set(sparse.loc[sparse["station_code"] == 10380, "year"].tolist())
    for year in (2015, 2016, 2020):
        assert year in moyola_sparse, f"Expected Moyola sparse year {year} not found"


@pytest.mark.parametrize("station_code,name", list(KEY_STATIONS.items()))
def test_key_station_2024_annual_mean_in_range(readings_df, station_code, name):
    annual_2024 = (
        readings_df.loc[readings_df["year"] == 2024]
        .groupby("station_code", dropna=True)["p_sol_mg_l"]
        .mean()
    )
    value = annual_2024.get(station_code)
    assert not pd.isna(value), f"No 2024 data for {name} ({station_code})"
    assert 0.05 <= value <= 0.20, f"{name} 2024 mean {value:.4f} outside expected 0.05–0.20"
