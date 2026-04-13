"""Full pipeline flow: ingest, join, and compute metrics."""

from __future__ import annotations

import os

from prefect import flow, task
from sqlalchemy import create_engine

from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.ingest.insert import insert_readings, insert_stations, insert_waterbodies
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


def _path_or_fallback(primary: str, fallback: str) -> str:
    return primary if os.path.exists(primary) else fallback


@task
def load_sources() -> tuple:
    foi_path = _path_or_fallback("data/raw/foi/annex_a.csv", "annex_a.csv")
    wfd_sites_path = _path_or_fallback(
        "data/raw/wfd_sites/WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson",
        "WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson",
    )
    waterbodies_path = "data/raw/wfd_waterbodies/WFD_River_Water_Bodies_2016.shp"

    stations_df, readings_df = load_and_clean_foi(foi_path)
    wfd_sites = load_wfd_sites(wfd_sites_path)
    waterbodies = load_wfd_waterbodies(waterbodies_path)
    enriched = enrich_stations(stations_df, wfd_sites)
    return waterbodies, enriched, readings_df


@task
def persist_data(waterbodies, enriched, readings_df) -> dict[str, int]:
    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    engine = create_engine(database_url)

    insert_waterbodies(waterbodies, engine)
    insert_stations(enriched, engine)
    insert_readings(readings_df, engine)

    return {
        "waterbodies": len(waterbodies),
        "stations": len(enriched),
        "readings": len(readings_df),
    }


@task
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


@flow(name="phosphorus-full-pipeline")
def run_full_pipeline() -> dict[str, int]:
    """Orchestrate full ingestion and metrics computation."""
    waterbodies, enriched, readings_df = load_sources()
    persist_summary = persist_data(waterbodies, enriched, readings_df)

    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    metrics_summary = compute_metrics(database_url)

    return {
        **persist_summary,
        **metrics_summary,
    }


if __name__ == "__main__":
	print(run_full_pipeline())