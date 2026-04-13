"""Station endpoints."""

from __future__ import annotations

import json
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query

from api.db import get_conn
from api.models import (
    CollectionMetadata,
    StationCollection,
    StationFeature,
    StationProperties,
    StationTimeSeries,
    TimeSeriesPoint,
)

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("/years", response_model=list[int])
def get_years() -> list[int]:
    """Return the list of years available in the dataset."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT year FROM annual_metrics ORDER BY year")
            return [row[0] for row in cur.fetchall()]


@router.get("/geojson", response_model=StationCollection)
def get_stations_geojson(
    year: int = Query(..., description="Year to return annual metrics for"),
    catchment: Optional[str] = Query(None, description="Filter to one named catchment"),
    wfd_matched_only: bool = Query(False, description="Only return WFD-matched stations"),
    with_data_only: bool = Query(False, description="Only return stations with annual data for the selected year"),
    metric: str = Query("annual", pattern="^(annual|rolling)$", description="Metric used for map values: annual or rolling"),
) -> StationCollection:
    """Return all stations as a GeoJSON FeatureCollection for a given year."""
    sql = """
        SELECT
            s.station_code,
            s.location_name,
            s.catchment_name,
            s.river_waterbody_id,
            s.wfd_matched,
            am.annual_mean_p_sol,
            am.rolling_mean_5yr,
            CASE
                WHEN %(metric)s = 'rolling' THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                ELSE am.annual_mean_p_sol
            END AS metric_p_sol,
            am.wfd_compliant,
            am.sparse_year,
            tr.trend_direction,
            tr.significant        AS trend_significant,
            tr.sens_slope,
            ST_AsGeoJSON(ST_Transform(s.geom, 4326)) AS geometry_json
        FROM stations s
        LEFT JOIN annual_metrics am
               ON s.station_code = am.station_code AND am.year = %(year)s
        LEFT JOIN trend_results tr
               ON s.station_code = tr.station_code
        WHERE (%(catchment)s IS NULL OR s.catchment_name = %(catchment)s)
          AND (%(wfd_matched_only)s = FALSE OR s.wfd_matched = TRUE)
                    AND (
                                %(with_data_only)s = FALSE
                                OR (
                                        CASE
                                            WHEN %(metric)s = 'rolling' THEN COALESCE(am.rolling_mean_5yr, am.annual_mean_p_sol)
                                                ELSE am.annual_mean_p_sol
                                        END
                                ) IS NOT NULL
                    )
        ORDER BY s.station_code
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sql,
                {
                    "year": year,
                    "catchment": catchment,
                    "wfd_matched_only": wfd_matched_only,
                    "with_data_only": with_data_only,
                    "metric": metric,
                },
            )
            rows = cur.fetchall()

    features: list[StationFeature] = []
    stations_with_data = 0
    stations_above_threshold = 0

    for row in rows:
        geometry = json.loads(row["geometry_json"]) if row["geometry_json"] else None
        props = StationProperties(
            station_code=row["station_code"],
            location_name=row["location_name"],
            catchment_name=row["catchment_name"],
            river_waterbody_id=row["river_waterbody_id"],
            wfd_matched=row["wfd_matched"],
            annual_mean_p_sol=row["annual_mean_p_sol"],
            rolling_mean_5yr=row["rolling_mean_5yr"],
            metric_p_sol=row["metric_p_sol"],
            wfd_compliant=row["wfd_compliant"],
            sparse_year=row["sparse_year"],
            trend_direction=row["trend_direction"],
            trend_significant=row["trend_significant"],
            sens_slope=row["sens_slope"],
        )
        features.append(StationFeature(geometry=geometry, properties=props))

        metric_value = row["metric_p_sol"]
        if metric_value is not None:
            stations_with_data += 1
            if float(metric_value) > 0.035:
                stations_above_threshold += 1

    metadata = CollectionMetadata(
        year=year,
        total_stations=len(features),
        stations_with_data=stations_with_data,
        stations_above_threshold=stations_above_threshold,
    )
    return StationCollection(features=features, metadata=metadata)


@router.get("/{station_code}/timeseries", response_model=StationTimeSeries)
def get_station_timeseries(station_code: int) -> StationTimeSeries:
    """Return the full 1990–2024 time series for a single station."""
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
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(station_sql, {"station_code": station_code})
            station_row = cur.fetchone()
            if station_row is None:
                raise HTTPException(status_code=404, detail=f"Station {station_code} not found")

            cur.execute(series_sql, {"station_code": station_code})
            series_rows = cur.fetchall()

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
