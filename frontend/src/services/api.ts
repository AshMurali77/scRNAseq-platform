import type { DERequest, DEResult, ModelSelection, ModelSelectionRequest, PipelineResult, QueryRequest, QueryResponse, TrajectoryRequest, TrajectoryResult } from '../types/pipeline'

export async function selectModel(request: ModelSelectionRequest): Promise<ModelSelection> {
  const response = await fetch('/select-model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    let message = `Model selection failed with status ${response.status}`
    try {
      const error = await response.json()
      message = error.detail ?? message
    } catch {
      // empty or non-JSON body
    }
    throw new Error(message)
  }

  return response.json()
}

export async function analyze(
  file: File,
  tissue: string,
  organism: string,
  modelName: string,
  skipQc: boolean = false,
  useLlm: boolean = true,
): Promise<PipelineResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('params', JSON.stringify({ tissue, organism, model_name: modelName, skip_qc: skipQc, use_llm: useLlm }))

  const response = await fetch('/analyze', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const error = await response.json()
      message = error.detail ?? message
    } catch {
      // empty or non-JSON body
    }
    throw new Error(message)
  }

  return response.json()
}

export async function runDE(request: DERequest): Promise<DEResult> {
  const response = await fetch('/downstream/de', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    let message = `DE analysis failed with status ${response.status}`
    try {
      const error = await response.json()
      message = error.detail ?? message
    } catch {
      // empty or non-JSON body
    }
    throw new Error(message)
  }

  return response.json()
}

export async function runTrajectory(request: TrajectoryRequest): Promise<TrajectoryResult> {
  const response = await fetch('/downstream/trajectory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    let message = `Trajectory analysis failed with status ${response.status}`
    try {
      const error = await response.json()
      message = error.detail ?? message
    } catch {
      // empty or non-JSON body
    }
    throw new Error(message)
  }

  return response.json()
}

export async function queryPipeline(request: QueryRequest): Promise<QueryResponse> {
  const response = await fetch('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    let message = `Query failed with status ${response.status}`
    try {
      const error = await response.json()
      message = error.detail ?? message
    } catch {
      // empty or non-JSON body
    }
    throw new Error(message)
  }

  return response.json()
}
