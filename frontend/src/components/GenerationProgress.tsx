import { useState } from 'react'
import type {
  GenerationJobStatusResponse,
  SectionInput,
  SectionJobStatus,
} from '../api/types'
import type { SectionRow } from './SectionTable'
import { primaryButtonClasses, textInputClasses } from '../styles'
import {
  SECTION_JOB_STATUS_BADGE_CLASSES,
  SECTION_JOB_STATUS_LABELS,
} from '../utils/sectionJobStatus'
import { DownloadButton } from './DownloadButton'
import { SectionDownloadButton } from './SectionDownloadButton'

function formatElapsedSeconds(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`
}

function formatCardCount(status: SectionJobStatus, cardCount: number): string {
  if (status === 'PENDING') return 'ー'
  if (status === 'RUNNING') return `${cardCount}〜`
  // DONE / PARTIALLY_DONE / FAILED (0件で終了) はいずれも確定値。
  return `${cardCount}`
}

function toSectionInput(row: SectionRow): SectionInput {
  return {
    title: row.title,
    // '' ("cleared, mid-edit" -- see SectionTable's start_page state)
    // becomes 0 here, which Pydantic's Field(ge=1) rejects with a 422.
    // Consistent with Phase5-8's design: this module never blocks
    // submission itself, the server-side check remains the actual gate.
    start_page: row.start_page === '' ? 0 : row.start_page,
    end_page: row.end_page,
    deck_path: row.deck_path,
    source_file: row.source_file,
  }
}

interface GenerationProgressProps {
  rows: SectionRow[]
  // jobId/status/isStarting/error/pollError all live in App.tsx now (see
  // the dev-log for the tab-switch bug this fixes) -- GenerationProgress
  // is purely a display + trigger for them, so it survives being
  // unmounted (e.g. while another tab is active) without losing progress.
  jobId: string | null
  status: GenerationJobStatusResponse | null
  isStarting: boolean
  error: string | null
  pollError: string | null
  onStart: (sections: SectionInput[], additionalPrompt: string) => void
  // Phase5-26: DownloadButton (whole job) now renders inside this
  // component (above the progress table), so this callback is forwarded
  // from App.tsx down to both it and each row's SectionDownloadButton.
  onDownloaded: () => void
}

export function GenerationProgress({
  rows,
  jobId,
  status,
  isStarting,
  error,
  pollError,
  onStart,
  onDownloaded,
}: GenerationProgressProps) {
  // Phase5-23: a single, job-wide free-text instruction forwarded to the AI
  // prompt for every selected section (see additional-prompt-input-ui.md).
  // No dedicated reset is needed -- App.tsx remounts this whole component
  // (key={`progress-${resetKey}`}) on reset, which clears this local state
  // along with the rest of the component's state.
  const [additionalPrompt, setAdditionalPrompt] = useState('')

  const selectedRows = rows.filter((row) => row.selected)
  const canStart = selectedRows.length > 0 && !isStarting && jobId === null

  function handleStart() {
    onStart(selectedRows.map(toSectionInput), additionalPrompt)
  }

  const doneCount =
    status?.section_jobs.filter((job) => job.status === 'DONE').length ?? 0
  const totalCount = status?.section_jobs.length ?? 0

  return (
    <div className="mt-4 flex flex-col gap-3 rounded-lg border border-gray-200 p-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="additional-prompt-input" className="text-sm text-gray-700">
          追加指示（任意）
        </label>
        <textarea
          id="additional-prompt-input"
          value={additionalPrompt}
          onChange={(event) => setAdditionalPrompt(event.target.value)}
          placeholder="計算テキストで例題もカード化して"
          rows={3}
          className={textInputClasses}
        />
      </div>

      <button
        type="button"
        onClick={handleStart}
        disabled={!canStart}
        className={`self-start bg-blue-600 ${primaryButtonClasses}`}
      >
        {isStarting
          ? '生成を開始しています...'
          : `生成開始（選択中 ${selectedRows.length} 件）`}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {pollError && (
        <p className="text-sm text-amber-600">
          接続エラーが発生しました。再試行中... （{pollError}）
        </p>
      )}

      {status && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              全{totalCount}節中{doneCount}節完了
            </p>
            <DownloadButton status={status} onDownloaded={onDownloaded} />
          </div>

          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-500">
                <th className="py-1 pr-2 font-medium">状態</th>
                <th className="py-1 pr-2 font-medium">節</th>
                <th className="py-1 pr-2 font-medium">経過時間</th>
                <th className="py-1 pr-2 font-medium">枚数</th>
                <th className="py-1 font-medium">
                  <span className="sr-only">操作</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {status.section_jobs.map((sectionJob, index) => (
                <tr
                  key={`${sectionJob.title}-${index}`}
                  className="border-b border-gray-100 last:border-0"
                >
                  <td className="py-1.5 pr-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium ${SECTION_JOB_STATUS_BADGE_CLASSES[sectionJob.status]}`}
                    >
                      {sectionJob.status === 'RUNNING' && (
                        <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                      )}
                      {SECTION_JOB_STATUS_LABELS[sectionJob.status]}
                    </span>
                  </td>
                  <td className="py-1.5 pr-2">
                    <div className="flex flex-col">
                      <span>{sectionJob.title}</span>
                      {(sectionJob.status === 'FAILED' ||
                        sectionJob.status === 'PARTIALLY_DONE') &&
                        sectionJob.error_message && (
                          <span className="text-xs text-red-600">
                            {sectionJob.error_message}
                          </span>
                        )}
                    </div>
                  </td>
                  <td className="py-1.5 pr-2 text-gray-500">
                    {sectionJob.elapsed_seconds === null
                      ? 'ー'
                      : formatElapsedSeconds(sectionJob.elapsed_seconds)}
                  </td>
                  <td className="py-1.5 pr-2 text-gray-500">
                    {formatCardCount(sectionJob.status, sectionJob.card_count)}
                  </td>
                  <td className="py-1.5">
                    <SectionDownloadButton
                      jobId={jobId!}
                      sectionIndex={index}
                      status={sectionJob.status}
                      onDownloaded={onDownloaded}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
