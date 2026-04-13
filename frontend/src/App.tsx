import { useState } from 'react'
import type { ModelSelection, PipelineResult } from './types/pipeline'
import { analyze, selectModel } from './services/api'
import UploadForm from './components/UploadForm'
import ResultsTable from './components/ResultsTable'
import StatusBanner from './components/StatusBanner'

type AppState =
  | { status: 'idle' }
  | { status: 'selecting_model' }
  | {
      status: 'clarification_needed'
      question: string
      reasoning: string
      file: File
      tissue: string
      organism: string
      useLlm: boolean
      round: number
    }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; result: PipelineResult; modelSelection: ModelSelection }

export default function App() {
  const [state, setState] = useState<AppState>({ status: 'idle' })
  const [clarificationText, setClarificationText] = useState('')

  async function handleSubmit(file: File, tissue: string, organism: string, useLlm: boolean) {
    setState({ status: 'selecting_model' })
    await runSelectModel(file, tissue, organism, useLlm)
  }

  async function runSelectModel(
    file: File,
    tissue: string,
    organism: string,
    useLlm: boolean,
    clarification?: string,
    clarificationRound: number = 0,
  ) {
    setState({ status: 'selecting_model' })
    try {
      const modelSelection = await selectModel({
        tissue,
        organism,
        clarification,
        use_llm: useLlm,
        clarification_round: clarificationRound,
      })

      if (modelSelection.clarifying_question) {
        setClarificationText('')
        setState({
          status: 'clarification_needed',
          question: modelSelection.clarifying_question,
          reasoning: modelSelection.reasoning,
          file,
          tissue,
          organism,
          useLlm,
          round: clarificationRound + 1,
        })
        return
      }

      // Confident selection — run the full pipeline immediately
      await runAnalyze(file, tissue, organism, modelSelection)
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' })
    }
  }

  async function handleClarificationSubmit() {
    if (state.status !== 'clarification_needed') return
    const { file, tissue, organism, useLlm, round } = state
    await runSelectModel(file, tissue, organism, useLlm, clarificationText, round)
  }

  async function runAnalyze(
    file: File,
    tissue: string,
    organism: string,
    modelSelection: ModelSelection,
  ) {
    setState({ status: 'loading' })
    try {
      const result = await analyze(file, tissue, organism, modelSelection.model_name)
      setState({ status: 'done', result, modelSelection })
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' })
    }
  }

  const isLoading =
    state.status === 'selecting_model' || state.status === 'loading'

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold text-gray-900">scRNA-seq Annotation Platform</h1>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8 flex flex-col gap-6">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-700">Upload dataset</h2>
          <UploadForm onSubmit={handleSubmit} disabled={isLoading} />
        </div>

        {/* Clarification question */}
        {state.status === 'clarification_needed' && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
            <p className="text-xs font-medium text-amber-800 mb-1">Model selection needs clarification</p>
            <p className="text-xs text-amber-700 mb-1 italic">{state.reasoning}</p>
            <p className="text-sm text-amber-900 font-medium mb-3">{state.question}</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={clarificationText}
                onChange={(e) => setClarificationText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && clarificationText.trim() && handleClarificationSubmit()}
                placeholder="Your answer…"
                className="flex-1 rounded border border-amber-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
              />
              <button
                onClick={handleClarificationSubmit}
                disabled={!clarificationText.trim()}
                className="rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                Submit
              </button>
            </div>
          </div>
        )}

        {(isLoading || state.status === 'error') && (
          <StatusBanner
            state={isLoading ? 'loading' : 'error'}
            message={state.status === 'error' ? state.message : undefined}
          />
        )}

        {state.status === 'done' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-700">Results</h2>
            <ResultsTable result={state.result} modelSelection={state.modelSelection} />
          </div>
        )}
      </main>
    </div>
  )
}
