interface Props {
  state: 'loading' | 'error'
  message?: string
}

export default function StatusBanner({ state, message }: Props) {
  if (state === 'loading') {
    return (
      <div className="flex items-center gap-3 rounded-lg bg-blue-50 px-4 py-3 text-blue-700">
        <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <span className="text-sm font-medium">Running pipeline — this may take a minute…</span>
      </div>
    )
  }

  return (
    <div className="rounded-lg bg-red-50 px-4 py-3 text-red-700">
      <p className="text-sm font-medium">Pipeline failed</p>
      {message && <p className="mt-1 text-sm opacity-80">{message}</p>}
    </div>
  )
}
