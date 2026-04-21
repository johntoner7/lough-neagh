import { UI_TEXT } from './uiText'

import type { SummaryStats } from './types'

interface Props {
  year: number
  summary: SummaryStats
  catchment: string
  catchments: string[]
  showAllStations: boolean
  showFarmLayer: boolean
  onCatchmentChange: (catchment: string) => void
  onToggleStationView: () => void
  onToggleFarmLayer: () => void
}

export default function ControlsPanel({
  year,
  summary,
  catchment,
  catchments,
  showAllStations,
  showFarmLayer,
  onCatchmentChange,
  onToggleStationView,
  onToggleFarmLayer,
}: Props) {
  const isBaselineYear = year === 1990

  const narration =
    year >= 1990 && year <= 1998 ? UI_TEXT.sidebar.narrationSewage :
    year >= 2005 && year <= 2024 ? UI_TEXT.sidebar.narrationStalled :
    null

  return (
    <aside className="controls-panel">

      {/* ── Headline stat ── */}
      <div className="cp-section cp-headline">
        {isBaselineYear ? (
          <>
            <div className="cp-headline-text cp-headline-text--baseline">
              {UI_TEXT.sidebar.baselineHeadline}
            </div>
            <div className="cp-headline-sub">
              {UI_TEXT.sidebar.baselineSubline}
            </div>
          </>
        ) : (
          <>
            <div className="cp-headline-pct">
              {summary.stationsWithData > 0 ? `${summary.pctAboveThreshold}%` : '—'}
            </div>
            <div className="cp-headline-label">{UI_TEXT.sidebar.aboveThresholdLabel}</div>
            <div className="cp-headline-sub">
              {summary.stationsWithData > 0 ? (
                <span>{UI_TEXT.sidebar.aboveThresholdSummary(summary.stationsAboveThreshold, summary.stationsWithData, year)}</span>
              ) : (
                <span>{UI_TEXT.sidebar.noDataForYear}</span>
              )}
            </div>
            {narration && (
              <div className="cp-headline-narration">{narration}</div>
            )}
          </>
        )}
        <div className="cp-headline-hint">{UI_TEXT.sidebar.headlineHint}</div>
      </div>

      {/* ── Catchment filter ── */}
      <div className="cp-section">
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

      {/* ── Station view toggle ── */}
      <div className="cp-section">
        <div className="section-label">{UI_TEXT.sidebar.sections.stationView}</div>
        <div className="station-toggle-group">
          <button
            className={`station-toggle-btn${!showAllStations ? ' active' : ''}`}
            onClick={() => { if (showAllStations) {onToggleStationView()} }}
            type="button"
          >
            6 key stations
          </button>
          <button
            className={`station-toggle-btn${showAllStations ? ' active' : ''}`}
            onClick={() => { if (!showAllStations) {onToggleStationView()} }}
            type="button"
          >
            All stations
          </button>
        </div>
      </div>

      {/* ── Legend ── */}
      <div className="cp-section">
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

      {/* ── Farm layer toggle ── */}
      <div className="cp-section">
        <div className="section-label">Cattle density (farm census)</div>
        <button
          className={`station-toggle-btn${showFarmLayer ? ' active' : ''}`}
          onClick={onToggleFarmLayer}
          type="button"
          style={{ width: '100%', marginBottom: showFarmLayer ? 8 : 0 }}
        >
          {showFarmLayer ? 'Hide layer' : 'Show layer'}
        </button>
        {showFarmLayer && (
          <div>
            <div className="legend-rows">
              <div className="legend-row">
                <span className="legend-dot" style={{ background: '#fef9c3', border: '1px solid #d1d5db' }} />
                <span>&lt; 0.5 cattle / ha</span>
              </div>
              <div className="legend-row">
                <span className="legend-dot" style={{ background: '#f59e0b' }} />
                <span>0.5 – 1.5 cattle / ha</span>
              </div>
              <div className="legend-row">
                <span className="legend-dot" style={{ background: '#b45309' }} />
                <span>1.5 – 2.5 cattle / ha</span>
              </div>
              <div className="legend-row">
                <span className="legend-dot" style={{ background: '#78350f' }} />
                <span>&gt; 2.5 cattle / ha</span>
              </div>
            </div>
            <div className="legend-note">Syncs to timeline (2015–2024). Hover a ward for details. Areas with more cattle tend to have higher phosphorus levels.</div>
          </div>
        )}
      </div>

      {/* ── Sediment callout ── */}
      <div className="cp-section">
        <div className="cp-sediment-callout">{UI_TEXT.sidebar.sedimentCallout}</div>
      </div>

    </aside>
  )
}
