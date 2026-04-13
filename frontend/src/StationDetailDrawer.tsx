import { useMemo, useRef, useState, type TouchEvent } from 'react'

import StationDetail from './StationDetail'
import { UI_TEXT } from './uiText'

import type { StationFeature, StationTimeSeries } from './types'

interface Props {
  open: boolean
  feature: StationFeature | null
  timeSeries: StationTimeSeries | null
  currentYear: number
  onClose: () => void
}

export default function StationDetailDrawer({
  open,
  feature,
  timeSeries,
  currentYear,
  onClose,
}: Props) {
  const startY = useRef<number | null>(null)
  const [dragOffset, setDragOffset] = useState(0)

  const drawerStyle = useMemo(() => {
    if (!open || dragOffset <= 0) {
      return undefined
    }
    return { transform: `translateY(${dragOffset}px)` }
  }, [dragOffset, open])

  if (!feature) {
    return null
  }

  const onTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    startY.current = event.touches[0].clientY
  }

  const onTouchMove = (event: TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) {
      return
    }
    const delta = event.touches[0].clientY - startY.current
    setDragOffset(delta > 0 ? delta : 0)
  }

  const onTouchEnd = () => {
    if (dragOffset > 90) {
      setDragOffset(0)
      onClose()
      return
    }
    setDragOffset(0)
    startY.current = null
  }

  return (
    <aside
      className={`station-drawer${open ? ' station-drawer--open' : ''}`}
      style={drawerStyle}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <button
        className="station-drawer-close"
        type="button"
        onClick={onClose}
        aria-label={UI_TEXT.drawer.closeAriaLabel}
      >
        {UI_TEXT.drawer.closeSymbol}
      </button>
      <div className="station-drawer-content">
        <StationDetail
          feature={feature}
          timeSeries={timeSeries}
          currentYear={currentYear}
          showBackButton={false}
        />
      </div>
    </aside>
  )
}
