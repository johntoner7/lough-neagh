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
  // Keep drag offset in a ref AND state: ref for reading in event handlers
  // (avoids stale closure race between touchmove and touchend), state for rendering.
  const dragOffsetRef = useRef(0)
  const [dragOffset, setDragOffset] = useState(0)
  const [showScrollHint, setShowScrollHint] = useState(false)

  // Reset drag state whenever the drawer closes
  useEffect(() => {
    if (!open) {
      dragOffsetRef.current = 0
      setDragOffset(0)
      startY.current = null
    }
  }, [open])

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

  const onHandleTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    startY.current = event.touches[0].clientY
  }

  const onHandleTouchMove = (event: TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) return
    const delta = event.touches[0].clientY - startY.current
    const offset = delta > 0 ? delta : 0
    dragOffsetRef.current = offset
    setDragOffset(offset)
  }

  const onHandleTouchEnd = () => {
    const offset = dragOffsetRef.current
    dragOffsetRef.current = 0
    setDragOffset(0)
    startY.current = null
    if (offset > 80) {
      onClose()
    }
  }

  // Content-area swipe: only initiate drag-to-close if already scrolled to top
  const onContentTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    const content = contentRef.current
    if (!content || content.scrollTop > 0) {
      startY.current = null
      return
    }
    startY.current = event.touches[0].clientY
  }

  const onContentTouchMove = (event: TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) return
    const delta = event.touches[0].clientY - startY.current
    if (delta <= 0) {
      // Scrolling up into content — cancel drag
      startY.current = null
      dragOffsetRef.current = 0
      setDragOffset(0)
      return
    }
    dragOffsetRef.current = delta
    setDragOffset(delta)
  }

  const onContentScroll = () => {
    const content = contentRef.current
    if (!content) return
    const hasOverflow = content.scrollHeight - content.clientHeight > 16
    const nearTop = content.scrollTop < 20
    setShowScrollHint(hasOverflow && nearTop)
  }

  return (
    <aside
      className={`station-drawer${open ? ' station-drawer--open' : ''}`}
      style={drawerStyle}
    >
      {/* Drag handle — swipe this down to dismiss */}
      <div
        className="drawer-handle"
        onTouchStart={onHandleTouchStart}
        onTouchMove={onHandleTouchMove}
        onTouchEnd={onHandleTouchEnd}
      >
        <div className="drawer-handle-bar" />
      </div>

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
        onTouchStart={onContentTouchStart}
        onTouchMove={onContentTouchMove}
        onTouchEnd={onHandleTouchEnd}
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
