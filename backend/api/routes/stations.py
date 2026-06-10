"""Station endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.db import get_conn
from api.models import StationTimeSeries
from api.repositories import stations as station_repo
from api.services.station_timeseries import build_station_timeseries_response
from api.services.stations import build_geojson_cache_key, parse_bbox_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stations", tags=["stations"])

# Keyed by (year, catchment, wfd_matched_only, with_data_only, metric, bbox).
# Station data for a given year is immutable once published, so we hold the
# serialised JSON bytes for the lifetime of the process.
_geojson_cache: dict[tuple, bytes] = {}

_YEAR_MIN = 1990
_YEAR_MAX = 2024


async def warm_cache() -> None:
    """Pre-fill cache for the default play parameters across all years."""
    for year in range(_YEAR_MIN, _YEAR_MAX + 1):
        key = (year, None, False, True, "rolling", None)
        if key in _geojson_cache:
            continue
        try:
            async with get_conn() as conn:
                _geojson_cache[key] = await station_repo.fetch_stations_geojson(
                    conn, year, None, False, True, "rolling", None, None
                )
            logger.info("Station cache warmed for year %d", year)
        except Exception:
            logger.exception("Station cache warmup failed for year %d", year)


@router.get("/years", response_model=list[int])
async def get_years(response: Response) -> list[int]:
    """Return the list of years available in the dataset."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    async with get_conn() as conn:
        return await station_repo.fetch_available_years(conn)


@router.get("/geojson", response_class=Response)
async def get_stations_geojson(
    year: int = Query(..., description="Year to return annual metrics for"),
    catchment: Optional[str] = Query(None, description="Filter to one named catchment"),
    wfd_matched_only: bool = Query(False, description="Only return WFD-matched stations"),
    with_data_only: bool = Query(False, description="Only return stations with annual data for the selected year"),
    metric: str = Query("annual", pattern="^(annual|rolling)$", description="Metric: annual or rolling"),
    bbox: Optional[str] = Query(None, description="Bounding box: minLon,minLat,maxLon,maxLat (WGS84)"),
) -> Response:
    """Return all stations as a GeoJSON FeatureCollection for a given year."""
    try:
        bbox_coords = parse_bbox_query(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cache_key = build_geojson_cache_key(year, catchment, wfd_matched_only, with_data_only, metric, bbox)
    if cache_key not in _geojson_cache:
        async with get_conn() as conn:
            _geojson_cache[cache_key] = await station_repo.fetch_stations_geojson(
                conn, year, catchment, wfd_matched_only, with_data_only, metric, bbox, bbox_coords
            )
    return Response(
        content=_geojson_cache[cache_key],
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{station_code}/timeseries", response_model=StationTimeSeries)
async def get_station_timeseries(station_code: int, response: Response) -> StationTimeSeries:
    """Return the full 1990–2024 time series for a single station."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    async with get_conn() as conn:
        station_row, series_rows = await station_repo.fetch_station_timeseries(conn, station_code)

    if station_row is None:
        raise HTTPException(status_code=404, detail=f"Station {station_code} not found")

    return build_station_timeseries_response(station_row, series_rows)
