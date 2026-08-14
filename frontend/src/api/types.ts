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
