import { useState } from 'react'
import { downloadGenerationJobPackage } from '../api/client'
import type { GenerationJobStatusResponse } from '../api/types'

interface DownloadButtonProps {
  status: GenerationJobStatusResponse | null
}

export function DownloadButton({ status }: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!status) return null

  const doneCount = status.section_jobs.filter(
    (sectionJob) => sectionJob.status === 'DONE',
  ).length

  // Nothing to download yet -- GenerationProgress's own "0/N件完了"
  // display already communicates this, so no button is shown rather than
  // one that would silently produce an empty (but technically valid)
  // .apkg if clicked.
  if (doneCount === 0) return null

  async function handleDownload() {
    setIsDownloading(true)
    setError(null)
    try {
      const { blob, filename } = await downloadGenerationJobPackage(
        status!.job_id,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="mt-4 flex flex-col gap-2">
      <button
        type="button"
        onClick={handleDownload}
        disabled={isDownloading}
        className="self-start rounded bg-green-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isDownloading
          ? 'ダウンロード中...'
          : status.is_complete
            ? 'ダウンロード'
            : '途中経過をダウンロード（一部完了）'}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
