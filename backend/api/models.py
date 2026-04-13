"""Pydantic schemas for the API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class StationProperties(BaseModel):
    station_code: int
    location_name: str
    catchment_name: Optional[str]
    river_waterbody_id: Optional[str]
    wfd_matched: bool
    annual_mean_p_sol: Optional[float]
    rolling_mean_5yr: Optional[float]
    metric_p_sol: Optional[float]
    wfd_compliant: Optional[bool]
    sparse_year: Optional[bool]
    trend_direction: Optional[str]
    trend_significant: Optional[bool]
    sens_slope: Optional[float]


class StationFeature(BaseModel):
    type: str = "Feature"
    geometry: Optional[dict]
    properties: StationProperties


class CollectionMetadata(BaseModel):
    year: int
    total_stations: int
    stations_with_data: int
    stations_above_threshold: int
    wfd_threshold_mg_l: float = 0.035
    data_note: Optional[str] = None


class StationCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[StationFeature]
    metadata: CollectionMetadata


class TimeSeriesPoint(BaseModel):
    year: int
    annual_mean_p_sol: Optional[float]
    rolling_mean_5yr: Optional[float]
    reading_count: int
    sparse_year: bool
    wfd_compliant: Optional[bool]


class StationTimeSeries(BaseModel):
    station_code: int
    location_name: str
    catchment_name: Optional[str]
    trend_direction: Optional[str]
    trend_significant: Optional[bool]
    sens_slope: Optional[float]
    series: list[TimeSeriesPoint]


class CatchmentSummary(BaseModel):
    catchment_name: str
    year: int
    station_count: int
    mean_p_sol: Optional[float]
    pct_above_threshold: Optional[float]
    stations: list[StationProperties]
