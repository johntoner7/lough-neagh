"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
import time
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.db import close_pool, get_conn
from api.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

from api.routes import catchments, farms, lakes, stations


def _db_is_empty() -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM stations")
                return cur.fetchone()[0] == 0
    except Exception:
        return True  # table doesn't exist yet


def _seed_in_background() -> None:
    logger.info("Database empty — running pipeline to seed data")
    try:
        from pipeline.flows.full_pipeline import run_full_pipeline
        summary = run_full_pipeline()
        logger.info("Seed complete: %s", summary)
    except Exception:
        logger.exception("Seed pipeline failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting up")
    if _db_is_empty():
        threading.Thread(target=_seed_in_background, daemon=True).start()
    yield
    close_pool()
    logger.info("Connection pool closed")


app = FastAPI(
    title="NI River Phosphorus API",
    description=(
        "Spatial API serving 35 years of DAERA river phosphorus monitoring data "
        "(1990–2024) for Northern Ireland. Annual means, 5-year rolling means, "
        "Mann-Kendall trend direction, and WFD compliance status per station."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)



@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s",
        request.method,
        request.url.path,
        extra={
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "status": response.status_code,
            "duration_ms": round(duration_ms, 1),
        },
    )
    return response


app.include_router(stations.router)
app.include_router(catchments.router)
app.include_router(lakes.router)
app.include_router(farms.router)





@app.get("/config")
def get_config() -> dict:
    """Return client-side configuration. Only exposes non-secret public keys."""
    return {"mapbox_token": os.environ.get("MAPBOX_TOKEN", "")}


@app.get("/health")
def health() -> dict:
    """Health check — also verifies database connectivity."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        logger.exception("Database health check failed")
        db_status = "unavailable"
    return {"status": "ok", "database": db_status}


@app.get("/")
def root() -> dict:
    """API description and available year range."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MIN(year), MAX(year) FROM annual_metrics")
                row = cur.fetchone()
                min_year, max_year = (row[0], row[1]) if row and row[0] else (None, None)
    except Exception:
        logger.exception("Failed to fetch year range")
        min_year, max_year = None, None

    return {
        "name": "NI River Phosphorus API",
        "description": (
            "35 years of DAERA river phosphorus monitoring data for Northern Ireland. "
            "Stations coloured by WFD compliance status (threshold: 0.035 mg/l P(SOL))."
        ),
        "years": {"min": min_year, "max": max_year},
        "endpoints": {
            "stations_geojson": "/stations/geojson?year={year}",
            "station_timeseries": "/stations/{station_code}/timeseries",
            "years": "/stations/years",
            "catchments": "/catchments",
            "catchment_summary": "/catchments/{catchment_name}/summary?year={year}",
            "lakes_geojson": "/lakes/geojson",
            "health": "/health",
            "docs": "/docs",
        },
    }
