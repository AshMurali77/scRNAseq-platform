import { useMemo, useState } from 'react'
import type { CellMetadata, ClusterValidation, ModelSelection, PipelineResult } from '../types/pipeline'
import UmapPlot from './UmapPlot'

const PAGE_SIZE = 50

interface Props {
  result: PipelineResult
  modelSelection: ModelSelection
}

// ------------------------------------------------------------------ helpers

const STATUS_CONFIG: Record<
  ClusterValidation['status'],
  { label: string; badge: string; row: string; dot: string }
> = {
  confirmed:   { label: 'Confirmed',   badge: 'bg-green-100 text-green-800',   row: '',                 dot: 'bg-green-500' },
  uncertain:   { label: 'Uncertain',   badge: 'bg-amber-100 text-amber-800',   row: 'bg-amber-50/40',   dot: 'bg-amber-400' },
  conflicting: { label: 'Conflicting', badge: 'bg-red-100 text-red-800',       row: 'bg-red-50/40',     dot: 'bg-red-500'   },
}

// ------------------------------------------------------------------ main

export default function ResultsTable({ result, modelSelection }: Props) {
  const [page, setPage] = useState(0)
  const [filterCluster, setFilterCluster] = useState('')
  const [filterCellType, setFilterCellType] = useState('')
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null)
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null)

  const confidencePct = Math.round(modelSelection.confidence * 100)
  const confidenceColor =
    modelSelection.confidence >= 0.85
      ? 'text-green-700'
      : modelSelection.confidence >= 0.7
        ? 'text-amber-700'
        : 'text-red-700'

  // Cluster id → majority-vote annotation label
  const clusterLabelMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const cs of result.cluster_summaries) map[cs.cluster_id] = cs.celltypist_label
    return map
  }, [result.cluster_summaries])

  // Cluster id → validation object
  const validationMap = useMemo(() => {
    const map: Record<string, ClusterValidation> = {}
    for (const v of result.cluster_validations) map[v.cluster_id] = v
    return map
  }, [result.cluster_validations])

  // Unique values for filter dropdowns
  const clusterOptions = useMemo(
    () => [...new Set(result.cells.map((c) => c.leiden_cluster))].sort((a, b) => +a - +b),
    [result.cells],
  )
  const cellTypeOptions = useMemo(
    () => [...new Set(result.cells.map((c) => c.celltypist_cell_type))].sort(),
    [result.cells],
  )

  const filtered = useMemo(() => {
    return result.cells.filter((c) => {
      if (filterCluster && c.leiden_cluster !== filterCluster) return false
      if (filterCellType && c.celltypist_cell_type !== filterCellType) return false
      return true
    })
  }, [result.cells, filterCluster, filterCellType])

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value)
      setPage(0)
    }
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const visible: CellMetadata[] = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const hasValidation = result.cluster_validations.length > 0
  const dm = result.dataset_metadata

  return (
    <div className="flex flex-col gap-6">

      {/* Dataset metadata */}
      {dm && (
        <div className={`rounded-lg border px-4 py-3 text-xs flex flex-col gap-1 ${
          dm.organism_mismatch
            ? 'border-red-200 bg-red-50'
            : 'border-gray-200 bg-gray-50'
        }`}>
          <p className={`font-medium ${dm.organism_mismatch ? 'text-red-700' : 'text-gray-600'}`}>
            {dm.organism_mismatch ? 'Dataset metadata mismatch detected' : 'Dataset metadata'}
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-0.5">
            <span className="text-gray-600">
              Organism in file:{' '}
              {dm.organism_in_file
                ? <span className={`font-medium ${dm.organism_mismatch ? 'text-red-700' : 'text-gray-800'}`}>{dm.organism_in_file}</span>
                : <span className="italic text-gray-400">not found</span>
              }
            </span>
            <span className="text-gray-600">
              Tissue in file:{' '}
              {dm.tissue_in_file
                ? <span className="font-medium text-gray-800">{dm.tissue_in_file}</span>
                : <span className="italic text-gray-400">not found</span>
              }
            </span>
          </div>
          {dm.organism_mismatch && (
            <p className="text-red-600 italic">
              This differs from your selection. Results may be unreliable.
            </p>
          )}
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Cells (input)" value={result.n_cells_input} />
        <Stat label="Cells (post-QC)" value={result.n_cells_after_qc} />
        <Stat label="HVGs" value={result.n_hvgs} />
        <Stat label="Clusters" value={result.n_clusters} />
      </div>

      {/* Model info */}
      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-blue-700">
            Model: {modelSelection.display_name}
          </p>
          <span className={`text-xs font-medium ${confidenceColor}`}>
            {confidencePct}% confidence
          </span>
        </div>
        <p className="text-xs text-blue-600">{modelSelection.description}</p>
        <p className="text-xs text-blue-500 italic">{modelSelection.reasoning}</p>
      </div>

      {/* Cluster annotations + validation */}
      <div>
        <h3 className="mb-2 text-xs font-medium text-gray-700">
          Cluster annotations
          {hasValidation && (
            <span className="ml-2 font-normal text-gray-400">— click a row to see expert review</span>
          )}
        </h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <Th>Cluster</Th>
                <Th>Cell type (majority vote)</Th>
                {hasValidation && <Th>Expert review</Th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {result.cluster_summaries.map((cs) => {
                const v = validationMap[cs.cluster_id]
                const cfg = v ? STATUS_CONFIG[v.status] : null
                const isExpanded = expandedCluster === cs.cluster_id

                return (
                  <>
                    <tr
                      key={cs.cluster_id}
                      onClick={() => v && setExpandedCluster(isExpanded ? null : cs.cluster_id)}
                      className={`transition-colors ${cfg?.row ?? ''} ${v ? 'cursor-pointer hover:brightness-95' : ''}`}
                    >
                      <td className="px-4 py-2 font-medium">{cs.cluster_id}</td>
                      <td className="px-4 py-2">{cs.celltypist_label}</td>
                      {hasValidation && (
                        <td className="px-4 py-2">
                          {cfg ? (
                            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${cfg.badge}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                              {cfg.label}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                    {v && isExpanded && (
                      <tr key={`${cs.cluster_id}-detail`} className={cfg?.row ?? ''}>
                        <td colSpan={hasValidation ? 3 : 2} className="px-4 pb-3 pt-0">
                          <div className="rounded-md border border-gray-100 bg-white px-3 py-2 text-xs text-gray-700 space-y-1">
                            <p>{v.explanation}</p>
                            {v.top_marker_genes.length > 0 && (
                              <p className="text-gray-400">
                                Markers used:{' '}
                                <span className="font-mono text-gray-600">
                                  {v.top_marker_genes.join(', ')}
                                </span>
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* UMAP plots */}
      {result.cells.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-medium text-gray-700">
            UMAP projections
            {selectedCellId && (
              <span className="ml-2 font-normal text-amber-600">
                — cell <span className="font-mono">{selectedCellId}</span> highlighted
              </span>
            )}
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UmapPlot
              cells={result.cells}
              colorKey="leiden_cluster"
              title="Leiden clusters"
              highlightedCellId={selectedCellId}
            />
            <UmapPlot
              cells={result.cells}
              colorKey="celltypist_cell_type"
              title="Cell type annotations"
              highlightedCellId={selectedCellId}
            />
          </div>
        </div>
      )}

      {/* Per-cell table */}
      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-xs font-medium text-gray-700">Per-cell results</h3>
          <div className="flex items-center gap-2">
            <FilterSelect
              value={filterCluster}
              onChange={handleFilterChange(setFilterCluster)}
              placeholder="All clusters"
              options={clusterOptions}
              label={(v) => `Cluster ${v}`}
            />
            <FilterSelect
              value={filterCellType}
              onChange={handleFilterChange(setFilterCellType)}
              placeholder="All cell types"
              options={cellTypeOptions}
              label={(v) => v}
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50 uppercase tracking-wide text-gray-500">
              <tr>
                <Th>Cell ID</Th>
                <Th>Cluster</Th>
                <Th>Annotation</Th>
                <Th>Cell Type</Th>
                <Th>UMAP X</Th>
                <Th>UMAP Y</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {visible.map((cell) => {
                const isSelected = cell.cell_id === selectedCellId
                return (
                  <tr
                    key={cell.cell_id}
                    onClick={() => setSelectedCellId(isSelected ? null : cell.cell_id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected ? 'bg-amber-50 hover:bg-amber-100' : 'hover:bg-gray-50'
                    }`}
                  >
                    <td className="px-3 py-1 font-mono text-gray-500 truncate max-w-[160px]" title={cell.cell_id}>
                      {cell.cell_id}
                    </td>
                    <td className="px-3 py-1 tabular-nums">{cell.leiden_cluster}</td>
                    <td className="px-3 py-1 text-gray-500">{clusterLabelMap[cell.leiden_cluster] ?? '—'}</td>
                    <td className="px-3 py-1">{cell.celltypist_cell_type}</td>
                    <td className="px-3 py-1 tabular-nums">{cell.umap_x.toFixed(3)}</td>
                    <td className="px-3 py-1 tabular-nums">{cell.umap_y.toFixed(3)}</td>
                  </tr>
                )
              })}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-center text-gray-400">
                    No cells match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
            <span>
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of{' '}
              {filtered.length}
              {filtered.length !== result.cells.length ? ` (filtered from ${result.cells.length})` : ''} cells
            </span>
            <div className="flex gap-2">
              <PageButton onClick={() => setPage((p) => p - 1)} disabled={page === 0}>
                Previous
              </PageButton>
              <PageButton onClick={() => setPage((p) => p + 1)} disabled={page === totalPages - 1}>
                Next
              </PageButton>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ sub-components

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value.toLocaleString()}</p>
    </div>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left">{children}</th>
}

function FilterSelect({
  value,
  onChange,
  placeholder,
  options,
  label,
}: {
  value: string
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void
  placeholder: string
  options: string[]
  label: (v: string) => string
}) {
  return (
    <select
      value={value}
      onChange={onChange}
      className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o} value={o}>{label(o)}</option>
      ))}
    </select>
  )
}

function PageButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled: boolean
}) {
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
