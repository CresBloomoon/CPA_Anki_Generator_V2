import type {
  GenerationJobStatusResponse,
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
