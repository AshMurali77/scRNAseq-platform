import { useEffect, useRef, useState } from 'react'
import type { ClusterSummary, DEGene, DEResult, TrajectoryEdge, TrajectoryNode, TrajectoryResult } from '../types/pipeline'
import { runDE, runTrajectory } from '../services/api'

const PAGE_SIZE = 10

function PageButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded border border-gray-300 px-3 py-1 text-xs transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}

// Tableau-20 palette (same as UmapPlot)
const TABLEAU20 = [
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
]

function clusterColor(cluster_id: string): string {
  const idx = parseInt(cluster_id, 10)
  if (!isNaN(idx)) return TABLEAU20[idx % TABLEAU20.length]
  // HSL fallback for non-numeric IDs
  const hash = cluster_id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return `hsl(${(hash * 57) % 360}, 60%, 50%)`
}

// ── PAGA Network Canvas ────────────────────────────────────────────────────

interface NetworkProps {
  nodes: TrajectoryNode[]
  edges: TrajectoryEdge[]
}

function PagaNetwork({ nodes, edges }: NetworkProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container || nodes.length === 0) return

    const dpr = window.devicePixelRatio || 1
    const W = container.clientWidth
    const H = container.clientHeight
    canvas.width = W * dpr
    canvas.height = H * dpr
    canvas.style.width = `${W}px`
    canvas.style.height = `${H}px`

    const ctx = canvas.getContext('2d')!
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, W, H)

    const n = nodes.length
    const cx = W / 2
    const cy = H / 2
    const radius = Math.min(W, H) * 0.36

    // Compute circular layout positions
    const positions: Record<string, { x: number; y: number }> = {}
    nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2
      positions[node.cluster_id] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      }
    })

    // Max weight for normalizing edge opacity/thickness
    const maxWeight = edges.reduce((m, e) => Math.max(m, e.weight), 0) || 1

    // Draw edges
    edges.forEach((edge) => {
      const src = positions[edge.source]
      const tgt = positions[edge.target]
      if (!src || !tgt) return
      const alpha = 0.15 + 0.75 * (edge.weight / maxWeight)
      const lineWidth = 1 + 4 * (edge.weight / maxWeight)
      ctx.beginPath()
      ctx.moveTo(src.x, src.y)
      ctx.lineTo(tgt.x, tgt.y)
      ctx.strokeStyle = `rgba(100,100,100,${alpha.toFixed(2)})`
      ctx.lineWidth = lineWidth
      ctx.stroke()
    })

    // Node radius proportional to cluster size
    const maxSize = nodes.reduce((m, nd) => Math.max(m, nd.size), 0) || 1
    const MIN_R = 14
    const MAX_R = 28

    // Draw nodes
    nodes.forEach((node) => {
      const pos = positions[node.cluster_id]
      const nodeR = MIN_R + (MAX_R - MIN_R) * (node.size / maxSize)
      const color = clusterColor(node.cluster_id)

      // Shadow
      ctx.shadowColor = 'rgba(0,0,0,0.15)'
      ctx.shadowBlur = 6

      ctx.beginPath()
      ctx.arc(pos.x, pos.y, nodeR, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()

      ctx.shadowBlur = 0

      // Cluster ID label inside node
      ctx.fillStyle = '#fff'
      ctx.font = `bold ${Math.max(10, nodeR * 0.55)}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.cluster_id, pos.x, pos.y)

      // Cell type label outside node
      const labelX = pos.x + (pos.x - cx) * 0.28
      const labelY = pos.y + (pos.y - cy) * 0.28 + (pos.y >= cy ? nodeR + 12 : -(nodeR + 4))
      const shortLabel = node.label.length > 20 ? node.label.slice(0, 18) + '…' : node.label
      ctx.fillStyle = '#374151'
      ctx.font = `10px sans-serif`
      ctx.fillText(shortLabel, labelX, labelY)
    })
  }, [nodes, edges])

  return (
    <div ref={containerRef} className="w-full" style={{ height: '380px' }}>
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  )
}

// ── DE results table ───────────────────────────────────────────────────────

function GeneRow({ gene }: { gene: DEGene }) {
  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50">
      <td className="px-3 py-1.5 font-mono text-xs text-gray-900">{gene.gene}</td>
      <td className={`px-3 py-1.5 text-xs font-medium ${gene.log_fold_change > 0 ? 'text-blue-700' : 'text-orange-600'}`}>
        {gene.log_fold_change > 0 ? '+' : ''}{gene.log_fold_change.toFixed(2)}
      </td>
      <td className="px-3 py-1.5 text-xs text-gray-600">{gene.score.toFixed(2)}</td>
      <td className="px-3 py-1.5 text-xs text-gray-600">{gene.pval_adj < 0.001 ? '<0.001' : gene.pval_adj.toFixed(3)}</td>
    </tr>
  )
}

const DE_HEADER = (
  <tr className="bg-gray-50">
    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Gene</th>
    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">log2FC</th>
    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Score</th>
    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">adj. p</th>
  </tr>
)

function GeneTable({ genes, label, accent }: { genes: DEGene[]; label: string; accent: string }) {
  const [page, setPage] = useState(0)
  const totalPages = Math.ceil(genes.length / PAGE_SIZE)
  const visible = genes.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  if (genes.length === 0) return null
  return (
    <div>
      <p className={`text-xs font-medium mb-1 ${accent}`}>{label} ({genes.length} genes)</p>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="w-full">
          <thead>{DE_HEADER}</thead>
          <tbody>{visible.map(g => <GeneRow key={g.gene} gene={g} />)}</tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="mt-2 flex items-center justify-between text-xs text-gray-600">
          <span>Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, genes.length)} of {genes.length}</span>
          <div className="flex gap-2">
            <PageButton onClick={() => setPage(p => p - 1)} disabled={page === 0}>Previous</PageButton>
            <PageButton onClick={() => setPage(p => p + 1)} disabled={page === totalPages - 1}>Next</PageButton>
          </div>
        </div>
      )}
    </div>
  )
}

function DETable({ result }: { result: DEResult }) {
  const { group1, group2, genes } = result
  const upGenes = genes.filter(g => g.log_fold_change > 0)
  const downGenes = genes.filter(g => g.log_fold_change < 0)

  return (
    <div className="mt-4 space-y-4">
      <GeneTable genes={upGenes} label={`Upregulated in cluster ${group1}`} accent="text-blue-700" />
      <GeneTable genes={downGenes} label={`Upregulated in cluster ${group2}`} accent="text-orange-600" />
    </div>
  )
}

// ── Main panel ─────────────────────────────────────────────────────────────

interface Props {
  sessionId: string
  clusterSummaries: ClusterSummary[]
}

export default function DownstreamPanel({ sessionId, clusterSummaries }: Props) {
  // Differential expression state
  const [deGroup1, setDeGroup1] = useState(clusterSummaries[0]?.cluster_id ?? '')
  const [deGroup2, setDeGroup2] = useState(clusterSummaries[1]?.cluster_id ?? '')
  const [deLoading, setDeLoading] = useState(false)
  const [deError, setDeError] = useState<string | null>(null)
  const [deResult, setDeResult] = useState<DEResult | null>(null)

  // Trajectory state
  const [trajLoading, setTrajLoading] = useState(false)
  const [trajError, setTrajError] = useState<string | null>(null)
  const [trajResult, setTrajResult] = useState<TrajectoryResult | null>(null)
  const [trajPage, setTrajPage] = useState(0)

  async function handleRunDE() {
    if (deGroup1 === deGroup2 || deLoading) return
    setDeLoading(true)
    setDeError(null)
    setDeResult(null)
    try {
      const result = await runDE({ session_id: sessionId, group1: deGroup1, group2: deGroup2 })
      setDeResult(result)
    } catch (err) {
      setDeError(err instanceof Error ? err.message : 'DE analysis failed')
    } finally {
      setDeLoading(false)
    }
  }

  async function handleRunTrajectory() {
    if (trajLoading) return
    setTrajLoading(true)
    setTrajError(null)
    setTrajResult(null)
    try {
      const result = await runTrajectory({ session_id: sessionId })
      setTrajResult(result)
      setTrajPage(0)
    } catch (err) {
      setTrajError(err instanceof Error ? err.message : 'Trajectory analysis failed')
    } finally {
      setTrajLoading(false)
    }
  }

  const selectClass = "rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none bg-white"

  function ClusterOption({ id }: { id: string }) {
    const label = clusterSummaries.find(s => s.cluster_id === id)?.celltypist_label ?? ''
    return <option value={id}>Cluster {id}{label ? ` — ${label}` : ''}</option>
  }

  return (
    <div className="space-y-6">
      {/* ── Differential Expression ────────────────────────────── */}
      <div>
        <h3 className="text-sm font-medium text-gray-800 mb-1">Differential Expression</h3>
        <p className="text-xs text-gray-400 mb-3">
          Compare gene expression between any two clusters using a Wilcoxon rank-sum test across all genes.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={deGroup1}
            onChange={e => { setDeGroup1(e.target.value); setDeResult(null) }}
            className={selectClass}
            disabled={deLoading}
          >
            {clusterSummaries.map(s => <ClusterOption key={s.cluster_id} id={s.cluster_id} />)}
          </select>
          <span className="text-xs text-gray-400 select-none">vs</span>
          <select
            value={deGroup2}
            onChange={e => { setDeGroup2(e.target.value); setDeResult(null) }}
            className={selectClass}
            disabled={deLoading}
          >
            {clusterSummaries.map(s => <ClusterOption key={s.cluster_id} id={s.cluster_id} />)}
          </select>
          <button
            onClick={handleRunDE}
            disabled={deLoading || deGroup1 === deGroup2}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {deLoading ? 'Running…' : 'Run DE'}
          </button>
        </div>
        {deGroup1 === deGroup2 && (
          <p className="mt-1.5 text-xs text-amber-600">Select two different clusters to compare.</p>
        )}
        {deError && <p className="mt-2 text-xs text-red-500">{deError}</p>}
        {deResult && <DETable result={deResult} />}
      </div>

      <hr className="border-gray-100" />

      {/* ── Trajectory Inference ───────────────────────────────── */}
      <div>
        <h3 className="text-sm font-medium text-gray-800 mb-1">Trajectory Inference (PAGA)</h3>
        <p className="text-xs text-gray-400 mb-3">
          Partition-based graph abstraction shows which clusters are transcriptionally connected.
          Edge thickness reflects connectivity strength.
        </p>
        <button
          onClick={handleRunTrajectory}
          disabled={trajLoading}
          className="rounded bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {trajLoading ? 'Running…' : 'Run PAGA'}
        </button>
        {trajError && <p className="mt-2 text-xs text-red-500">{trajError}</p>}
        {trajResult && (
          <div className="mt-4">
            <PagaNetwork nodes={trajResult.nodes} edges={trajResult.edges} />
            {trajResult.edges.length === 0 && (
              <p className="text-xs text-gray-400 text-center mt-2">
                No cluster connections met the minimum threshold.
              </p>
            )}
            {(() => {
              const trajTotalPages = Math.ceil(trajResult.edges.length / PAGE_SIZE)
              const visibleEdges = trajResult.edges.slice(trajPage * PAGE_SIZE, (trajPage + 1) * PAGE_SIZE)
              return (
                <div className="mt-3">
                  <div className="overflow-x-auto rounded border border-gray-200">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Cluster A</th>
                          <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Cluster B</th>
                          <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Connectivity</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleEdges.map((e, i) => {
                          const srcLabel = trajResult.nodes.find(n => n.cluster_id === e.source)?.label ?? ''
                          const tgtLabel = trajResult.nodes.find(n => n.cluster_id === e.target)?.label ?? ''
                          return (
                            <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                              <td className="px-3 py-1.5 text-xs text-gray-800">
                                <span className="font-medium">{e.source}</span>
                                {srcLabel && <span className="text-gray-400 ml-1">({srcLabel})</span>}
                              </td>
                              <td className="px-3 py-1.5 text-xs text-gray-800">
                                <span className="font-medium">{e.target}</span>
                                {tgtLabel && <span className="text-gray-400 ml-1">({tgtLabel})</span>}
                              </td>
                              <td className="px-3 py-1.5 text-xs text-gray-600">
                                <div className="flex items-center gap-2">
                                  <div
                                    className="h-1.5 rounded-full bg-indigo-400"
                                    style={{ width: `${Math.round(e.weight * 80)}px` }}
                                  />
                                  {e.weight.toFixed(3)}
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  {trajTotalPages > 1 && (
                    <div className="mt-2 flex items-center justify-between text-xs text-gray-600">
                      <span>Showing {trajPage * PAGE_SIZE + 1}–{Math.min((trajPage + 1) * PAGE_SIZE, trajResult.edges.length)} of {trajResult.edges.length} connections</span>
                      <div className="flex gap-2">
                        <PageButton onClick={() => setTrajPage(p => p - 1)} disabled={trajPage === 0}>Previous</PageButton>
                        <PageButton onClick={() => setTrajPage(p => p + 1)} disabled={trajPage === trajTotalPages - 1}>Next</PageButton>
                      </div>
                    </div>
                  )}
                </div>
              )
            })()}
          </div>
        )}
      </div>
    </div>
  )
}
