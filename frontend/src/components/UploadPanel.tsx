import { useEffect, useRef, useState } from 'react'
import { getRootPathHistory, scanPdfs, uploadPdf } from '../api/client'
import type { ScanResponse } from '../api/types'
import { iconButtonClasses, primaryButtonClasses, textInputClasses } from '../styles'
import { TrashIcon } from './icons'

const ROOT_PATH_HISTORY_DATALIST_ID = 'upload-panel-root-path-history-options'

interface UploadPanelProps {
  onFilesUploaded: (sourceFiles: string[]) => void
  onScanComplete: (result: ScanResponse) => void
}

export function UploadPanel({
  onFilesUploaded,
  onScanComplete,
}: UploadPanelProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [rootPath, setRootPath] = useState('公認会計士試験::')
  const [rootPathHistory, setRootPathHistory] = useState<string[]>([])
  const [isScanning, setIsScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dropWarning, setDropWarning] = useState<string | null>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetched once on mount only -- this is a convenience suggestion list, not
  // a source of truth the UI depends on, so a failure here is swallowed
  // silently rather than surfaced as an error (it must never block scanning).
  useEffect(() => {
    getRootPathHistory()
      .then((response) =>
        setRootPathHistory(response.entries.map((entry) => entry.path)),
      )
      .catch(() => {
        // Non-critical: the root path input still works without suggestions.
      })
  }, [])

  const canScan = selectedFiles.length > 0 && rootPath.trim() !== '' && !isScanning

  // Shared by both the native file dialog and drag-and-drop: filters out
  // non-PDF files (accept="application/pdf" only affects the dialog, not
  // drops, so this check must run here to cover both entry points
  // uniformly) and adds the rest to the existing selection, skipping any
  // that are already selected (matched by name+size -- content hashing
  // would be more precise but is overkill for "did I already pick this
  // file" -- see dev-log for the full reasoning).
  function applySelectedFiles(files: File[]) {
    const pdfFiles = files.filter((file) => file.type === 'application/pdf')
    const nonPdfFiles = files.filter(
      (file) => file.type !== 'application/pdf',
    )

    setDropWarning(
      nonPdfFiles.length > 0
        ? `PDF以外のファイルは追加されませんでした：${nonPdfFiles
            .map((file) => file.name)
            .join('、')}`
        : null,
    )

    setSelectedFiles((prev) => {
      const existingKeys = new Set(
        prev.map((file) => `${file.name}:${file.size}`),
      )
      const uniqueNewFiles = pdfFiles.filter(
        (file) => !existingKeys.has(`${file.name}:${file.size}`),
      )
      return [...prev, ...uniqueNewFiles]
    })
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    applySelectedFiles(Array.from(event.target.files ?? []))
    // Without this, re-selecting the exact same file next time wouldn't
    // fire onChange at all (the input's value wouldn't have changed).
    event.target.value = ''
  }

  function handleRemoveFile(fileToRemove: File) {
    setSelectedFiles((prev) => prev.filter((file) => file !== fileToRemove))
  }

  function handleDragEnter(event: React.DragEvent) {
    event.preventDefault()
    setIsDraggingOver(true)
  }

  function handleDragOver(event: React.DragEvent) {
    // Required -- without this, the browser's default behavior (open the
    // file in a new tab) kicks in and onDrop never fires.
    event.preventDefault()
  }

  function handleDragLeave(event: React.DragEvent) {
    event.preventDefault()
    setIsDraggingOver(false)
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault()
    setIsDraggingOver(false)
    applySelectedFiles(Array.from(event.dataTransfer.files))
  }

  async function handleScan() {
    setIsScanning(true)
    setError(null)
    try {
      const uploaded = await Promise.all(selectedFiles.map(uploadPdf))
      const sourceFiles = uploaded.map((result) => result.source_file)
      // Reported even if the scan call below throws, so a file that was
      // uploaded but produced e.g. a 422 is still available to attach to a
      // manually-added row afterwards.
      onFilesUploaded(sourceFiles)
      const scanResult = await scanPdfs(sourceFiles, rootPath.trim())
      onScanComplete(scanResult)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsScanning(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-gray-200 p-4">
      <div>
        <label className="block text-sm font-medium text-gray-700">
          PDFファイル（複数選択可）
        </label>
        {/*
          The only element with drag/click handlers -- every child below
          has pointer-events-none, so dragenter/dragleave can't fire from
          children entering/leaving (the classic flicker bug) since
          children never receive pointer events in the first place.
        */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`mt-1 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center text-sm transition-colors ${
            isDraggingOver
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 bg-gray-50'
          }`}
        >
          <p className="pointer-events-none text-gray-600">
            ここにPDFをドロップ、またはクリックして選択
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {dropWarning && (
          <p className="mt-1 text-sm text-amber-600">{dropWarning}</p>
        )}

        {selectedFiles.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1 text-sm text-gray-600">
            {selectedFiles.map((file) => (
              <li
                key={`${file.name}:${file.size}`}
                className="flex items-center gap-2"
              >
                <button
                  type="button"
                  onClick={() => handleRemoveFile(file)}
                  aria-label={`${file.name}を選択解除`}
                  title={`${file.name}を選択解除`}
                  className={`text-red-600 hover:text-red-800 ${iconButtonClasses}`}
                >
                  <TrashIcon />
                </button>
                <span>{file.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">
          ルートパス（例: 公認会計士試験::財務会計論::理論）
        </label>
        <input
          type="text"
          value={rootPath}
          onChange={(event) => setRootPath(event.target.value)}
          placeholder="公認会計士試験::財務会計論::理論"
          list={ROOT_PATH_HISTORY_DATALIST_ID}
          className={`mt-1 block w-full ${textInputClasses}`}
        />
        <datalist id={ROOT_PATH_HISTORY_DATALIST_ID}>
          {rootPathHistory.map((path) => (
            <option key={path} value={path} />
          ))}
        </datalist>
      </div>

      <button
        type="button"
        onClick={handleScan}
        disabled={!canScan}
        className={`self-start bg-blue-600 ${primaryButtonClasses}`}
      >
        {isScanning ? 'スキャン中...' : 'スキャン開始'}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
