import { useEffect } from 'react'

import { YEAR_MAX } from '../constants'

export function useYearAnimation(
  isPlaying: boolean,
  setIsPlaying: React.Dispatch<React.SetStateAction<boolean>>,
  setYear: React.Dispatch<React.SetStateAction<number>>,
): void {
  useEffect(() => {
    if (!isPlaying) return
    const timer = setInterval(() => {
      setYear(y => {
        if (y >= YEAR_MAX) { setIsPlaying(false); return y }
        return y + 1
      })
    }, 1500)
    return () => clearInterval(timer)
  }, [isPlaying, setIsPlaying, setYear])
}
