"""Catchment endpoints."""

from __future__ import annotations

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.db import get_conn
from api.models import CatchmentSummary, StationProperties

router = APIRouter(prefix="/catchments", tags=["catchments"])


@router.get("", response_model=list[str])
def list_catchments(response: Response) -> list[str]:
    """Return distinct catchment names from the stations table."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT catchment_name FROM stations "
                "WHERE catchment_name IS NOT NULL ORDER BY catchment_name"
            )
            return [row[0] for row in cur.fetchall()]


@router.get("/{catchment_name}/summary", response_model=CatchmentSummary)
def get_catchment_summary(
    catchment_name: str,
    response: Response,
    year: int = Query(..., description="Year to compute summary for"),
) -> CatchmentSummary:
    """Return all stations in a catchment for a year, with aggregate P(SOL) stats."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    sql = """
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
            tr.significant        AS trend_significant,
            tr.sens_slope
        FROM stations s
        LEFT JOIN annual_metrics am
               ON s.station_code = am.station_code AND am.year = %(year)s
        LEFT JOIN trend_results tr
               ON s.station_code = tr.station_code
        WHERE s.catchment_name = %(catchment_name)s
        ORDER BY s.station_code
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"year": year, "catchment_name": catchment_name})
            rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Catchment '{catchment_name}' not found")

    stations: list[StationProperties] = [
        StationProperties(
            station_code=r["station_code"],
            location_name=r["location_name"],
            catchment_name=r["catchment_name"],
            river_waterbody_id=r["river_waterbody_id"],
            wfd_matched=r["wfd_matched"],
            annual_mean_p_sol=r["annual_mean_p_sol"],
            rolling_mean_5yr=r["rolling_mean_5yr"],
            wfd_compliant=r["wfd_compliant"],
            sparse_year=r["sparse_year"],
            trend_direction=r["trend_direction"],
            trend_significant=r["trend_significant"],
            sens_slope=r["sens_slope"],
        )
        for r in rows
    ]

    values_with_data = [s.annual_mean_p_sol for s in stations if s.annual_mean_p_sol is not None]
    mean_p_sol = sum(values_with_data) / len(values_with_data) if values_with_data else None

    above = sum(1 for s in stations if s.wfd_compliant is False)
    pct_above = (above / len(values_with_data) * 100) if values_with_data else None

    return CatchmentSummary(
        catchment_name=catchment_name,
        year=year,
        station_count=len(stations),
        mean_p_sol=mean_p_sol,
        pct_above_threshold=pct_above,
        stations=stations,
    )
