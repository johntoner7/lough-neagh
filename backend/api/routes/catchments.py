"""Catchment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.db import get_conn
from api.models import CatchmentSummary, StationProperties
from api.repositories import catchments as catchment_repo
from api.services.catchments import summarize_catchment_stations

router = APIRouter(prefix="/catchments", tags=["catchments"])


@router.get("", response_model=list[str])
async def list_catchments(response: Response) -> list[str]:
    """Return distinct catchment names from the stations table."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    async with get_conn() as conn:
        return await catchment_repo.fetch_catchment_names(conn)


@router.get("/{catchment_name}/summary", response_model=CatchmentSummary)
async def get_catchment_summary(
    catchment_name: str,
    response: Response,
    year: int = Query(..., description="Year to compute summary for"),
) -> CatchmentSummary:
    """Return all stations in a catchment for a year, with aggregate P(SOL) stats."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    async with get_conn() as conn:
        rows = await catchment_repo.fetch_catchment_stations(conn, catchment_name, year)

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

    mean_p_sol, pct_above = summarize_catchment_stations(stations)

    return CatchmentSummary(
        catchment_name=catchment_name,
        year=year,
        station_count=len(stations),
        mean_p_sol=mean_p_sol,
        pct_above_threshold=pct_above,
        stations=stations,
    )
