export interface StationProperties {
  station_code: number
  location_name: string
  catchment_name: string | null
  river_waterbody_id: string | null
  wfd_matched: boolean
  annual_mean_p_sol: number | null
  rolling_mean_5yr: number | null
  metric_p_sol: number | null
  wfd_compliant: boolean | null
  sparse_year: boolean | null
  trend_direction: string | null
  trend_significant: boolean | null
  sens_slope: number | null
}

export interface StationFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] } | null
  properties: StationProperties
}

export interface CollectionMetadata {
  year: number
  total_stations: number
  stations_with_data: number
  stations_above_threshold: number
  wfd_threshold_mg_l: number
  data_note: string | null
}

export interface StationCollection {
  type: 'FeatureCollection'
  features: StationFeature[]
  metadata: CollectionMetadata
}

export interface SummaryStats {
  stationsWithData: number
  stationsAboveThreshold: number
  pctAboveThreshold: number
  networkMean: string
}

export interface TimeSeriesPoint {
  year: number
  annual_mean_p_sol: number | null
  rolling_mean_5yr: number | null
  reading_count: number
  sparse_year: boolean
  wfd_compliant: boolean | null
}

export interface StationTimeSeries {
  station_code: number
  location_name: string
  catchment_name: string | null
  trend_direction: string | null
  trend_significant: boolean | null
  sens_slope: number | null
  series: TimeSeriesPoint[]
}

// GeoJSON FeatureCollection typed for Mapbox sources
export type GeoJSONCollection = {
  type: 'FeatureCollection'
  features: StationFeature[]
}

export interface ScreenPoint {
  x: number
  y: number
}
