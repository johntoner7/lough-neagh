"""API route tests.

Uses FastAPI's TestClient against a real database. The conftest.py fixture
will skip this entire module if the database is unavailable.

Run from the backend/ directory:
    pytest tests/api/ -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

KNOWN_STATION = 10233   # Six Mile Water — present across the full 1990–2024 range
KNOWN_CATCHMENT = "Blackwater"
RECENT_YEAR = 2023
EARLY_YEAR = 1990


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_status_ok(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_database_connected(self, client: TestClient) -> None:
        assert client.get("/health").json()["database"] == "connected"


# ---------------------------------------------------------------------------
# /stations/years
# ---------------------------------------------------------------------------

class TestStationYears:
    def test_returns_list_of_ints(self, client: TestClient) -> None:
        r = client.get("/stations/years")
        assert r.status_code == 200
        years = r.json()
        assert isinstance(years, list)
        assert all(isinstance(y, int) for y in years)

    def test_covers_expected_range(self, client: TestClient) -> None:
        years = client.get("/stations/years").json()
        assert min(years) <= EARLY_YEAR
        assert max(years) >= RECENT_YEAR

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/stations/years")
        assert "public" in r.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# /stations/geojson
# ---------------------------------------------------------------------------

class TestStationsGeoJSON:
    def test_returns_feature_collection(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR})
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert isinstance(body["features"], list)
        assert len(body["features"]) > 0

    def test_metadata_fields(self, client: TestClient) -> None:
        body = client.get("/stations/geojson", params={"year": RECENT_YEAR}).json()
        meta = body["metadata"]
        assert meta["year"] == RECENT_YEAR
        assert meta["total_stations"] >= meta["stations_with_data"]
        assert meta["wfd_threshold_mg_l"] == pytest.approx(0.035)

    def test_feature_properties_schema(self, client: TestClient) -> None:
        features = client.get("/stations/geojson", params={"year": RECENT_YEAR}).json()["features"]
        for f in features[:5]:  # spot-check first five
            props = f["properties"]
            assert "station_code" in props
            assert "location_name" in props
            assert "wfd_matched" in props

    def test_catchment_filter(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT})
        assert r.status_code == 200
        features = r.json()["features"]
        assert len(features) > 0
        assert all(f["properties"]["catchment_name"] == KNOWN_CATCHMENT for f in features)

    def test_catchment_filter_returns_fewer_than_full(self, client: TestClient) -> None:
        full = client.get("/stations/geojson", params={"year": RECENT_YEAR}).json()["features"]
        filtered = client.get("/stations/geojson", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT}).json()["features"]
        assert len(filtered) < len(full)

    def test_rolling_metric(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "metric": "rolling"})
        assert r.status_code == 200
        # metric_p_sol should be populated for stations that have rolling data
        features_with_data = [
            f for f in r.json()["features"]
            if f["properties"]["metric_p_sol"] is not None
        ]
        assert len(features_with_data) > 0

    def test_invalid_metric_rejected(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "metric": "invalid"})
        assert r.status_code == 422

    def test_missing_year_rejected(self, client: TestClient) -> None:
        r = client.get("/stations/geojson")
        assert r.status_code == 422

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR})
        assert "public" in r.headers.get("cache-control", "")

    # -- bbox filter --

    def test_bbox_filter_reduces_results(self, client: TestClient) -> None:
        full = client.get("/stations/geojson", params={"year": RECENT_YEAR}).json()["features"]
        # Tight bbox around eastern NI
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "bbox": "-6.1,54.5,-5.8,54.7"})
        assert r.status_code == 200
        filtered = r.json()["features"]
        assert len(filtered) < len(full)

    def test_bbox_filter_empty_outside_ni(self, client: TestClient) -> None:
        # Bbox entirely outside Northern Ireland (North Sea)
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "bbox": "2.0,51.0,3.0,52.0"})
        assert r.status_code == 200
        assert r.json()["features"] == []

    def test_bbox_invalid_format_rejected(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "bbox": "-6.0,54.0"})
        assert r.status_code == 422

    def test_bbox_non_numeric_rejected(self, client: TestClient) -> None:
        r = client.get("/stations/geojson", params={"year": RECENT_YEAR, "bbox": "a,b,c,d"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /stations/{station_code}/timeseries
# ---------------------------------------------------------------------------

class TestStationTimeseries:
    def test_returns_timeseries(self, client: TestClient) -> None:
        r = client.get(f"/stations/{KNOWN_STATION}/timeseries")
        assert r.status_code == 200
        body = r.json()
        assert body["station_code"] == KNOWN_STATION
        assert isinstance(body["series"], list)
        assert len(body["series"]) > 0

    def test_series_fields(self, client: TestClient) -> None:
        series = client.get(f"/stations/{KNOWN_STATION}/timeseries").json()["series"]
        for point in series[:3]:
            assert "year" in point
            assert "reading_count" in point
            assert "sparse_year" in point

    def test_series_ordered_by_year(self, client: TestClient) -> None:
        series = client.get(f"/stations/{KNOWN_STATION}/timeseries").json()["series"]
        years = [p["year"] for p in series]
        assert years == sorted(years)

    def test_unknown_station_returns_404(self, client: TestClient) -> None:
        r = client.get("/stations/999999/timeseries")
        assert r.status_code == 404

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get(f"/stations/{KNOWN_STATION}/timeseries")
        assert "public" in r.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# /catchments
# ---------------------------------------------------------------------------

class TestCatchments:
    def test_returns_list_of_strings(self, client: TestClient) -> None:
        r = client.get("/catchments")
        assert r.status_code == 200
        names = r.json()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)

    def test_known_catchment_present(self, client: TestClient) -> None:
        names = client.get("/catchments").json()
        assert KNOWN_CATCHMENT in names

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/catchments")
        assert "public" in r.headers.get("cache-control", "")


class TestCatchmentSummary:
    def test_returns_summary(self, client: TestClient) -> None:
        r = client.get(f"/catchments/{KNOWN_CATCHMENT}/summary", params={"year": RECENT_YEAR})
        assert r.status_code == 200
        body = r.json()
        assert body["catchment_name"] == KNOWN_CATCHMENT
        assert body["year"] == RECENT_YEAR
        assert body["station_count"] > 0

    def test_stations_list_matches_count(self, client: TestClient) -> None:
        body = client.get(f"/catchments/{KNOWN_CATCHMENT}/summary", params={"year": RECENT_YEAR}).json()
        assert len(body["stations"]) == body["station_count"]

    def test_unknown_catchment_returns_404(self, client: TestClient) -> None:
        r = client.get("/catchments/NoSuchCatchment/summary", params={"year": RECENT_YEAR})
        assert r.status_code == 404

    def test_missing_year_rejected(self, client: TestClient) -> None:
        r = client.get(f"/catchments/{KNOWN_CATCHMENT}/summary")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /lakes/geojson
# ---------------------------------------------------------------------------

class TestLakesGeoJSON:
    def test_returns_feature_collection(self, client: TestClient) -> None:
        r = client.get("/lakes/geojson")
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert len(body["features"]) > 0

    def test_feature_properties_schema(self, client: TestClient) -> None:
        features = client.get("/lakes/geojson").json()["features"]
        for f in features[:5]:
            props = f["properties"]
            assert "lake_id" in props
            assert "lake_name" in props
            assert "ecological_status" in props

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/lakes/geojson")
        assert "public" in r.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# /farms/geojson
# ---------------------------------------------------------------------------

class TestFarmsGeoJSON:
    def test_returns_feature_collection(self, client: TestClient) -> None:
        r = client.get("/farms/geojson")
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert len(body["features"]) > 0

    def test_metadata_year(self, client: TestClient) -> None:
        body = client.get("/farms/geojson").json()
        assert "metadata" in body
        assert "year" in body["metadata"]

    def test_feature_properties_schema(self, client: TestClient) -> None:
        features = client.get("/farms/geojson").json()["features"]
        for f in features[:5]:
            props = f["properties"]
            assert "ward_name" in props
            assert "cattle_per_ha" in props
            assert "lu_per_ha" in props

    def test_catchment_filter(self, client: TestClient) -> None:
        r = client.get("/farms/geojson", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT})
        assert r.status_code == 200
        features = r.json()["features"]
        assert len(features) > 0

    def test_catchment_filter_returns_fewer_than_full(self, client: TestClient) -> None:
        full = client.get("/farms/geojson", params={"year": RECENT_YEAR}).json()["features"]
        filtered = client.get("/farms/geojson", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT}).json()["features"]
        assert len(filtered) < len(full)

    def test_year_clamping(self, client: TestClient) -> None:
        # Year before range should clamp to 2015
        r = client.get("/farms/geojson", params={"year": 1990})
        assert r.status_code == 200
        assert r.json()["metadata"]["year"] == 2015

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/farms/geojson")
        assert "public" in r.headers.get("cache-control", "")


# ---------------------------------------------------------------------------
# /river-segments/*
# ---------------------------------------------------------------------------

class TestRiverSegmentsGeometry:
    def test_returns_feature_collection(self, client: TestClient) -> None:
        r = client.get("/river-segments/geometry")
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert isinstance(body["features"], list)
        assert len(body["features"]) > 0

    def test_features_have_numeric_id(self, client: TestClient) -> None:
        features = client.get("/river-segments/geometry").json()["features"]
        for f in features[:5]:
            assert "id" in f
            assert isinstance(f["id"], (int, str))

    def test_catchment_filter_reduces_results(self, client: TestClient) -> None:
        full = client.get("/river-segments/geometry").json()["features"]
        filtered = client.get("/river-segments/geometry", params={"catchment": KNOWN_CATCHMENT}).json()["features"]
        assert 0 < len(filtered) < len(full)

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/river-segments/geometry")
        assert "public" in r.headers.get("cache-control", "")


class TestRiverSegmentsMetrics:
    def test_returns_dict_keyed_by_segment_id(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics", params={"year": RECENT_YEAR})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)
        assert len(body) > 0

    def test_values_are_float_or_null(self, client: TestClient) -> None:
        body = client.get("/river-segments/metrics", params={"year": RECENT_YEAR}).json()
        for v in list(body.values())[:20]:
            assert v is None or isinstance(v, float)

    def test_annual_metric(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics", params={"year": RECENT_YEAR, "metric": "annual"})
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_invalid_metric_rejected(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics", params={"year": RECENT_YEAR, "metric": "invalid"})
        assert r.status_code == 422

    def test_missing_year_rejected(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics")
        assert r.status_code == 422

    def test_catchment_filter(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT})
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/river-segments/metrics", params={"year": RECENT_YEAR})
        assert "public" in r.headers.get("cache-control", "")


class TestRiverSegmentsGeoJSON:
    def test_returns_feature_collection(self, client: TestClient) -> None:
        r = client.get("/river-segments/geojson", params={"year": RECENT_YEAR})
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == "FeatureCollection"
        assert isinstance(body["features"], list)
        assert len(body["features"]) > 0

    def test_features_have_metric_property(self, client: TestClient) -> None:
        features = client.get("/river-segments/geojson", params={"year": RECENT_YEAR}).json()["features"]
        for f in features[:5]:
            assert "metric_p_sol" in f["properties"]

    def test_missing_year_rejected(self, client: TestClient) -> None:
        r = client.get("/river-segments/geojson")
        assert r.status_code == 422

    def test_invalid_metric_rejected(self, client: TestClient) -> None:
        r = client.get("/river-segments/geojson", params={"year": RECENT_YEAR, "metric": "invalid"})
        assert r.status_code == 422

    def test_cache_header(self, client: TestClient) -> None:
        r = client.get("/river-segments/geojson", params={"year": RECENT_YEAR})
        assert "public" in r.headers.get("cache-control", "")

    def test_catchment_filter_reduces_results(self, client: TestClient) -> None:
        full = client.get("/river-segments/geojson", params={"year": RECENT_YEAR}).json()["features"]
        filtered = client.get("/river-segments/geojson", params={"year": RECENT_YEAR, "catchment": KNOWN_CATCHMENT}).json()["features"]
        assert 0 < len(filtered) < len(full)
