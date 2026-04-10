import { useState } from 'react'
import type { CellMetadata, PipelineResult } from '../types/pipeline'

const PAGE_SIZE = 50

interface Props {
  result: PipelineResult
}

export default function ResultsTable({ result }: Props) {
  const [page, setPage] = useState(0)

  const totalPages = Math.ceil(result.cells.length / PAGE_SIZE)
  const visible: CellMetadata[] = result.cells.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Cells (input)" value={result.n_cells_input} />
        <Stat label="Cells (post-QC)" value={result.n_cells_after_qc} />
        <Stat label="HVGs" value={result.n_hvgs} />
        <Stat label="Clusters" value={result.n_clusters} />
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <Th>Cell ID</Th>
              <Th>Cluster</Th>
              <Th>Cell Type</Th>
              <Th>UMAP X</Th>
              <Th>UMAP Y</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {visible.map((cell) => (
              <tr key={cell.cell_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs text-gray-600">{cell.cell_id}</td>
                <td className="px-4 py-2">{cell.leiden_cluster}</td>
                <td className="px-4 py-2">{cell.celltypist_cell_type}</td>
                <td className="px-4 py-2 tabular-nums">{cell.umap_x.toFixed(3)}</td>
                <td className="px-4 py-2 tabular-nums">{cell.umap_y.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, result.cells.length)} of {result.cells.length} cells
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
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value.toLocaleString()}</p>
    </div>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 text-left">{children}</th>
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
