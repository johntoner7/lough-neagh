import { UI_TEXT } from './uiText'

interface Props {
  catchment: string
  catchments: string[]
  showAllStations: boolean
  onCatchmentChange: (catchment: string) => void
  onToggleStationView: () => void
}

export default function ControlsPanel({
  catchment,
  catchments,
  showAllStations,
  onCatchmentChange,
  onToggleStationView,
}: Props) {
  return (
    <aside className="controls-panel">

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
        <button
          className={`btn-small${showAllStations ? ' active' : ''}`}
          onClick={onToggleStationView}
          type="button"
        >
          {showAllStations ? UI_TEXT.sidebar.controls.showKeyOnly : UI_TEXT.sidebar.controls.showAll}
        </button>
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

    </aside>
  )
}
