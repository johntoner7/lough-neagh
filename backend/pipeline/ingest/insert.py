"""Database insertion utilities for pipeline data."""

from __future__ import annotations

import os

import geopandas as gpd
import pandas as pd
from sqlalchemy import text
from shapely.geometry import Point


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


def insert_stations(enriched_stations_gdf: gpd.GeoDataFrame, engine) -> None:
    """Insert all stations into the `stations` table."""
    required_columns = [
        "station_code",
        "location_name",
        "wfd_site_id",
        "river_waterbody_id",
        "catchment_name",
        "easting",
        "northing",
        "wfd_matched",
        "first_reading",
        "last_reading",
        "total_readings",
    ]

    stations = enriched_stations_gdf.copy()
    crs = stations.crs
    stations = stations.rename(columns={"geometry": "geom"})
    stations = gpd.GeoDataFrame(stations, geometry="geom", crs=crs)

    for column in required_columns:
        if column not in stations.columns:
            stations[column] = None

    stations = stations[required_columns + ["geom"]].copy()
    stations["station_code"] = pd.to_numeric(stations["station_code"], errors="coerce").astype("Int64")
    stations["easting"] = pd.to_numeric(stations["easting"], errors="coerce").round().astype("Int64")
    stations["northing"] = pd.to_numeric(stations["northing"], errors="coerce").round().astype("Int64")

    geom_x = stations["geom"].x.round().astype("Int64")
    geom_y = stations["geom"].y.round().astype("Int64")
    stations["easting"] = stations["easting"].fillna(geom_x)
    stations["northing"] = stations["northing"].fillna(geom_y)

    # Validate Irish Grid coordinate ranges: easting 0-400k, northing 0-470k
    valid_easting = (stations["easting"] >= 0) & (stations["easting"] <= 400000)
    valid_northing = (stations["northing"] >= 0) & (stations["northing"] <= 470000)
    valid_coords = valid_easting & valid_northing

    # Set invalid coordinates and geometry to null
    invalid_mask = ~valid_coords
    if invalid_mask.any():
        stations.loc[invalid_mask, "easting"] = None
        stations.loc[invalid_mask, "northing"] = None
        stations.loc[invalid_mask, "geom"] = None

    missing_coords = stations["easting"].isna() | stations["northing"].isna()
    if missing_coords.any():
        stations.loc[missing_coords, "easting"] = 0
        stations.loc[missing_coords, "northing"] = 0
        stations.loc[missing_coords, "geom"] = [Point(0, 0)] * int(missing_coords.sum())

    stations["easting"] = stations["easting"].astype("Int64")
    stations["northing"] = stations["northing"].astype("Int64")

    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE readings RESTART IDENTITY;"))
        connection.execute(text("TRUNCATE TABLE stations RESTART IDENTITY CASCADE;"))

    stations.to_postgis("stations", engine, if_exists="append", index=False)


def insert_readings(readings_df: pd.DataFrame, engine) -> None:
    """Insert cleaned readings into the `readings` table in chunks."""
    columns = [
        "station_code",
        "reading_date",
        "p_sol_mg_l",
        "no3_n_mg_l",
        "no2_n_mg_l",
        "below_detection",
        "sparse_year",
    ]
    readings = readings_df.copy()
    readings = readings[columns]
    readings["station_code"] = pd.to_numeric(readings["station_code"], errors="coerce").astype("Int64")
    readings["reading_date"] = pd.to_datetime(readings["reading_date"], errors="coerce").dt.date

    readings.to_sql(
        "readings",
        engine,
        if_exists="append",
        index=False,
        chunksize=10_000,
        method="multi",
    )


def insert_waterbodies(waterbodies_gdf: gpd.GeoDataFrame, engine) -> None:
    """Insert WFD waterbody polygons into the `waterbodies` table."""
    waterbodies_gdf.to_postgis("waterbodies", engine, if_exists="replace", index=False)
