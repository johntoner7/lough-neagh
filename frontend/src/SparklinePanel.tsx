import SparklineChart from './SparklineChart'

import type { StationTimeSeries } from './types'

// Ordered list of the six key Lough Neagh tributaries
const KEY_STATION_ORDER = [10212, 10233, 10271, 10328, 10361, 10380]

interface Props {
  allSeries: Map<number, StationTimeSeries>
  currentYear: number
}

export default function SparklinePanel({ allSeries, currentYear }: Props) {
  const allValues: number[] = []

  for (const ts of allSeries.values()) {
    for (const point of ts.series) {
      if (typeof point.annual_mean_p_sol === 'number') {
        allValues.push(point.annual_mean_p_sol)
      }
      if (typeof point.rolling_mean_5yr === 'number') {
        allValues.push(point.rolling_mean_5yr)
      }
    }
  }

  const observedMax = allValues.length ? Math.max(...allValues) : 0.2
  const paddedMax = Math.max(0.1, observedMax * 1.1)
  const sharedYMax = Math.ceil(paddedMax / 0.05) * 0.05
  const sharedTickStep = 0.05

  return (
    <div className="sparkline-panel">
      {KEY_STATION_ORDER.map(code => {
        const ts = allSeries.get(code)
        return (
          <div key={code} className="sparkline-cell">
            <div className="sparkline-cell-label">
              {ts ? ts.location_name : `Station ${code}`}
            </div>
            {ts ? (
              <SparklineChart
                series={ts.series}
                currentYear={currentYear}
                yMax={sharedYMax}
                yTickStep={sharedTickStep}
              />
            ) : (
              <div className="sparkline-cell-loading">Loading…</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
