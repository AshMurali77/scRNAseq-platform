import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ConversationMessage, PipelineResult, QueryContext } from '../types/pipeline'
import { queryPipeline } from '../services/api'

interface Props {
  result: PipelineResult
  tissue: string
  organism: string
}

export default function ChatPanel({ result, tissue, organism }: Props) {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Build the query context once from the result — excludes per-cell data and plots
  const context = useMemo<QueryContext>(() => ({
    n_cells_input: result.n_cells_input,
    n_cells_after_qc: result.n_cells_after_qc,
    n_hvgs: result.n_hvgs,
    n_clusters: result.n_clusters,
    model_display_name: result.model_display_name,
    tissue,
    organism,
    cluster_summaries: result.cluster_summaries,
    cluster_validations: result.cluster_validations,
    marker_genes: result.marker_genes,
    dataset_metadata: result.dataset_metadata,
  }), [result, tissue, organism])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend() {
    const question = input.trim()
    if (!question || loading) return

    const userMsg: ConversationMessage = { role: 'user', content: question }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const response = await queryPipeline({
        question,
        conversation_history: messages,
        context,
      })
      setMessages([...nextMessages, { role: 'assistant', content: response.answer }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col" style={{ height: '420px' }}>
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && !loading && (
          <p className="text-xs text-gray-400 text-center pt-10 select-none">
            Ask questions about your clusters, cell types, or marker genes.
            <br />
            <span className="italic">
              e.g. "Why is cluster 2 labeled monocytes?" or "What markers distinguish cluster 0?"
            </span>
          </p>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-blue-600 text-white whitespace-pre-wrap">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-900">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ children }) => (
                      <div className="overflow-x-auto mb-1.5">
                        <table className="min-w-full text-xs border border-gray-300 rounded">{children}</table>
                      </div>
                    ),
                    thead: ({ children }) => <thead className="bg-gray-200">{children}</thead>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    tr: ({ children }) => <tr className="border-t border-gray-300">{children}</tr>,
                    th: ({ children }) => (
                      <th className="px-2 py-1 text-left font-semibold text-gray-700 whitespace-nowrap">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="px-2 py-1 text-gray-800">{children}</td>
                    ),
                    p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    em: ({ children }) => <em className="italic">{children}</em>,
                    ul: ({ children }) => <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="text-sm">{children}</li>,
                    code: ({ children, className }) =>
                      className ? (
                        <pre className="bg-gray-200 rounded px-2 py-1 text-xs overflow-x-auto mb-1.5">
                          <code>{children}</code>
                        </pre>
                      ) : (
                        <code className="bg-gray-200 rounded px-1 text-xs font-mono">{children}</code>
                      ),
                    h1: ({ children }) => <h1 className="font-semibold text-base mb-1">{children}</h1>,
                    h2: ({ children }) => <h2 className="font-semibold text-sm mb-1">{children}</h2>,
                    h3: ({ children }) => <h3 className="font-medium text-sm mb-0.5">{children}</h3>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-3 py-2">
              <span className="text-xs text-gray-500 animate-pulse">Thinking…</span>
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-red-500 text-center">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-200 px-4 py-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          disabled={loading}
          placeholder="Ask about your results…"
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          Send
        </button>
      </div>
    </div>
  )
}
