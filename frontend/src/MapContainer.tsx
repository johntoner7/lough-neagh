import { useCallback, useRef, useState } from 'react'
import Map, {
  Source,
  Layer,
  Marker,
  NavigationControl,
  type MapMouseEvent,
  type MapRef,
  type ViewStateChangeEvent,
} from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

import { UI_TEXT } from './uiText'

import type { GeoJSONCollection, ScreenPoint, StationFeature } from './types'
import type { ExpressionSpecification } from 'mapbox-gl'

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


// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  token: string
  stationsData: GeoJSONCollection
  keyStationsData: GeoJSONCollection
  selectedFeature: StationFeature | null
  onStationClick: (feature: StationFeature, point: ScreenPoint) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function MapContainer({
  token,
  stationsData,
  keyStationsData,
  selectedFeature,
  onStationClick,
}: Props) {
  const mapRef = useRef<MapRef>(null)
  const [zoom, setZoom] = useState(7.8)

  const handleZoom = useCallback((e: ViewStateChangeEvent) => {
    setZoom(e.viewState.zoom)
  }, [])

  const handleMapClick = useCallback((e: MapMouseEvent) => {
    const feature = e.features?.[0]
    if (!feature) {return}
    const props = feature.properties as StationFeature['properties']
    onStationClick(
      { ...feature, properties: props } as unknown as StationFeature,
      { x: e.point.x, y: e.point.y },
    )
  }, [onStationClick])

  return (
    <Map
      ref={mapRef}
      mapboxAccessToken={token}
      mapStyle="mapbox://styles/mapbox/light-v11"
      initialViewState={{ longitude: -6.7, latitude: 54.63, zoom: 7.8 }}
      style={{ width: '100%', height: '100%' }}
      interactiveLayerIds={['stations-circle', 'key-stations-circle']}
      onClick={handleMapClick}
      onZoom={handleZoom}
      onMouseEnter={() => { document.body.style.cursor = 'pointer' }}
      onMouseLeave={() => { document.body.style.cursor = '' }}
      attributionControl={false}
    >
      <NavigationControl position="top-right" showCompass={false} />

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

      {/* ── Lough Neagh callout annotation ── */}
      <Marker
        longitude={-6.4}
        latitude={54.6}
        anchor="center"
        pitchAlignment="viewport"
        rotationAlignment="viewport"
      >
        <div
          className="lough-neagh-callout"
          style={{ transform: `scale(${Math.pow(2, zoom - 7.8).toFixed(4)})`, transformOrigin: 'center' }}
        >
          {UI_TEXT.map.calloutLine1}<br />{UI_TEXT.map.calloutLine2}
        </div>
      </Marker>
    </Map>
  )
}
