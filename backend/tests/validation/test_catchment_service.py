from __future__ import annotations

from backend.api.models import StationProperties
from backend.api.services.catchments import summarize_catchment_stations


def test_summarize_catchment_stations_computes_means_and_threshold_share() -> None:
    stations = [
        StationProperties(
            station_code=1,
            location_name="A",
            catchment_name="Bann",
            river_waterbody_id=None,
            wfd_matched=True,
            annual_mean_p_sol=0.04,
            rolling_mean_5yr=None,
            wfd_compliant=False,
            sparse_year=False,
            trend_direction=None,
            trend_significant=None,
            sens_slope=None,
        ),
        StationProperties(
            station_code=2,
            location_name="B",
            catchment_name="Bann",
            river_waterbody_id=None,
            wfd_matched=True,
            annual_mean_p_sol=0.02,
            rolling_mean_5yr=None,
            wfd_compliant=True,
            sparse_year=False,
            trend_direction=None,
            trend_significant=None,
            sens_slope=None,
        ),
        StationProperties(
            station_code=3,
            location_name="C",
            catchment_name="Bann",
            river_waterbody_id=None,
            wfd_matched=True,
            annual_mean_p_sol=None,
            rolling_mean_5yr=None,
            wfd_compliant=None,
            sparse_year=None,
            trend_direction=None,
            trend_significant=None,
            sens_slope=None,
        ),
    ]

    mean_p_sol, pct_above_threshold = summarize_catchment_stations(stations)

    assert mean_p_sol == 0.03
    assert pct_above_threshold == 50.0


def test_summarize_catchment_stations_handles_no_data() -> None:
    stations = [
        StationProperties(
            station_code=1,
            location_name="A",
            catchment_name="Bann",
            river_waterbody_id=None,
            wfd_matched=True,
            annual_mean_p_sol=None,
            rolling_mean_5yr=None,
            wfd_compliant=None,
            sparse_year=False,
            trend_direction=None,
            trend_significant=None,
            sens_slope=None,
        )
    ]

    mean_p_sol, pct_above_threshold = summarize_catchment_stations(stations)

    assert mean_p_sol is None
    assert pct_above_threshold is None