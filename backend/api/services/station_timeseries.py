"""Pure helpers for station time-series response mapping."""

from __future__ import annotations

from collections.abc import Mapping

from api.models import StationTimeSeries, TimeSeriesPoint


def build_station_timeseries_response(
    station_row: Mapping[str, object],
    series_rows: list[Mapping[str, object]],
) -> StationTimeSeries:
    """Convert DB rows into the API response model."""
    series = [
        TimeSeriesPoint(
            year=row["year"],
            annual_mean_p_sol=row["annual_mean_p_sol"],
            rolling_mean_5yr=row["rolling_mean_5yr"],
            reading_count=row["reading_count"] or 0,
            sparse_year=bool(row["sparse_year"]),
            wfd_compliant=row["wfd_compliant"],
        )
        for row in series_rows
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