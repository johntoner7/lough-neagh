import { useMemo } from 'react'

import type { GeoJSONCollection, SummaryStats } from '../types'

export function useSummaryStats(stationsData: GeoJSONCollection): SummaryStats {
  return useMemo(() => {
    const features = stationsData.features
    const withData = features.filter(f => f.properties.metric_p_sol !== null)
    const aboveThreshold = withData.filter(f => (f.properties.metric_p_sol ?? 0) >= 0.035)
    const pct = withData.length > 0
      ? Math.round((aboveThreshold.length / withData.length) * 100)
      : 0
    const mean = withData.length > 0
      ? (withData.reduce((s, f) => s + (f.properties.metric_p_sol ?? 0), 0) / withData.length).toFixed(3)
      : '—'
    return {
      stationsWithData: withData.length,
      stationsAboveThreshold: aboveThreshold.length,
      pctAboveThreshold: pct,
      networkMean: mean,
    }
  }, [stationsData])
}
