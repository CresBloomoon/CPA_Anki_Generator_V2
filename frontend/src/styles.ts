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

// Border color deliberately left out of tableFieldClasses (Phase5-8):
// SectionTable needs to switch between a default and an error border, and
// always applying exactly one of fieldBorderDefaultClasses /
// fieldBorderErrorClasses (never both at once) avoids relying on
// Tailwind's utility-generation order to decide which color class wins.
export const tableFieldClasses = 'rounded border px-2 py-1.5'
export const fieldBorderDefaultClasses = 'border-gray-300'
export const fieldBorderErrorClasses = 'border-red-500'

export const checkboxClasses = 'h-5 w-5'
