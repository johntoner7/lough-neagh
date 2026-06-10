"""Pure helpers for catchment summary calculations."""

from __future__ import annotations

from api.models import StationProperties


def summarize_catchment_stations(stations: list[StationProperties]) -> tuple[float | None, float | None]:
    """Compute mean P(SOL) and percent above the WFD threshold from station data."""
    values_with_data = [station.annual_mean_p_sol for station in stations if station.annual_mean_p_sol is not None]
    mean_p_sol = sum(values_with_data) / len(values_with_data) if values_with_data else None

    above_threshold = sum(1 for station in stations if station.wfd_compliant is False)
    pct_above_threshold = (above_threshold / len(values_with_data) * 100) if values_with_data else None

    return mean_p_sol, pct_above_threshold