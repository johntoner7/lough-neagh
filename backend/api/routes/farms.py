"""Farm census ward choropleth endpoint."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import get_conn
from api.models import FarmCollection, FarmCollectionMetadata, FarmFeature, FarmProperties

router = APIRouter(prefix="/farms", tags=["farms"])

_CENSUS_MIN_YEAR = 2015
_CENSUS_MAX_YEAR = 2024


def _clamp_year(year: int) -> int:
    return max(_CENSUS_MIN_YEAR, min(_CENSUS_MAX_YEAR, year))


@router.get("/geojson", response_model=FarmCollection)
def get_farms_geojson(
    response: Response,
    year: int = Query(2024, description="Year for farm census data (2015–2024)"),
) -> FarmCollection:
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

    sql = """
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
            ST_AsGeoJSON(geometry) AS geometry_json
        FROM farm_census_wards
        WHERE year = %(year)s
        ORDER BY ward_name
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"year": census_year})
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

    features = []
    for row in rows:
        r = dict(zip(cols, row))
        geom_json = r.pop("geometry_json")
        if not geom_json:
            continue
        features.append(FarmFeature(
            geometry=json.loads(geom_json),
            properties=FarmProperties(**r),
        ))

    return FarmCollection(
        features=features,
        metadata=FarmCollectionMetadata(year=census_year),
    )


@router.get("/years")
def get_farm_years() -> list[int]:
    """Return the years available in the farm census."""
    return list(range(_CENSUS_MIN_YEAR, _CENSUS_MAX_YEAR + 1))
