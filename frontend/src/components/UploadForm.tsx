import { useRef, useState } from 'react'

interface Props {
  onSubmit: (file: File) => void
  disabled: boolean
}

export default function UploadForm({ onSubmit, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setSelectedFile(e.target.files?.[0] ?? null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedFile) onSubmit(selectedFile)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
          onChange={handleFileChange}
        />
      </div>

      <button
        type="submit"
        disabled={!selectedFile || disabled}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Run pipeline
      </button>
    </form>
  )
}
