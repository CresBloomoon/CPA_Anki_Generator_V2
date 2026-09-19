import { useEffect, useState } from 'react'
import { getGenerationJobStatus, listGenerationJobs } from '../api/client'
import type {
  GenerationJobStatusResponse,
  GenerationJobSummaryResponse,
} from '../api/types'
import {
  SECTION_JOB_STATUS_BADGE_CLASSES,
  SECTION_JOB_STATUS_LABELS,
} from '../utils/sectionJobStatus'
import { SectionDownloadButton } from './SectionDownloadButton'

function formatCreatedAt(createdAt: string): string {
  return new Date(createdAt).toLocaleString()
}

// root_path isn't sent by the frontend yet (that wiring is Phase7-2-6), so
// every real job has "" for now -- fall back to a short, readable slice of
// job_id so rows aren't blank in the meantime (see Phase7-2-5's dev-log).
function jobHeading(job: GenerationJobSummaryResponse): string {
  return job.root_path || `ジョブ ${job.job_id.slice(0, 8)}`
}

export function HistoryPanel() {
  const [jobs, setJobs] = useState<GenerationJobSummaryResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Single-expand accordion: opening one job closes whichever was open.
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  // Detail fetches are cached per job_id (fetched at most once, on first
  // expand) since a listed job has already stopped generating and its
  // section detail won't change afterward (see Phase7-2-5's dev-log for
  // the one known exception, which is out of scope here).
  const [jobDetails, setJobDetails] = useState<
    Record<string, GenerationJobStatusResponse>
  >({})
  // Keyed by job_id (not a single scalar) so a failure fetching one job's
  // detail only shows an error on that job's row, not every row.
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({})
  const [loadingDetailJobId, setLoadingDetailJobId] = useState<string | null>(
    null,
  )

  useEffect(() => {
    listGenerationJobs()
      .then((response) => setJobs(response.jobs))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setIsLoading(false))
  }, [])

  async function handleToggle(jobId: string) {
    if (expandedJobId === jobId) {
      setExpandedJobId(null)
      return
    }
    setExpandedJobId(jobId)

    if (jobDetails[jobId]) return

    setLoadingDetailJobId(jobId)
    try {
      const detail = await getGenerationJobStatus(jobId)
      setJobDetails((prev) => ({ ...prev, [jobId]: detail }))
      setDetailErrors((prev) => {
        if (!(jobId in prev)) return prev
        const next = { ...prev }
        delete next[jobId]
        return next
      })
    } catch (err) {
      setDetailErrors((prev) => ({
        ...prev,
        [jobId]: err instanceof Error ? err.message : String(err),
      }))
    } finally {
      setLoadingDetailJobId(null)
    }
  }

  if (isLoading) {
    return <p className="text-sm text-gray-500">履歴を読み込み中...</p>
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (jobs.length === 0) {
    return (
      <p className="text-sm text-gray-500">まだ生成したジョブがありません。</p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {jobs.map((job) => {
        const isExpanded = expandedJobId === job.job_id
        const detail = jobDetails[job.job_id]
        const detailError = detailErrors[job.job_id]
        const isLoadingDetail = loadingDetailJobId === job.job_id

        return (
          <div
            key={job.job_id}
            className="rounded-lg border border-gray-200"
          >
            <button
              type="button"
              onClick={() => handleToggle(job.job_id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex flex-col">
                <span className="text-sm font-medium">{jobHeading(job)}</span>
                <span className="text-xs text-gray-500">
                  {formatCreatedAt(job.created_at)} ・ 全{job.section_count}
                  節中{job.done_section_count}節完了
                  {job.is_complete ? '' : '（未完了）'}
                </span>
              </div>
              <span className="text-xs text-gray-400">
                {isExpanded ? '閉じる' : '開く'}
              </span>
            </button>

            {isExpanded && (
              <div className="border-t border-gray-200 px-4 py-3">
                {isLoadingDetail && (
                  <p className="text-sm text-gray-500">読み込み中...</p>
                )}
                {detailError && (
                  <p className="text-sm text-red-600">{detailError}</p>
                )}
                {detail && (
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-xs text-gray-500">
                        <th className="py-1 pr-2 font-medium">状態</th>
                        <th className="py-1 pr-2 font-medium">節</th>
                        <th className="py-1 font-medium">
                          <span className="sr-only">操作</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.section_jobs.map((sectionJob, index) => (
                        <tr
                          key={`${sectionJob.title}-${index}`}
                          className="border-b border-gray-100 last:border-0"
                        >
                          <td className="py-1.5 pr-2">
                            <span
                              className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${SECTION_JOB_STATUS_BADGE_CLASSES[sectionJob.status]}`}
                            >
                              {SECTION_JOB_STATUS_LABELS[sectionJob.status]}
                            </span>
                          </td>
                          <td className="py-1.5 pr-2">{sectionJob.title}</td>
                          <td className="py-1.5">
                            <SectionDownloadButton
                              jobId={job.job_id}
                              sectionIndex={index}
                              status={sectionJob.status}
                              onDownloaded={() => {}}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
