"""Validation tests for WFD waterbody join (TEST 3).

Requires: data files + a running database.
WARNING: inserts into the waterbodies table (truncate + reload).
Skipped automatically when data or database is unavailable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from .conftest import KEY_STATIONS


@pytest.fixture(scope="module")
def waterbodies_in_db(waterbodies_gdf, db_engine):
    from backend.pipeline.ingest.insert import insert_waterbodies
    insert_waterbodies(waterbodies_gdf, db_engine)
    return db_engine


@pytest.fixture(scope="module")
def stations_test_table(enriched_stations, waterbodies_in_db):
    engine = waterbodies_in_db
    matched = enriched_stations[enriched_stations["wfd_matched"]].copy()
    matched = matched[["station_code", "river_waterbody_id", "geometry"]]
    matched.to_postgis("stations_test", engine, if_exists="replace", index=False)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS stations_test"))


def test_waterbody_count(waterbodies_gdf):
    assert len(waterbodies_gdf) >= 400


def test_all_matched_stations_have_waterbody_polygon(stations_test_table):
    engine = stations_test_table
    with engine.begin() as conn:
        match_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stations_test s
                JOIN waterbodies w ON s.river_waterbody_id = w.river_waterbody_id
                """
            )
        ).scalar_one()
    assert int(match_count) == 525


def test_no_matched_stations_missing_waterbody_polygon(stations_test_table):
    engine = stations_test_table
    with engine.begin() as conn:
        missing = conn.execute(
            text(
                """
                SELECT s.river_waterbody_id
                FROM stations_test s
                LEFT JOIN waterbodies w ON s.river_waterbody_id = w.river_waterbody_id
                WHERE w.river_waterbody_id IS NULL
                """
            )
        ).fetchall()
    assert len(missing) == 0, f"{len(missing)} matched stations missing waterbody polygons"


@pytest.mark.parametrize("station_code,name", list(KEY_STATIONS.items()))
def test_key_station_within_waterbody(stations_test_table, station_code, name):
    engine = stations_test_table
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    ST_Contains(w.geometry, s.geometry) AS contains,
                    ST_DWithin(w.geometry, s.geometry, 500) AS within_500m
                FROM stations_test s
                JOIN waterbodies w ON s.river_waterbody_id = w.river_waterbody_id
                WHERE s.station_code = :code
                """
            ),
            {"code": station_code},
        ).mappings().first()
    assert row is not None, f"Key station {name} ({station_code}) not found in stations_test"
    assert bool(row["contains"]) or bool(row["within_500m"]), (
        f"Key station {name} ({station_code}) not within waterbody polygon or 500m"
    )
