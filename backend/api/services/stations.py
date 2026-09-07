"""Pure helpers for station route orchestration."""

from __future__ import annotations


def parse_bbox_query(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parse a bbox query string into a 4-tuple of floats."""
    if bbox is None:
        return None

    parts = bbox.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must be four comma-separated floats: minLon,minLat,maxLon,maxLat")

    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("bbox values must be numeric") from exc


def build_geojson_cache_key(
    year: int,
    catchment: str | None,
    wfd_matched_only: bool,
    with_data_only: bool,
    metric: str,
    bbox: str | None,
) -> tuple:
    """Build the immutable cache key used for station GeoJSON responses."""
    return (year, catchment, wfd_matched_only, with_data_only, metric, bbox)