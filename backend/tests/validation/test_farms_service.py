from __future__ import annotations

from backend.api.services.farms import build_farm_cache_key, clamp_farm_year


def test_clamp_farm_year_limits_lower_bound() -> None:
    assert clamp_farm_year(2010) == 2015


def test_clamp_farm_year_limits_upper_bound() -> None:
    assert clamp_farm_year(2030) == 2024


def test_clamp_farm_year_keeps_in_range_values() -> None:
    assert clamp_farm_year(2022) == 2022


def test_build_farm_cache_key_returns_stable_tuple() -> None:
    assert build_farm_cache_key(2024, "Bann") == (2024, "Bann")