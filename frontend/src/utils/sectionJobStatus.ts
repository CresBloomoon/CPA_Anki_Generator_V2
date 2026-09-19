import type { SectionJobStatus } from '../api/types'

// Shared by GenerationProgress (in-progress job) and HistoryPanel (past
// jobs) so the two views describe the same status the same way (see
// Phase7-2-5's dev-log).
export const SECTION_JOB_STATUS_LABELS: Record<SectionJobStatus, string> = {
  PENDING: '待機中',
  RUNNING: '生成中',
  DONE: '完了',
  PARTIALLY_DONE: '一部完了',
  FAILED: '失敗',
}

export const SECTION_JOB_STATUS_BADGE_CLASSES: Record<SectionJobStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-600',
  RUNNING: 'bg-blue-100 text-blue-700',
  DONE: 'bg-green-100 text-green-700',
  PARTIALLY_DONE: 'bg-amber-100 text-amber-700',
  FAILED: 'bg-red-100 text-red-700',
}
