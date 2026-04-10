import { useState } from 'react'
import type { PipelineResult } from './types/pipeline'
import { analyze } from './services/api'
import UploadForm from './components/UploadForm'
import ResultsTable from './components/ResultsTable'
import StatusBanner from './components/StatusBanner'

type AppState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; result: PipelineResult }

export default function App() {
  const [state, setState] = useState<AppState>({ status: 'idle' })

  async function handleSubmit(file: File, tissue: string, organism: string) {
    setState({ status: 'loading' })
    try {
      const result = await analyze(file, tissue, organism)
      setState({ status: 'done', result })
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' })
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold text-gray-900">scRNA-seq Annotation Platform</h1>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8 flex flex-col gap-6">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-700">Upload dataset</h2>
          <UploadForm onSubmit={handleSubmit} disabled={state.status === 'loading'} />
        </div>

        {(state.status === 'loading' || state.status === 'error') && (
          <StatusBanner
            state={state.status}
            message={state.status === 'error' ? state.message : undefined}
          />
        )}

        {state.status === 'done' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-700">Results</h2>
            <ResultsTable result={state.result} />
          </div>
        )}
      </main>
    </div>
  )
}
