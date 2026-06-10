"""Validation tests for API endpoints (TEST 6).

Tests data-value assertions against a running database.
Skipped automatically when the database is unavailable.
"""

from __future__ import annotations

import pytest

STATION_CODE = 10233  # Six Mile Water


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "database" in body


def test_geojson_2024_structure(api_client):
    r = api_client.get("/stations/geojson", params={"year": 2024})
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 0


def test_geojson_2024_metadata(api_client):
    meta = api_client.get("/stations/geojson", params={"year": 2024}).json()["metadata"]
    assert meta["total_stations"] >= meta["stations_with_data"]
    assert meta["wfd_threshold_mg_l"] == pytest.approx(0.035)


def test_phosphorus_improvement_1990_vs_2024(api_client):
    def mean_p_sol(year: int) -> float:
        values = [
            f["properties"]["annual_mean_p_sol"]
            for f in api_client.get("/stations/geojson", params={"year": year}).json()["features"]
            if f["properties"]["annual_mean_p_sol"] is not None
        ]
        return sum(values) / len(values)

    assert mean_p_sol(1990) > mean_p_sol(2024)


def test_catchment_filter_blackwater(api_client):
    all_features = api_client.get("/stations/geojson", params={"year": 2024}).json()["features"]
    bw_features = api_client.get(
        "/stations/geojson", params={"year": 2024, "catchment": "Blackwater"}
    ).json()["features"]

    assert len(bw_features) < len(all_features)
    wrong = [
        f for f in bw_features
        if f["properties"]["catchment_name"] not in (None, "Blackwater")
    ]
    assert wrong == []


def test_station_timeseries(api_client):
    r = api_client.get(f"/stations/{STATION_CODE}/timeseries")
    assert r.status_code == 200
    ts = r.json()
    assert ts["station_code"] == STATION_CODE
    assert len(ts["series"]) > 0
    assert ts["trend_direction"] in ("increasing", "decreasing", "no trend", "insufficient data")


def test_catchments_list(api_client):
    r = api_client.get("/catchments")
    assert r.status_code == 200
    names = r.json()
    assert isinstance(names, list)
    assert len(names) > 0


def test_catchment_summary_blackwater(api_client):
    r = api_client.get("/catchments/Blackwater/summary", params={"year": 2024})
    assert r.status_code == 200
    summary = r.json()
    assert summary["catchment_name"] == "Blackwater"
    assert summary["station_count"] > 0
