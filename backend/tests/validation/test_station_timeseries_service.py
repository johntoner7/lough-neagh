from __future__ import annotations

from api.services.station_timeseries import build_station_timeseries_response


def test_build_station_timeseries_response_maps_rows_to_models() -> None:
    station_row = {
        "station_code": 10233,
        "location_name": "Six Mile Water",
        "catchment_name": "Bann",
        "trend_direction": "decreasing",
        "trend_significant": True,
        "sens_slope": -0.0012,
    }
    series_rows = [
        {
            "year": 2023,
            "annual_mean_p_sol": 0.041,
            "rolling_mean_5yr": 0.039,
            "reading_count": 12,
            "sparse_year": False,
            "wfd_compliant": False,
        },
        {
            "year": 2024,
            "annual_mean_p_sol": None,
            "rolling_mean_5yr": None,
            "reading_count": 0,
            "sparse_year": True,
            "wfd_compliant": None,
        },
    ]

    response = build_station_timeseries_response(station_row, series_rows)

    assert response.station_code == 10233
    assert response.location_name == "Six Mile Water"
    assert response.trend_direction == "decreasing"
    assert len(response.series) == 2
    assert response.series[0].year == 2023
    assert response.series[0].reading_count == 12
    assert response.series[1].reading_count == 0
