"""Validation tests for computed metrics (TEST 5).

Requires a running database with annual_metrics and trend_results populated.
Skipped automatically when the database is unavailable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from .conftest import KEY_STATIONS


def test_annual_metrics_row_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM annual_metrics")).scalar_one()
    assert int(count) >= 1000


def test_rolling_mean_null_for_2024(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM annual_metrics"
                " WHERE year = 2024 AND rolling_mean_5yr IS NOT NULL"
            )
        ).scalar_one()
    assert int(count) <= 10, f"Expected rolling_mean_5yr null for 2024, got {count} non-null"


@pytest.mark.parametrize("station_code,name", list(KEY_STATIONS.items()))
def test_key_station_has_annual_metrics(db_engine, station_code, name):
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM annual_metrics WHERE station_code = :code"
            ),
            {"code": station_code},
        ).scalar_one()
    assert int(count) > 0, f"No annual_metrics rows for {name} ({station_code})"


@pytest.mark.parametrize("station_code,name", list(KEY_STATIONS.items()))
def test_key_station_has_trend_result(db_engine, station_code, name):
    with db_engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT trend_direction FROM trend_results WHERE station_code = :code"
            ),
            {"code": station_code},
        ).fetchone()
    assert row is not None, f"No trend_results row for {name} ({station_code})"
    assert row[0] in ("increasing", "decreasing", "no trend", "insufficient data")
