import { useEffect, useRef, useState, type TouchEvent } from 'react'

interface DragToDismiss {
  dragOffset: number
  contentRef: React.RefObject<HTMLDivElement>
  handleTouchHandlers: {
    onTouchStart: (e: TouchEvent<HTMLDivElement>) => void
    onTouchMove: (e: TouchEvent<HTMLDivElement>) => void
    onTouchEnd: () => void
  }
  contentTouchHandlers: {
    onTouchStart: (e: TouchEvent<HTMLDivElement>) => void
    onTouchMove: (e: TouchEvent<HTMLDivElement>) => void
    onTouchEnd: () => void
  }
}

export function useDragToDismiss(open: boolean, onClose: () => void): DragToDismiss {
  const startY = useRef<number | null>(null)
  // Ref for reading in event handlers (avoids stale closure race between touchmove/touchend)
  const dragOffsetRef = useRef(0)
  const [dragOffset, setDragOffset] = useState(0)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      dragOffsetRef.current = 0
      setDragOffset(0)
      startY.current = null
    }
  }, [open])

  const commitOffset = (offset: number) => {
    dragOffsetRef.current = offset
    setDragOffset(offset)
  }

  const onHandleTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    startY.current = e.touches[0].clientY
  }

  const onHandleTouchMove = (e: TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) return
    const delta = e.touches[0].clientY - startY.current
    commitOffset(delta > 0 ? delta : 0)
  }

  const onHandleTouchEnd = () => {
    const offset = dragOffsetRef.current
    commitOffset(0)
    startY.current = null
    if (offset > 80) onClose()
  }

  // Content-area swipe: only start drag if already scrolled to top
  const onContentTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    const content = contentRef.current
    if (!content || content.scrollTop > 0) {
      startY.current = null
      return
    }
    startY.current = e.touches[0].clientY
  }

  const onContentTouchMove = (e: TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) return
    const delta = e.touches[0].clientY - startY.current
    if (delta <= 0) {
      // Scrolling up into content — cancel drag
      startY.current = null
      commitOffset(0)
      return
    }
    commitOffset(delta)
  }

  return {
    dragOffset,
    contentRef,
    handleTouchHandlers: {
      onTouchStart: onHandleTouchStart,
      onTouchMove: onHandleTouchMove,
      onTouchEnd: onHandleTouchEnd,
    },
    contentTouchHandlers: {
      onTouchStart: onContentTouchStart,
      onTouchMove: onContentTouchMove,
      onTouchEnd: onHandleTouchEnd,
    },
  }
}
