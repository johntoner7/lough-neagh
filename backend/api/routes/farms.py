"""Farm census ward choropleth endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/farms", tags=["farms"])

_CENSUS_MIN_YEAR = 2015
_CENSUS_MAX_YEAR = 2024

# Farm census data is static for a given year; cache serialised JSON bytes to
# make repeated requests (e.g. play-button ticks) sub-millisecond.
_geojson_cache: dict[int, bytes] = {}

# Simplification tolerance in degrees (~110 m). Ward boundaries for a
# choropleth map need far less precision than cadastral data.
_SIMPLIFY_TOLERANCE = 0.001
_GEOJSON_DECIMAL_PLACES = 5

_SQL = """
    WITH ward_data AS (
        SELECT
            ward_name,
            ward_code,
            num_farms,
            area_ha,
            cattle,
            sheep,
            pigs,
            cattle_per_ha,
            lu_per_ha,
            COALESCE(geom_simplified, ST_SimplifyPreserveTopology(geometry, %(tol)s)) AS geom
        FROM farm_census_wards
        WHERE year = %(year)s
          AND (geom_simplified IS NOT NULL OR geometry IS NOT NULL)
    ),
    agg AS (
        SELECT COALESCE(
            json_agg(
                json_build_object(
                    'type',       'Feature',
                    'geometry',   ST_AsGeoJSON(geom, %(dp)s)::json,
                    'properties', json_build_object(
                        'ward_name',    ward_name,
                        'ward_code',    ward_code,
                        'num_farms',    num_farms,
                        'area_ha',      area_ha,
                        'cattle',       cattle,
                        'sheep',        sheep,
                        'pigs',         pigs,
                        'cattle_per_ha', cattle_per_ha,
                        'lu_per_ha',    lu_per_ha
                    )
                )
                ORDER BY ward_name
            ),
            '[]'::json
        ) AS features
        FROM ward_data
    )
    SELECT json_build_object(
        'type',     'FeatureCollection',
        'features', features,
        'metadata', json_build_object('year', %(year)s::int)
    )::text AS result
    FROM agg
"""


def _clamp_year(year: int) -> int:
    return max(_CENSUS_MIN_YEAR, min(_CENSUS_MAX_YEAR, year))


async def _fetch_farms_json(year: int) -> bytes:
    async with get_conn() as conn:
        cur = await conn.execute(
            _SQL,
            {"year": year, "tol": _SIMPLIFY_TOLERANCE, "dp": _GEOJSON_DECIMAL_PLACES},
        )
        row = await cur.fetchone()
    return (row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}').encode()


async def warm_cache() -> None:
    """Pre-fill _geojson_cache for all census years in the background."""
    for year in range(_CENSUS_MIN_YEAR, _CENSUS_MAX_YEAR + 1):
        if year in _geojson_cache:
            continue
        try:
            _geojson_cache[year] = await _fetch_farms_json(year)
            logger.info("Farm cache warmed for year %d", year)
        except Exception:
            logger.exception("Farm cache warmup failed for year %d", year)


@router.get("/geojson")
async def get_farms_geojson(
    response: Response,
    year: int = Query(2024, description="Year for farm census data (2015–2024)"),
) -> Response:
    """
    Farm census ward polygons as a GeoJSON FeatureCollection.

    Returns OSNI ward boundaries (WGS84) joined with NISRA farm census data
    for the requested year (clamped to 2015–2024).

    Properties per feature:
    - ward_name, ward_code
    - cattle_per_ha: primary agricultural P-pressure proxy
    - lu_per_ha: livestock units per hectare (cattle×1 + sheep×0.15 + pigs×0.25)
    - cattle, sheep, pigs, num_farms, area_ha
    """
    census_year = _clamp_year(year)
    response.headers["Cache-Control"] = "public, max-age=86400"

    if census_year not in _geojson_cache:
        _geojson_cache[census_year] = await _fetch_farms_json(census_year)

    return Response(content=_geojson_cache[census_year], media_type="application/json")


@router.get("/years")
def get_farm_years() -> list[int]:
    """Return the years available in the farm census."""
    return list(range(_CENSUS_MIN_YEAR, _CENSUS_MAX_YEAR + 1))
