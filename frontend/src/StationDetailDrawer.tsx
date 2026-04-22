import { useEffect, useMemo, useState } from 'react'

import { useDragToDismiss } from './hooks/useDragToDismiss'
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
  const { dragOffset, contentRef, handleTouchHandlers, contentTouchHandlers } =
    useDragToDismiss(open, onClose)

  const [showScrollHint, setShowScrollHint] = useState(false)

  const drawerStyle = useMemo(() => {
    if (!open || dragOffset <= 0) return undefined
    return { transform: `translateY(${dragOffset}px)` }
  }, [dragOffset, open])

  useEffect(() => {
    const content = contentRef.current
    if (!content || !open) { setShowScrollHint(false); return }

    const updateHint = () => {
      const hasOverflow = content.scrollHeight - content.clientHeight > 16
      const nearTop = content.scrollTop < 20
      setShowScrollHint(hasOverflow && nearTop)
    }

    updateHint()
    const rafId = requestAnimationFrame(updateHint)
    window.addEventListener('resize', updateHint)
    return () => { cancelAnimationFrame(rafId); window.removeEventListener('resize', updateHint) }
  }, [open, feature, timeSeries])

  if (!feature) return null

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
      <div className="drawer-handle" {...handleTouchHandlers}>
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
        {...contentTouchHandlers}
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
