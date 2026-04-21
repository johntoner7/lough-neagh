from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.ingest.wfd_sites import load_wfd_sites
from backend.pipeline.ingest.insert import insert_waterbodies
from backend.pipeline.ingest.wfd_waterbodies import load_wfd_waterbodies
from backend.pipeline.process.join import enrich_stations


KEY_STATIONS = {
    10233: "Six Mile Water",
    10212: "River Main",
    10380: "Moyola",
    10361: "Ballinderry",
    10328: "Blackwater",
    10271: "Upper Bann",
}


def _candidate_database_urls() -> list[str]:
    candidates: list[str] = []

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        candidates.append(env_url)

    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                candidates.append(line.split("=", 1)[1].strip())
                break

    candidates.extend(
        [
            "postgresql://user:password@localhost:5433/phosphorus_db",
            "postgresql://user:password@127.0.0.1:5433/phosphorus_db",
            "postgresql://user:password@localhost:5432/phosphorus_db",
            "postgresql://user:password@127.0.0.1:5432/phosphorus_db",
        ]
    )

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _resolve_database_url() -> str:
    last_error: Exception | None = None
    for candidate in _candidate_database_urls():
        try:
            conn = psycopg2.connect(candidate)
            conn.close()
            return candidate
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not connect to any candidate DATABASE_URL: {last_error}")


def main() -> None:
    failures: list[str] = []

    foi_path = Path("data/raw/foi/annex_a.csv")
    wfd_sites_path = Path("data/raw/wfd_sites/WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson")
    waterbodies_path = Path("data/raw/wfd_waterbodies/WFD_River_Water_Bodies_2016.shp")

    if not waterbodies_path.exists():
        raise FileNotFoundError(f"Missing shapefile: {waterbodies_path}")

    if not foi_path.exists():
        foi_path = Path("annex_a.csv")
    if not wfd_sites_path.exists():
        wfd_sites_path = Path("WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson")

    stations_df, _ = load_and_clean_foi(str(foi_path))
    wfd_sites = load_wfd_sites(str(wfd_sites_path))
    enriched = enrich_stations(stations_df, wfd_sites)

    waterbodies = load_wfd_waterbodies(str(waterbodies_path))

    print("=== TEST 3: WATERBODY JOIN SANITY CHECK ===")
    print(f"Loaded waterbodies: {len(waterbodies)}")
    if len(waterbodies) < 400:
        failures.append(f"Expected ~450 waterbodies, got {len(waterbodies)}")

    database_url = _resolve_database_url()
    print(f"Using database URL: {database_url}")
    engine = create_engine(database_url)

    insert_waterbodies(waterbodies, engine)

    matched_stations = enriched[enriched["wfd_matched"]].copy()
    matched_stations = matched_stations[["station_code", "river_waterbody_id", "geometry"]]
    matched_stations.to_postgis("stations_test", engine, if_exists="replace", index=False)

    with engine.begin() as connection:
        match_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stations_test s
                JOIN waterbodies w
                  ON s.river_waterbody_id = w.river_waterbody_id
                """
            )
        ).scalar_one()
        print(f"Matched stations with waterbody IDs present in table: {match_count}")
        if int(match_count) != 525:
            failures.append(f"Expected 525 matched stations resolving to polygons, got {match_count}")

        missing_ids = connection.execute(
            text(
                """
                SELECT s.river_waterbody_id
                FROM stations_test s
                LEFT JOIN waterbodies w
                  ON s.river_waterbody_id = w.river_waterbody_id
                WHERE w.river_waterbody_id IS NULL
                ORDER BY s.river_waterbody_id
                """
            )
        ).fetchall()
        if missing_ids:
            print("Missing waterbody IDs for matched stations:")
            for row in missing_ids[:20]:
                print(f"- {row[0]}")
            failures.append(f"Found {len(missing_ids)} matched stations with missing waterbody polygons")

        print("\nKey station spatial containment / proximity checks:")
        for station_code, name in KEY_STATIONS.items():
            row = connection.execute(
                text(
                    """
                    SELECT
                      ST_Contains(w.geometry, s.geometry) AS contains,
                      ST_DWithin(w.geometry, s.geometry, 500) AS within_500m,
                      ST_Distance(w.geometry, s.geometry) AS distance_m
                    FROM stations_test s
                    JOIN waterbodies w
                      ON s.river_waterbody_id = w.river_waterbody_id
                    WHERE s.station_code = :station_code
                    """
                ),
                {"station_code": station_code},
            ).mappings().first()

            if row is None:
                failures.append(f"Could not find key station in stations_test: {station_code}")
                print(f"- {name} ({station_code}): missing")
                continue

            contains = bool(row["contains"])
            within_500m = bool(row["within_500m"])
            distance_m = float(row["distance_m"])
            print(
                f"- {name} ({station_code}): "
                f"contains={contains}, within_500m={within_500m}, distance={distance_m:.1f}m"
            )
            if not (contains or within_500m):
                failures.append(f"Key station {name} ({station_code}) not within waterbody polygon or 500m")

    output_path = Path("tests/validation/waterbodies_map.png")
    fig, ax = plt.subplots(figsize=(10, 10))
    waterbodies.boundary.plot(ax=ax, linewidth=0.3, color="steelblue")
    enriched.plot(ax=ax, markersize=2, color="darkred", alpha=0.7)
    ax.set_title("WFD Waterbodies with Station Points")
    ax.set_xlabel("Easting")
    ax.set_ylabel("Northing")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved map: {output_path}")

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS stations_test"))

    print("\n--- Result ---")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()