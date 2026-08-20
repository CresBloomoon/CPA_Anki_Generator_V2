// Shared sizing for interactive elements across the app. Colors
// (bg-blue-600, bg-green-600, ...) stay at each call site since they carry
// semantic meaning (blue = primary action, green = download/success,
// gray border = secondary action) that differs per use; only the
// size/padding/shape/disabled-state tier is centralized here, so future
// size adjustments happen in one place instead of being repeated at every
// call site.

export const primaryButtonClasses =
  'rounded px-6 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50'

export const secondaryButtonClasses =
  'rounded border border-gray-300 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50'

export const iconButtonClasses = 'rounded p-1.5'

export const textInputClasses =
  'rounded border border-gray-300 px-3 py-2 text-sm'

export const tableFieldClasses = 'rounded border border-gray-300 px-2 py-1.5'

export const checkboxClasses = 'h-5 w-5'
