import { useEffect, useState } from 'react'

import { fetchCatchments, fetchConfig, fetchTimeSeries } from '../api'
import { KEY_STATION_CODES_ORDERED } from '../constants'
import { UI_TEXT } from '../uiText'

import type { StationTimeSeries } from '../types'

interface AppInitState {
  token: string
  catchments: string[]
  timeSeriesByCode: Record<number, StationTimeSeries>
  setTimeSeriesByCode: React.Dispatch<React.SetStateAction<Record<number, StationTimeSeries>>>
  error: string | null
}

export function useAppInit(): AppInitState {
  const [token, setToken] = useState('')
  const [catchments, setCatchments] = useState<string[]>([])
  const [timeSeriesByCode, setTimeSeriesByCode] = useState<Record<number, StationTimeSeries>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchConfig()
      .then(cfg => setToken(cfg.mapbox_token))
      .catch(e => {
        console.error('Failed to load config:', e)
        setError(UI_TEXT.app.errorMessage)
      })

    fetchCatchments()
      .then(setCatchments)
      .catch(e => console.warn('Could not load catchments:', e))

    Promise.allSettled(KEY_STATION_CODES_ORDERED.map(code => fetchTimeSeries(code)))
      .then(results => {
        const nextSeries: Record<number, StationTimeSeries> = {}
        results.forEach((result, i) => {
          if (result.status === 'fulfilled') {
            nextSeries[KEY_STATION_CODES_ORDERED[i]] = result.value
          } else {
            console.warn(`Could not load time series for station ${KEY_STATION_CODES_ORDERED[i]}:`, result.reason)
          }
        })
        setTimeSeriesByCode(prev => ({ ...nextSeries, ...prev }))
      })
  }, [])

  return { token, catchments, timeSeriesByCode, setTimeSeriesByCode, error }
}
