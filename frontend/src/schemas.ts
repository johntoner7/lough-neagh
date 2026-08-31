import { z } from 'zod'

export const ConfigSchema = z.object({
  mapbox_token: z.string(),
})

const StationPropertiesSchema = z.object({
  station_code: z.number(),
  location_name: z.string(),
  catchment_name: z.string().nullable(),
  river_waterbody_id: z.string().nullable(),
  wfd_matched: z.boolean(),
  annual_mean_p_sol: z.number().nullable(),
  rolling_mean_5yr: z.number().nullable(),
  metric_p_sol: z.number().nullable(),
  wfd_compliant: z.boolean().nullable(),
  sparse_year: z.boolean().nullable(),
  trend_direction: z.string().nullable(),
  trend_significant: z.boolean().nullable(),
  sens_slope: z.number().nullable(),
})

export const StationFeatureSchema = z.object({
  type: z.literal('Feature'),
  geometry: z.object({
    type: z.literal('Point'),
    coordinates: z.tuple([z.number(), z.number()]),
  }).nullable(),
  properties: StationPropertiesSchema,
})

const CollectionMetadataSchema = z.object({
  year: z.number(),
  total_stations: z.number(),
  stations_with_data: z.number(),
  stations_above_threshold: z.number(),
  wfd_threshold_mg_l: z.number(),
  data_note: z.string().nullable(),
})

export const StationCollectionSchema = z.object({
  type: z.literal('FeatureCollection'),
  features: z.array(StationFeatureSchema),
  metadata: CollectionMetadataSchema,
})

const TimeSeriesPointSchema = z.object({
  year: z.number(),
  annual_mean_p_sol: z.number().nullable(),
  rolling_mean_5yr: z.number().nullable(),
  reading_count: z.number(),
  sparse_year: z.boolean(),
  wfd_compliant: z.boolean().nullable(),
})

export const StationTimeSeriesSchema = z.object({
  station_code: z.number(),
  location_name: z.string(),
  catchment_name: z.string().nullable(),
  trend_direction: z.string().nullable(),
  trend_significant: z.boolean().nullable(),
  sens_slope: z.number().nullable(),
  series: z.array(TimeSeriesPointSchema),
})

const StormOverflowPropertiesSchema = z.object({
  car_id: z.string(),
  name: z.string(),
  // Null when the asset has not been modelled — never coerce these to 0.
  spill_frequency: z.number().nullable(),
  spill_volume_m3: z.number().nullable(),
  classification: z.string().nullable(),
  modelled: z.boolean(),
  monitored: z.boolean(),
  receiving_waterbody_name: z.string().nullable(),
  local_management_area: z.string().nullable(),
  catchment_name: z.string().nullable(),
  coord_is_discharge_point: z.boolean(),
})

export const StormOverflowFeatureSchema = z.object({
  type: z.literal('Feature'),
  geometry: z.object({
    type: z.literal('Point'),
    coordinates: z.tuple([z.number(), z.number()]),
  }).nullable(),
  properties: StormOverflowPropertiesSchema,
})

export const StormOverflowCollectionSchema = z.object({
  type: z.literal('FeatureCollection'),
  features: z.array(StormOverflowFeatureSchema),
  metadata: z.object({
    snapshot: z.string(),
    asset_count: z.number(),
    modelled_count: z.number(),
  }),
})

export const StormOverflowSummarySchema = z.object({
  catchment_name: z.string().nullable(),
  snapshot: z.string(),
  asset_count: z.number(),
  modelled_count: z.number(),
  total_spills: z.number().nullable(),
  total_volume_m3: z.number().nullable(),
})

export const CatchmentsSchema = z.array(z.string())

// ── Inferred types — import these instead of hand-written interfaces ──────────

export type StationProperties = z.infer<typeof StationPropertiesSchema>
export type StationFeature = z.infer<typeof StationFeatureSchema>
export type CollectionMetadata = z.infer<typeof CollectionMetadataSchema>
export type StationCollection = z.infer<typeof StationCollectionSchema>
export type TimeSeriesPoint = z.infer<typeof TimeSeriesPointSchema>
export type StationTimeSeries = z.infer<typeof StationTimeSeriesSchema>
export type StormOverflowProperties = z.infer<typeof StormOverflowPropertiesSchema>
export type StormOverflowFeature = z.infer<typeof StormOverflowFeatureSchema>
export type StormOverflowCollection = z.infer<typeof StormOverflowCollectionSchema>
export type StormOverflowSummary = z.infer<typeof StormOverflowSummarySchema>
