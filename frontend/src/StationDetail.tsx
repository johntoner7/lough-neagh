import SparklineChart from './SparklineChart'
import { UI_TEXT } from './uiText'

import type { StationFeature, StationTimeSeries } from './types'

// ─── Interpretive text for the 6 key Lough Neagh tributaries ──────────────────

const INTERPRETIVE: Record<number, string> = UI_TEXT.stationDetail.interpretive

// ─── Helpers ──────────────────────────────────────────────────────────────────

function trendLabel(dir: string | null, sig: boolean | null): string {
  if (!dir || dir === UI_TEXT.stationDetail.trend.insufficientData) {return UI_TEXT.stationDetail.trend.noData}
  if (dir === 'decreasing' && sig) {return UI_TEXT.stationDetail.trend.improving}
  if (dir === 'increasing' && sig) {return UI_TEXT.stationDetail.trend.worsening}
  return UI_TEXT.stationDetail.trend.noClearTrend
}

function trendColor(dir: string | null, sig: boolean | null): string {
  if (dir === 'decreasing' && sig) {return '#3D8B5E'}
  if (dir === 'increasing' && sig) {return '#c0551a'}
  return '#888680'
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  feature: StationFeature
  timeSeries: StationTimeSeries | null
  currentYear: number
  onBack?: () => void
  showBackButton?: boolean
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function StationDetail({
  feature,
  timeSeries,
  currentYear,
  onBack,
  showBackButton = true,
}: Props) {
  const p = feature.properties
  const currentYearPoint = timeSeries?.series.find(point => point.year === currentYear)
  const currentReading = currentYearPoint
    ? (currentYearPoint.rolling_mean_5yr ?? currentYearPoint.annual_mean_p_sol)
    : p.metric_p_sol
  const hasData = typeof currentReading === 'number'
  const compliant = hasData ? currentReading <= 0.035 : null
  const isSparseYear = currentYearPoint ? currentYearPoint.sparse_year : Boolean(p.sparse_year)

  return (
    <div className="station-detail">
      {showBackButton && onBack && (
        <button className="detail-back" onClick={onBack} type="button">
          {UI_TEXT.stationDetail.backToAll}
        </button>
      )}

      <div className="detail-name">{p.location_name}</div>
      {p.catchment_name && (
        <div className="detail-catchment">{p.catchment_name}{UI_TEXT.stationDetail.catchmentSuffix}</div>
      )}

      <div className="detail-stat-row">
        <span className="detail-value">
          {hasData ? currentReading.toFixed(3) : '—'}
          <span className="detail-unit">{UI_TEXT.stationDetail.unit}</span>
        </span>
        {hasData && (
          <span
            className="detail-badge"
            style={{ color: compliant ? '#3D8B5E' : '#c0551a' }}
          >
            {compliant ? UI_TEXT.stationDetail.badgeCompliant : UI_TEXT.stationDetail.badgeAboveLimit}
          </span>
        )}
      </div>

      {isSparseYear && (
        <div className="detail-sparse">{UI_TEXT.stationDetail.sparseYearWarning}</div>
      )}

      <div
        className="detail-trend"
        style={{ color: trendColor(p.trend_direction, p.trend_significant) }}
      >
        {trendLabel(p.trend_direction, p.trend_significant)}
      </div>

      {INTERPRETIVE[p.station_code] && (
        <p className="detail-interp">{INTERPRETIVE[p.station_code]}</p>
      )}

      {timeSeries ? (
        <div className="detail-chart-wrap">
          <div className="detail-chart-label">{UI_TEXT.stationDetail.chartLabel}</div>
          <SparklineChart series={timeSeries.series} currentYear={currentYear} />
          <div className="detail-chart-legend">
            <span className="chart-legend-swatch" style={{ background: '#c0551a' }} />
            {UI_TEXT.stationDetail.chartLegendAnnual}
            <span className="chart-legend-swatch" style={{ background: '#888680', marginLeft: 8 }} />
            {UI_TEXT.stationDetail.chartLegendRolling}
            <span className="chart-legend-swatch" style={{ background: '#fd8d3c', marginLeft: 8 }} />
            {UI_TEXT.stationDetail.chartLegendWfd}
          </div>
        </div>
      ) : (
        <div className="detail-loading">
          <div className="spinner" />
          {UI_TEXT.stationDetail.chartLoading}
        </div>
      )}
    </div>
  )
}
