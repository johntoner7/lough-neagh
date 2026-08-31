import { useCallback, useRef, useState, useEffect } from 'react'
import Map, {
  Source,
  Layer,
  NavigationControl,
  type MapMouseEvent,
  type MapRef,
} from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

import { API_BASE, fetchStormOverflows } from '../api'
import { FARM_YEAR_MIN, FARM_YEAR_MAX, LAKE_STATUS_YEAR, STORM_OVERFLOW_SNAPSHOT_YEAR, lowRiverPhosphorusColor, highRiverPhosphorusColor, midRiverPhosphorusColor, highCattleDensityColor, lowCattleDensityColor, midCattleDensityColor, veryHighCattleDensityColor, overflowUnsatisfactoryColor, overflowSatisfactoryColor, overflowUnmodelledColor } from '../constants'
import { UI_TEXT } from '../uiText'

import type { GeoJSONCollection, ScreenPoint, StationFeature, StormOverflowCollection } from '../types'
import type { ExpressionSpecification } from 'mapbox-gl'

interface FarmHover {
  dea_name: string
  cattle_per_ha: number | null
  cattle: number
  sheep: number
  num_farms: number
  x: number
  y: number
}

interface OverflowHover {
  name: string
  classification: string | null
  modelled: boolean
  spill_frequency: number | null
  spill_volume_m3: number | null
  receiving_waterbody_name: string | null
  coord_is_discharge_point: boolean
  x: number
  y: number
}

// ─── Constants ────────────────────────────────────────────────────────────────

export const KEY_STATION_CODES = new Set([10233, 10212, 10380, 10361, 10328, 10271])

// ─── Threshold colour scale by P(SOL) concentration ──────────────────────────
// null → grey; <0.035 → steel blue; 0.035–0.1 → amber; >0.1 → deep red

const stationColor = [
  'case',
  ['==', ['get', 'metric_p_sol'], null],
  '#e5e7eb',
  [
    'step',
    ['get', 'metric_p_sol'],
    lowRiverPhosphorusColor,
    0.035, midRiverPhosphorusColor,
    0.1, highRiverPhosphorusColor,
  ],
] as unknown as ExpressionSpecification

const riverLineColor = [
  'case',
  ['==', ['get', 'metric_p_sol'], null],
  '#e5e7eb', 
  [
    'step',
    ['get', 'metric_p_sol'],
    lowRiverPhosphorusColor, // < 0.035: Sky Blue (Clean/Good)
    0.035, midRiverPhosphorusColor, // Above limit: Solid Orange
    0.1, highRiverPhosphorusColor, // > 0.1: Deep Crimson Red (Serious/High)
  ],
] as unknown as ExpressionSpecification

const lakeStatusColor = [
  'match',
  ['get', 'ecological_status'],
  'Good', '#22c55e',
  'Moderate', '#eab308',
  'Poor', '#f97316',
  'Bad', '#b91c1c',
  '#64748b',
] as unknown as ExpressionSpecification

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  token: string
  year: number
  isPlaying: boolean
  catchment: string
  stationsData: GeoJSONCollection
  keyStationsData: GeoJSONCollection
  selectedFeature: StationFeature | null
  showFarmLayer: boolean
  showOverflowLayer: boolean
  onStationClick?: (feature: StationFeature, point: ScreenPoint) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

const cattleColor = [
  'step',
  ['coalesce', ['get', 'cattle_per_ha'], 0],
  lowCattleDensityColor, // 0 - 0.5: Near-white (Low)
  0.5, midCattleDensityColor, // 0.5 - 1.5: Minty Green (Medium - light and airy)
  1.5, highCattleDensityColor, // 1.5 - 2.5: Deep Green (High - big jump in darkness)
  2.5, veryHighCattleDensityColor, // > 2.5: Black-Green (Very High - extremely dense)
] as unknown as ExpressionSpecification

// Spill frequency is heavily skewed (median 3, 95th percentile 104, max 336),
// so radius scales with the square root — a linear scale would let a handful of
// assets swamp the map while everything else collapsed to a dot.
const overflowRadiusAtZoom = (min: number, max: number) => [
  'interpolate', ['linear'],
  ['sqrt', ['coalesce', ['get', 'spill_frequency'], 0]],
  0, min,
  18.5, max, // sqrt(336) ≈ 18.3, the largest modelled asset
]

const overflowRadius = [
  'interpolate', ['linear'], ['zoom'],
  7, overflowRadiusAtZoom(2, 9),
  11, overflowRadiusAtZoom(3, 26),
] as unknown as ExpressionSpecification

const overflowColor = [
  'match',
  ['get', 'classification'],
  'Unsatisfactory', overflowUnsatisfactoryColor,
  'Satisfactory', overflowSatisfactoryColor,
  overflowUnmodelledColor,
] as unknown as ExpressionSpecification

// mapbox-gl returns feature properties untyped, with absent values as undefined.
const asNumber = (v: unknown): number | null => (v === null || v === undefined ? null : Number(v))
const asString = (v: unknown): string | null => (v === null || v === undefined ? null : String(v))

const stationRadius = [
  'interpolate', ['exponential', 1.6], ['zoom'],
  7, 4,
  8, 6.5,
  9, 10,
  10, 14,
  12, 21,
] as unknown as ExpressionSpecification


const selectedStationRadius = [
  'interpolate', ['exponential', 1.45], ['zoom'],
  7, 9,
  8, 11,
  9, 14,
  10, 18,
  12, 24,
] as unknown as ExpressionSpecification


export default function MapContainer({
  token,
  year,
  isPlaying,
  catchment,
  stationsData,
  keyStationsData,
  selectedFeature,
  showFarmLayer,
  showOverflowLayer,
  onStationClick,
}: Props) {
  const mapRef = useRef<MapRef>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const farmCacheRef = useRef<globalThis.Map<string, GeoJSON.FeatureCollection>>(new globalThis.Map())
  const farmRequestRef = useRef<globalThis.Map<string, Promise<GeoJSON.FeatureCollection>>>(new globalThis.Map())
  const riverCacheRef = useRef<globalThis.Map<string, GeoJSON.FeatureCollection>>(new globalThis.Map())
  const overflowCacheRef = useRef<globalThis.Map<string, StormOverflowCollection>>(new globalThis.Map())

  useEffect(() => {
    const el = containerRef.current
    if (!el) {return}
    const observer = new ResizeObserver(() => {
      mapRef.current?.getMap().resize()
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const [lakePolygons, setLakePolygons] = useState<GeoJSON.FeatureCollection | null>(null)
  const [riverData, setRiverData] = useState<GeoJSON.FeatureCollection | null>(null)
  const [farmPolygons, setFarmPolygons] = useState<GeoJSON.FeatureCollection | null>(null)
  const [farmHover, setFarmHover] = useState<FarmHover | null>(null)
  const [farmLayerError, setFarmLayerError] = useState(false)
  const [farmLayerLoading, setFarmLayerLoading] = useState(false)
  const [overflowPoints, setOverflowPoints] = useState<StormOverflowCollection | null>(null)
  const [overflowHover, setOverflowHover] = useState<OverflowHover | null>(null)
  const [overflowLayerError, setOverflowLayerError] = useState(false)
  const [overflowLayerLoading, setOverflowLayerLoading] = useState(false)
  const [legendOpen, setLegendOpen] = useState(() => window.innerWidth > 760)

  useEffect(() => {
    fetch(`${API_BASE}/lakes/geojson`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => setLakePolygons(data as GeoJSON.FeatureCollection))
      .catch(err => console.error('Failed to fetch lakes:', err))
  }, [])

  useEffect(() => {
    const key = `${year}:${catchment || 'all'}`
    const cached = riverCacheRef.current.get(key)
    if (cached) { setRiverData(cached); return }
    let cancelled = false
    const params = new URLSearchParams({ year: String(year), metric: 'rolling' })
    if (catchment) {params.append('catchment', catchment)}
    fetch(`${API_BASE}/river-segments/geojson?${params}`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) {return}
        const fc = data as GeoJSON.FeatureCollection
        riverCacheRef.current.set(key, fc)
        setRiverData(fc)
      })
      .catch(err => console.error(`Failed to fetch river segments for year ${year}:`, err))
    return () => { cancelled = true }
  }, [year, catchment])

  // Storm overflows are a single published snapshot, so there is no year axis to
  // prefetch along — only the catchment filter changes the response.
  useEffect(() => {
    if (!showOverflowLayer || year !== STORM_OVERFLOW_SNAPSHOT_YEAR) {
      setOverflowLayerLoading(false)
      setOverflowLayerError(false)
      return
    }

    const key = catchment || 'all'
    const cached = overflowCacheRef.current.get(key)
    if (cached) {
      setOverflowPoints(cached)
      setOverflowLayerLoading(false)
      setOverflowLayerError(false)
      return
    }

    const controller = new AbortController()
    setOverflowLayerLoading(true)
    setOverflowLayerError(false)

    fetchStormOverflows(catchment, controller.signal)
      .then(data => {
        if (controller.signal.aborted) {return}
        overflowCacheRef.current.set(key, data)
        setOverflowPoints(data)
      })
      .catch(err => {
        if (controller.signal.aborted) {return}
        console.error('Failed to fetch storm overflows:', err)
        setOverflowPoints(null)
        setOverflowLayerError(true)
      })
      .finally(() => {
        if (controller.signal.aborted) {return}
        setOverflowLayerLoading(false)
      })

    return () => controller.abort()
  }, [catchment, showOverflowLayer, year])

  const farmCacheKey = (farmYear: number) => `${farmYear}:${catchment || 'all'}`

  const fetchFarmPolygons = useCallback((farmYear: number, signal?: AbortSignal) => {
    const key = farmCacheKey(farmYear)
    const cached = farmCacheRef.current.get(key)
    if (cached) {return Promise.resolve(cached)}

    const inflight = farmRequestRef.current.get(key)
    if (inflight) {return inflight}

    const params = new URLSearchParams({ year: String(farmYear) })
    if (catchment) {params.append('catchment', catchment)}
    const request = fetch(`${API_BASE}/farms/geojson?${params}`, signal ? { signal } : undefined)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        const polygons = data as GeoJSON.FeatureCollection
        farmCacheRef.current.set(key, polygons)
        return polygons
      })
      .finally(() => {
        farmRequestRef.current.delete(key)
      })

    farmRequestRef.current.set(key, request)
    return request
  }, [catchment])

  const prefetchFarmYear = useCallback((farmYear: number) => {
    if (farmYear < FARM_YEAR_MIN || farmYear > FARM_YEAR_MAX) {return}
    const key = farmCacheKey(farmYear)
    if (farmCacheRef.current.has(key) || farmRequestRef.current.has(key)) {return}

    void fetchFarmPolygons(farmYear).catch(err => {
      console.warn(`Farm prefetch failed for year ${farmYear}:`, err)
    })
  }, [fetchFarmPolygons, catchment])

  useEffect(() => {
    if (!showFarmLayer) {
      setFarmLayerLoading(false)
      setFarmLayerError(false)
      return
    }

    const farmYear = Math.max(FARM_YEAR_MIN, Math.min(FARM_YEAR_MAX, year))
    const cached = farmCacheRef.current.get(farmCacheKey(farmYear))
    if (cached) {
      setFarmPolygons(cached)
      setFarmLayerLoading(false)
      setFarmLayerError(false)
      if (isPlaying) {prefetchFarmYear(farmYear + 1)}
      return
    }

    const controller = new AbortController()
    setFarmLayerLoading(true)
    setFarmLayerError(false)

    fetchFarmPolygons(farmYear, controller.signal)
      .then(data => {
        if (controller.signal.aborted) {return}
        setFarmPolygons(data)
        setFarmLayerError(false)
        if (isPlaying) {prefetchFarmYear(farmYear + 1)}
      })
      .catch(err => {
        if (controller.signal.aborted) {return}
        console.error('Failed to fetch farms:', err)
        setFarmPolygons(null)
        setFarmLayerError(true)
      })
      .finally(() => {
        if (controller.signal.aborted) {return}
        setFarmLayerLoading(false)
      })
      return () => controller.abort()
  }, [year, catchment, showFarmLayer, isPlaying, fetchFarmPolygons, prefetchFarmYear])

  const handleMapClick = useCallback((e: MapMouseEvent) => {
    if (!onStationClick) {return}
    const feature = e.features?.[0]
    if (!feature) {return}
    // mapbox-gl coerces boolean/null properties when returning rendered features,
    // so we extract only the station_code and look up the clean object from stationsData
    const code = feature.properties?.station_code
    if (typeof code !== 'number') {return}
    const match = stationsData.features.find(f => f.properties.station_code === code)
      ?? keyStationsData.features.find(f => f.properties.station_code === code)
    if (!match) {return}
    onStationClick(match, { x: e.point.x, y: e.point.y })
  }, [onStationClick, stationsData, keyStationsData])

  const overflowVisible = showOverflowLayer && year === STORM_OVERFLOW_SNAPSHOT_YEAR && overflowPoints !== null

  const handleMouseMove = useCallback((e: MapMouseEvent) => {
    const map = mapRef.current
    if (!map) {return}

    const clear = () => { setFarmHover(null); setOverflowHover(null) }
    // Querying a layer id that is not in the style is an error, and layers mount
    // a tick after the state that gates them.
    const present = (...ids: string[]) => ids.filter(id => map.getLayer(id))

    if (!showFarmLayer && !overflowVisible) {
      clear()
      return
    }

    // Stations stay the map's primary subject — a station under the cursor
    // suppresses every other tooltip.
    if (map.queryRenderedFeatures(e.point, { layers: present('stations-circle') }).length > 0) {
      clear()
      return
    }

    // Points beat polygons: an overflow sitting on a ward wins the hover.
    if (overflowVisible) {
      const overflowHit = map.queryRenderedFeatures(e.point, {
        layers: present('overflow-modelled', 'overflow-unmodelled'),
      })
      if (overflowHit.length > 0) {
        const p = overflowHit[0].properties as Record<string, unknown>
        setFarmHover(null)
        setOverflowHover({
          name: String(p.name ?? ''),
          classification: asString(p.classification),
          // mapbox-gl coerces booleans when returning rendered features
          modelled: p.modelled === true || p.modelled === 'true',
          spill_frequency: asNumber(p.spill_frequency),
          spill_volume_m3: asNumber(p.spill_volume_m3),
          receiving_waterbody_name: asString(p.receiving_waterbody_name),
          coord_is_discharge_point: p.coord_is_discharge_point === true || p.coord_is_discharge_point === 'true',
          x: e.point.x,
          y: e.point.y,
        })
        return
      }
    }
    setOverflowHover(null)

    if (!showFarmLayer) {
      setFarmHover(null)
      return
    }
    const farmHit = map.queryRenderedFeatures(e.point, { layers: present('farm-fill') })
    if (farmHit.length > 0) {
      const p = farmHit[0].properties as Record<string, unknown>
      setFarmHover({
        dea_name: String(p.dea_name ?? ''),
        cattle_per_ha: p.cattle_per_ha != null ? Number(p.cattle_per_ha) : null,
        cattle: Number(p.cattle ?? 0),
        sheep: Number(p.sheep ?? 0),
        num_farms: Number(p.num_farms ?? 0),
        x: e.point.x,
        y: e.point.y,
      })
    } else {
      setFarmHover(null)
    }
  }, [showFarmLayer, overflowVisible])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%' }}>
    {showFarmLayer && farmLayerLoading && (
      <div style={{
        position: 'absolute',
        inset: 0,
        zIndex: 9,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.22), rgba(255,255,255,0.08))',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          borderRadius: 999,
          background: 'rgba(255,255,255,0.92)',
          border: '1px solid rgba(17,24,39,0.12)',
          boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
          color: '#374151',
          fontSize: 12,
          fontWeight: 600,
        }}>
          <div className="spinner" aria-hidden="true" />
          <span>{UI_TEXT.sidebar.farmLayer.loading}</span>
        </div>
      </div>
    )}
    {showFarmLayer && farmLayerError && (
      <div style={{
        position: 'absolute',
        bottom: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        background: 'rgba(254,243,199,0.97)',
        border: '1px solid #d97706',
        borderRadius: 6,
        padding: '6px 12px',
        fontSize: 12,
        color: '#92400e',
        pointerEvents: 'none',
        whiteSpace: 'nowrap',
      }}>
        Farm layer unavailable — data could not be loaded
      </div>
    )}
    {showOverflowLayer && year === STORM_OVERFLOW_SNAPSHOT_YEAR && overflowLayerLoading && (
      <div style={{
        position: 'absolute',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        borderRadius: 999,
        background: 'rgba(255,255,255,0.94)',
        border: '1px solid rgba(17,24,39,0.12)',
        boxShadow: '0 4px 14px rgba(15,23,42,0.1)',
        color: '#374151',
        fontSize: 12,
        fontWeight: 600,
        pointerEvents: 'none',
      }}>
        <div className="spinner" aria-hidden="true" />
        <span>{UI_TEXT.sidebar.overflowLayer.loading}</span>
      </div>
    )}
    {showOverflowLayer && year === STORM_OVERFLOW_SNAPSHOT_YEAR && overflowLayerError && (
      <div style={{
        position: 'absolute',
        bottom: 40,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        background: 'rgba(254,243,199,0.97)',
        border: '1px solid #d97706',
        borderRadius: 6,
        padding: '6px 12px',
        fontSize: 12,
        color: '#92400e',
        pointerEvents: 'none',
        whiteSpace: 'nowrap',
      }}>
        {UI_TEXT.sidebar.overflowLayer.unavailable}
      </div>
    )}
    {overflowHover && (
      <div style={{
        position: 'absolute',
        left: overflowHover.x + 12,
        top: overflowHover.y - 8,
        zIndex: 11,
        background: 'rgba(255,255,255,0.96)',
        border: '1px solid #d1d5db',
        borderRadius: 6,
        padding: '8px 10px',
        fontSize: 12,
        lineHeight: 1.6,
        pointerEvents: 'none',
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
        maxWidth: 220,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 2 }}>{overflowHover.name}</div>
        {overflowHover.modelled ? (
          <div>
            <span style={{ color: overflowUnsatisfactoryColor, fontWeight: 600 }}>
              {overflowHover.spill_frequency?.toLocaleString() ?? '—'}
            </span>
            {` ${UI_TEXT.sidebar.overflowLayer.spillsUnit}`}
            {overflowHover.spill_volume_m3 !== null && (
              <span style={{ color: '#6b7280' }}>
                {` · ${Math.round(overflowHover.spill_volume_m3).toLocaleString()} ${UI_TEXT.sidebar.overflowLayer.volumeUnit}`}
              </span>
            )}
          </div>
        ) : (
          <div style={{ color: '#6b7280', fontStyle: 'italic' }}>
            {UI_TEXT.sidebar.overflowLayer.notModelled}
          </div>
        )}
        {overflowHover.classification && (
          <div style={{ color: '#6b7280' }}>{overflowHover.classification}</div>
        )}
        {overflowHover.receiving_waterbody_name && (
          <div style={{ color: '#6b7280' }}>→ {overflowHover.receiving_waterbody_name}</div>
        )}
        {!overflowHover.coord_is_discharge_point && (
          <div style={{ color: '#9ca3af', marginTop: 2, fontSize: 11 }}>
            {UI_TEXT.sidebar.overflowLayer.approximateLocation}
          </div>
        )}
      </div>
    )}
    {farmHover && (
      <div style={{
        position: 'absolute',
        left: farmHover.x + 12,
        top: farmHover.y - 8,
        zIndex: 10,
        background: 'rgba(255,255,255,0.95)',
        border: '1px solid #d1d5db',
        borderRadius: 6,
        padding: '8px 10px',
        fontSize: 12,
        lineHeight: 1.6,
        pointerEvents: 'none',
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
        maxWidth: 180,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 2 }}>{farmHover.dea_name}</div>
        <div><span style={{ color: '#92400e', fontWeight: 600 }}>{farmHover.cattle_per_ha?.toFixed(2) ?? '—'}</span> cattle / ha</div>
        <div style={{ color: '#6b7280', marginTop: 2 }}>
          {farmHover.cattle.toLocaleString()} cattle · {farmHover.sheep.toLocaleString()} sheep
        </div>
        <div style={{ color: '#6b7280' }}>{farmHover.num_farms} farms</div>
      </div>
    )}
    <div
      style={{
        position: 'absolute',
        right: 8,
        bottom: 36,
        zIndex: 10,
        background: 'rgba(255,255,255,0.94)',
        border: '1px solid rgba(17,24,39,0.12)',
        borderRadius: 8,
        fontSize: 'clamp(9.5px,2.6vw,11px)',
        lineHeight: 1.25,
        color: '#1f2937',
        pointerEvents: 'none',
        width: 'min(210px, calc(100vw - 16px))',
      }}
      aria-label="Map legend"
    >
      <button
        onClick={() => setLegendOpen(v => !v)}
        aria-expanded={legendOpen}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '7px 9px',
          background: 'none',
          border: 'none',
          borderBottom: legendOpen ? '1px solid rgba(17,24,39,0.08)' : 'none',
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 'inherit',
          color: '#1f2937',
          pointerEvents: 'auto',
          borderRadius: legendOpen ? '8px 8px 0 0' : 8,
        }}
      >
        <span>Map key</span>
        <span style={{ fontSize: 10, color: '#888', marginLeft: 6 }}>{legendOpen ? '▾' : '▸'}</span>
      </button>
      {legendOpen && (
        <div style={{ padding: '8px 9px', maxHeight: showFarmLayer || overflowVisible ? '46vh' : '30vh', overflowY: 'auto' }}>
          <div style={{ fontWeight: 700, marginBottom: 5 }}>River phosphorus (lines)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 18, height: 3, borderRadius: 1, background: lowRiverPhosphorusColor, flexShrink: 0 }} />
            <span>Low (&lt; 0.035 mg/l)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 18, height: 3, borderRadius: 1, background: midRiverPhosphorusColor, flexShrink: 0 }} />
            <span>Above limit (0.035–0.1)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 18, height: 3, borderRadius: 1, background: highRiverPhosphorusColor, flexShrink: 0 }} />
            <span>High (&gt; 0.1 mg/l)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: showFarmLayer ? 8 : 0 }}>
            <span style={{ width: 18, height: 3, borderRadius: 1, background: '#e5e7eb', flexShrink: 0 }} />
            <span>No reading</span>
          </div>
          {showFarmLayer && (
            <>
              <div style={{ height: 1, background: 'rgba(17,24,39,0.1)', marginBottom: 8 }} />
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Cattle density (areas)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: lowCattleDensityColor, border: '1px solid #7bc67e', opacity: 0.5, flexShrink: 0 }} />
                <span>Low (&lt; 0.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: midCattleDensityColor, opacity: 0.5, flexShrink: 0 }} />
                <span>Medium (0.5–1.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: highCattleDensityColor, opacity: 0.5, flexShrink: 0 }} />
                <span>High (1.5–2.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: veryHighCattleDensityColor, opacity: 0.5, flexShrink: 0 }} />
                <span>Very high (&gt; 2.5 / ha)</span>
              </div>
            </>
          )}
          {overflowVisible && (
            <>
              <div style={{ height: 1, background: 'rgba(17,24,39,0.1)', margin: '8px 0' }} />
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{UI_TEXT.sidebar.overflowLayer.legendTitle}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: overflowUnsatisfactoryColor, flexShrink: 0 }} />
                <span>{UI_TEXT.sidebar.overflowLayer.legendUnsatisfactory}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: overflowSatisfactoryColor, flexShrink: 0 }} />
                <span>{UI_TEXT.sidebar.overflowLayer.legendSatisfactory}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'transparent', border: `1px solid ${overflowUnmodelledColor}`, boxSizing: 'border-box', flexShrink: 0 }} />
                <span>{UI_TEXT.sidebar.overflowLayer.legendUnmodelled}</span>
              </div>
              <div style={{ color: '#6b7280', marginBottom: 3 }}>{UI_TEXT.sidebar.overflowLayer.legendSizeNote}</div>
              <div style={{ color: '#6b7280', fontSize: '0.92em' }}>{UI_TEXT.sidebar.overflowLayer.legendFootnote}</div>
            </>
          )}
          {year === LAKE_STATUS_YEAR && (
            <>
              <div style={{ height: 1, background: 'rgba(17,24,39,0.1)', margin: '8px 0' }} />
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Lake ecological status</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(34,197,94,0.45)', border: '2px solid #22c55e', flexShrink: 0, boxSizing: 'border-box' }} />
                <span>Good</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(234,179,8,0.45)', border: '2px solid #eab308', flexShrink: 0, boxSizing: 'border-box' }} />
                <span>Moderate</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(249,115,22,0.45)', border: '2px solid #f97316', flexShrink: 0, boxSizing: 'border-box' }} />
                <span>Poor</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(185,28,28,0.45)', border: '2px solid #b91c1c', flexShrink: 0, boxSizing: 'border-box' }} />
                <span>Bad</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
    <Map
      ref={mapRef}
      mapboxAccessToken={token}
      mapStyle="mapbox://styles/mapbox/light-v11"
      initialViewState={{ longitude: -6.7, latitude: 54.63, zoom: 7.8 }}
      style={{ width: '100%', height: '100%' }}
      preserveDrawingBuffer
      interactiveLayerIds={(() => {
        const layers: string[] = []
        if (onStationClick) {layers.push('stations-circle')}
        layers.push('river-lines')
        return layers
      })()}
      onClick={handleMapClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => { document.body.style.cursor = ''; setFarmHover(null); setOverflowHover(null) }}
      attributionControl={false}
    >
      <NavigationControl position="top-right" showCompass={false} />

      {/* ── River segments: fetched per year with metric_p_sol in properties ── */}
      <Source
        id="river-segs"
        type="geojson"
        data={riverData ?? { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection}
      >
        <Layer
          id="river-lines"
          type="line"
          beforeId="water"
          paint={{
            'line-color': riverLineColor,
            'line-width': ['interpolate', ['linear'], ['zoom'], 7, 1.2, 12, 4],
            'line-opacity': ['case', ['==', ['get', 'metric_p_sol'], null], 0.25, 0.95] as unknown as number,
          }}
        />
      </Source>

      {/* ── Farm DEA choropleth: cattle density pressure layer ── */}
      {showFarmLayer && farmPolygons && (
        <Source id="farm-deas" type="geojson" data={farmPolygons}>
          <Layer
            id="farm-fill"
            type="fill"
            beforeId="river-lines"
            paint={{
              'fill-color': cattleColor,
              'fill-opacity': 0.5,
            }}
          />
          <Layer
            id="farm-line"
            type="line"
            beforeId="river-lines"
            paint={{
              'line-color': '#1f2937',
              'line-opacity': 0.3,
              'line-width': 0.8,
            }}
          />
        </Source>
      )}

      {/* ── Lake polygons: All WFD lakes with dynamic labels — static context, no interaction ── */}
      {lakePolygons && year === LAKE_STATUS_YEAR && (
        <Source id="lake-polygons" type="geojson" data={lakePolygons}>
          <Layer
            id="lake-fill"
            type="fill"
            paint={{
              'fill-color': lakeStatusColor,
              'fill-opacity': 0.45,
            }}
          />
          <Layer
            id="lake-line"
            type="line"
            paint={{
              'line-color': lakeStatusColor,
              'line-opacity': 0.65,
              'line-width': 1.2,
            }}
          />
          <Layer
            id="lake-label"
            type="symbol"
            filter={['all', ['!=', ['get', 'label_text'], null], ['!', ['in', 'Lough Neagh', ['get', 'label_text']]]]}
            layout={{
              'text-field': ['get', 'label_text'],
              'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
              'text-size': 10,
              'text-anchor': 'center',
              'text-allow-overlap': false,
              'text-ignore-placement': false,
            }}
            paint={{
              'text-color': '#9b1c1c',
              'text-halo-color': 'rgba(255,255,255,0.75)',
              'text-halo-width': 1,
              'text-opacity': 0.75,
            }}
          />
        </Source>
      )}

      {/* ── Storm overflows: NI Water modelled spills, 2025 snapshot ──
           Declared after the pressure layers and before the stations, so the
           points sit above rivers and farms but never obscure the stations. ── */}
      {overflowVisible && overflowPoints && (
        <Source id="storm-overflows" type="geojson" data={overflowPoints as unknown as GeoJSON.FeatureCollection}>
          {/* Assets NI Water has modelled — size by predicted spills per year */}
          <Layer
            id="overflow-modelled"
            type="circle"
            filter={['==', ['get', 'modelled'], true]}
            paint={{
              'circle-radius': overflowRadius,
              'circle-color': overflowColor,
              'circle-opacity': 0.75,
              'circle-stroke-width': 0.8,
              'circle-stroke-color': 'rgba(255,255,255,0.85)',
            }}
          />
          {/* Not yet modelled — hollow ring, no size encoding, and held back
              until zoom 9 so 1,200+ rings do not bury the station circles. */}
          <Layer
            id="overflow-unmodelled"
            type="circle"
            filter={['==', ['get', 'modelled'], false]}
            minzoom={9}
            paint={{
              'circle-radius': 3,
              'circle-color': 'rgba(0,0,0,0)',
              'circle-opacity': 0.6,
              'circle-stroke-width': 1,
              'circle-stroke-color': overflowUnmodelledColor,
            }}
          />
        </Source>
      )}

      {/* ── Layer 1: All stations — 5 px circles coloured by concentration ── */}
      <Source id="stations" type="geojson" data={stationsData as GeoJSON.FeatureCollection}>
        <Layer
          id="stations-circle"
          type="circle"
          paint={{
            'circle-radius': stationRadius,
            'circle-color': stationColor,
            // show points only at closer zooms to avoid clutter
            'circle-opacity': [
              'interpolate', ['linear'], ['zoom'],
              7, 0,
              10, 0.85,
            ],
            'circle-stroke-width': [
              'interpolate', ['linear'], ['zoom'],
              7, 0.5,
              13, 1.2,
            ],
            'circle-stroke-color': 'rgba(255,255,255,0.4)',
          }}
        />
      </Source>

      <Source
        id="selected-station"
        type="geojson"
        data={{
          type: 'FeatureCollection',
          features: selectedFeature ? [selectedFeature] : [],
        } as GeoJSON.FeatureCollection}
      >
        <Layer
          id="selected-station-highlight"
          type="circle"
          paint={{
            'circle-radius': selectedStationRadius,
            'circle-color': stationColor,
            'circle-opacity': 1,
            'circle-stroke-width': [
              'interpolate', ['linear'], ['zoom'],
              7, 1.8,
              13, 3,
            ],
            'circle-stroke-color': '#111827',
          }}
        />
      </Source>
    </Map>
    </div>
  )
}
