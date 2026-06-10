"""Full pipeline: ingest all sources and compute derived metrics."""

from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text

from backend.pipeline.ingest.farm_census import backfill_farm_census_catchments, insert_farm_census
from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.ingest.insert import insert_lakes, insert_readings, insert_river_segments, insert_stations, insert_waterbodies
from backend.pipeline.ingest.lakes import load_lakes
from backend.pipeline.ingest.wfd_sites import load_wfd_sites
from backend.pipeline.ingest.wfd_waterbodies import load_wfd_waterbodies
from backend.pipeline.process.join import enrich_stations, join_segments_to_stations
from backend.pipeline.process.metrics import (
    compute_annual_means,
    compute_rolling_means,
    compute_trend_results,
    insert_annual_metrics,
    insert_trend_results,
    load_annual_data_for_trends,
)

_DATA_RAW = Path(__file__).parents[3] / "data" / "raw"


def load_sources() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    foi_path = str(_DATA_RAW / "foi" / "annex_a.csv")
    wfd_sites_path = str(next((_DATA_RAW / "wfd_sites").glob("*.geojson")))
    waterbodies_path = str(_DATA_RAW / "wfd_waterbodies" / "WFD_River_Water_Bodies_2016.shp")
    lakes_path = str(_DATA_RAW / "lakes" / "Lake_Polygon_Classification_Ecological_Status_2024.geojson")

    stations_df, readings_df = load_and_clean_foi(foi_path)
    wfd_sites = load_wfd_sites(wfd_sites_path)
    waterbodies = load_wfd_waterbodies(waterbodies_path)
    lakes = load_lakes(lakes_path)
    enriched = enrich_stations(stations_df, wfd_sites)
    return waterbodies, lakes, enriched, readings_df


def persist_data(
    waterbodies: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    enriched: gpd.GeoDataFrame,
    readings_df: pd.DataFrame,
    database_url: str,
) -> dict[str, int]:
    engine = create_engine(database_url)

    print("    inserting waterbodies...", flush=True)
    insert_waterbodies(waterbodies, engine)
    print("    inserting lakes...", flush=True)
    insert_lakes(lakes, engine)
    print("    inserting stations...", flush=True)
    insert_stations(enriched, engine)
    print("    inserting readings...", flush=True)
    insert_readings(readings_df, engine)

    return {
        "waterbodies": len(waterbodies),
        "lakes": len(lakes),
        "stations": len(enriched),
        "readings": len(readings_df),
    }


def compute_metrics(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)

    annual_df = compute_annual_means(engine)
    annual_df = compute_rolling_means(annual_df)
    insert_annual_metrics(annual_df, engine)

    trend_input = load_annual_data_for_trends(engine)
    trend_df = compute_trend_results(trend_input)
    insert_trend_results(trend_df, engine)

    return {
        "station_years": len(annual_df),
        "trends_computed": len(trend_df),
    }


def ingest_river_segments(enriched: gpd.GeoDataFrame, database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    segments = join_segments_to_stations(enriched)
    insert_river_segments(segments, engine)
    return {"river_segments": len(segments)}


def ingest_farms(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    n = insert_farm_census(engine)
    catchments = backfill_farm_census_catchments(database_url)
    return {"farm_ward_years": n, "farm_ward_catchments": catchments}


def run_full_pipeline(database_url: str | None = None) -> dict[str, int]:
    """Ingest all sources and compute derived metrics."""
    if database_url is None:
        database_url = (
            os.environ.get("DATABASE_PUBLIC_URL")
            or os.environ.get("DATABASE_URL")
            or "postgresql://user:password@localhost:5433/phosphorus_db"
        )

    print("  Loading sources...", flush=True)
    waterbodies, lakes, enriched, readings_df = load_sources()
    print(
        f"  Sources loaded: {len(waterbodies)} waterbodies, "
        f"{len(enriched)} stations, {len(readings_df)} readings",
        flush=True,
    )

    print("  Clearing geojson cache...", flush=True)
    _cache_engine = create_engine(database_url)
    with _cache_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE geojson_cache;"))

    print("  Persisting data...", flush=True)
    persist_summary = persist_data(waterbodies, lakes, enriched, readings_df, database_url)
    print("  Data persisted", flush=True)

    print("  Computing metrics...", flush=True)
    metrics_summary = compute_metrics(database_url)
    print("  Metrics computed", flush=True)

    print("  Ingesting river segments...", flush=True)
    seg_summary = ingest_river_segments(enriched, database_url)
    print("  River segments ingested", flush=True)

    print("  Ingesting farm census...", flush=True)
    farm_summary = ingest_farms(database_url)
    print("  Farm census ingested", flush=True)

    return {**persist_summary, **metrics_summary, **seg_summary, **farm_summary}


if __name__ == "__main__":
    print(run_full_pipeline())
