import { useCallback, useRef, useState, useEffect } from 'react'
import Map, {
  Source,
  Layer,
  NavigationControl,
  type MapMouseEvent,
  type MapRef,
} from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

import { API_BASE } from './api'

import type { GeoJSONCollection, ScreenPoint, StationFeature } from './types'
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
  'interpolate', ['linear'], ['coalesce', ['get', 'cattle_per_ha'], 0],
  0,   '#fde68a',
  0.75, '#f59e0b',
  1.25, '#ea580c',
  1.75, '#9a3412',
  2.5, '#3b0d01',
] as unknown as ExpressionSpecification

const FARM_MIN_YEAR = 2015
const FARM_MAX_YEAR = 2024

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

  useEffect(() => {
    fetch(`${API_BASE}/lakes/geojson`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) {setLakePolygons(data as GeoJSON.FeatureCollection)} })
      .catch(err => console.error('Failed to fetch lakes:', err))
  }, [])

  useEffect(() => {
    if (!showFarmLayer) {return}
    const farmYear = Math.max(FARM_MIN_YEAR, Math.min(FARM_MAX_YEAR, year))
    fetch(`${API_BASE}/farms/geojson?year=${farmYear}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) {setFarmPolygons(data as GeoJSON.FeatureCollection)} })
      .catch(err => console.error('Failed to fetch farms:', err))
  }, [year, showFarmLayer])

  const handleMapClick = useCallback((e: MapMouseEvent) => {
    const feature = e.features?.[0]
    if (!feature) {return}
    const props = feature.properties as StationFeature['properties']
    onStationClick(
      { ...feature, properties: props } as unknown as StationFeature,
      { x: e.point.x, y: e.point.y },
    )
  }, [onStationClick])

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
              'fill-opacity': 0.65,
            }}
          />
          <Layer
            id="farm-line"
            type="line"
            paint={{
              'line-color': '#92400e',
              'line-opacity': 0.3,
              'line-width': 0.8,
            }}
          />
        </Source>
      )}

      {/* ── Lake polygons: All WFD lakes with dynamic labels — static context, no interaction ── */}
      {lakePolygons && (
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
            'circle-radius': 5,
            'circle-color': stationColor,
            'circle-opacity': 0.85,
            'circle-stroke-width': 0.5,
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
            'circle-radius': 10,
            'circle-color': stationColor,
            'circle-opacity': 0.95,
            'circle-stroke-width': 2,
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
            'circle-radius': 13,
            'circle-color': stationColor,
            'circle-opacity': 1,
            'circle-stroke-width': 3,
            'circle-stroke-color': '#111827',
          }}
        />
      </Source>
    </Map>
    </div>
  )
}
