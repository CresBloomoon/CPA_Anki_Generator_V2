import { useEffect } from 'react'

interface ToastProps {
  message: string
  variant?: 'success'
  durationMs?: number
  onDismiss: () => void
}

// Deliberately minimal: a single visual component with its own auto-dismiss
// timer, driven by a plain `toastMessage: string | null` state at the call
// site (App.tsx) rather than a global toast queue/context/hook -- there is
// currently exactly one caller (settings save success), so a shared
// notification system would be premature. See Phase5-12 dev-log.
export function Toast({
  message,
  variant = 'success',
  durationMs = 3000,
  onDismiss,
}: ToastProps) {
  useEffect(() => {
    const timeoutId = setTimeout(onDismiss, durationMs)
    return () => clearTimeout(timeoutId)
  }, [durationMs, onDismiss])

  const variantClasses =
    variant === 'success' ? 'bg-green-600 text-white' : ''

  return (
    <div
      role="status"
      className={`fixed right-4 top-4 z-50 rounded px-4 py-2 text-sm shadow-lg ${variantClasses}`}
    >
      {message}
    </div>
  )
}
