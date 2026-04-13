from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


def main() -> None:
    engine = create_engine(_database_url())
    failures: list[str] = []

    print("=== TEST 4: DATABASE POPULATION CHECK ===")

    with engine.begin() as connection:
        stations_count = connection.execute(text("SELECT COUNT(*) FROM stations")).scalar_one()
        readings_count = connection.execute(text("SELECT COUNT(*) FROM readings")).scalar_one()
        waterbodies_count = connection.execute(text("SELECT COUNT(*) FROM waterbodies")).scalar_one()

        print(f"stations count: {stations_count}")
        print(f"readings count: {readings_count}")
        print(f"waterbodies count: {waterbodies_count}")

        if int(stations_count) != 1201:
            failures.append(f"Expected 1201 stations, got {stations_count}")
        if not (165000 <= int(readings_count) <= 175000):
            failures.append(f"Expected ~170000 readings, got {readings_count}")
        if int(waterbodies_count) < 400:
            failures.append(f"Expected ~450 waterbodies, got {waterbodies_count}")

        print("\nRecent readings for station 10233:")
        recent = connection.execute(
            text(
                """
                SELECT station_code, reading_date, p_sol_mg_l
                FROM readings
                WHERE station_code = 10233
                ORDER BY reading_date DESC
                LIMIT 5
                """
            )
        ).fetchall()
        for row in recent:
            print(row)

        print("\nStations within 10km of Lough Neagh centre:")
        nearby = connection.execute(
            text(
                """
                SELECT location_name, station_code
                FROM stations
                WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(270000, 370000), 29902), 10000)
                ORDER BY location_name
                """
            )
        ).fetchall()
        print(f"count: {len(nearby)}")
        for row in nearby[:25]:
            print(row)

        null_geom = connection.execute(text("SELECT COUNT(*) FROM stations WHERE geom IS NULL")).scalar_one()
        print(f"\nStations with null geometry: {null_geom}")
        if int(null_geom) != 0:
            failures.append(f"Expected 0 null geometries, got {null_geom}")

    print("\n--- Result ---")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()