"""Full pipeline flow: ingest, join, and compute metrics."""

from __future__ import annotations

import os
from pathlib import Path

# Resolve data root: locally backend/ sits under repo root (parents[3]),
# in Docker backend/ contents are copied directly to /app (parents[2])
_LOCAL_ROOT = Path(__file__).parents[3]
_DOCKER_ROOT = Path(__file__).parents[2]
_REPO_ROOT = _LOCAL_ROOT if (_LOCAL_ROOT / "data").exists() else _DOCKER_ROOT
_DATA_RAW = _REPO_ROOT / "data" / "raw"
from sqlalchemy import create_engine

try:
    # Local dev: repo root in PYTHONPATH, backend is a package
    from backend.pipeline.ingest.farm_census import insert_farm_census
    from backend.pipeline.ingest.foi import load_and_clean_foi
    from backend.pipeline.ingest.insert import insert_readings, insert_stations, insert_waterbodies, insert_lakes
    from backend.pipeline.ingest.lakes import load_lakes
    from backend.pipeline.ingest.wfd_sites import load_wfd_sites
    from backend.pipeline.ingest.wfd_waterbodies import load_wfd_waterbodies
    from backend.pipeline.process.join import enrich_stations
    from backend.pipeline.process.metrics import (
        compute_annual_means,
        compute_rolling_means,
        compute_trend_results,
        insert_annual_metrics,
        insert_trend_results,
    )
except ModuleNotFoundError:
    # Docker: backend/ contents copied directly to /app, no backend package
    from pipeline.ingest.farm_census import insert_farm_census
    from pipeline.ingest.foi import load_and_clean_foi
    from pipeline.ingest.insert import insert_readings, insert_stations, insert_waterbodies, insert_lakes
    from pipeline.ingest.lakes import load_lakes
    from pipeline.ingest.wfd_sites import load_wfd_sites
    from pipeline.ingest.wfd_waterbodies import load_wfd_waterbodies
    from pipeline.process.join import enrich_stations
    from pipeline.process.metrics import (
        compute_annual_means,
        compute_rolling_means,
        compute_trend_results,
        insert_annual_metrics,
        insert_trend_results,
    )


def load_sources() -> tuple:
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


def persist_data(waterbodies, lakes, enriched, readings_df) -> dict[str, int]:
    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(database_url)

    insert_waterbodies(waterbodies, engine)
    insert_lakes(lakes, engine)
    insert_stations(enriched, engine)
    insert_readings(readings_df, engine)

    return {
        "waterbodies": len(waterbodies),
        "lakes": len(lakes),
        "stations": len(enriched),
        "readings": len(readings_df),
    }


def ingest_farms(engine_url: str) -> dict[str, int]:
    engine = create_engine(engine_url)
    n = insert_farm_census(engine)
    return {"farm_ward_years": n}


def compute_metrics(engine_url: str) -> dict[str, int]:
    engine = create_engine(engine_url)

    annual_df = compute_annual_means(engine)
    annual_df = compute_rolling_means(annual_df)
    insert_annual_metrics(annual_df, engine)

    trend_df = compute_trend_results(engine)
    insert_trend_results(trend_df, engine)

    return {
        "station_years": len(annual_df),
        "trends_computed": len(trend_df),
    }


def run_full_pipeline() -> dict[str, int]:
    """Ingest all sources and compute derived metrics."""
    waterbodies, lakes, enriched, readings_df = load_sources()
    persist_summary = persist_data(waterbodies, lakes, enriched, readings_df)

    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    metrics_summary = compute_metrics(database_url)
    farm_summary = ingest_farms(database_url)

    return {
        **persist_summary,
        **metrics_summary,
        **farm_summary,
    }


if __name__ == "__main__":
	print(run_full_pipeline())