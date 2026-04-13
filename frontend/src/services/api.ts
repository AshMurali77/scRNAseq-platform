import type { ModelSelection, ModelSelectionRequest, PipelineResult } from '../types/pipeline'

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
): Promise<PipelineResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('params', JSON.stringify({ tissue, organism, model_name: modelName }))

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
