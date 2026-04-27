"""Farm census ward ingestion: joins NISRA CSV with OSNI ward boundaries."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from sqlalchemy import text

_DATA_ROOT = Path(__file__).parents[3] / "data" / "raw" / "farms"

WARDS_GEOJSON = _DATA_ROOT / "osni_open_data_largescale_boundaries_wards_2012.geojson"

CENSUS_YEARS = list(range(2015, 2025))

METRICS = {
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


def _strip_suffix(name: str) -> str:
    """Remove council disambiguation suffix e.g. '(NORTH DOWN AND ARDS)'."""
    return re.sub(r"\s*\([^)]+\)\s*$", "", name.upper()).strip()


def load_farm_census() -> gpd.GeoDataFrame:
    """
    Join NISRA farm census CSV with OSNI ward boundaries.

    Returns a GeoDataFrame with one row per (ward, year) containing
    cattle headcounts, area, and derived density metrics.
    """
    census_csv = _find_census_csv()

    with open(WARDS_GEOJSON) as f:
        geo = json.load(f)

    geo_lookup: dict[str, list[dict]] = defaultdict(list)
    for feat in geo["features"]:
        props = feat["properties"]
        key = props["WARDNAME"].upper()
        geo_lookup[key].append({
            "ward_code": props["WardCode"],
            "ward_name": props["WARDNAME"],
            "geometry": shape(feat["geometry"]),
        })

    census: dict[str, dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    with open(census_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            label = row["Statistic Label"]
            if label not in METRICS or row["Ward"] == "Northern Ireland" or not row["VALUE"]:
                continue
            try:
                year = int(row["Year"])
                value = float(row["VALUE"])
            except ValueError:
                continue
            if year not in CENSUS_YEARS:
                continue
            key = _strip_suffix(row["Ward"])
            census[key][year][METRICS[label]] = value

    records = []
    for geo_key, geo_entries in geo_lookup.items():
        ward_data = census.get(geo_key, {})

        for year in CENSUS_YEARS:
            year_data = ward_data.get(year, {})
            cattle = int(year_data.get("cattle", 0)) or None
            sheep = int(year_data.get("sheep", 0)) or None
            pigs = int(year_data.get("pigs", 0)) or None
            num_farms = int(year_data.get("num_farms", 0)) or None
            area_ha = year_data.get("area_ha") or None

            cattle_per_ha = round(cattle / area_ha, 3) if cattle and area_ha else None
            lu = ((cattle or 0) + (sheep or 0) * 0.15 + (pigs or 0) * 0.25)
            lu_per_ha = round(lu / area_ha, 3) if lu and area_ha else None

            for entry in geo_entries:
                records.append({
                    "ward_name": entry["ward_name"],
                    "ward_code": entry["ward_code"],
                    "year": year,
                    "num_farms": num_farms,
                    "area_ha": area_ha,
                    "cattle": cattle,
                    "sheep": sheep,
                    "pigs": pigs,
                    "cattle_per_ha": cattle_per_ha,
                    "lu_per_ha": lu_per_ha,
                    "geometry": entry["geometry"],
                })

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    for col in ("num_farms", "cattle", "sheep", "pigs"):
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce").astype("Int64")
    return gdf


def insert_farm_census(engine) -> int:
    """Truncate and reload farm_census_wards table. Returns row count inserted."""
    gdf = load_farm_census()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE farm_census_wards RESTART IDENTITY;"))
    gdf.to_postgis("farm_census_wards", engine, if_exists="append", index=False)

    return len(gdf)
