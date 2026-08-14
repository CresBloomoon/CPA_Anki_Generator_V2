// crypto.randomUUID() requires a Secure Context (HTTPS or localhost) and
// throws on plain-HTTP access over Tailscale (e.g. http://homepi:5173).
// These IDs are only used as React keys and as lookup keys for immutable
// row updates -- no cryptographic strength is needed -- so a simple shared
// counter is enough. Shared (not one counter per call site) so IDs handed
// out from different places never collide.
let counter = 0

export function createId(): string {
  counter += 1
  return `id-${counter}`
}
