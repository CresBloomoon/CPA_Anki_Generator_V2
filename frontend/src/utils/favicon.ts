// Phase5-27: overlays a small status dot onto the tab favicon while the tab
// is backgrounded, to surface "still generating" / "finished, not yet seen"
// without an on-screen indicator the user isn't looking at. Reads the
// current <link rel="icon"> at call time (rather than hardcoding a path) so
// swapping the app's actual favicon image later needs no change here.
//
// Full favicon replacement was tried first but made the app's own logo
// disappear entirely while a dot was shown -- see Phase5-27's dev-log for
// why this was reworked into a small overlay instead.
const ICON_SIZE = 32
const DOT_RADIUS = 6
const DOT_COLORS = {
  generating: '#2563eb', // blue-600, matches the RUNNING status badge
  completed: '#16a34a', // green-600, matches the DONE status badge
} as const

let cachedLink: HTMLLinkElement | null = null
let originalHref: string | null = null

function getFaviconLink(): { link: HTMLLinkElement; originalHref: string } | null {
  if (cachedLink && originalHref !== null) {
    return { link: cachedLink, originalHref }
  }
  const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) return null
  cachedLink = link
  originalHref = link.href
  return { link, originalHref }
}

let cachedBaseImage: HTMLImageElement | null = null
let cachedBaseImagePromise: Promise<HTMLImageElement> | null = null

function loadBaseImage(href: string): Promise<HTMLImageElement> {
  if (cachedBaseImage) return Promise.resolve(cachedBaseImage)
  if (cachedBaseImagePromise) return cachedBaseImagePromise

  cachedBaseImagePromise = new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => {
      cachedBaseImage = image
      resolve(image)
    }
    image.onerror = reject
    image.src = href
  })
  return cachedBaseImagePromise
}

async function buildDotIconDataUrl(
  kind: 'generating' | 'completed',
  baseImageHref: string,
): Promise<string | null> {
  const baseImage = await loadBaseImage(baseImageHref)

  const canvas = document.createElement('canvas')
  canvas.width = ICON_SIZE
  canvas.height = ICON_SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.clearRect(0, 0, ICON_SIZE, ICON_SIZE)
  ctx.drawImage(baseImage, 0, 0, ICON_SIZE, ICON_SIZE)

  const center = ICON_SIZE - DOT_RADIUS - 1
  ctx.beginPath()
  ctx.arc(center, center, DOT_RADIUS, 0, Math.PI * 2)
  ctx.fillStyle = DOT_COLORS[kind]
  ctx.fill()
  // A thin white ring keeps the dot legible against whatever color the
  // base logo happens to have in that corner.
  ctx.lineWidth = 1.5
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()

  return canvas.toDataURL('image/png')
}

export async function setFaviconIcon(
  kind: 'generating' | 'completed' | null,
): Promise<void> {
  const favicon = getFaviconLink()
  if (!favicon) return

  if (kind === null) {
    favicon.link.href = favicon.originalHref
    return
  }

  const dataUrl = await buildDotIconDataUrl(kind, favicon.originalHref)
  if (dataUrl) {
    favicon.link.href = dataUrl
  }
}
