"""Station endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from psycopg.rows import dict_row

from api.constants import WFD_THRESHOLD_MG_L
from api.db import get_conn
from api.models import StationTimeSeries, TimeSeriesPoint

router = APIRouter(prefix="/stations", tags=["stations"])

# Keyed by (year, catchment, wfd_matched_only, with_data_only, metric, bbox).
# Station data for a given year is immutable once published, so we hold the
# serialised JSON bytes for the lifetime of the process.
_geojson_cache: dict[tuple, bytes] = {}


@router.get("/years", response_model=list[int])
async def get_years(response: Response) -> list[int]:
    """Return the list of years available in the dataset."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    async with get_conn() as conn:
        cur = await conn.execute("SELECT DISTINCT year FROM annual_metrics ORDER BY year")
        return [row[0] for row in await cur.fetchall()]


def _parse_bbox(bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    """Parse a bbox query string 'minLon,minLat,maxLon,maxLat' into a float tuple."""
    if bbox is None:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=422, detail="bbox must be four comma-separated floats: minLon,minLat,maxLon,maxLat")
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox values must be numeric")


async def _fetch_stations_json(
    year: int,
    catchment: Optional[str],
    wfd_matched_only: bool,
    with_data_only: bool,
    metric: str,
    bbox: Optional[str],
    bbox_coords: Optional[tuple[float, float, float, float]],
) -> bytes:
    """Run the DB query and return serialised GeoJSON bytes, assembled entirely in SQL."""
    sql = """
        WITH station_data AS (
            SELECT
                s.station_code,
                s.location_name,
                s.catchment_name,
                s.river_waterbody_id,
                s.wfd_matched,
                am.annual_mean_p_sol,
                am.rolling_mean_5yr,
                CASE
                    WHEN %(metric)s::text = 'rolling' THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                    ELSE am.annual_mean_p_sol
                END AS metric_p_sol,
                am.wfd_compliant,
                am.sparse_year,
                tr.trend_direction,
                tr.significant        AS trend_significant,
                tr.sens_slope,
                s.geom_4326
            FROM stations s
            LEFT JOIN annual_metrics am
                   ON s.station_code = am.station_code AND am.year = %(year)s
            LEFT JOIN trend_results tr
                   ON s.station_code = tr.station_code
            WHERE (%(catchment)s::text IS NULL OR s.catchment_name = %(catchment)s)
              AND (%(wfd_matched_only)s = FALSE OR s.wfd_matched = TRUE)
              AND (
                    %(with_data_only)s = FALSE
                    OR (
                        CASE
                            WHEN %(metric)s::text = 'rolling' THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                            ELSE am.annual_mean_p_sol
                        END
                    ) IS NOT NULL
              )
              AND (
                    %(bbox)s::text IS NULL
                    OR ST_Intersects(
                        s.geom_4326,
                        ST_MakeEnvelope(%(min_lon)s::float8, %(min_lat)s::float8, %(max_lon)s::float8, %(max_lat)s::float8, 4326)
                    )
              )
        ),
        agg AS (
            SELECT
                COALESCE(
                    json_agg(
                        json_build_object(
                            'type',       'Feature',
                            'geometry',   CASE WHEN geom_4326 IS NOT NULL THEN ST_AsGeoJSON(geom_4326)::json ELSE NULL END,
                            'properties', json_build_object(
                                'station_code',       station_code,
                                'location_name',      location_name,
                                'catchment_name',     catchment_name,
                                'river_waterbody_id', river_waterbody_id,
                                'wfd_matched',        wfd_matched,
                                'annual_mean_p_sol',  annual_mean_p_sol,
                                'rolling_mean_5yr',   rolling_mean_5yr,
                                'metric_p_sol',       metric_p_sol,
                                'wfd_compliant',      wfd_compliant,
                                'sparse_year',        sparse_year,
                                'trend_direction',    trend_direction,
                                'trend_significant',  trend_significant,
                                'sens_slope',         sens_slope
                            )
                        )
                        ORDER BY station_code
                    ),
                    '[]'::json
                )                                                                  AS features,
                COUNT(*)::int                                                      AS total_stations,
                COUNT(metric_p_sol)::int                                           AS stations_with_data,
                COUNT(*) FILTER (WHERE metric_p_sol > %(threshold)s::float)::int   AS stations_above_threshold
            FROM station_data
        )
        SELECT json_build_object(
            'type',     'FeatureCollection',
            'features', features,
            'metadata', json_build_object(
                'year',                     %(year)s::int,
                'total_stations',           total_stations,
                'stations_with_data',       stations_with_data,
                'stations_above_threshold', stations_above_threshold,
                'wfd_threshold_mg_l',       %(threshold)s::float,
                'data_note',                NULL::text
            )
        )::text AS result
        FROM agg
    """
    async with get_conn() as conn:
        cur = await conn.execute(
            sql,
            {
                "year": year,
                "catchment": catchment,
                "wfd_matched_only": wfd_matched_only,
                "with_data_only": with_data_only,
                "metric": metric,
                "threshold": WFD_THRESHOLD_MG_L,
                "bbox": bbox,
                "min_lon": bbox_coords[0] if bbox_coords else None,
                "min_lat": bbox_coords[1] if bbox_coords else None,
                "max_lon": bbox_coords[2] if bbox_coords else None,
                "max_lat": bbox_coords[3] if bbox_coords else None,
            },
        )
        row = await cur.fetchone()
    return (row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}').encode()


@router.get("/geojson", response_class=Response)
async def get_stations_geojson(
    year: int = Query(..., description="Year to return annual metrics for"),
    catchment: Optional[str] = Query(None, description="Filter to one named catchment"),
    wfd_matched_only: bool = Query(False, description="Only return WFD-matched stations"),
    with_data_only: bool = Query(False, description="Only return stations with annual data for the selected year"),
    metric: str = Query("annual", pattern="^(annual|rolling)$", description="Metric used for map values: annual or rolling"),
    bbox: Optional[str] = Query(None, description="Bounding box filter: minLon,minLat,maxLon,maxLat (WGS84)"),
) -> Response:
    """Return all stations as a GeoJSON FeatureCollection for a given year."""
    bbox_coords = _parse_bbox(bbox)
    cache_key = (year, catchment, wfd_matched_only, with_data_only, metric, bbox)
    if cache_key not in _geojson_cache:
        _geojson_cache[cache_key] = await _fetch_stations_json(
            year, catchment, wfd_matched_only, with_data_only, metric, bbox, bbox_coords
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
    station_sql = """
        SELECT
            s.station_code,
            s.location_name,
            s.catchment_name,
            tr.trend_direction,
            tr.significant AS trend_significant,
            tr.sens_slope
        FROM stations s
        LEFT JOIN trend_results tr ON s.station_code = tr.station_code
        WHERE s.station_code = %(station_code)s
    """
    series_sql = """
        SELECT
            year,
            annual_mean_p_sol,
            rolling_mean_5yr,
            reading_count,
            sparse_year,
            wfd_compliant
        FROM annual_metrics
        WHERE station_code = %(station_code)s
        ORDER BY year
    """
    async with get_conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(station_sql, {"station_code": station_code})
            station_row = await cur.fetchone()
            if station_row is None:
                raise HTTPException(status_code=404, detail=f"Station {station_code} not found")

            await cur.execute(series_sql, {"station_code": station_code})
            series_rows = await cur.fetchall()

    series = [
        TimeSeriesPoint(
            year=r["year"],
            annual_mean_p_sol=r["annual_mean_p_sol"],
            rolling_mean_5yr=r["rolling_mean_5yr"],
            reading_count=r["reading_count"] or 0,
            sparse_year=bool(r["sparse_year"]),
            wfd_compliant=r["wfd_compliant"],
        )
        for r in series_rows
    ]

    return StationTimeSeries(
        station_code=station_row["station_code"],
        location_name=station_row["location_name"],
        catchment_name=station_row["catchment_name"],
        trend_direction=station_row["trend_direction"],
        trend_significant=station_row["trend_significant"],
        sens_slope=station_row["sens_slope"],
        series=series,
    )
