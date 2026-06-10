"""Validation tests for station–WFD join (TEST 2).

Requires: data/raw/foi/annex_a.csv + WFD sites GeoJSON.
Skipped automatically when either file is absent.
"""

from __future__ import annotations

import pytest

from .conftest import KEY_STATIONS

EXPECTED_TOTAL = 1201
EXPECTED_MATCHED = 525
EXPECTED_UNMATCHED = 676


def test_total_station_count(enriched_stations):
    assert len(enriched_stations) == EXPECTED_TOTAL


def test_wfd_matched_count(enriched_stations):
    counts = enriched_stations["wfd_matched"].value_counts(dropna=False)
    assert int(counts.get(True, 0)) == EXPECTED_MATCHED


def test_wfd_unmatched_count(enriched_stations):
    counts = enriched_stations["wfd_matched"].value_counts(dropna=False)
    assert int(counts.get(False, 0)) == EXPECTED_UNMATCHED


@pytest.mark.parametrize("station_code,name", list(KEY_STATIONS.items()))
def test_key_station_present_and_matched(enriched_stations, station_code, name):
    row = enriched_stations[enriched_stations["station_code"] == station_code]
    assert not row.empty, f"Key station {name} ({station_code}) missing"
    assert bool(row.iloc[0]["wfd_matched"]), f"Key station {name} ({station_code}) not WFD-matched"


def test_no_null_geometries(enriched_stations):
    null_count = int(enriched_stations.geometry.isna().sum())
    assert null_count == 0


def test_bounding_box_within_ni(enriched_stations):
    minx, miny, maxx, maxy = enriched_stations.total_bounds
    assert 150_000 <= minx <= 370_000
    assert 150_000 <= maxx <= 370_000
    assert 300_000 <= miny <= 470_000
    assert 300_000 <= maxy <= 470_000
