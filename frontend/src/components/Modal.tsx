import type { ReactNode } from 'react'
import { CloseIcon } from './icons'
import { iconButtonClasses } from '../styles'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
}

// Generic overlay + dialog shell. The overlay itself carries onClose so
// clicking anywhere outside the dialog closes it; the dialog box stops
// that click from bubbling back up to the overlay.
export function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="閉じる"
            title="閉じる"
            className={`text-gray-500 hover:text-gray-800 ${iconButtonClasses}`}
          >
            <CloseIcon />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
