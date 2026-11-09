"use client"

import { useRef, useEffect, useCallback } from "react"
import type { MuteRegion, AudibleSegment } from "@/lib/api"

interface WaveformViewerProps {
  amplitudes: number[]
  duration: number
  currentTime: number
  muteRegions: MuteRegion[]
  audibleSegments: AudibleSegment[]
  zoomLevel: number
  onSeek: (time: number) => void
  onRegionCreate: (start: number, end: number) => void
  isShiftHeld: boolean
  highlightedTimeRange?: { start: number; end: number } | null
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return "0:00"
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

const RULER_HEIGHT = 20
const NICE_INTERVALS = [1, 2, 5, 10, 15, 30, 60]

function getTickInterval(duration: number, canvasWidth: number): { major: number; minor: number } {
  const targetPx = 120
  const secondsPerPixel = duration / canvasWidth
  const targetInterval = secondsPerPixel * targetPx

  let major = NICE_INTERVALS[NICE_INTERVALS.length - 1]
  for (const interval of NICE_INTERVALS) {
    if (interval >= targetInterval) {
      major = interval
      break
    }
  }

  // Minor ticks: subdivide major interval
  let minor = major / 4
  if (major >= 60) minor = 15
  else if (major >= 30) minor = 10
  else if (major >= 10) minor = 5
  else if (major >= 5) minor = 1
  else if (major >= 2) minor = 0.5
  else minor = 0.25

  return { major, minor }
}

export function WaveformViewer({
  amplitudes,
  duration,
  currentTime,
  muteRegions,
  audibleSegments,
  zoomLevel,
  onSeek,
  onRegionCreate,
  isShiftHeld,
  highlightedTimeRange,
}: WaveformViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)
  const dragStartTimeRef = useRef(0)
  const dragStartXRef = useRef(0)

  // Draw waveform
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !amplitudes.length) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height
    const waveformHeight = height - RULER_HEIGHT
    const centerY = waveformHeight / 2

    // Clear with dark background
    ctx.fillStyle = "#0d1117"
    ctx.fillRect(0, 0, width, height)

    // Draw center line
    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)"
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(0, centerY)
    ctx.lineTo(width, centerY)
    ctx.stroke()
    ctx.setLineDash([])

    // Draw waveform bars
    const barWidth = width / amplitudes.length

    amplitudes.forEach((amp, i) => {
      const x = i * barWidth
      const barHeight = Math.max(2, amp * waveformHeight * 0.9)
      const y = centerY - barHeight / 2
      const time = (i / amplitudes.length) * duration

      // Check if in mute region
      const inMuteRegion = muteRegions.some(
        (r) => time >= r.start_seconds && time <= r.end_seconds
      )

      // Check if in audible segment (backing vocals detected)
      const inAudibleSegment = audibleSegments.some(
        (s) => time >= s.start_seconds && time <= s.end_seconds
      )

      if (inMuteRegion) {
        // Muted regions are very dim
        ctx.fillStyle = "rgba(13, 17, 23, 0.8)"
      } else if (inAudibleSegment) {
        // Pink for detected backing vocals
        ctx.fillStyle = "#ec4899"
      } else {
        // Blue for regular audio
        ctx.fillStyle = "#60a5fa"
      }

      ctx.fillRect(x, y, Math.max(1, barWidth - 0.5), barHeight)
    })

    // Draw highlight overlay
    if (highlightedTimeRange && duration > 0) {
      const startX = (highlightedTimeRange.start / duration) * width
      const endX = (highlightedTimeRange.end / duration) * width

      // Semi-transparent white overlay on waveform area
      ctx.fillStyle = "rgba(255, 255, 255, 0.12)"
      ctx.fillRect(startX, 0, endX - startX, waveformHeight)

      // Vertical edge lines
      ctx.strokeStyle = "rgba(255, 255, 255, 0.5)"
      ctx.lineWidth = 1
      ctx.setLineDash([])
      ctx.beginPath()
      ctx.moveTo(startX, 0)
      ctx.lineTo(startX, waveformHeight)
      ctx.moveTo(endX, 0)
      ctx.lineTo(endX, waveformHeight)
      ctx.stroke()

      // Pink tint in ruler area for highlighted range
      ctx.fillStyle = "rgba(236, 72, 153, 0.3)"
      ctx.fillRect(startX, waveformHeight, endX - startX, RULER_HEIGHT)
    }

    // Draw time ruler
    const rulerY = waveformHeight
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)"
    ctx.fillRect(0, rulerY, width, RULER_HEIGHT)

    // Ruler top border
    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)"
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, rulerY)
    ctx.lineTo(width, rulerY)
    ctx.stroke()

    if (duration > 0) {
      const { major, minor } = getTickInterval(duration, width)

      // Draw minor ticks
      ctx.strokeStyle = "rgba(255, 255, 255, 0.15)"
      ctx.lineWidth = 1
      for (let t = 0; t <= duration; t += minor) {
        const x = (t / duration) * width
        ctx.beginPath()
        ctx.moveTo(x, rulerY)
        ctx.lineTo(x, rulerY + 4)
        ctx.stroke()
      }

      // Draw major ticks with labels
      ctx.strokeStyle = "rgba(255, 255, 255, 0.4)"
      ctx.fillStyle = "rgba(255, 255, 255, 0.6)"
      ctx.font = "10px monospace"
      ctx.textBaseline = "bottom"
      for (let t = 0; t <= duration; t += major) {
        const x = (t / duration) * width
        ctx.beginPath()
        ctx.moveTo(x, rulerY)
        ctx.lineTo(x, rulerY + 8)
        ctx.stroke()

        const label = formatTime(t)
        const textWidth = ctx.measureText(label).width
        // Avoid drawing label past right edge
        const labelX = Math.min(x + 3, width - textWidth - 2)
        ctx.fillText(label, Math.max(2, labelX), rulerY + RULER_HEIGHT - 2)
      }
    }
  }, [amplitudes, duration, muteRegions, audibleSegments, highlightedTimeRange])

  // Resize canvas
  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    canvas.width = container.clientWidth * zoomLevel
    canvas.height = container.clientHeight
  }, [zoomLevel])

  // Handle resize and redraw
  useEffect(() => {
    resizeCanvas()
    drawWaveform()
  }, [resizeCanvas, drawWaveform, zoomLevel])

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      resizeCanvas()
      drawWaveform()
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [resizeCanvas, drawWaveform])

  // Auto-scroll to show highlighted range when zoomed
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas || !highlightedTimeRange || !duration || zoomLevel <= 1) return

    const startFraction = highlightedTimeRange.start / duration
    const endFraction = highlightedTimeRange.end / duration
    const centerFraction = (startFraction + endFraction) / 2
    const targetScrollLeft = centerFraction * canvas.width - container.clientWidth / 2

    container.scrollTo({
      left: Math.max(0, targetScrollLeft),
      behavior: "smooth",
    })
  }, [highlightedTimeRange, duration, zoomLevel])

  // Calculate playhead position
  const playheadPosition =
    duration > 0 && canvasRef.current
      ? (currentTime / duration) * canvasRef.current.width
      : 0

  // Handle mouse events for seeking and region selection
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = (x / rect.width) * duration

    if (!Number.isFinite(duration) || duration <= 0) return

    if (e.shiftKey || isShiftHeld) {
      // Start region selection
      isDraggingRef.current = true
      dragStartTimeRef.current = time
      dragStartXRef.current = x
    } else {
      // Seek
      onSeek(time)
    }
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return
    // Selection overlay is handled by parent
  }

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const time = (x / rect.width) * duration

    if (!Number.isFinite(duration) || duration <= 0) {
      isDraggingRef.current = false
      return
    }

    const start = Math.min(dragStartTimeRef.current, time)
    const end = Math.max(dragStartTimeRef.current, time)

    if (end - start > 0.5) {
      onRegionCreate(start, end)
    }

    isDraggingRef.current = false
  }

  const handleMouseLeave = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDraggingRef.current) {
      handleMouseUp(e)
    }
  }

  return (
    <div
      ref={containerRef}
      className="relative flex-1 overflow-x-auto overflow-y-hidden bg-[#0d1117] min-h-[120px]"
    >
      <div
        className="relative h-full"
        style={{ width: `${zoomLevel * 100}%`, minWidth: "100%" }}
      >
        <canvas
          ref={canvasRef}
          className="block h-full cursor-pointer"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        />
        {/* Playhead */}
        <div
          className="absolute top-0 w-0.5 h-full bg-primary pointer-events-none z-10"
          style={{
            left: `${playheadPosition}px`,
            boxShadow: "0 0 8px var(--primary)",
          }}
        >
          <div className="absolute -top-0 -left-1 w-2.5 h-2.5 bg-primary rounded-full" />
        </div>
      </div>
    </div>
  )
}
