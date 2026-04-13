import type { StationProperties } from './types'

interface Props {
  properties: StationProperties
  year: number
}

function trendLabel(direction: string | null, significant: boolean | null): string {
  if (direction === 'insufficient data') {return 'Insufficient data'}
  if (direction === 'decreasing' && significant) {return '↓ Improving'}
  if (direction === 'increasing' && significant) {return '↑ Worsening'}
  return '→ No significant trend'
}

function trendColor(direction: string | null, significant: boolean | null): string {
  if (direction === 'decreasing' && significant) {return 'var(--compliant)'}
  if (direction === 'increasing' && significant) {return '#EF4444'}
  return 'var(--text-dim)'
}

export default function PopupCard({ properties: p, year }: Props) {
  const hasData = p.annual_mean_p_sol !== null
  const annualMean = hasData ? p.annual_mean_p_sol!.toFixed(3) : null
  const rolling = p.rolling_mean_5yr !== null ? p.rolling_mean_5yr.toFixed(3) : null

  const trend = trendLabel(p.trend_direction, p.trend_significant)
  const trendClr = trendColor(p.trend_direction, p.trend_significant)

  return (
    <div className="popup-card">
      {/* Eyebrow */}
      <div className="popup-eyebrow">{p.location_name}</div>

      {/* Primary stat */}
      <div className="popup-stat">
        {hasData ? annualMean : '—'}
        <span className="popup-unit">&thinsp;mg/l P(SOL)</span>
      </div>
      <div className="popup-sub">
        Annual mean &middot; {year}
      </div>

      <div className="popup-divider" />

      {/* Data rows */}
      <div className="popup-row">
        <span className="popup-label">WFD status</span>
        {!hasData ? (
          <span style={{ color: 'var(--text-dim)' }}>No data</span>
        ) : p.wfd_compliant ? (
          <span style={{ color: 'var(--compliant)' }}>▼ Compliant</span>
        ) : (
          <span style={{ color: 'var(--above)' }}>▲ Above threshold</span>
        )}
      </div>

      {p.catchment_name && (
        <div className="popup-row">
          <span className="popup-label">Catchment</span>
          <span className="popup-value">{p.catchment_name}</span>
        </div>
      )}

      {rolling && (
        <div className="popup-row">
          <span className="popup-label">5-yr rolling mean</span>
          <span className="popup-value">{rolling} mg/l</span>
        </div>
      )}

      <div className="popup-row">
        <span className="popup-label">Trend (post-2010)</span>
        <span style={{ color: trendClr }}>{trend}</span>
      </div>

      {p.sparse_year && (
        <div className="popup-sparse">⚠ Sparse year — fewer than 8 readings</div>
      )}

      <div className="popup-divider" />
      <div className="popup-source">Source: DAERA, 2026</div>
    </div>
  )
}
