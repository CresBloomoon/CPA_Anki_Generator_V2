import { useEffect, useState } from 'react'
import {
  GenerationJobNotFoundError,
  getGenerationJobStatus,
  startGenerationJob,
} from '../api/client'
import type {
  GenerationJobStatusResponse,
  SectionInput,
  SectionJobStatus,
} from '../api/types'
import type { SectionRow } from './SectionTable'
import { primaryButtonClasses } from '../styles'

const POLL_INTERVAL_MS = 2000
// At the poll interval above, 10 consecutive failures is ~20 seconds --
// long enough to ride out a brief Tailscale reconnect, short enough to
// stop polling forever against a backend that's actually down.
const MAX_CONSECUTIVE_POLL_FAILURES = 10

const STATUS_LABELS: Record<SectionJobStatus, string> = {
  PENDING: '待機中',
  RUNNING: '生成中',
  DONE: '完了',
  FAILED: '失敗',
}

const STATUS_BADGE_CLASSES: Record<SectionJobStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-600',
  RUNNING: 'bg-blue-100 text-blue-700',
  DONE: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
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
  // Optional: not wired up by App yet (no consumer exists until Phase5-5's
  // download UI needs job_id/is_complete). Kept as part of the component's
  // API now so that phase can just pass a callback without touching this
  // component's internals.
  onStatusChange?: (status: GenerationJobStatusResponse | null) => void
}

export function GenerationProgress({
  rows,
  onStatusChange,
}: GenerationProgressProps) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<GenerationJobStatusResponse | null>(
    null,
  )
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)

  const selectedRows = rows.filter((row) => row.selected)
  const canStart = selectedRows.length > 0 && !isStarting && jobId === null

  async function handleStart() {
    setIsStarting(true)
    setError(null)
    try {
      const response = await startGenerationJob(
        selectedRows.map(toSectionInput),
        '',
      )
      setJobId(response.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsStarting(false)
    }
  }

  useEffect(() => {
    if (!jobId) return

    let cancelled = false
    // Counts only *consecutive* failures (reset to 0 on any success), not
    // a total failure count -- a brief Tailscale blip shouldn't count
    // against a job that's otherwise polling fine.
    let consecutiveFailures = 0
    const intervalId = setInterval(async () => {
      try {
        const result = await getGenerationJobStatus(jobId)
        if (cancelled) return
        consecutiveFailures = 0
        setPollError(null)
        setStatus(result)
        onStatusChange?.(result)
        if (result.is_complete) {
          clearInterval(intervalId)
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof GenerationJobNotFoundError) {
          // JobStore is in-memory only -- a backend restart mid-generation
          // loses the job for good, so retrying is pointless.
          setError(
            '生成ジョブが見つかりません。バックエンドが再起動された可能性があります。',
          )
          clearInterval(intervalId)
          return
        }
        consecutiveFailures += 1
        if (consecutiveFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
          // Without this cap, a fully-stopped backend leaves this stuck
          // showing "接続エラーが発生しました。再試行中..." forever.
          setError(
            `接続エラーが${consecutiveFailures}回連続で発生したため、進捗確認を停止しました。ネットワーク接続を確認してください。`,
          )
          setPollError(null)
          clearInterval(intervalId)
          return
        }
        // Likely transient (network blip over Tailscale, etc.) -- keep
        // polling and keep the last-known status on screen, just surface
        // that something's currently not working.
        setPollError(err instanceof Error ? err.message : String(err))
      }
    }, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      clearInterval(intervalId)
    }
  }, [jobId, onStatusChange])

  const doneCount =
    status?.section_jobs.filter((job) => job.status === 'DONE').length ?? 0
  const totalCount = status?.section_jobs.length ?? 0
  const progressPercent = totalCount > 0 ? (doneCount / totalCount) * 100 : 0

  return (
    <div className="mt-4 flex flex-col gap-3 rounded-lg border border-gray-200 p-4">
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
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-blue-600 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-sm text-gray-600">
            {doneCount} / {totalCount} 件完了
          </p>

          <ul className="flex flex-col gap-1 text-sm">
            {status.section_jobs.map((sectionJob, index) => (
              <li
                key={`${sectionJob.title}-${index}`}
                className="flex items-center gap-2"
              >
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[sectionJob.status]}`}
                >
                  {STATUS_LABELS[sectionJob.status]}
                </span>
                <span>{sectionJob.title}</span>
                {sectionJob.status === 'DONE' && (
                  <span className="text-gray-500">
                    （{sectionJob.card_count}枚）
                  </span>
                )}
                {sectionJob.status === 'FAILED' && sectionJob.error_message && (
                  <span className="text-red-600">
                    {sectionJob.error_message}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
