import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { fetchCatchments, fetchConfig, fetchStations, fetchTimeSeries } from './api'
import ControlsPanel from './ControlsPanel'
import MapContainer, { KEY_STATION_CODES } from './MapContainer'
import SparklinePanel from './SparklinePanel'
import StationDetailDrawer from './StationDetailDrawer'
import TimelineBar from './TimelineBar'
import { UI_TEXT } from './uiText'

import type {
  GeoJSONCollection,
  StationFeature,
  StationTimeSeries,
} from './types'

const KEY_STATION_CODES_ORDERED = [10212, 10233, 10271, 10328, 10361, 10380]

const EMPTY_COLLECTION: GeoJSONCollection = { type: 'FeatureCollection', features: [] }

export default function App() {
  const [token, setToken] = useState('')
  const [catchments, setCatchments] = useState<string[]>([])
  const [year, setYear] = useState(1990)
  const [catchment, setCatchment] = useState('')
  const [showAllStations, setShowAllStations] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [stationsData, setStationsData] = useState<GeoJSONCollection>(EMPTY_COLLECTION)
  const [keyStationsData, setKeyStationsData] = useState<GeoJSONCollection>(EMPTY_COLLECTION)
  const [selectedFeature, setSelectedFeature] = useState<StationFeature | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [timeSeriesByCode, setTimeSeriesByCode] = useState<Record<number, StationTimeSeries>>({})
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  // ── Initialise: token, catchments, and all 6 key sparklines ──────────────
  useEffect(() => {
    fetchConfig()
      .then(cfg => setToken(cfg.mapbox_token))
      .catch(e => setError((e as Error).message))
    fetchCatchments()
      .then(setCatchments)
      .catch(e => console.warn('Could not load catchments:', e))
    Promise.allSettled(KEY_STATION_CODES_ORDERED.map(code => fetchTimeSeries(code)))
      .then(results => {
        const nextSeries: Record<number, StationTimeSeries> = {}
        results.forEach((result, i) => {
          if (result.status === 'fulfilled') {
            nextSeries[KEY_STATION_CODES_ORDERED[i]] = result.value
          }
        })
        setTimeSeriesByCode(prev => ({ ...nextSeries, ...prev }))
      })
  }, [])

  // ── Load all stations whenever year / catchment changes ───────────────────
  useEffect(() => {
    if (!token) {return}
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    fetchStations(year, catchment, /* withDataOnly */ true, 'rolling', ctrl.signal)
      .then(data => {
        const keyFeatures = data.features.filter(f =>
          KEY_STATION_CODES.has(f.properties.station_code),
        )
        const visibleFeatures = showAllStations ? data.features : keyFeatures
        setStationsData({ type: 'FeatureCollection', features: visibleFeatures })
        setKeyStationsData({ type: 'FeatureCollection', features: keyFeatures })
      })
      .catch(e => {
        if ((e as Error).name !== 'AbortError') {console.warn('Station fetch error:', e)}
      })
  }, [token, year, catchment, showAllStations])

  // ── Play animation ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isPlaying) {return}
    const timer = setInterval(() => {
      setYear(y => {
        if (y >= 2024) { setIsPlaying(false); return y }
        return y + 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [isPlaying])

  const handleYearChange = useCallback((y: number) => {
    setIsPlaying(false)
    setYear(y)
  }, [])

  const handleCatchmentChange = useCallback((value: string) => {
    setCatchment(value)
    if (value) {
      setShowAllStations(true)
    }
  }, [])

  const handleTogglePlay = useCallback(() => {
    setIsPlaying(p => {
      if (!p && year === 2024) {setYear(1990)}
      return !p
    })
  }, [year])

  const handleToggleStationView = useCallback(() => {
    setShowAllStations(v => !v)
  }, [])

  const handleStationClick = useCallback((feature: StationFeature) => {
    setSelectedFeature(feature)
    setDrawerOpen(true)

    const code = feature.properties.station_code
    if (!timeSeriesByCode[code]) {
      fetchTimeSeries(code)
        .then(ts => {
          setTimeSeriesByCode(prev => {
            if (prev[code]) {
              return prev
            }
            return { ...prev, [code]: ts }
          })
        })
        .catch(e => console.warn(`Timeseries fetch error for station ${code}:`, e))
    }
  }, [timeSeriesByCode])

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false)
  }, [])

  const allKeySeriesData = useMemo(() => {
    const map = new Map<number, StationTimeSeries>()
    for (const code of KEY_STATION_CODES_ORDERED) {
      const series = timeSeriesByCode[code]
      if (series) {
        map.set(code, series)
      }
    }
    return map
  }, [timeSeriesByCode])

  if (error) {
    return (
      <div className="error-screen">
        <span>{UI_TEXT.app.errorPrefix} {error}</span>
        <p>{UI_TEXT.app.apiRunningHint} <code>{UI_TEXT.app.apiRunCommand}</code></p>
      </div>
    )
  }

  if (!token) {
    return (
      <div className="error-screen">
        <span className="loading-text">{UI_TEXT.app.connecting}</span>
      </div>
    )
  }

  const selectedTimeSeries = selectedFeature
    ? timeSeriesByCode[selectedFeature.properties.station_code] ?? null
    : null

  return (
    <div className="app-layout">
      <section className="hero-section">
        <header className="app-header app-header--mini">
          <div className="app-header-title">{UI_TEXT.sidebar.title}</div>
          <div className="app-header-subtitle">{UI_TEXT.sidebar.subtitle}</div>
          <div className="app-header-divider" aria-hidden="true" />
          <div className="app-header-argument">
            <span>{UI_TEXT.header.argumentLine1}</span>
            <span>{UI_TEXT.header.argumentLine2}</span>
          </div>
        </header>

        <div className="map-and-controls">
          <div className="map-column">
            <div className="map-container">
              <MapContainer
                token={token}
                stationsData={stationsData}
                keyStationsData={keyStationsData}
                selectedFeature={selectedFeature}
                onStationClick={handleStationClick}
              />

              {drawerOpen && (
                <button
                  className="map-backdrop"
                  type="button"
                  aria-label={UI_TEXT.drawer.closeAriaLabel}
                  onClick={closeDrawer}
                />
              )}

              <StationDetailDrawer
                open={drawerOpen}
                feature={selectedFeature}
                timeSeries={selectedTimeSeries}
                currentYear={year}
                onClose={closeDrawer}
              />
            </div>
          </div>

          <ControlsPanel
            catchment={catchment}
            catchments={catchments}
            showAllStations={showAllStations}
            onCatchmentChange={handleCatchmentChange}
            onToggleStationView={handleToggleStationView}
          />
        </div>
      </section>

      <TimelineBar
        year={year}
        onYearChange={handleYearChange}
      />

      <SparklinePanel allSeries={allKeySeriesData} currentYear={year} />

      <footer className="sparkline-methodology">
        <p>{UI_TEXT.sidebar.methodology.line1}</p>
        <p>{UI_TEXT.sidebar.methodology.line2}</p>
        <p>{UI_TEXT.sidebar.methodology.line3}</p>
        <p>{UI_TEXT.sidebar.methodology.source}</p>
      </footer>

      <button
        className={`floating-play-btn${isPlaying ? ' active' : ''}`}
        onClick={handleTogglePlay}
        type="button"
      >
        {isPlaying ? UI_TEXT.sidebar.controls.pause : UI_TEXT.sidebar.controls.play}
      </button>
    </div>
  )
}
