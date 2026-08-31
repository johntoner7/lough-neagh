import {
  CatchmentsSchema,
  ConfigSchema,
  StationCollectionSchema,
  StationTimeSeriesSchema,
  StormOverflowCollectionSchema,
  StormOverflowSummarySchema,
} from './schemas'

import type {
  StationCollection,
  StationTimeSeries,
  StormOverflowCollection,
  StormOverflowSummary,
} from './types'

const DEFAULT_API_BASE = 'http://localhost:8000'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE).replace(/\/+$/, '')

export async function fetchConfig(): Promise<{ mapbox_token: string }> {
  const res = await fetch(`${API_BASE}/config`)
  if (!res.ok) {throw new Error(`Config fetch failed: ${res.status}`)}
  return ConfigSchema.parse(await res.json())
}

export async function fetchCatchments(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/catchments`)
  if (!res.ok) {throw new Error(`Catchments fetch failed: ${res.status}`)}
  return CatchmentsSchema.parse(await res.json())
}

export async function fetchStations(
  year: number,
  catchment: string,
  withDataOnly: boolean,
  metric: 'annual' | 'rolling',
  signal?: AbortSignal,
): Promise<StationCollection> {
  const params = new URLSearchParams({ year: String(year) })
  if (catchment) {params.append('catchment', catchment)}
  if (withDataOnly) {params.append('with_data_only', 'true')}
  params.append('metric', metric)
  const res = await fetch(`${API_BASE}/stations/geojson?${params}`, { signal })
  if (!res.ok) {throw new Error(`Stations fetch failed: ${res.status}`)}
  return StationCollectionSchema.parse(await res.json())
}

export async function fetchTimeSeries(
  stationCode: number,
  signal?: AbortSignal,
): Promise<StationTimeSeries> {
  const res = await fetch(`${API_BASE}/stations/${stationCode}/timeseries`, { signal })
  if (!res.ok) {throw new Error(`Timeseries fetch failed: ${res.status}`)}
  return StationTimeSeriesSchema.parse(await res.json())
}

export async function fetchStormOverflows(
  catchment: string,
  signal?: AbortSignal,
): Promise<StormOverflowCollection> {
  const params = new URLSearchParams()
  if (catchment) {params.append('catchment', catchment)}
  const query = params.toString()
  const res = await fetch(`${API_BASE}/storm-overflows/geojson${query ? `?${query}` : ''}`, { signal })
  if (!res.ok) {throw new Error(`Storm overflows fetch failed: ${res.status}`)}
  return StormOverflowCollectionSchema.parse(await res.json())
}

export async function fetchStormOverflowSummary(
  catchment: string,
  signal?: AbortSignal,
): Promise<StormOverflowSummary> {
  const params = new URLSearchParams()
  if (catchment) {params.append('catchment', catchment)}
  const query = params.toString()
  const res = await fetch(`${API_BASE}/storm-overflows/summary${query ? `?${query}` : ''}`, { signal })
  if (!res.ok) {throw new Error(`Storm overflow summary fetch failed: ${res.status}`)}
  return StormOverflowSummarySchema.parse(await res.json())
}
