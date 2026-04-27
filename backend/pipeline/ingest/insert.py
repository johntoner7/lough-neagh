"""Database insertion utilities for pipeline data."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from sqlalchemy import text


def insert_stations(enriched_stations_gdf: gpd.GeoDataFrame, engine) -> None:
    """Truncate and reload the stations table (also truncates dependent readings)."""
    required_columns = [
        "station_code", "location_name", "wfd_site_id", "river_waterbody_id",
        "catchment_name", "easting", "northing", "wfd_matched",
        "first_reading", "last_reading", "total_readings",
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

    # Validate Irish Grid coordinate ranges: easting 0–400k, northing 0–470k
    valid = (
        (stations["easting"] >= 0) & (stations["easting"] <= 400_000) &
        (stations["northing"] >= 0) & (stations["northing"] <= 470_000)
    )
    stations.loc[~valid, ["easting", "northing", "geom"]] = None

    missing = stations["easting"].isna() | stations["northing"].isna()
    if missing.any():
        stations.loc[missing, "easting"] = 0
        stations.loc[missing, "northing"] = 0
        stations.loc[missing, "geom"] = [Point(0, 0)] * int(missing.sum())

    stations["easting"] = stations["easting"].astype("Int64")
    stations["northing"] = stations["northing"].astype("Int64")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE readings RESTART IDENTITY;"))
        conn.execute(text("TRUNCATE TABLE stations RESTART IDENTITY CASCADE;"))
    stations.to_postgis("stations", engine, if_exists="append", index=False, chunksize=100)


def insert_readings(readings_df: pd.DataFrame, engine) -> None:
    """Append cleaned readings (stations table was already truncated by insert_stations)."""
    columns = [
        "station_code", "reading_date", "p_sol_mg_l", "p_tot_mg_l",
        "no3_n_mg_l", "no2_n_mg_l", "below_detection", "sparse_year",
    ]
    readings = readings_df[columns].copy()
    readings["station_code"] = pd.to_numeric(readings["station_code"], errors="coerce").astype("Int64")
    readings["reading_date"] = pd.to_datetime(readings["reading_date"], errors="coerce").dt.date

    readings.to_sql(
        "readings", engine,
        if_exists="append", index=False,
        chunksize=10_000, method="multi",
    )


def insert_waterbodies(waterbodies_gdf: gpd.GeoDataFrame, engine) -> None:
    """Truncate and reload the waterbodies table."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE waterbodies RESTART IDENTITY;"))
    waterbodies_gdf.to_postgis("waterbodies", engine, if_exists="append", index=False, chunksize=50)


def insert_lakes(lakes_gdf: gpd.GeoDataFrame, engine) -> None:
    """Truncate and reload the lakes table."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE lakes RESTART IDENTITY;"))
    lakes_gdf.to_postgis("lakes", engine, if_exists="append", index=False, chunksize=50)
