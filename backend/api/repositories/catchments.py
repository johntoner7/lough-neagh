"""SQL queries for catchment data."""

from __future__ import annotations

from psycopg.rows import dict_row

_CATCHMENT_STATIONS_SQL = """
    SELECT
        s.station_code,
        s.location_name,
        s.catchment_name,
        s.river_waterbody_id,
        s.wfd_matched,
        am.annual_mean_p_sol,
        am.rolling_mean_5yr,
        am.wfd_compliant,
        am.sparse_year,
        tr.trend_direction,
        tr.significant AS trend_significant,
        tr.sens_slope
    FROM stations s
    LEFT JOIN annual_metrics am
           ON s.station_code = am.station_code AND am.year = %(year)s
    LEFT JOIN trend_results tr
           ON s.station_code = tr.station_code
    WHERE s.catchment_name = %(catchment_name)s
    ORDER BY s.station_code
"""

_CATCHMENT_NAMES_SQL = (
    "SELECT DISTINCT catchment_name FROM stations "
    "WHERE catchment_name IS NOT NULL ORDER BY catchment_name"
)


async def fetch_catchment_stations(conn, catchment_name: str, year: int) -> list[dict]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            _CATCHMENT_STATIONS_SQL,
            {"year": year, "catchment_name": catchment_name},
        )
        return await cur.fetchall()


async def fetch_catchment_names(conn) -> list[str]:
    cur = await conn.execute(_CATCHMENT_NAMES_SQL)
    return [row[0] for row in await cur.fetchall()]
