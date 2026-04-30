"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

load_dotenv()

from api.db import close_pool, get_conn, init_pool
from api.logging_config import configure_logging
from api.routes import catchments, farms, lakes, river_segments, stations
from scripts.create_tables import main as create_tables
from scripts.init_db import main as init_db

configure_logging()
logger = logging.getLogger(__name__)


def _init_db() -> None:
    """Ensure PostGIS extensions and schema tables exist on startup."""
    database_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")

    init_db(database_url)
    create_tables(database_url)
    logger.info("Database schema ensured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting up")
    _init_db()
    await init_pool()
    asyncio.create_task(stations.warm_cache())
    asyncio.create_task(farms.warm_cache())
    asyncio.create_task(river_segments.warm_cache())
    yield
    await close_pool()
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

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
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


@app.exception_handler(PoolTimeout)
async def pool_timeout_handler(request: Request, exc: PoolTimeout):
    logger.warning("Connection pool timeout: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable, please retry"})


app.include_router(stations.router)
app.include_router(catchments.router)
app.include_router(lakes.router)
app.include_router(farms.router)
app.include_router(river_segments.router)


@app.get("/config")
def get_config() -> dict:
    """Return client-side configuration. Only exposes non-secret public keys."""
    return {"mapbox_token": os.environ.get("MAPBOX_TOKEN", "")}


@app.get("/health")
async def health() -> dict:
    """Health check — also verifies database connectivity."""
    try:
        async with get_conn() as conn:
            await conn.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        logger.exception("Database health check failed")
        db_status = "unavailable"
    return {"status": "ok", "database": db_status}


@app.get("/")
async def root() -> dict:
    """API description and available year range."""
    try:
        async with get_conn() as conn:
            cur = await conn.execute("SELECT MIN(year), MAX(year) FROM annual_metrics")
            row = await cur.fetchone()
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
            "river_segments_geojson": "/river-segments/geojson?year={year}",
            "health": "/health",
            "docs": "/docs",
        },
    }
