import { useCallback, useRef, useState, useEffect } from 'react'
import Map, {
  Source,
  Layer,
  NavigationControl,
  type MapMouseEvent,
  type MapRef,
} from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

import { API_BASE } from '../api'
import { FARM_YEAR_MIN, FARM_YEAR_MAX, LAKE_STATUS_YEAR } from '../constants'

import type { GeoJSONCollection, ScreenPoint, StationFeature } from '../types'
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

// ─── Constants ────────────────────────────────────────────────────────────────

export const KEY_STATION_CODES = new Set([10233, 10212, 10380, 10361, 10328, 10271])

// ─── Threshold colour scale by P(SOL) concentration ──────────────────────────
// null → grey; <0.035 → green; 0.035–0.1 → amber; >0.1 → red

const stationColor = [
  'case',
  ['==', ['get', 'metric_p_sol'], null],
  '#cccccc',
  [
    'step',
    ['get', 'metric_p_sol'],
    '#4ade80',
    0.035, '#fb923c',
    0.1, '#dc2626',
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
  stationsData: GeoJSONCollection
  keyStationsData: GeoJSONCollection
  selectedFeature: StationFeature | null
  showFarmLayer: boolean
  onStationClick: (feature: StationFeature, point: ScreenPoint) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

const cattleColor = [
  'step',
  ['coalesce', ['get', 'cattle_per_ha'], 0],
  '#4ade80',
  0.5, '#fb923c',
  1.5, '#dc2626',
  2.5, '#991b1b',
] as unknown as ExpressionSpecification

const stationRadius = [
  'interpolate', ['exponential', 1.6], ['zoom'],
  7, 4,
  8, 6.5,
  9, 10,
  10, 14,
  12, 21,
] as unknown as ExpressionSpecification

const keyStationRadius = [
  'interpolate', ['exponential', 1.6], ['zoom'],
  7, 8,
  8, 12,
  9, 17,
  10, 23,
  12, 32,
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
  stationsData,
  keyStationsData,
  selectedFeature,
  showFarmLayer,
  onStationClick,
}: Props) {
  const mapRef = useRef<MapRef>(null)
  const [lakePolygons, setLakePolygons] = useState<GeoJSON.FeatureCollection | null>(null)
  const [farmPolygons, setFarmPolygons] = useState<GeoJSON.FeatureCollection | null>(null)
  const [farmHover, setFarmHover] = useState<FarmHover | null>(null)
  const [farmLayerError, setFarmLayerError] = useState(false)
  const [legendOpen, setLegendOpen] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/lakes/geojson`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => setLakePolygons(data as GeoJSON.FeatureCollection))
      .catch(err => console.error('Failed to fetch lakes:', err))
  }, [])

  useEffect(() => {
    if (!showFarmLayer) { setFarmLayerError(false); return }
    const farmYear = Math.max(FARM_YEAR_MIN, Math.min(FARM_YEAR_MAX, year))
    fetch(`${API_BASE}/farms/geojson?year=${farmYear}`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => { setFarmPolygons(data as GeoJSON.FeatureCollection); setFarmLayerError(false) })
      .catch(err => { console.error('Failed to fetch farms:', err); setFarmLayerError(true) })
  }, [year, showFarmLayer])

  const handleMapClick = useCallback((e: MapMouseEvent) => {
    const feature = e.features?.[0]
    if (!feature) return
    // mapbox-gl coerces boolean/null properties when returning rendered features,
    // so we extract only the station_code and look up the clean object from stationsData
    const code = feature.properties?.station_code
    if (typeof code !== 'number') return
    const match = stationsData.features.find(f => f.properties.station_code === code)
      ?? keyStationsData.features.find(f => f.properties.station_code === code)
    if (!match) return
    onStationClick(match, { x: e.point.x, y: e.point.y })
  }, [onStationClick, stationsData, keyStationsData])

  const handleMouseMove = useCallback((e: MapMouseEvent) => {
    if (!showFarmLayer || !mapRef.current) {
      setFarmHover(null)
      return
    }
    const stationHit = mapRef.current.queryRenderedFeatures(e.point, {
      layers: ['stations-circle', 'key-stations-circle'],
    })
    if (stationHit.length > 0) {
      setFarmHover(null)
      return
    }
    const farmHit = mapRef.current.queryRenderedFeatures(e.point, { layers: ['farm-fill'] })
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
  }, [showFarmLayer])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
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
        bottom: 8,
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
        <div style={{ padding: '8px 9px', maxHeight: showFarmLayer ? '40vh' : '30vh', overflowY: 'auto' }}>
          <div style={{ fontWeight: 700, marginBottom: 5 }}>River phosphorus (dots)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#4ade80', flexShrink: 0 }} />
            <span>Low (&lt; 0.035 mg/l)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#fb923c', flexShrink: 0 }} />
            <span>Above limit (0.035–0.1)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#dc2626', flexShrink: 0 }} />
            <span>High (&gt; 0.1 mg/l)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: showFarmLayer ? 8 : 0 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#cccccc', flexShrink: 0 }} />
            <span>No reading</span>
          </div>
          {showFarmLayer && (
            <>
              <div style={{ height: 1, background: 'rgba(17,24,39,0.1)', marginBottom: 8 }} />
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Cattle density (areas)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: '#4ade80', flexShrink: 0 }} />
                <span>Low (&lt; 0.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: '#fb923c', flexShrink: 0 }} />
                <span>Medium (0.5–1.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: '#dc2626', flexShrink: 0 }} />
                <span>High (1.5–2.5 / ha)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: '#991b1b', flexShrink: 0 }} />
                <span>Very high (&gt; 2.5 / ha)</span>
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
      interactiveLayerIds={['stations-circle', 'key-stations-circle']}
      onClick={handleMapClick}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => { document.body.style.cursor = ''; setFarmHover(null) }}
      attributionControl={false}
    >
      <NavigationControl position="top-right" showCompass={false} />

      {/* ── Farm DEA choropleth: cattle density pressure layer ── */}
      {showFarmLayer && farmPolygons && (
        <Source id="farm-deas" type="geojson" data={farmPolygons}>
          <Layer
            id="farm-fill"
            type="fill"
            paint={{
              'fill-color': cattleColor,
              'fill-opacity': 0.38,
            }}
          />
          <Layer
            id="farm-line"
            type="line"
            paint={{
              'line-color': '#991b1b',
              'line-opacity': 0.22,
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
              'fill-opacity': 0.24,
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
            filter={['!=', ['get', 'label_text'], null]}
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

      {/* ── Layer 1: All stations — 5 px circles coloured by concentration ── */}
      <Source id="stations" type="geojson" data={stationsData as GeoJSON.FeatureCollection}>
        <Layer
          id="stations-circle"
          type="circle"
          paint={{
            'circle-radius': stationRadius,
            'circle-color': stationColor,
            'circle-opacity': 0.85,
            'circle-stroke-width': [
              'interpolate', ['linear'], ['zoom'],
              7, 0.5,
              13, 1.2,
            ],
            'circle-stroke-color': 'rgba(255,255,255,0.4)',
          }}
        />
      </Source>

      {/* ── Layer 2: 6 key Lough Neagh tributaries — larger, white-stroked ── */}
      <Source id="key-stations" type="geojson" data={keyStationsData as GeoJSON.FeatureCollection}>
        <Layer
          id="key-stations-circle"
          type="circle"
          paint={{
            'circle-radius': keyStationRadius,
            'circle-color': stationColor,
            'circle-opacity': 0.95,
            'circle-stroke-width': [
              'interpolate', ['linear'], ['zoom'],
              7, 1.8,
              13, 3,
            ],
            'circle-stroke-color': '#ffffff',
          }}
        />
        <Layer
          id="key-stations-labels"
          type="symbol"
          layout={{
            'text-field': ['coalesce', ['get', 'catchment_name'], ['get', 'location_name']],
            'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
            'text-size': 11,
            'text-offset': [0, 1.4],
            'text-anchor': 'top',
            'text-allow-overlap': true,
          }}
          paint={{
            'text-color': '#2d2d2d',
            'text-halo-color': 'rgba(255,255,255,0.9)',
            'text-halo-width': 1.5,
            'text-opacity': 0.9,
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
