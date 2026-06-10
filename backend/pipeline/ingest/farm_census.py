"""Farm census ward ingestion: joins NISRA CSV with OSNI ward boundaries."""

from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon
from sqlalchemy import create_engine, text

_DATA_ROOT = Path(__file__).parents[3] / "data" / "raw" / "farms"

WARDS_GEOJSON = _DATA_ROOT / "osni_open_data_largescale_boundaries_wards_2012.geojson"

CENSUS_YEARS = list(range(2015, 2025))

_METRIC_LABELS = {
    "Cattle": "cattle",
    "Sheep": "sheep",
    "Pigs": "pigs",
    "Number of Farms": "num_farms",
    "Area farmed in hectares": "area_ha",
}


def _find_census_csv() -> Path:
    candidates = sorted(_DATA_ROOT.glob("FCWARD.*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No FCWARD.*.csv found in {_DATA_ROOT}")
    return candidates[-1]


def load_farm_census() -> gpd.GeoDataFrame:
    """
    Join NISRA farm census CSV with OSNI ward boundaries.

    Returns a GeoDataFrame with one row per (ward, year) containing
    cattle headcounts, area, and derived density metrics.
    """
    census_csv = _find_census_csv()

    wards = gpd.read_file(WARDS_GEOJSON)[["WardCode", "WARDNAME", "geometry"]].rename(
        columns={"WardCode": "ward_code", "WARDNAME": "ward_name"}
    )
    wards["_key"] = wards["ward_name"].str.upper()

    raw = pd.read_csv(census_csv, encoding="utf-8-sig")
    raw = raw[
        raw["Statistic Label"].isin(_METRIC_LABELS)
        & (raw["Ward"] != "Northern Ireland")
        & raw["VALUE"].notna()
    ].copy()
    raw["year"] = pd.to_numeric(raw["Year"], errors="coerce").astype("Int64")
    raw["value"] = pd.to_numeric(raw["VALUE"], errors="coerce")
    raw = raw[raw["year"].isin(CENSUS_YEARS)]
    raw["metric"] = raw["Statistic Label"].map(_METRIC_LABELS)
    raw["_key"] = (
        raw["Ward"]
        .str.upper()
        .str.replace(r"\s*\([^)]+\)\s*$", "", regex=True)
        .str.strip()
    )

    pivot = raw.pivot_table(
        index=["_key", "year"], columns="metric", values="value", aggfunc="first"
    ).reset_index()
    pivot.columns.name = None

    wards_expanded = wards.loc[wards.index.repeat(len(CENSUS_YEARS))].reset_index(drop=True)
    wards_expanded["year"] = CENSUS_YEARS * len(wards)
    merged = wards_expanded.merge(pivot, on=["_key", "year"], how="left").drop(columns="_key")

    for col in ("cattle", "sheep", "pigs", "num_farms", "area_ha"):
        if col in merged.columns:
            merged[col] = merged[col].replace({0: None})

    merged["cattle_per_ha"] = (merged["cattle"] / merged["area_ha"]).round(3)
    lu = (
        merged["cattle"].fillna(0)
        + merged["sheep"].fillna(0) * 0.15
        + merged["pigs"].fillna(0) * 0.25
    )
    merged["lu_per_ha"] = (lu.where(lu > 0) / merged["area_ha"]).round(3)

    for col in ("num_farms", "cattle", "sheep", "pigs"):
        merged[col] = pd.to_numeric(merged[col], errors="coerce").astype("Int64")

    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def insert_farm_census(engine) -> int:
    """Truncate and reload farm_census_wards table. Returns row count inserted."""
    print("    loading farm census data...", flush=True)
    gdf = load_farm_census()
    print(f"    loaded {len(gdf)} ward-year rows; normalising geometries...", flush=True)
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: g if g is None or isinstance(g, MultiPolygon) else MultiPolygon([g])
    )
    print("    truncating farm_census_wards...", flush=True)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE farm_census_wards RESTART IDENTITY;"))
    print(f"    writing {len(gdf)} rows to farm_census_wards...", flush=True)
    gdf.to_postgis("farm_census_wards", engine, if_exists="append", index=False, chunksize=500)
    print("    populating geom_simplified...", flush=True)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE farm_census_wards"
            " SET geom_simplified = ST_SimplifyPreserveTopology(geometry, 0.001)"
            " WHERE geometry IS NOT NULL;"
        ))
    print("    farm_census_wards write complete", flush=True)
    return len(gdf)


def backfill_farm_census_catchments(database_url: str | None = None) -> int:
    """Stamp each ward-year row with the catchment whose station geometry it overlaps most.

    The catchment polygons are derived from station locations, so this works even when
    there is no standalone catchment boundary table in the database.
    """
    url = database_url or os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE farm_census_wards ADD COLUMN IF NOT EXISTS catchment_name TEXT;"))
        print("    backfilling catchment names (spatial join on unique wards)...", flush=True)
        conn.execute(text(
            """
            WITH catchment_boundaries AS (
                SELECT
                    s.catchment_name,
                    ST_ConvexHull(
                        ST_Collect(COALESCE(s.geom_4326, ST_Transform(s.geom, 4326)))
                    ) AS geom
                FROM stations s
                WHERE s.catchment_name IS NOT NULL
                  AND (s.geom_4326 IS NOT NULL OR s.geom IS NOT NULL)
                GROUP BY s.catchment_name
            ),
            ward_centroids AS (
                SELECT DISTINCT ON (ward_code)
                    ward_code,
                    ST_PointOnSurface(ST_Transform(geometry, 29902)) AS centroid,
                    ST_Transform(geometry, 29902) AS geom_29902
                FROM farm_census_wards
                WHERE geometry IS NOT NULL
            ),
            ward_catchment AS (
                SELECT DISTINCT ON (wc.ward_code)
                    wc.ward_code,
                    cb.catchment_name
                FROM ward_centroids wc
                CROSS JOIN catchment_boundaries cb
                WHERE cb.geom IS NOT NULL
                ORDER BY wc.ward_code,
                    COALESCE(ST_Area(ST_Intersection(wc.geom_29902, ST_Transform(cb.geom, 29902))), 0) DESC,
                    ST_Distance(wc.centroid, ST_PointOnSurface(ST_Transform(cb.geom, 29902))) ASC
            )
            UPDATE farm_census_wards fw
            SET catchment_name = wc.catchment_name
            FROM ward_catchment wc
            WHERE fw.ward_code = wc.ward_code
              AND fw.geometry IS NOT NULL
              AND fw.catchment_name IS NULL;
            """
        ))
        print("    catchment backfill query complete; counting results...", flush=True)
        cur = conn.execute(text("SELECT COUNT(*) FROM farm_census_wards WHERE catchment_name IS NOT NULL;"))
        count = cur.scalar() or 0
    return int(count)
