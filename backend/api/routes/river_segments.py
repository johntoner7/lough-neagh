"""River segment endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/river-segments", tags=["river-segments"])

# Segments whose nearest station is further than this are returned with null
# metric (renders as grey) — they are too remote to have a meaningful reading.
_MAX_STATION_DIST_M = 10_000

# Simplification tolerance in degrees (~110 m) and decimal places for GeoJSON.
# At NI national scale (zoom 8–10), sub-100m precision is invisible.
_SIMPLIFY_TOLERANCE = 0.001
_GEOJSON_DECIMAL_PLACES = 5

_YEAR_MIN = 1990
_YEAR_MAX = 2024

_geojson_cache: dict[tuple, bytes] = {}
_geometry_cache: bytes | None = None
_metrics_cache: dict[tuple, bytes] = {}

_GEOMETRY_SQL = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(
            json_agg(
                json_build_object(
                    'type',       'Feature',
                    'id',         id,
                    'geometry',   CASE WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom, %(dp)s)::json ELSE NULL END,
                    'properties', '{}'::json
                )
                ORDER BY id
            ),
            '[]'::json
        )
    )::text AS result
    FROM (
        SELECT
            id,
            COALESCE(
                geom_simplified,
                ST_SimplifyPreserveTopology(COALESCE(geom_4326, ST_Transform(geom, 4326)), %(tol)s)
            ) AS geom
        FROM river_segments
    ) sub
"""

_METRICS_SQL = """
    SELECT COALESCE(
        json_object_agg(sub.id::text, sub.metric_p_sol),
        '{}'::json
    )::text AS result
    FROM (
        SELECT
            rs.id,
            CASE
                WHEN rs.nearest_dist_m > %(max_dist)s THEN NULL
                WHEN %(metric)s = 'rolling'
                    THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                ELSE am.annual_mean_p_sol
            END AS metric_p_sol
        FROM river_segments rs
        LEFT JOIN annual_metrics am
               ON am.station_code = rs.nearest_station_code
              AND am.year = %(year)s
    ) sub
"""

_SQL = """
    WITH seg_data AS (
        SELECT
            rs.id,
            CASE
                WHEN rs.nearest_dist_m > %(max_dist)s THEN NULL
                WHEN %(metric)s = 'rolling'
                    THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                ELSE am.annual_mean_p_sol
            END AS metric_p_sol,
            COALESCE(
                rs.geom_simplified,
                ST_SimplifyPreserveTopology(COALESCE(rs.geom_4326, ST_Transform(rs.geom, 4326)), %(tol)s)
            ) AS geom
        FROM river_segments rs
        LEFT JOIN annual_metrics am
               ON am.station_code = rs.nearest_station_code
              AND am.year = %(year)s
    )
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(
            json_agg(
                json_build_object(
                    'type',       'Feature',
                    'geometry',   CASE WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom, %(dp)s)::json ELSE NULL END,
                    'properties', json_build_object('metric_p_sol', metric_p_sol)
                )
                ORDER BY id
            ),
            '[]'::json
        )
    )::text AS result
    FROM seg_data
"""


async def _fetch_segments_json(year: int, metric: str) -> bytes:
    db_key = f"river_segments_{metric}_{year}"

    # L2: shared DB cache — survives across workers and restarts.
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT data FROM geojson_cache WHERE cache_key = %s", [db_key]
        )
        row = await cur.fetchone()
        if row:
            return bytes(row[0])

    # Cache miss — compute, then store for all workers.
    async with get_conn() as conn:
        cur = await conn.execute(
            _SQL,
            {
                "year": year,
                "metric": metric,
                "max_dist": _MAX_STATION_DIST_M,
                "tol": _SIMPLIFY_TOLERANCE,
                "dp": _GEOJSON_DECIMAL_PLACES,
            },
        )
        row = await cur.fetchone()
    result = (row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}').encode()

    try:
        async with get_conn() as conn:
            await conn.execute(
                "INSERT INTO geojson_cache (cache_key, data) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [db_key, result],
            )
    except Exception:
        logger.warning("Failed to write segment cache for key %s", db_key)

    return result


async def _fetch_geometry() -> bytes:
    global _geometry_cache
    if _geometry_cache is not None:
        return _geometry_cache

    db_key = "river_segments_geometry"
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT data FROM geojson_cache WHERE cache_key = %s", [db_key]
        )
        row = await cur.fetchone()
        if row:
            _geometry_cache = bytes(row[0])
            return _geometry_cache

    async with get_conn() as conn:
        cur = await conn.execute(
            _GEOMETRY_SQL,
            {"dp": _GEOJSON_DECIMAL_PLACES, "tol": _SIMPLIFY_TOLERANCE},
        )
        row = await cur.fetchone()
    result = (row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}').encode()

    try:
        async with get_conn() as conn:
            await conn.execute(
                "INSERT INTO geojson_cache (cache_key, data) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [db_key, result],
            )
    except Exception:
        logger.warning("Failed to write geometry cache")

    _geometry_cache = result
    return result


async def _fetch_metrics(year: int, metric: str) -> bytes:
    key = (year, metric)
    if key in _metrics_cache:
        return _metrics_cache[key]

    async with get_conn() as conn:
        cur = await conn.execute(
            _METRICS_SQL,
            {"year": year, "metric": metric, "max_dist": _MAX_STATION_DIST_M},
        )
        row = await cur.fetchone()
    result = (row[0] if row and row[0] else "{}").encode()
    _metrics_cache[key] = result
    return result


async def warm_cache() -> None:
    """Pre-fill geometry and per-year rolling metrics in the background."""
    try:
        await _fetch_geometry()
        logger.info("Segment geometry cache warmed")
    except Exception:
        logger.exception("Segment geometry cache warmup failed")

    for year in range(_YEAR_MIN, _YEAR_MAX + 1):
        key = (year, "rolling")
        if key in _metrics_cache:
            continue
        try:
            _metrics_cache[key] = await _fetch_metrics(year, "rolling")
            logger.info("Segment metrics cache warmed for year %d", year)
        except Exception:
            logger.exception("Segment metrics cache warmup failed for year %d", year)

    # Also keep the combined geojson cache warm for the benchmark/legacy endpoint
    for year in range(_YEAR_MIN, _YEAR_MAX + 1):
        key = (year, "rolling")
        if key in _geojson_cache:
            continue
        try:
            _geojson_cache[key] = await _fetch_segments_json(year, "rolling")
        except Exception:
            logger.exception("Segment geojson cache warmup failed for year %d", year)


@router.get("/geometry", response_class=Response)
async def get_river_segments_geometry() -> Response:
    """Return river segment geometry as GeoJSON (static, year-independent).
    Features carry numeric `id` for use with Mapbox feature-state."""
    content = await _fetch_geometry()
    return Response(
        content=content,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/metrics", response_class=Response)
async def get_river_segments_metrics(
    year: int = Query(..., description="Year"),
    metric: str = Query("rolling", pattern="^(annual|rolling)$"),
) -> Response:
    """Return {segmentId: metric_p_sol | null} for all segments for the given year."""
    content = await _fetch_metrics(year, metric)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/geojson", response_class=Response)
async def get_river_segments_geojson(
    year: int = Query(..., description="Year to colour segments by"),
    metric: str = Query("rolling", pattern="^(annual|rolling)$"),
) -> Response:
    """Return all river segments as GeoJSON, coloured by the nearest station's
    annual phosphorus metric for the given year."""
    cache_key = (year, metric)
    if cache_key not in _geojson_cache:
        _geojson_cache[cache_key] = await _fetch_segments_json(year, metric)
    return Response(
        content=_geojson_cache[cache_key],
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )
