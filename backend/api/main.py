"""FastAPI application entry point."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.api.db import get_conn
from backend.api.routes import catchments, stations

app = FastAPI(
    title="NI River Phosphorus API",
    description=(
        "Spatial API serving 35 years of DAERA river phosphorus monitoring data "
        "(1990–2024) for Northern Ireland. Annual means, 5-year rolling means, "
        "Mann-Kendall trend direction, and WFD compliance status per station."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(stations.router)
app.include_router(catchments.router)


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
            "health": "/health",
            "docs": "/docs",
        },
    }
