import React, { useState, useRef, useEffect, ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight, GripVertical } from 'lucide-react'

interface ResizablePanelsProps {
  leftPanel: ReactNode
  rightPanel: ReactNode
  defaultLeftWidth?: number // percentage
  minLeftWidth?: number // pixels
  minRightWidth?: number // pixels
  onResize?: (leftWidthPercent: number) => void
}

export function ResizablePanels({
  leftPanel,
  rightPanel,
  defaultLeftWidth = 50,
  minLeftWidth = 320,
  minRightWidth = 320,
  onResize
}: ResizablePanelsProps) {
  const [leftWidthPercent, setLeftWidthPercent] = useState(defaultLeftWidth)
  const [isResizing, setIsResizing] = useState(false)
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false)
  const [isRightCollapsed, setIsRightCollapsed] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragHandleRef = useRef<HTMLDivElement>(null)

  // Collapse thresholds
  const COLLAPSE_THRESHOLD = 15 // percentage
  const EXPAND_THRESHOLD = 5 // pixels from edge

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return

      const containerRect = containerRef.current.getBoundingClientRect()
      const containerWidth = containerRect.width
      const x = e.clientX - containerRect.left
      const newLeftWidthPercent = (x / containerWidth) * 100

      // Check for collapse conditions
      if (newLeftWidthPercent < COLLAPSE_THRESHOLD && !isLeftCollapsed) {
        setIsLeftCollapsed(true)
        setIsRightCollapsed(false)
        setLeftWidthPercent(0)
      } else if (newLeftWidthPercent > 100 - COLLAPSE_THRESHOLD && !isRightCollapsed) {
        setIsRightCollapsed(true)
        setIsLeftCollapsed(false)
        setLeftWidthPercent(100)
      } else if (!isLeftCollapsed && !isRightCollapsed) {
        // Normal resize within bounds
        const minLeftPercent = (minLeftWidth / containerWidth) * 100
        const maxLeftPercent = 100 - (minRightWidth / containerWidth) * 100
        const clampedPercent = Math.max(minLeftPercent, Math.min(maxLeftPercent, newLeftWidthPercent))
        setLeftWidthPercent(clampedPercent)
      }

      onResize?.(leftWidthPercent)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, isLeftCollapsed, isRightCollapsed, minLeftWidth, minRightWidth, onResize, leftWidthPercent])

  // Handle edge detection for expanding collapsed panels
  useEffect(() => {
    const handleMouseMoveForExpand = (e: MouseEvent) => {
      if (!containerRef.current || isResizing) return

      const containerRect = containerRef.current.getBoundingClientRect()
      const x = e.clientX - containerRect.left

      // Check if near left edge when left panel is collapsed
      if (isLeftCollapsed && x < EXPAND_THRESHOLD) {
        document.body.style.cursor = 'col-resize'
      }
      // Check if near right edge when right panel is collapsed
      else if (isRightCollapsed && x > containerRect.width - EXPAND_THRESHOLD) {
        document.body.style.cursor = 'col-resize'
      }
      else if (!isResizing) {
        document.body.style.cursor = ''
      }
    }

    document.addEventListener('mousemove', handleMouseMoveForExpand)
    return () => document.removeEventListener('mousemove', handleMouseMoveForExpand)
  }, [isLeftCollapsed, isRightCollapsed, isResizing])

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)

    // If starting from a collapsed state, expand first
    if (isLeftCollapsed) {
      setIsLeftCollapsed(false)
      setLeftWidthPercent(25)
    } else if (isRightCollapsed) {
      setIsRightCollapsed(false)
      setLeftWidthPercent(75)
    }
  }

  const toggleLeftPanel = () => {
    if (isLeftCollapsed) {
      setIsLeftCollapsed(false)
      setIsRightCollapsed(false)
      setLeftWidthPercent(defaultLeftWidth)
    } else {
      setIsLeftCollapsed(true)
      setIsRightCollapsed(false)
      setLeftWidthPercent(0)
    }
  }

  const toggleRightPanel = () => {
    if (isRightCollapsed) {
      setIsRightCollapsed(false)
      setIsLeftCollapsed(false)
      setLeftWidthPercent(defaultLeftWidth)
    } else {
      setIsRightCollapsed(true)
      setIsLeftCollapsed(false)
      setLeftWidthPercent(100)
    }
  }

  return (
    <div ref={containerRef} className="flex h-full relative">
      {/* Left Panel */}
      <div
        className={cn(
          "h-full overflow-hidden transition-all duration-300",
          isLeftCollapsed && "w-0"
        )}
        style={{ width: isLeftCollapsed ? '0%' : `${leftWidthPercent}%` }}
      >
        {!isLeftCollapsed && leftPanel}
      </div>

      {/* Resize Handle */}
      <div
        ref={dragHandleRef}
        className={cn(
          "relative w-1 bg-border hover:bg-primary/50 transition-colors cursor-col-resize group",
          "before:absolute before:inset-y-0 before:-left-1 before:-right-1 before:content-['']",
          isResizing && "bg-primary"
        )}
        onMouseDown={handleDragStart}
      >
        {/* Center grip indicator */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
          <GripVertical className="w-4 h-4 text-muted-foreground" />
        </div>

        {/* Collapse/Expand buttons */}
        {!isResizing && (
          <>
            <button
              onClick={toggleLeftPanel}
              className={cn(
                "absolute top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-background border border-border",
                "flex items-center justify-center hover:bg-muted transition-colors",
                "opacity-0 group-hover:opacity-100",
                isLeftCollapsed ? "left-0" : "-left-3"
              )}
            >
              {isLeftCollapsed ? (
                <ChevronRight className="w-3 h-3" />
              ) : (
                <ChevronLeft className="w-3 h-3" />
              )}
            </button>

            <button
              onClick={toggleRightPanel}
              className={cn(
                "absolute top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-background border border-border",
                "flex items-center justify-center hover:bg-muted transition-colors",
                "opacity-0 group-hover:opacity-100",
                isRightCollapsed ? "right-0" : "-right-3"
              )}
            >
              {isRightCollapsed ? (
                <ChevronLeft className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </button>
          </>
        )}
      </div>

      {/* Right Panel */}
      <div
        className={cn(
          "h-full overflow-hidden transition-all duration-300",
          isRightCollapsed && "w-0"
        )}
        style={{ width: isRightCollapsed ? '0%' : `${100 - leftWidthPercent}%` }}
      >
        {!isRightCollapsed && rightPanel}
      </div>

      {/* Edge detection areas for expanding collapsed panels */}
      {isLeftCollapsed && (
        <div
          className="absolute left-0 top-0 bottom-0 w-2 cursor-col-resize z-10"
          onMouseDown={handleDragStart}
        />
      )}
      {isRightCollapsed && (
        <div
          className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize z-10"
          onMouseDown={handleDragStart}
        />
      )}
    </div>
  )
}