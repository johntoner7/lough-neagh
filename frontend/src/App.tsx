import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { fetchTimeSeries } from './api'
import { KEY_STATION_CODES_ORDERED, YEAR_MIN, YEAR_MAX } from './constants'
import ControlsPanel from './ControlsPanel'
import { useAppInit } from './hooks/useAppInit'
import { useStationsFetch } from './hooks/useStationsFetch'
import { useSummaryStats } from './hooks/useSummaryStats'
import { useYearAnimation } from './hooks/useYearAnimation'
import MapContainer from './MapContainer'
import SparklinePanel from './SparklinePanel'
import StationDetailDrawer from './StationDetailDrawer'
import TimelineBar from './TimelineBar'
import { UI_TEXT } from './uiText'

import type { StationFeature, StationTimeSeries } from './types'

export default function App() {
  const { token, catchments, timeSeriesByCode, setTimeSeriesByCode, error } = useAppInit()

  const [year, setYear] = useState(YEAR_MAX)
  const [catchment, setCatchment] = useState('')
  const [showAllStations, setShowAllStations] = useState(true)
  const [showFarmLayer, setShowFarmLayer] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<StationFeature | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const { stationsData, keyStationsData } = useStationsFetch(token, year, catchment, showAllStations)
  const summary = useSummaryStats(stationsData)
  useYearAnimation(isPlaying, setIsPlaying, setYear)

  // Ref so handleStationClick always reads the latest cache without depending on it
  const timeSeriesCacheRef = useRef(timeSeriesByCode)
  useEffect(() => { timeSeriesCacheRef.current = timeSeriesByCode }, [timeSeriesByCode])

  // Tracks codes with a fetch already in flight to prevent duplicate requests
  const inflightCodes = useRef(new Set<number>())

  const handleYearChange = useCallback((y: number) => {
    setIsPlaying(false)
    setYear(y)
  }, [])

  const handleCatchmentChange = useCallback((value: string) => {
    setCatchment(value)
    if (value) setShowAllStations(true)
  }, [])

  const handleTogglePlay = useCallback(() => {
    setIsPlaying(p => {
      if (!p && year === YEAR_MAX) setYear(YEAR_MIN)
      return !p
    })
  }, [year])

  const handleToggleStationView = useCallback(() => setShowAllStations(v => !v), [])
  const handleToggleFarmLayer = useCallback(() => setShowFarmLayer(v => !v), [])

  const handleStationClick = useCallback((feature: StationFeature) => {
    setSelectedFeature(feature)
    setDrawerOpen(true)

    const code = feature.properties.station_code
    if (!timeSeriesCacheRef.current[code] && !inflightCodes.current.has(code)) {
      inflightCodes.current.add(code)
      fetchTimeSeries(code)
        .then(ts => {
          setTimeSeriesByCode(prev => prev[code] ? prev : { ...prev, [code]: ts })
        })
        .catch(e => console.warn(`Timeseries fetch error for station ${code}:`, e))
        .finally(() => inflightCodes.current.delete(code))
    }
  }, [setTimeSeriesByCode])

  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  const allKeySeriesData = useMemo(() => {
    const map = new Map<number, StationTimeSeries>()
    for (const code of KEY_STATION_CODES_ORDERED) {
      const series = timeSeriesByCode[code]
      if (series) map.set(code, series)
    }
    return map
  }, [timeSeriesByCode])

  if (error) {
    return (
      <div className="error-screen">
        <div className="loading-screen">
          <span className="error-screen__title">{UI_TEXT.app.errorTitle}</span>
          <p className="error-screen__message">{error}</p>
          <button className="error-screen__retry" onClick={() => window.location.reload()}>
            {UI_TEXT.app.errorRetry}
          </button>
        </div>
      </div>
    )
  }

  if (!token) {
    return (
      <div className="error-screen">
        <div className="loading-screen">
          <div className="spinner spinner--lg" />
          <span>{UI_TEXT.app.connecting}</span>
        </div>
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
                year={year}
                stationsData={stationsData}
                keyStationsData={keyStationsData}
                selectedFeature={selectedFeature}
                showFarmLayer={showFarmLayer}
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
            year={year}
            summary={summary}
            catchment={catchment}
            catchments={catchments}
            showAllStations={showAllStations}
            showFarmLayer={showFarmLayer}
            onCatchmentChange={handleCatchmentChange}
            onToggleStationView={handleToggleStationView}
            onToggleFarmLayer={handleToggleFarmLayer}
          />
        </div>
      </section>

      <TimelineBar year={year} onYearChange={handleYearChange} />

      <SparklinePanel allSeries={allKeySeriesData} currentYear={year} />

      <footer className="sparkline-methodology">
        <p>{UI_TEXT.sidebar.methodology.line1}</p>
        <p>{UI_TEXT.sidebar.methodology.line2}</p>
        <p>{UI_TEXT.sidebar.methodology.line3}</p>
        <p>{UI_TEXT.sidebar.methodology.source}</p>
      </footer>

      <div className="floating-player">
        <button
          className="player-btn player-step"
          onClick={() => handleYearChange(Math.max(YEAR_MIN, year - 1))}
          type="button"
          disabled={year <= YEAR_MIN}
          aria-label="Previous year"
        >
          ‹
        </button>
        <div className="player-divider" />
        <button
          className={`player-btn player-play${isPlaying ? ' active' : ''}`}
          onClick={handleTogglePlay}
          type="button"
          aria-label={isPlaying ? UI_TEXT.sidebar.controls.pause : UI_TEXT.sidebar.controls.play}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <div className="player-divider" />
        <span className="player-year">{year}</span>
        <div className="player-divider" />
        <button
          className="player-btn player-step"
          onClick={() => handleYearChange(Math.min(YEAR_MAX, year + 1))}
          type="button"
          disabled={year >= YEAR_MAX}
          aria-label="Next year"
        >
          ›
        </button>
      </div>
    </div>
  )
}
