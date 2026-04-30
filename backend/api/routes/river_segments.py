"""River segment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import get_conn

router = APIRouter(prefix="/river-segments", tags=["river-segments"])

# Segments whose nearest station is further than this are returned with null
# metric (renders as grey) — they are too remote to have a meaningful reading.
_MAX_STATION_DIST_M = 8_000

_geojson_cache: dict[tuple, bytes] = {}


async def _fetch_segments_json(year: int, metric: str) -> bytes:
    sql = """
        WITH seg_data AS (
            SELECT
                rs.id,
                CASE
                    WHEN rs.nearest_dist_m > %(max_dist)s THEN NULL
                    WHEN %(metric)s = 'rolling'
                        THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                    ELSE am.annual_mean_p_sol
                END AS metric_p_sol,
                COALESCE(rs.geom_4326, ST_Transform(rs.geom, 4326)) AS geom
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
                        'geometry',   CASE WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json ELSE NULL END,
                        'properties', json_build_object('metric_p_sol', metric_p_sol)
                    )
                    ORDER BY id
                ),
                '[]'::json
            )
        )::text AS result
        FROM seg_data
    """
    async with get_conn() as conn:
        cur = await conn.execute(sql, {"year": year, "metric": metric, "max_dist": _MAX_STATION_DIST_M})
        row = await cur.fetchone()
    return (row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}').encode()


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
        # Historical year data never changes — cache aggressively in the browser.
        headers={"Cache-Control": "public, max-age=86400"},
    )
