"""Shared fixtures for validation tests.

These tests require external data files and/or a running database.
Each fixture skips automatically when its dependency is unavailable,
so the suite degrades gracefully in CI without the full data set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).parents[2]
_DATA_ROOT = _BACKEND_DIR.parent / "data" / "raw"

FOI_CSV = _DATA_ROOT / "foi" / "annex_a.csv"
WFD_SITES_GEOJSON = (
    _DATA_ROOT
    / "wfd_sites"
    / "WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson"
)
WATERBODIES_SHP = _DATA_ROOT / "wfd_waterbodies" / "WFD_River_Water_Bodies_2016.shp"

KEY_STATIONS = {
    10233: "Six Mile Water",
    10212: "River Main",
    10380: "Moyola",
    10361: "Ballinderry",
    10328: "Blackwater",
    10271: "Upper Bann",
}


def _resolve_database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env_file = _BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return None


@pytest.fixture(scope="session")
def foi_data():
    if not FOI_CSV.exists():
        pytest.skip(f"FOI data not available: {FOI_CSV}")
    from backend.pipeline.ingest.foi import load_and_clean_foi
    return load_and_clean_foi(str(FOI_CSV))


@pytest.fixture(scope="session")
def wfd_sites_gdf():
    if not WFD_SITES_GEOJSON.exists():
        pytest.skip(f"WFD sites GeoJSON not available: {WFD_SITES_GEOJSON}")
    from backend.pipeline.ingest.wfd_sites import load_wfd_sites
    return load_wfd_sites(str(WFD_SITES_GEOJSON))


@pytest.fixture(scope="session")
def waterbodies_gdf():
    if not WATERBODIES_SHP.exists():
        pytest.skip(f"Waterbodies shapefile not available: {WATERBODIES_SHP}")
    from backend.pipeline.ingest.wfd_waterbodies import load_wfd_waterbodies
    return load_wfd_waterbodies(str(WATERBODIES_SHP))


@pytest.fixture(scope="session")
def enriched_stations(foi_data, wfd_sites_gdf):
    from backend.pipeline.process.join import enrich_stations
    stations_df, _ = foi_data
    return enrich_stations(stations_df, wfd_sites_gdf)


@pytest.fixture(scope="session")
def db_engine():
    url = _resolve_database_url()
    if not url:
        pytest.skip("DATABASE_URL not set")
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        conn.close()
    except Exception as exc:
        pytest.skip(f"Database unavailable: {exc}")
    from sqlalchemy import create_engine
    return create_engine(url)


@pytest.fixture(scope="session")
def api_client(db_engine):
    from fastapi.testclient import TestClient

    from api.main import app
    client = TestClient(app)
    r = client.get("/health")
    if r.status_code != 200 or r.json().get("database") != "connected":
        pytest.skip("API health check failed — skipping API validation tests")
    return client
