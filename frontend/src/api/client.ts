import type { ScanResponse, UploadPdfResponse } from './types'

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
