"""Storm overflow endpoints.

NI Water modelled spill estimates — a single published snapshot with no year
axis, so unlike farms this is cached per catchment only.

Roughly half the assets in the register have no modelled estimate. Those rows
are returned with `modelled: false` and null spill figures rather than being
filtered out or defaulted to zero: "not yet modelled" and "does not spill" are
different claims, and the map draws them differently.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import Response
from psycopg.rows import dict_row

from api.constants import STORM_OVERFLOW_SNAPSHOT
from api.db import get_conn
from api.models import StormOverflowCollection, StormOverflowSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storm-overflows", tags=["storm-overflows"])

# Serialised GeoJSON bytes keyed by catchment (None = all). The snapshot never
# changes between deploys, so a plain dict is enough.
_geojson_cache: dict[str | None, bytes] = {}

_GEOJSON_DECIMAL_PLACES = 5

_GEOJSON_SQL = """
    WITH overflow_data AS (
        SELECT
            car_id,
            name,
            spill_frequency,
            spill_volume_m3,
            classification,
            modelled,
            monitored,
            receiving_waterbody_name,
            local_management_area,
            catchment_name,
            coord_is_discharge_point,
            geom_4326
        FROM storm_overflows
        WHERE geom_4326 IS NOT NULL
          AND (%(catchment)s::text IS NULL OR catchment_name = %(catchment)s)
    ),
    agg AS (
        SELECT
            COALESCE(
                json_agg(
                    json_build_object(
                        'type',       'Feature',
                        'geometry',   ST_AsGeoJSON(geom_4326, %(dp)s)::json,
                        'properties', json_build_object(
                            'car_id',                   car_id,
                            'name',                     name,
                            'spill_frequency',          spill_frequency,
                            'spill_volume_m3',          spill_volume_m3,
                            'classification',           classification,
                            'modelled',                 modelled,
                            'monitored',                monitored,
                            'receiving_waterbody_name', receiving_waterbody_name,
                            'local_management_area',    local_management_area,
                            'catchment_name',           catchment_name,
                            'coord_is_discharge_point', coord_is_discharge_point
                        )
                    )
                    ORDER BY modelled, spill_frequency NULLS FIRST
                ),
                '[]'::json
            ) AS features,
            count(*)                       AS asset_count,
            count(*) FILTER (WHERE modelled) AS modelled_count
        FROM overflow_data
    )
    SELECT json_build_object(
        'type',     'FeatureCollection',
        'features', features,
        'metadata', json_build_object(
            'snapshot',       %(snapshot)s::text,
            'asset_count',    asset_count,
            'modelled_count', modelled_count
        )
    )::text AS result
    FROM agg
"""

_SUMMARY_SQL = """
    SELECT
        count(*)                          AS asset_count,
        count(*) FILTER (WHERE modelled)  AS modelled_count,
        sum(spill_frequency)              AS total_spills,
        sum(spill_volume_m3)              AS total_volume_m3
    FROM storm_overflows
    WHERE %(catchment)s::text IS NULL OR catchment_name = %(catchment)s
"""


async def _fetch_geojson(catchment: str | None) -> bytes:
    async with get_conn() as conn:
        cur = await conn.execute(
            _GEOJSON_SQL,
            {
                "catchment": catchment,
                "dp": _GEOJSON_DECIMAL_PLACES,
                "snapshot": STORM_OVERFLOW_SNAPSHOT,
            },
        )
        row = await cur.fetchone()

    if row and row[0]:
        return row[0].encode()

    empty = json.dumps({
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "snapshot": STORM_OVERFLOW_SNAPSHOT,
            "asset_count": 0,
            "modelled_count": 0,
        },
    })
    return empty.encode()


async def warm_cache() -> None:
    """Pre-fill the unfiltered response in the background at startup."""
    if None in _geojson_cache:
        return
    try:
        _geojson_cache[None] = await _fetch_geojson(None)
        logger.info("Storm overflow cache warmed")
    except Exception:
        logger.exception("Storm overflow cache warmup failed")


@router.get("/geojson", response_model=StormOverflowCollection)
async def get_storm_overflows_geojson(
    catchment: str | None = Query(None),
) -> Response:
    """
    Storm overflow assets as a GeoJSON FeatureCollection (WGS84).

    Properties per feature:
    - car_id, name: NI Water Corporate Asset Register identity
    - spill_frequency, spill_volume_m3: modelled annual estimates, null where
      the asset has not been modelled
    - modelled: false means no estimate exists — NOT that the asset never spills
    - classification: Unsatisfactory / Satisfactory / To be Determined / Not Modelled
    - monitored: whether the asset carries a spill monitor
    - catchment_name: resolved from the receiving waterbody, else the management area
    - coord_is_discharge_point: false where the point marks the asset, not the outfall
    """
    if catchment not in _geojson_cache:
        _geojson_cache[catchment] = await _fetch_geojson(catchment)

    return Response(
        content=_geojson_cache[catchment],
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/summary", response_model=StormOverflowSummary)
async def get_storm_overflow_summary(
    response: Response,
    catchment: str | None = Query(None),
) -> StormOverflowSummary:
    """Asset counts and modelled spill totals, optionally for one catchment."""
    response.headers["Cache-Control"] = "public, max-age=86400"

    async with get_conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(_SUMMARY_SQL, {"catchment": catchment})
            row = await cur.fetchone()

    return StormOverflowSummary(
        catchment_name=catchment,
        asset_count=row["asset_count"] if row else 0,
        modelled_count=row["modelled_count"] if row else 0,
        total_spills=row["total_spills"] if row else None,
        total_volume_m3=row["total_volume_m3"] if row else None,
    )
