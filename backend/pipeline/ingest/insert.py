"""Database insertion utilities for pipeline data."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import linemerge
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


def insert_river_segments(segments_gdf: gpd.GeoDataFrame, engine) -> None:
    """Truncate and reload the river_segments table."""
    gdf = segments_gdf.copy()
    # DB column is named 'geom'; rename the active geometry column to match
    gdf = gdf.rename_geometry("geom")
    # If the GeoDataFrame contains duplicate rseg_cd values, drop them to
    # avoid unique constraint violations during bulk copy.
    if "rseg_cd" in gdf.columns:
        dup_count = int(gdf["rseg_cd"].duplicated(keep=False).sum())
        if dup_count:
            print(f"Warning: {dup_count} duplicate rseg_cd values found — dropping duplicates before insert")
            gdf = gdf.drop_duplicates(subset=["rseg_cd"])

    # Convert MultiLineString geometries to LineString to match DB column type.
    def _to_linestring(geom):
        if geom is None:
            return None
        if isinstance(geom, LineString):
            return geom
        if isinstance(geom, MultiLineString):
            merged = linemerge(geom)
            if isinstance(merged, LineString):
                return merged
            parts = list(merged.geoms) if hasattr(merged, "geoms") else list(geom.geoms)
            if parts:
                return max(parts, key=lambda g: g.length)
        return geom

    multi_count = int((gdf["geom"].geom_type == "MultiLineString").sum())
    if multi_count:
        print(f"Warning: {multi_count} MultiLineString geometries found — converting to LineString before insert")
    gdf["geom"] = gdf["geom"].apply(lambda g: _to_linestring(g))

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE river_segments RESTART IDENTITY CASCADE;"))
    gdf.to_postgis("river_segments", engine, if_exists="append", index=False, chunksize=500)
