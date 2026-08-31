export type {
  StationProperties,
  StationFeature,
  CollectionMetadata,
  StationCollection,
  TimeSeriesPoint,
  StationTimeSeries,
  StormOverflowProperties,
  StormOverflowFeature,
  StormOverflowCollection,
  StormOverflowSummary,
} from './schemas'

// Types not derived from API responses — kept here
export interface SummaryStats {
  stationsWithData: number
  stationsAboveThreshold: number
  pctAboveThreshold: number
  networkMean: string
}

export type GeoJSONCollection = {
  type: 'FeatureCollection'
  features: import('./schemas').StationFeature[]
}

export interface ScreenPoint {
  x: number
  y: number
}
