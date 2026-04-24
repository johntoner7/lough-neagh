"""Farm census ward ingestion: joins NISRA CSV with OSNI ward boundaries."""

from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from sqlalchemy import create_engine, text

_DATA_ROOT = Path(__file__).parents[3] / "data" / "raw" / "farms"

WARDS_GEOJSON = _DATA_ROOT / "osni_open_data_largescale_boundaries_wards_2012.geojson"
CENSUS_CSV = _DATA_ROOT / "FCWARD.20260420T210410.csv"

CENSUS_YEARS = list(range(2015, 2025))

METRICS = {
    "Cattle": "cattle",
    "Sheep": "sheep",
    "Pigs": "pigs",
    "Number of Farms": "num_farms",
    "Area farmed in hectares": "area_ha",
}


def _strip_suffix(name: str) -> str:
    """Remove council disambiguation suffix e.g. '(NORTH DOWN AND ARDS)'."""
    return re.sub(r"\s*\([^)]+\)\s*$", "", name.upper()).strip()


def load_farm_census() -> gpd.GeoDataFrame:
    """
    Join NISRA farm census CSV with OSNI ward boundaries.

    Returns a GeoDataFrame with one row per (ward, year) containing
    cattle headcounts, area, and derived density metrics.
    """
    with open(WARDS_GEOJSON) as f:
        geo = json.load(f)

    # Build lookup: stripped name → list of (ward_code, geometry)
    # Multiple polygons may share a stripped name (different council areas)
    geo_lookup: dict[str, list[dict]] = defaultdict(list)
    for feat in geo["features"]:
        props = feat["properties"]
        key = props["WARDNAME"].upper()
        geo_lookup[key].append({
            "ward_code": props["WardCode"],
            "ward_name": props["WARDNAME"],
            "geometry": shape(feat["geometry"]),
        })

    # Parse CSV into nested dict: stripped_name → year → metric → value
    census: dict[str, dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    with open(CENSUS_CSV, encoding="utf-8-sig") as f:
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

    # Join: for each geo ward, sum census values from all CSV rows that match
    records = []
    for geo_key, geo_entries in geo_lookup.items():
        # Aggregate any CSV rows that strip to the same name (same-named wards)
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

            # One DB row per geo polygon (ward_code is unique per polygon)
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

    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'farm_census_wards')"
        )).scalar()

    if table_exists:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE farm_census_wards RESTART IDENTITY"))
        gdf.to_postgis("farm_census_wards", engine, if_exists="append", index=False)
    else:
        gdf.to_postgis("farm_census_wards", engine, if_exists="replace", index=False)

    return len(gdf)


def main() -> None:
    url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(url)
    n = insert_farm_census(engine)
    print(f"Inserted {n} rows into farm_census_wards")


if __name__ == "__main__":
    main()
