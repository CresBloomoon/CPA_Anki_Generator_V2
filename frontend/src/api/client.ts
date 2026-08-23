import type {
  AiProviderSettings,
  AvailableModelsResponse,
  GenerationJobStatusResponse,
  RootPathHistoryResponse,
  ScanResponse,
  SectionInput,
  StartGenerationJobResponse,
  UploadPdfResponse,
} from './types'

// Thrown specifically for a 404 on GET /generation-jobs/{id}, so callers
// can distinguish "this job no longer exists" (JobStore is in-memory only,
// so a backend restart mid-generation loses it -- retrying is pointless)
// from a transient network/connection failure (worth retrying).
export class GenerationJobNotFoundError extends Error {}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') {
      return body.detail
    }
    return JSON.stringify(body.detail)
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

export async function uploadPdf(file: File): Promise<UploadPdfResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/pdfs', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<UploadPdfResponse>
}

export async function scanPdfs(
  sourceFiles: string[],
  rootPath: string,
): Promise<ScanResponse> {
  const response = await fetch('/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_files: sourceFiles, root_path: rootPath }),
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<ScanResponse>
}

export async function getRootPathHistory(): Promise<RootPathHistoryResponse> {
  const response = await fetch('/root-path-history')

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<RootPathHistoryResponse>
}

export async function getSettings(): Promise<AiProviderSettings> {
  const response = await fetch('/settings')

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<AiProviderSettings>
}

export async function getAvailableModels(): Promise<AvailableModelsResponse> {
  const response = await fetch('/settings/available-models')

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<AvailableModelsResponse>
}

export async function updateSettings(
  provider: string,
  modelName: string,
): Promise<AiProviderSettings> {
  const response = await fetch('/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, model_name: modelName }),
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<AiProviderSettings>
}

export async function startGenerationJob(
  sections: SectionInput[],
  additionalPrompt: string,
): Promise<StartGenerationJobResponse> {
  const response = await fetch('/generation-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sections,
      additional_prompt: additionalPrompt,
    }),
  })

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<StartGenerationJobResponse>
}

export async function getGenerationJobStatus(
  jobId: string,
): Promise<GenerationJobStatusResponse> {
  const response = await fetch(
    `/generation-jobs/${encodeURIComponent(jobId)}`,
  )

  if (response.status === 404) {
    throw new GenerationJobNotFoundError(await extractErrorMessage(response))
  }
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  return response.json() as Promise<GenerationJobStatusResponse>
}

export interface DownloadedFile {
  blob: Blob
  filename: string
}

function extractFilename(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition')
  if (!disposition) return fallback
  const match = /filename="([^"]+)"/.exec(disposition)
  return match ? match[1] : fallback
}

export async function downloadGenerationJobPackage(
  jobId: string,
): Promise<DownloadedFile> {
  const response = await fetch(
    `/generation-jobs/${encodeURIComponent(jobId)}/download`,
  )

  if (response.status === 404) {
    throw new GenerationJobNotFoundError(await extractErrorMessage(response))
  }
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response))
  }

  const blob = await response.blob()
  const filename = extractFilename(response, 'generated.apkg')
  return { blob, filename }
}
