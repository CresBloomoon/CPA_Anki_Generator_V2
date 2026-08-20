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
}

export interface StartGenerationJobResponse {
  job_id: string
}

export type SectionJobStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'

export interface SectionJobStatusResponse {
  title: string
  status: SectionJobStatus
  card_count: number
  error_message: string | null
}

export interface GenerationJobStatusResponse {
  job_id: string
  is_complete: boolean
  section_jobs: SectionJobStatusResponse[]
}
