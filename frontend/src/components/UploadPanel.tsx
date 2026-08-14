import { useState } from 'react'
import { scanPdfs, uploadPdf } from '../api/client'
import type { ScanResponse } from '../api/types'

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
  const [isScanning, setIsScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canScan = selectedFiles.length > 0 && rootPath.trim() !== '' && !isScanning

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    setSelectedFiles(Array.from(event.target.files ?? []))
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
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={handleFileChange}
          className="mt-1 block w-full text-sm"
        />
        {selectedFiles.length > 0 && (
          <ul className="mt-1 text-sm text-gray-600">
            {selectedFiles.map((file) => (
              <li key={file.name}>{file.name}</li>
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
          className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      <button
        type="button"
        onClick={handleScan}
        disabled={!canScan}
        className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isScanning ? 'スキャン中...' : 'スキャン開始'}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
