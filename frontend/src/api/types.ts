// Mirrors backend/app/routes/schemas/pdf.py. Kept as plain hand-written
// types (no codegen) so the shape stays explicit and easy to read.

export interface UploadPdfResponse {
  source_file: string
  size_bytes: number
}

export interface SectionScanResult {
  title: string
  start_page: number
  end_page: number | null
  deck_path: string
  source_file: string
}

export interface ScanResponse {
  sections: SectionScanResult[]
  warnings: string[]
}

// Mirrors backend/app/routes/schemas/root_path_history.py.

export interface RootPathHistoryEntry {
  path: string
  last_used_at: string
}

export interface RootPathHistoryResponse {
  entries: RootPathHistoryEntry[]
}

// Mirrors backend/app/routes/schemas/settings.py.

export interface AiProviderSettings {
  provider: string
  model_name: string
}

export interface AvailableModelsResponse {
  models: Record<string, string[]>
}

// Mirrors backend/app/routes/schemas/generation.py.

export interface SectionInput {
  title: string
  start_page: number
  end_page: number | null
  deck_path: string
  source_file: string
}

export interface StartGenerationRequest {
  sections: SectionInput[]
  additional_prompt: string
  root_path: string
}

export interface StartGenerationJobResponse {
  job_id: string
}

export type SectionJobStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'DONE'
  | 'PARTIALLY_DONE'
  | 'FAILED'

export interface SectionJobStatusResponse {
  title: string
  status: SectionJobStatus
  card_count: number
  error_message: string | null
  // Phase4-6: backend field only for now -- not yet displayed anywhere
  // (see Phase5-26's planned progress table).
  elapsed_seconds: number | null
  // Total only (input + output combined) -- see the token-usage-display
  // feature's dev-log for why the split stays backend-internal.
  token_count: number
}

export interface GenerationJobStatusResponse {
  job_id: string
  is_complete: boolean
  section_jobs: SectionJobStatusResponse[]
}

// 履歴一覧（GET /generation-jobs）専用の軽量な型。GenerationJobStatus
// Responseと違い、セクションごとの詳細は持たない（Phase7-2-5の
// dev-log参照）。
export interface GenerationJobSummaryResponse {
  job_id: string
  root_path: string
  created_at: string
  is_complete: boolean
  section_count: number
  done_section_count: number
  // Sum across all section_jobs, including FAILED ones (see
  // GenerationJob.total_token_usage()'s docstring on the backend).
  total_token_count: number
}

export interface GenerationJobListResponse {
  jobs: GenerationJobSummaryResponse[]
}
