"""Create the core database tables for the phosphorus pipeline."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


TABLES_SQL = """
CREATE TABLE IF NOT EXISTS stations (
    station_code        INTEGER PRIMARY KEY,
    location_name       TEXT NOT NULL,
    wfd_site_id         TEXT,
    river_waterbody_id  TEXT,
    catchment_name      TEXT,
    easting             INTEGER NOT NULL,
    northing            INTEGER NOT NULL,
    geom                GEOMETRY(POINT, 29902),
    wfd_matched         BOOLEAN NOT NULL DEFAULT FALSE,
    first_reading       DATE,
    last_reading        DATE,
    total_readings      INTEGER
);

CREATE TABLE IF NOT EXISTS readings (
    id                  SERIAL PRIMARY KEY,
    station_code        INTEGER REFERENCES stations(station_code),
    reading_date        DATE NOT NULL,
    p_sol_mg_l          FLOAT,
    p_tot_mg_l          FLOAT,
    no3_n_mg_l          FLOAT,
    no2_n_mg_l          FLOAT,
    below_detection     BOOLEAN DEFAULT FALSE,
    sparse_year         BOOLEAN DEFAULT FALSE,
    likely_outlier      BOOLEAN DEFAULT FALSE
);

ALTER TABLE readings
ADD COLUMN IF NOT EXISTS p_tot_mg_l FLOAT;

ALTER TABLE readings
ADD COLUMN IF NOT EXISTS likely_outlier BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS annual_metrics (
    id                  SERIAL PRIMARY KEY,
    station_code        INTEGER REFERENCES stations(station_code),
    year                INTEGER NOT NULL,
    annual_mean_p_sol   FLOAT,
    reading_count       INTEGER,
    sparse_year         BOOLEAN DEFAULT FALSE,
    wfd_compliant       BOOLEAN,
    rolling_mean_5yr    FLOAT,
    UNIQUE(station_code, year)
);

CREATE TABLE IF NOT EXISTS trend_results (
    station_code        INTEGER PRIMARY KEY REFERENCES stations(station_code),
    trend_direction     TEXT,
    p_value             FLOAT,
    sens_slope          FLOAT,
    significant         BOOLEAN,
    years_analysed      INTEGER,
    computed_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS waterbodies (
    river_waterbody_id  TEXT PRIMARY KEY,
    catchment_name      TEXT,
    geom                GEOMETRY(MULTIPOLYGON, 29902)
);

CREATE TABLE IF NOT EXISTS lakes (
    lake_id             TEXT PRIMARY KEY,
    lake_name           TEXT,
    ecological_status   TEXT,
    total_phosphorus    TEXT,
    label_text          TEXT,
    geom                GEOMETRY(MULTIPOLYGON, 29902)
);

CREATE TABLE IF NOT EXISTS farm_census_wards (
    id              SERIAL PRIMARY KEY,
    ward_name       TEXT NOT NULL,
    ward_code       TEXT NOT NULL,
    catchment_name  TEXT,
    year            INTEGER NOT NULL,
    num_farms       INTEGER,
    area_ha         FLOAT,
    cattle          INTEGER,
    sheep           INTEGER,
    pigs            INTEGER,
    cattle_per_ha   FLOAT,
    lu_per_ha       FLOAT,
    geometry        GEOMETRY(MULTIPOLYGON, 4326),
    UNIQUE(ward_code, year)
);

CREATE TABLE IF NOT EXISTS river_segments (
    id                   SERIAL PRIMARY KEY,
    rseg_cd              TEXT NOT NULL UNIQUE,
    rwb_cd               TEXT,
    strahler             FLOAT,
    nearest_station_code INTEGER,
    nearest_dist_m       FLOAT,
    geom                 GEOMETRY(LINESTRING, 29902) NOT NULL
);

ALTER TABLE stations ADD COLUMN IF NOT EXISTS geom_4326 GEOMETRY(POINT, 4326);
UPDATE stations SET geom_4326 = ST_Transform(geom, 4326) WHERE geom_4326 IS NULL AND geom IS NOT NULL;
CREATE TABLE IF NOT EXISTS geojson_cache (
    cache_key  TEXT PRIMARY KEY,
    data       BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_stations_geom_4326 ON stations USING GIST(geom_4326);
CREATE INDEX IF NOT EXISTS idx_waterbodies_geom ON waterbodies USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_lakes_geom ON lakes USING GIST(geom);
ALTER TABLE farm_census_wards ADD COLUMN IF NOT EXISTS geom_simplified GEOMETRY;
ALTER TABLE farm_census_wards ALTER COLUMN geom_simplified TYPE GEOMETRY USING geom_simplified::geometry;
UPDATE farm_census_wards
    SET geom_simplified = ST_SimplifyPreserveTopology(geometry, 0.001)
    WHERE geom_simplified IS NULL AND geometry IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_farm_census_wards_geom ON farm_census_wards USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_farm_census_wards_geom_simplified ON farm_census_wards USING GIST(geom_simplified);
CREATE INDEX IF NOT EXISTS idx_farm_census_wards_year ON farm_census_wards(year);
ALTER TABLE farm_census_wards ADD COLUMN IF NOT EXISTS catchment_name TEXT;
CREATE INDEX IF NOT EXISTS idx_farm_census_wards_catchment ON farm_census_wards(catchment_name);
CREATE INDEX IF NOT EXISTS idx_readings_station_date ON readings(station_code, reading_date);
CREATE INDEX IF NOT EXISTS idx_annual_metrics_station_year ON annual_metrics(station_code, year);
CREATE INDEX IF NOT EXISTS idx_annual_metrics_year_station ON annual_metrics(year, station_code);
ALTER TABLE river_segments ADD COLUMN IF NOT EXISTS geom_4326 GEOMETRY(LINESTRING, 4326);
UPDATE river_segments SET geom_4326 = ST_Transform(geom, 4326) WHERE geom_4326 IS NULL AND geom IS NOT NULL;
ALTER TABLE river_segments ADD COLUMN IF NOT EXISTS geom_simplified GEOMETRY;
UPDATE river_segments
    SET geom_simplified = ST_SimplifyPreserveTopology(ST_Transform(geom, 4326), 0.001)
    WHERE geom_simplified IS NULL AND geom IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_river_segments_geom ON river_segments USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_river_segments_geom_4326 ON river_segments USING GIST(geom_4326);
CREATE INDEX IF NOT EXISTS idx_river_segments_geom_simplified ON river_segments USING GIST(geom_simplified);
CREATE INDEX IF NOT EXISTS idx_river_segments_station ON river_segments(nearest_station_code);

CREATE TABLE IF NOT EXISTS storm_overflows (
    car_id                   TEXT PRIMARY KEY,
    name                     TEXT NOT NULL,
    spill_frequency          FLOAT,
    spill_volume_m3          FLOAT,
    classification           TEXT,
    modelled                 BOOLEAN NOT NULL DEFAULT FALSE,
    monitored                BOOLEAN NOT NULL DEFAULT FALSE,
    receiving_waterbody_id   TEXT,
    receiving_waterbody_name TEXT,
    local_management_area    TEXT,
    catchment_name           TEXT,
    coord_is_discharge_point BOOLEAN NOT NULL DEFAULT FALSE,
    geom                     GEOMETRY(POINT, 29902),
    geom_4326                GEOMETRY(POINT, 4326)
);

CREATE INDEX IF NOT EXISTS idx_storm_overflows_geom_4326 ON storm_overflows USING GIST(geom_4326);
CREATE INDEX IF NOT EXISTS idx_storm_overflows_catchment ON storm_overflows(catchment_name);
"""


def main(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(url)

    with engine.begin() as connection:
        for statement in TABLES_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                connection.execute(text(f"{stmt};"))

    print("Core tables ensured.")


if __name__ == "__main__":
    main()
