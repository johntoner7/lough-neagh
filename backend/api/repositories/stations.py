"""SQL queries for station data.

All functions accept a psycopg connection and return plain Python types so
they are easy to test against a real database without FastAPI involvement.
"""

from __future__ import annotations

from psycopg.rows import dict_row

from api.constants import WFD_THRESHOLD_MG_L

_STATIONS_GEOJSON_SQL = """
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
                WHEN %(metric)s::text = 'rolling'
                    THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
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
                        WHEN %(metric)s::text = 'rolling'
                            THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                        ELSE am.annual_mean_p_sol
                    END
                ) IS NOT NULL
          )
          AND (
                %(bbox)s::text IS NULL
                OR ST_Intersects(
                    s.geom_4326,
                    ST_MakeEnvelope(
                        %(min_lon)s::float8, %(min_lat)s::float8,
                        %(max_lon)s::float8, %(max_lat)s::float8,
                        4326
                    )
                )
          )
    ),
    agg AS (
        SELECT
            COALESCE(
                json_agg(
                    json_build_object(
                        'type',       'Feature',
                        'geometry',   CASE
                            WHEN geom_4326 IS NOT NULL
                            THEN ST_AsGeoJSON(geom_4326)::json
                            ELSE NULL
                        END,
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
            )                                                                   AS features,
            COUNT(*)::int                                                        AS total_stations,
            COUNT(metric_p_sol)::int                                             AS stations_with_data,
            COUNT(*) FILTER (WHERE metric_p_sol > %(threshold)s::float)::int     AS stations_above_threshold
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

_STATION_HEADER_SQL = """
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

_STATION_SERIES_SQL = """
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

_AVAILABLE_YEARS_SQL = "SELECT DISTINCT year FROM annual_metrics ORDER BY year"


async def fetch_stations_geojson(
    conn,
    year: int,
    catchment: str | None,
    wfd_matched_only: bool,
    with_data_only: bool,
    metric: str,
    bbox: str | None,
    bbox_coords: tuple[float, float, float, float] | None,
) -> bytes:
    cur = await conn.execute(
        _STATIONS_GEOJSON_SQL,
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
    result = row[0] if row and row[0] else '{"type":"FeatureCollection","features":[]}'
    return result.encode()


async def fetch_station_timeseries(
    conn,
    station_code: int,
) -> tuple[dict | None, list[dict]]:
    """Return (station_header_row, series_rows) for the given station."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(_STATION_HEADER_SQL, {"station_code": station_code})
        station_row = await cur.fetchone()
        if station_row is None:
            return None, []
        await cur.execute(_STATION_SERIES_SQL, {"station_code": station_code})
        series_rows = await cur.fetchall()
    return station_row, series_rows


async def fetch_available_years(conn) -> list[int]:
    cur = await conn.execute(_AVAILABLE_YEARS_SQL)
    return [row[0] for row in await cur.fetchall()]
