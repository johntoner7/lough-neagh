"""Pure helpers for farms route orchestration."""

from __future__ import annotations


def clamp_farm_year(year: int, minimum_year: int = 2015, maximum_year: int = 2024) -> int:
    """Clamp a requested farm census year to the available data range."""
    return max(minimum_year, min(maximum_year, year))


def build_farm_cache_key(year: int, catchment: str | None) -> tuple[int, str | None]:
    """Build the immutable cache key for farm GeoJSON responses."""
    return (year, catchment)