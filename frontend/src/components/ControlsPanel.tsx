import { YEAR_MAX, YEAR_MIN } from '../constants'
import { getEraCaption } from '../eraCaptions'
import { UI_TEXT } from '../uiText'

import type { SummaryStats } from '../types'

interface Props {
  year: number
  summary: SummaryStats
  catchment: string
  catchments: string[]
  showFarmLayer: boolean
  onYearChange: (year: number) => void
  onCatchmentChange: (catchment: string) => void
  onToggleFarmLayer: () => void
}

export default function ControlsPanel({
  year,
  summary,
  catchment,
  catchments,
  showFarmLayer,
  onYearChange,
  onCatchmentChange,
  onToggleFarmLayer,
}: Props) {
  const isBaselineYear = year === YEAR_MIN

  const narration = getEraCaption(year)

  return (
    <aside className="controls-panel">
      <div className="cp-section cp-controls-cluster">
        <div className="section-label">Map controls</div>
        <div className="cp-control-item">
          <div className="cp-control-label">Year</div>
          <select
            className="select-input"
            value={String(year)}
            onChange={e => onYearChange(Number(e.target.value))}
          >
            {Array.from({ length: YEAR_MAX - YEAR_MIN + 1 }, (_, i) => YEAR_MAX - i).map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <div className="cp-control-item">
          <div className="cp-control-label">{UI_TEXT.sidebar.farmLayer.title}</div>
          <button
            className={`station-toggle-btn${showFarmLayer ? ' active' : ''}`}
            onClick={onToggleFarmLayer}
            type="button"
            style={{ width: '100%' }}
          >
            {showFarmLayer ? UI_TEXT.sidebar.farmLayer.hide : UI_TEXT.sidebar.farmLayer.show}
          </button>
        </div>

        <div className="cp-control-item">
          <div className="cp-control-label">{UI_TEXT.sidebar.sections.catchment}</div>
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

      </div>

      <details className="cp-section cp-collapsible" open>
        <summary className="cp-collapsible-summary">River status summary</summary>
        <div className="cp-collapsible-body cp-headline">
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
      </details>

      <details className="cp-section cp-collapsible" open>
        <summary className="cp-collapsible-summary">Why recovery is slow</summary>
        <div className="cp-collapsible-body">
          <div className="cp-sediment-callout">{UI_TEXT.sidebar.sedimentCallout}</div>
        </div>
      </details>

    </aside>
  )
}
