import { UI_TEXT } from './uiText'
import './Sidebar.css'

import type { SummaryStats } from './types'

interface Props {
  year: number
  catchment: string
  catchments: string[]
  showAllStations: boolean
  summary: SummaryStats
  sidebarOpen: boolean
  onToggleStationView: () => void
  onCatchmentChange: (catchment: string) => void
  onToggleSidebar: () => void
}

export default function Sidebar({
  year,
  catchment,
  catchments,
  showAllStations,
  summary,
  sidebarOpen,
  onCatchmentChange,
  onToggleStationView,
  onToggleSidebar,
}: Props) {
  const isBaselineYear = year === 1990

  return (
    <aside className={`sidebar${sidebarOpen ? '' : ' sidebar--collapsed'}`} style={{ height: '100vh' }}>
      {/* ── Header — always visible ── */}
      <div className="sidebar-header">
        <div className="sidebar-header-inner">
          <div className="sidebar-header-text">
            <div className="sidebar-title">{UI_TEXT.sidebar.title}</div>
            <div className="sidebar-subtitle">{UI_TEXT.sidebar.subtitle}</div>
          </div>
          <button
            className="sidebar-toggle"
            onClick={onToggleSidebar}
            type="button"
            aria-label={sidebarOpen ? UI_TEXT.sidebar.collapseAriaLabel : UI_TEXT.sidebar.expandAriaLabel}
          >
            {sidebarOpen ? '‹' : '›'}
          </button>
        </div>
      </div>

      {/* ── Body — hidden when collapsed ── */}
      <div className="sidebar-body">

        {/* ── Headline stat ── */}
        <div className="sidebar-section">
          <div className="headline-block">
            {isBaselineYear ? (
              <>
                <div className="headline-pct headline-pct-baseline">
                  {UI_TEXT.sidebar.baselineHeadline}
                </div>
                <div className="headline-sub">
                  {UI_TEXT.sidebar.baselineSubline}
                </div>
              </>
            ) : (
              <>
                <div className="headline-pct">
                  {summary.stationsWithData > 0 ? `${summary.pctAboveThreshold}%` : '—'}
                </div>
                <div className="headline-label">{UI_TEXT.sidebar.aboveThresholdLabel}</div>
                <div className="headline-sub">
                  {summary.stationsWithData > 0 ? (
                    <span>{UI_TEXT.sidebar.aboveThresholdSummary(summary.stationsAboveThreshold, summary.stationsWithData, year)}</span>
                  ) : (
                    <span>{UI_TEXT.sidebar.noDataForYear}</span>
                  )}
                </div>
              </>
            )}
            <div className="headline-hint">{UI_TEXT.sidebar.headlineHint}</div>
          </div>
        </div>

        {/* ── Station visibility mode ── */}
        <div className="sidebar-section">
          <div className="section-label">{UI_TEXT.sidebar.sections.stationView}</div>
          <button
            className={`btn-small${showAllStations ? ' active' : ''}`}
            onClick={onToggleStationView}
            type="button"
          >
            {showAllStations ? UI_TEXT.sidebar.controls.showKeyOnly : UI_TEXT.sidebar.controls.showAll}
          </button>
        </div>

        {/* ── Catchment filter ── */}
        <div className="sidebar-section">
          <div className="section-label">{UI_TEXT.sidebar.sections.catchment}</div>
          <select
            className="select-input"
            value={catchment}
            onChange={e => onCatchmentChange(e.target.value)}
          >
            <option value="">{UI_TEXT.sidebar.controls.allCatchments}</option>
            {catchments.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>

        {/* ── Legend ── */}
        <div className="sidebar-section">
          <div className="section-label">{UI_TEXT.sidebar.sections.concentration}</div>
          <div className="legend-rows">
            <div className="legend-row">
              <span className="legend-dot" style={{ background: '#4ade80' }} />
              <span>{UI_TEXT.sidebar.legend.belowWfd}</span>
            </div>
            <div className="legend-row">
              <span className="legend-dot" style={{ background: '#fb923c' }} />
              <span>{UI_TEXT.sidebar.legend.midBand}</span>
            </div>
            <div className="legend-row">
              <span className="legend-dot" style={{ background: '#dc2626' }} />
              <span>{UI_TEXT.sidebar.legend.highBand}</span>
            </div>
          </div>
          <div className="legend-note">
            {UI_TEXT.sidebar.legend.wfdLimitPrefix} <strong>{UI_TEXT.sidebar.legend.wfdLimitValue}</strong>
          </div>
          <div className="legend-rows" style={{ marginTop: 8 }}>
            <div className="legend-row">
              <span className="legend-dot" style={{ background: '#cccccc' }} />
              <span>{UI_TEXT.sidebar.legend.noData}</span>
            </div>
          </div>
        </div>

        {/* ── Spacer ── */}
        <div style={{ flex: 1 }} />

        {/* ── Source / methodology ── */}
        <div className="methodology">
          {UI_TEXT.sidebar.methodology.line1}
          {UI_TEXT.sidebar.methodology.line2}
          {UI_TEXT.sidebar.methodology.line3}
          <br />
          {UI_TEXT.sidebar.methodology.source}
        </div>

      </div>
    </aside>
  )
}
