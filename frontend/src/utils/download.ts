import type { DownloadedFile } from '../api/client'

// Shared by DownloadButton (whole job) and SectionDownloadButton (single
// section, Phase5-26) -- both fetch a DownloadedFile via a different API
// call, but the actual "save this blob as a file" mechanics are identical.
export function triggerDownload(file: DownloadedFile): void {
  const url = URL.createObjectURL(file.blob)
  const link = document.createElement('a')
  link.href = url
  link.download = file.filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
