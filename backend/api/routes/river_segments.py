"""River segment endpoints."""

from __future__ import annotations

import json

import psycopg2.extras
from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import get_conn

router = APIRouter(prefix="/river-segments", tags=["river-segments"])

# Segments whose nearest station is further than this are returned with null
# metric (renders as grey) — they are too remote to have a meaningful reading.
_MAX_STATION_DIST_M = 5_000

_geojson_cache: dict[tuple, bytes] = {}


def _fetch_segments_json(year: int, metric: str) -> bytes:
    sql = """
        SELECT
            CASE
                WHEN rs.nearest_dist_m > %(max_dist)s THEN NULL
                WHEN %(metric)s = 'rolling'
                    THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                ELSE am.annual_mean_p_sol
            END AS metric_p_sol,
            ST_AsGeoJSON(ST_Transform(rs.geom, 4326)) AS geometry_json
        FROM river_segments rs
        LEFT JOIN annual_metrics am
               ON am.station_code = rs.nearest_station_code
              AND am.year = %(year)s
        ORDER BY rs.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"year": year, "metric": metric, "max_dist": _MAX_STATION_DIST_M})
            rows = cur.fetchall()

    features = []
    for row in rows:
        geometry = json.loads(row["geometry_json"]) if row["geometry_json"] else None
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "metric_p_sol": (
                    float(row["metric_p_sol"]) if row["metric_p_sol"] is not None else None
                ),
            },
        })

    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


@router.get("/geojson", response_class=Response)
def get_river_segments_geojson(
    year: int = Query(..., description="Year to colour segments by"),
    metric: str = Query("rolling", pattern="^(annual|rolling)$"),
) -> Response:
    """Return all river segments as GeoJSON, coloured by the nearest station's
    annual phosphorus metric for the given year."""
    cache_key = (year, metric)
    if cache_key not in _geojson_cache:
        _geojson_cache[cache_key] = _fetch_segments_json(year, metric)
    return Response(
        content=_geojson_cache[cache_key],
        media_type="application/json",
        # Historical year data never changes — cache aggressively in the browser.
        headers={"Cache-Control": "public, max-age=86400"},
    )
