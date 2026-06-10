"""End-to-end validation tests (TEST 11).

Covers: DB integrity, API narrative checks, spatial sanity, annual refresh idempotency.
Requires a running database and (for annual refresh) the FOI CSV.
Skipped automatically when dependencies are unavailable.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

from .conftest import FOI_CSV, KEY_STATIONS

KEY_STATION_CODES = list(KEY_STATIONS.keys())


# ---------------------------------------------------------------------------
# DB integrity
# ---------------------------------------------------------------------------

def test_stations_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM stations")).scalar_one()
    assert int(count) == 1201


def test_readings_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM readings")).scalar_one()
    assert 165_000 <= int(count) <= 175_000


def test_annual_metrics_populated(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM annual_metrics")).scalar_one()
    assert int(count) > 1000


def test_trend_results_populated(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM trend_results")).scalar_one()
    assert int(count) > 100


def test_key_stations_in_annual_metrics(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM annual_metrics"
                " WHERE station_code = ANY(:codes)"
            ),
            {"codes": KEY_STATION_CODES},
        ).scalar_one()
    assert int(count) >= len(KEY_STATION_CODES) * 30


def test_key_stations_in_trend_results(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM trend_results"
                " WHERE station_code = ANY(:codes)"
            ),
            {"codes": KEY_STATION_CODES},
        ).scalar_one()
    assert int(count) == len(KEY_STATION_CODES)


# ---------------------------------------------------------------------------
# API narrative checks
# ---------------------------------------------------------------------------

def test_api_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_1990_geojson_returns_features(api_client):
    r = api_client.get("/stations/geojson", params={"year": 1990})
    assert r.status_code == 200
    assert len(r.json()["features"]) > 0


def test_2024_geojson_returns_features(api_client):
    r = api_client.get("/stations/geojson", params={"year": 2024})
    assert r.status_code == 200
    assert len(r.json()["features"]) > 0


def test_phosphorus_improvement_narrative(api_client):
    means_1990 = [
        f["properties"]["annual_mean_p_sol"]
        for f in api_client.get("/stations/geojson", params={"year": 1990}).json()["features"]
        if f["properties"]["annual_mean_p_sol"] is not None
    ]
    means_2024 = [
        f["properties"]["annual_mean_p_sol"]
        for f in api_client.get("/stations/geojson", params={"year": 2024}).json()["features"]
        if f["properties"]["annual_mean_p_sol"] is not None
    ]
    mean_1990 = sum(means_1990) / len(means_1990)
    mean_2024 = sum(means_2024) / len(means_2024)
    assert mean_1990 > 0.15, f"Expected 1990 mean > 0.15, got {mean_1990}"
    assert mean_2024 < 0.10, f"Expected 2024 mean < 0.10, got {mean_2024}"
    assert mean_1990 > mean_2024


def test_key_stations_have_2024_data(api_client):
    features = api_client.get("/stations/geojson", params={"year": 2024}).json()["features"]
    data_by_code = {
        int(f["properties"]["station_code"]): f["properties"]["annual_mean_p_sol"]
        for f in features
    }
    missing = [code for code in KEY_STATION_CODES if data_by_code.get(code) is None]
    assert missing == [], f"Key stations missing 2024 annual mean: {missing}"


def test_moyola_1990_annual_mean(api_client):
    series = api_client.get("/stations/10380/timeseries").json().get("series", [])
    y1990 = next((pt for pt in series if pt.get("year") == 1990), None)
    assert y1990 is not None
    assert y1990["annual_mean_p_sol"] > 0.10


# ---------------------------------------------------------------------------
# Spatial sanity
# ---------------------------------------------------------------------------

def test_station_10233_geometry_matches_source(db_engine):
    with db_engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    easting, northing,
                    ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(easting, northing), 29902)
                    ) AS dist
                FROM stations WHERE station_code = 10233
                """
            )
        ).mappings().first()
    assert row is not None
    assert float(row["dist"] or 0.0) <= 1.0


def test_station_10233_coordinates_within_ni(db_engine):
    with db_engine.begin() as conn:
        row = conn.execute(
            text("SELECT easting, northing FROM stations WHERE station_code = 10233")
        ).mappings().first()
    assert row is not None
    assert 150_000 <= int(row["easting"]) <= 360_000
    assert 300_000 <= int(row["northing"]) <= 470_000


# ---------------------------------------------------------------------------
# Annual refresh idempotency
# ---------------------------------------------------------------------------

def _write_small_slice(source: Path, dest: Path, nrows: int = 250) -> None:
    with source.open("r", encoding="utf-8", newline="") as src, \
            dest.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst)
        for idx, row in enumerate(reader):
            writer.writerow(row)
            if idx >= nrows:
                break


def test_annual_refresh_idempotent(db_engine):
    if not FOI_CSV.exists():
        pytest.skip(f"FOI CSV not available: {FOI_CSV}")
    with tempfile.TemporaryDirectory() as tmpdir:
        small_csv = Path(tmpdir) / "slice.csv"
        _write_small_slice(FOI_CSV, small_csv)
        proc = subprocess.run(
            [sys.executable, "-m", "backend.pipeline.flows.annual_refresh",
             "--csv-path", str(small_csv)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    assert proc.returncode == 0, f"annual_refresh failed:\n{proc.stderr}"
    assert "new_readings: 0" in f"{proc.stdout}\n{proc.stderr}"
