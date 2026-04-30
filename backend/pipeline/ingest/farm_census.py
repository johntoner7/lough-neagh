"""Farm census ward ingestion: joins NISRA CSV with OSNI ward boundaries."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

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

    # Read ward geometries via geopandas — avoids manual json.load + shapely.shape per feature
    wards = gpd.read_file(WARDS_GEOJSON)[["WardCode", "WARDNAME", "geometry"]].rename(
        columns={"WardCode": "ward_code", "WARDNAME": "ward_name"}
    )
    wards["_key"] = wards["ward_name"].str.upper()

    # Vectorised CSV load — faster than csv.DictReader row-by-row
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

    # Pivot to wide format: one row per (ward_key, year), one column per metric
    pivot = raw.pivot_table(
        index=["_key", "year"], columns="metric", values="value", aggfunc="first"
    ).reset_index()
    pivot.columns.name = None

    # Expand wards × years then merge census data — replaces the nested dict loop
    wards_expanded = wards.loc[wards.index.repeat(len(CENSUS_YEARS))].reset_index(drop=True)
    wards_expanded["year"] = CENSUS_YEARS * len(wards)
    merged = wards_expanded.merge(pivot, on=["_key", "year"], how="left").drop(columns="_key")

    # Zero → None: matches original "0 means no data" convention
    for col in ("cattle", "sheep", "pigs", "num_farms", "area_ha"):
        if col in merged.columns:
            merged[col] = merged[col].replace({0: None})

    # Derived density metrics
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
    gdf = load_farm_census()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE farm_census_wards RESTART IDENTITY;"))
    gdf.to_postgis("farm_census_wards", engine, if_exists="append", index=False, chunksize=500)
    return len(gdf)
