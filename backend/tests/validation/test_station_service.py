from __future__ import annotations

import pytest

from backend.api.services.stations import build_geojson_cache_key, parse_bbox_query


def test_parse_bbox_query_returns_float_tuple() -> None:
    assert parse_bbox_query("-6.1,54.5,-5.8,54.7") == (-6.1, 54.5, -5.8, 54.7)


def test_parse_bbox_query_allows_none() -> None:
    assert parse_bbox_query(None) is None


def test_parse_bbox_query_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="four comma-separated floats"):
        parse_bbox_query("-6.0,54.0")


def test_parse_bbox_query_rejects_non_numeric_values() -> None:
    with pytest.raises(ValueError, match="bbox values must be numeric"):
        parse_bbox_query("a,b,c,d")


def test_build_geojson_cache_key_keeps_parameter_order() -> None:
    assert build_geojson_cache_key(2024, "Bann", True, False, "rolling", "-6,54,-5,55") == (
        2024,
        "Bann",
        True,
        False,
        "rolling",
        "-6,54,-5,55",
    )