"""Validation tests for database population (TEST 4).

Requires a running database with the full pipeline already applied.
Skipped automatically when the database is unavailable.
"""

from __future__ import annotations

from sqlalchemy import text


def test_station_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM stations")).scalar_one()
    assert int(count) == 1201


def test_readings_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM readings")).scalar_one()
    assert 165_000 <= int(count) <= 175_000


def test_waterbodies_count(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM waterbodies")).scalar_one()
    assert int(count) >= 400


def test_no_null_station_geometries(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM stations WHERE geom IS NULL")
        ).scalar_one()
    assert int(count) == 0


def test_station_spatial_index_works(db_engine):
    with db_engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM stations
                WHERE ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(270000, 370000), 29902),
                    10000
                )
                """
            )
        ).scalar_one()
    assert int(count) > 0
