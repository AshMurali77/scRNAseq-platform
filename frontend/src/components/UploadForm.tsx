import { useRef, useState } from 'react'

// Used when rule-based mode is active — must stay in sync with
// _RULE_BASED_LOOKUP keys in app/pipeline/annotate.py.
const TISSUE_OPTIONS: Record<string, string[]> = {
  human: ['blood', 'pbmc', 'bone marrow', 'spleen', 'lymph node', 'thymus', 'lung', 'brain', 'hippocampus', 'colon', 'colorectal', 'heart'],
  mouse: ['lung', 'brain', 'hippocampus', 'cortex'],
}

interface Props {
  onSubmit: (file: File, tissue: string, organism: string, useLlm: boolean) => void
  disabled: boolean
}

export default function UploadForm({ onSubmit, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [organism, setOrganism] = useState<string>('')
  const [tissue, setTissue] = useState<string>('')
  const [useLlm, setUseLlm] = useState(true)

  function handleOrganismChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setOrganism(e.target.value)
    setTissue('')
  }

  function handleLlmToggle(next: boolean) {
    setUseLlm(next)
    setTissue('')  // reset tissue when switching modes
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedFile && tissue && organism) onSubmit(selectedFile, tissue, organism, useLlm)
  }

  const canSubmit = !!selectedFile && !!tissue && !!organism && !disabled

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {/* File drop zone */}
      <div
        className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 px-6 py-10 transition hover:border-blue-400 hover:bg-blue-50"
        onClick={() => inputRef.current?.click()}
      >
        <svg className="mb-2 h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm text-gray-600">
          {selectedFile ? selectedFile.name : 'Click to select a .h5ad file'}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".h5ad"
          className="hidden"
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {/* Model selection mode toggle */}
      <div className="flex items-center gap-3 rounded-lg border border-gray-200 px-4 py-3">
        <span className="text-xs font-medium text-gray-600">Model selection:</span>
        <div className="flex rounded-md border border-gray-300 overflow-hidden text-xs">
          <button
            type="button"
            onClick={() => handleLlmToggle(false)}
            className={`px-3 py-1.5 transition ${
              !useLlm
                ? 'bg-gray-800 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            Rule-based
          </button>
          <button
            type="button"
            onClick={() => handleLlmToggle(true)}
            className={`px-3 py-1.5 transition border-l border-gray-300 ${
              useLlm
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            LLM
          </button>
        </div>
        <span className="text-xs text-gray-400">
          {useLlm ? 'AI-powered — accepts any tissue description' : 'Fast deterministic lookup'}
        </span>
      </div>

      {/* Organism + tissue */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-600">Organism</label>
          <select
            value={organism}
            onChange={handleOrganismChange}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-400 focus:outline-none"
          >
            <option value="">Select organism…</option>
            {Object.keys(TISSUE_OPTIONS).map((o) => (
              <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-600">Tissue</label>
          {useLlm ? (
            <input
              type="text"
              value={tissue}
              onChange={(e) => setTissue(e.target.value)}
              disabled={!organism}
              placeholder="e.g. kidney cortex, dorsal root ganglion…"
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
            />
          ) : (
            <select
              value={tissue}
              onChange={(e) => setTissue(e.target.value)}
              disabled={!organism}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-400 focus:outline-none disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
            >
              <option value="">Select tissue…</option>
              {(TISSUE_OPTIONS[organism] ?? []).map((t) => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Run pipeline
      </button>
    </form>
  )
}
