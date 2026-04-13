import { useEffect, useMemo, useRef, useState, type TouchEvent } from 'react'

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
  const contentRef = useRef<HTMLDivElement | null>(null)
  const [dragOffset, setDragOffset] = useState(0)
  const [showScrollHint, setShowScrollHint] = useState(false)

  const drawerStyle = useMemo(() => {
    if (!open || dragOffset <= 0) {
      return undefined
    }
    return { transform: `translateY(${dragOffset}px)` }
  }, [dragOffset, open])

  useEffect(() => {
    const content = contentRef.current
    if (!content || !open) {
      setShowScrollHint(false)
      return
    }

    const updateHint = () => {
      const hasOverflow = content.scrollHeight - content.clientHeight > 16
      const nearTop = content.scrollTop < 20
      setShowScrollHint(hasOverflow && nearTop)
    }

    updateHint()
    const rafId = requestAnimationFrame(updateHint)
    window.addEventListener('resize', updateHint)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', updateHint)
    }
  }, [open, feature, timeSeries])

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

  const onContentScroll = () => {
    const content = contentRef.current
    if (!content) {
      return
    }
    const hasOverflow = content.scrollHeight - content.clientHeight > 16
    const nearTop = content.scrollTop < 20
    setShowScrollHint(hasOverflow && nearTop)
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
      <div
        ref={contentRef}
        className="station-drawer-content"
        onScroll={onContentScroll}
      >
        <StationDetail
          feature={feature}
          timeSeries={timeSeries}
          currentYear={currentYear}
          showBackButton={false}
        />
        <div className={`station-drawer-scroll-hint${showScrollHint ? ' station-drawer-scroll-hint--visible' : ''}`}>
          Scroll for full station history ↓
        </div>
      </div>
    </aside>
  )
}
