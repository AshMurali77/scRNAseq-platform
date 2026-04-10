import type { PipelineResult } from '../types/pipeline'

export async function analyze(file: File, tissue: string, organism: string): Promise<PipelineResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('params', JSON.stringify({ tissue, organism }))

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
      // Response body was empty or non-JSON (e.g. proxy error)
    }
    throw new Error(message)
  }

  return response.json()
}
