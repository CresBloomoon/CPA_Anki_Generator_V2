import { useState } from 'react'
import { downloadGenerationJobSectionPackage } from '../api/client'
import type { SectionJobStatus } from '../api/types'
import { iconButtonClasses } from '../styles'
import { triggerDownload } from '../utils/download'
import { DownloadIcon } from './icons'

interface SectionDownloadButtonProps {
  jobId: string
  sectionIndex: number
  status: SectionJobStatus
  onDownloaded: () => void
}

export function SectionDownloadButton({
  jobId,
  sectionIndex,
  status,
  onDownloaded,
}: SectionDownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Disabled for PENDING/RUNNING/FAILED alike -- deliberately no visual
  // distinction between "not ready yet" and "failed" (see Phase5-26's
  // dev-log): one greyed-out look, one rule.
  const isReady = status === 'DONE' || status === 'PARTIALLY_DONE'

  async function handleDownload() {
    setIsDownloading(true)
    setError(null)
    try {
      const file = await downloadGenerationJobSectionPackage(
        jobId,
        sectionIndex,
      )
      triggerDownload(file)
      onDownloaded()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={handleDownload}
        disabled={!isReady || isDownloading}
        aria-label="このセクションをダウンロード"
        title="このセクションをダウンロード"
        className={`text-gray-500 hover:text-gray-800 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-gray-500 ${iconButtonClasses}`}
      >
        <DownloadIcon />
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
