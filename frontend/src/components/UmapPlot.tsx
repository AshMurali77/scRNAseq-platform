import { useEffect, useMemo, useRef } from 'react'
import type { CellMetadata } from '../types/pipeline'

// Tableau-20 palette, then HSL fallback for many cell types
const PALETTE = [
  '#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B2',
  '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD',
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]

function paletteColor(i: number, total: number): string {
  if (i < PALETTE.length) return PALETTE[i]
  return `hsl(${Math.round((i / total) * 360)}, 62%, 50%)`
}

interface Props {
  cells: CellMetadata[]
  colorKey: 'leiden_cluster' | 'celltypist_cell_type'
  title: string
  highlightedCellId: string | null
}

export default function UmapPlot({ cells, colorKey, title, highlightedCellId }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const colorMap = useMemo(() => {
    const keys = [...new Set(cells.map((c) => c[colorKey]))].sort()
    const map: Record<string, string> = {}
    keys.forEach((k, i) => { map[k] = paletteColor(i, keys.length) })
    return map
  }, [cells, colorKey])

  // Pre-compute cell lookup and coordinate bounds once
  const { cellById, xMin, xMax, yMin, yMax } = useMemo(() => {
    const cellById: Record<string, CellMetadata> = {}
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity
    for (const cell of cells) {
      cellById[cell.cell_id] = cell
      if (cell.umap_x < xMin) xMin = cell.umap_x
      if (cell.umap_x > xMax) xMax = cell.umap_x
      if (cell.umap_y < yMin) yMin = cell.umap_y
      if (cell.umap_y > yMax) yMax = cell.umap_y
    }
    // Add 5% margin so edge points aren't clipped
    const xPad = (xMax - xMin) * 0.05
    const yPad = (yMax - yMin) * 0.05
    return { cellById, xMin: xMin - xPad, xMax: xMax + xPad, yMin: yMin - yPad, yMax: yMax + yPad }
  }, [cells])

  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    function draw() {
      if (!canvas || !container) return
      const dpr = window.devicePixelRatio || 1
      const w = container.clientWidth
      const h = container.clientHeight
      if (w === 0 || h === 0) return

      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`

      const ctx = canvas.getContext('2d')!
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, w, h)

      const xRange = xMax - xMin || 1
      const yRange = yMax - yMin || 1

      function toPixel(x: number, y: number): [number, number] {
        return [
          ((x - xMin) / xRange) * w,
          (1 - (y - yMin) / yRange) * h,
        ]
      }

      // All non-highlighted cells
      for (const cell of cells) {
        if (cell.cell_id === highlightedCellId) continue
        const [px, py] = toPixel(cell.umap_x, cell.umap_y)
        ctx.beginPath()
        ctx.arc(px, py, 2, 0, Math.PI * 2)
        ctx.fillStyle = colorMap[cell[colorKey]] ?? '#aaa'
        ctx.globalAlpha = 0.65
        ctx.fill()
      }
      ctx.globalAlpha = 1

      // Highlighted cell drawn last so it sits on top
      if (highlightedCellId) {
        const cell = cellById[highlightedCellId]
        if (cell) {
          const [px, py] = toPixel(cell.umap_x, cell.umap_y)
          // White halo
          ctx.beginPath()
          ctx.arc(px, py, 8, 0, Math.PI * 2)
          ctx.fillStyle = '#fff'
          ctx.fill()
          // Coloured fill
          ctx.beginPath()
          ctx.arc(px, py, 6, 0, Math.PI * 2)
          ctx.fillStyle = '#f59e0b' // amber-400
          ctx.fill()
          // Dark border
          ctx.beginPath()
          ctx.arc(px, py, 6, 0, Math.PI * 2)
          ctx.strokeStyle = '#78350f'
          ctx.lineWidth = 1.5
          ctx.stroke()
        }
      }
    }

    draw()

    const observer = new ResizeObserver(draw)
    observer.observe(container)
    return () => observer.disconnect()
  }, [cells, colorKey, colorMap, cellById, xMin, xMax, yMin, yMax, highlightedCellId])

  const legendEntries = useMemo(() => Object.entries(colorMap), [colorMap])

  return (
    <div className="flex flex-col rounded-lg border border-gray-200 bg-white overflow-hidden">
      <p className="px-3 py-1.5 text-xs font-medium text-gray-600 border-b border-gray-100 shrink-0">
        {title}
      </p>
      <div ref={containerRef} className="relative shrink-0" style={{ height: '260px' }}>
        <canvas ref={canvasRef} className="absolute inset-0" />
      </div>
      <div className="px-3 py-2 border-t border-gray-100 flex flex-wrap gap-x-3 gap-y-1 overflow-y-auto max-h-20 shrink-0">
        {legendEntries.map(([key, color]) => (
          <span key={key} className="flex items-center gap-1 text-xs text-gray-600 leading-none">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
            {key}
          </span>
        ))}
      </div>
    </div>
  )
}
