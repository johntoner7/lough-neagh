"""Pydantic response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel

from api.constants import WFD_THRESHOLD_MG_L


class StationProperties(BaseModel):
    station_code: int
    location_name: str
    catchment_name: str | None
    river_waterbody_id: str | None
    wfd_matched: bool
    annual_mean_p_sol: float | None
    rolling_mean_5yr: float | None
    metric_p_sol: float | None = None
    wfd_compliant: bool | None
    sparse_year: bool | None
    trend_direction: str | None
    trend_significant: bool | None
    sens_slope: float | None


class StationFeature(BaseModel):
    type: str = "Feature"
    geometry: dict | None
    properties: StationProperties


class CollectionMetadata(BaseModel):
    year: int
    total_stations: int
    stations_with_data: int
    stations_above_threshold: int
    wfd_threshold_mg_l: float = WFD_THRESHOLD_MG_L
    data_note: str | None = None


class StationCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[StationFeature]
    metadata: CollectionMetadata


class TimeSeriesPoint(BaseModel):
    year: int
    annual_mean_p_sol: float | None
    rolling_mean_5yr: float | None
    reading_count: int
    sparse_year: bool
    wfd_compliant: bool | None


class StationTimeSeries(BaseModel):
    station_code: int
    location_name: str
    catchment_name: str | None
    trend_direction: str | None
    trend_significant: bool | None
    sens_slope: float | None
    series: list[TimeSeriesPoint]


class CatchmentSummary(BaseModel):
    catchment_name: str
    year: int
    station_count: int
    mean_p_sol: float | None
    pct_above_threshold: float | None
    stations: list[StationProperties]


class LakeProperties(BaseModel):
    lake_id: str
    lake_name: str
    ecological_status: str | None
    total_phosphorus: str | None
    label_text: str | None


class LakeFeature(BaseModel):
    type: str = "Feature"
    geometry: dict | None
    properties: LakeProperties


class LakeCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[LakeFeature]


class FarmProperties(BaseModel):
    ward_name: str
    ward_code: str
    num_farms: int | None
    area_ha: float | None
    cattle: int | None
    sheep: int | None
    pigs: int | None
    cattle_per_ha: float | None
    lu_per_ha: float | None


class FarmFeature(BaseModel):
    type: str = "Feature"
    geometry: dict | None
    properties: FarmProperties


class FarmCollectionMetadata(BaseModel):
    year: int


class FarmCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[FarmFeature]
    metadata: FarmCollectionMetadata
