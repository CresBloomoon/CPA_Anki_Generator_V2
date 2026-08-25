import { useState } from 'react'
import { downloadGenerationJobPackage } from '../api/client'
import type { GenerationJobStatusResponse } from '../api/types'
import { primaryButtonClasses } from '../styles'

interface DownloadButtonProps {
  status: GenerationJobStatusResponse | null
  // Called once the download actually succeeds (not on click) -- App.tsx
  // uses this to know it's now safe to reset without warning the user
  // about losing undownloaded cards (see Phase5-22's dev-log).
  onDownloaded: () => void
}

export function DownloadButton({ status, onDownloaded }: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!status) return null

  // PARTIALLY_DONE sections also hold cards (see Phase4-8's
  // on_block_generated callback) and are included in the backend's
  // collect_generated_cards(), so they must count here too -- otherwise
  // the button never appears for a job whose only section stopped partway
  // through, silently keeping already-paid-for cards out of reach.
  const doneCount = status.section_jobs.filter(
    (sectionJob) =>
      sectionJob.status === 'DONE' || sectionJob.status === 'PARTIALLY_DONE',
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
      onDownloaded()
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
        className={`self-start bg-green-600 ${primaryButtonClasses}`}
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
