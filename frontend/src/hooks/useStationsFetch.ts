import { useEffect, useState } from 'react'

import { fetchStations } from '../api'
import { KEY_STATION_CODES } from '../MapContainer'

import type { GeoJSONCollection } from '../types'

const EMPTY_COLLECTION: GeoJSONCollection = { type: 'FeatureCollection', features: [] }

interface StationsFetchState {
  stationsData: GeoJSONCollection
  keyStationsData: GeoJSONCollection
}

export function useStationsFetch(
  token: string,
  year: number,
  catchment: string,
): StationsFetchState {
  const [stationsData, setStationsData] = useState<GeoJSONCollection>(EMPTY_COLLECTION)
  const [keyStationsData, setKeyStationsData] = useState<GeoJSONCollection>(EMPTY_COLLECTION)

  useEffect(() => {
    if (!token) return
    const ctrl = new AbortController()

    fetchStations(year, catchment, true, 'rolling', ctrl.signal)
      .then(data => {
        const keyFeatures = data.features.filter(f =>
          KEY_STATION_CODES.has(f.properties.station_code),
        )
        setStationsData({ type: 'FeatureCollection', features: data.features })
        setKeyStationsData({ type: 'FeatureCollection', features: keyFeatures })
      })
      .catch(e => {
        if (e instanceof DOMException && e.name === 'AbortError') return
        console.warn('Station fetch error:', e)
      })

    return () => ctrl.abort()
  }, [token, year, catchment])

  return { stationsData, keyStationsData }
}
