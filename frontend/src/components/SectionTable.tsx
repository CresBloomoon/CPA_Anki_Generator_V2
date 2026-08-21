import { useEffect, useRef, useState } from 'react'
import { PlusIcon, TrashIcon } from './icons'
import { createId } from '../utils/id'
import {
  checkboxClasses,
  fieldBorderDefaultClasses,
  fieldBorderErrorClasses,
  iconButtonClasses,
  secondaryButtonClasses,
  tableFieldClasses,
} from '../styles'
import {
  getDeckPathError,
  getEndPageError,
  getStartPageError,
  getTitleError,
} from '../validation'

// The fields Phase5-8 shows visual validation for (source_file is
// deliberately excluded -- see Phase5-8 design discussion).
type TouchableField = 'title' | 'start_page' | 'end_page' | 'deck_path'

// This component owns the shape of a row (SectionRow), not just the
// backend's ScanResponse shape: `id` (for stable React keys and immutable
// updates), `selected` (a UI-only concern -- see CLAUDE.md), and
// `touchedFields` (Phase5-8: which fields the user has blurred at least
// once, so warnings only appear after a field has actually been visited)
// exist only here, never on the wire.
export interface SectionRow {
  id: string
  selected: boolean
  title: string
  // '' means "the field is cleared and mid-edit" -- see the start_page
  // <input>'s onChange. Not persisted anywhere outside this component;
  // GenerationProgress's toSectionInput() converts it to a number before
  // it ever reaches the API.
  start_page: number | ''
  end_page: number | null
  deck_path: string
  source_file: string
  touchedFields?: Partial<Record<TouchableField, boolean>>
}

interface SectionTableProps {
  rows: SectionRow[]
  onRowsChange: (rows: SectionRow[]) => void
  sourceFileOptions: string[]
}

const DECK_PATH_DATALIST_ID = 'section-table-deck-path-options'

// Each row repeats the same six fields, so every <input>/<select> needs an
// id derived from something stable per-row -- row.id (from createId(),
// already used as the React key) fits, rather than the array index (which
// would get reassigned to a different row after a delete).
function fieldId(rowId: string, field: string): string {
  return `section-${rowId}-${field}`
}

// Only the columns holding actual data are resizable -- the checkbox and
// delete-button columns are fixed-size icon columns with nothing to
// resize. Kept as a single Record (rather than five separate useState
// calls) so this can later be swapped for a value loaded from/saved to a
// backend without restructuring the component (see Phase5-7 plan entry).
type ColumnKey = 'title' | 'start_page' | 'end_page' | 'deck_path' | 'source_file'

const DEFAULT_COLUMN_WIDTHS: Record<ColumnKey, number> = {
  title: 192,
  start_page: 80,
  end_page: 96,
  deck_path: 256,
  source_file: 160,
}

const FIXED_ICON_COLUMN_WIDTH = 40
const MIN_COLUMN_WIDTH = 40

// Defined at module scope (not inside SectionTable) so it isn't recreated
// -- and its DOM node remounted -- on every render.
//
// The outer div is the drag hit area (wider than the visible line, so it's
// easy to grab) and carries `group` so hovering anywhere in it -- not just
// over the thin inner line -- highlights that line via `group-hover`.
function ResizeHandle({
  onMouseDown,
}: {
  onMouseDown: (event: React.MouseEvent) => void
}) {
  return (
    <div
      onMouseDown={onMouseDown}
      className="group absolute right-0 top-0 flex h-full w-3 cursor-col-resize select-none items-center justify-center"
    >
      <div className="h-full w-1 bg-gray-300 group-hover:bg-blue-400" />
    </div>
  )
}

export function SectionTable({
  rows,
  onRowsChange,
  sourceFileOptions,
}: SectionTableProps) {
  const deckPathOptions = Array.from(
    new Set(rows.map((row) => row.deck_path).filter((path) => path !== '')),
  )

  const allSelected = rows.length > 0 && rows.every((row) => row.selected)
  const someSelected = rows.some((row) => row.selected)

  // The checkbox's indeterminate visual state is a DOM property, not an
  // HTML attribute -- React has no JSX prop for it, so it must be set
  // imperatively on the actual <input> element.
  const selectAllRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected && !allSelected
    }
  }, [someSelected, allSelected])

  function toggleSelectAll() {
    const nextSelected = !allSelected
    onRowsChange(rows.map((row) => ({ ...row, selected: nextSelected })))
  }

  const [columnWidths, setColumnWidths] = useState(DEFAULT_COLUMN_WIDTHS)

  function startResize(columnKey: ColumnKey, event: React.MouseEvent) {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = columnWidths[columnKey]

    function handleMouseMove(moveEvent: MouseEvent) {
      const delta = moveEvent.clientX - startX
      setColumnWidths((prev) => ({
        ...prev,
        [columnKey]: Math.max(MIN_COLUMN_WIDTH, startWidth + delta),
      }))
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  function updateRow(id: string, patch: Partial<SectionRow>) {
    onRowsChange(
      rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    )
  }

  function markTouched(id: string, field: TouchableField) {
    onRowsChange(
      rows.map((row) =>
        row.id === id
          ? { ...row, touchedFields: { ...row.touchedFields, [field]: true } }
          : row,
      ),
    )
  }

  function deleteRow(id: string) {
    onRowsChange(rows.filter((row) => row.id !== id))
  }

  function addRow() {
    onRowsChange([
      ...rows,
      {
        id: createId(),
        selected: true,
        title: '',
        start_page: 1,
        end_page: null,
        deck_path: '',
        source_file: '',
      },
    ])
  }

  return (
    <div className="mt-4">
      <div className="overflow-x-auto">
        <table
          className="w-full min-w-max border-collapse text-sm"
          style={{ tableLayout: 'fixed' }}
        >
          <colgroup>
            <col style={{ width: FIXED_ICON_COLUMN_WIDTH }} />
            <col style={{ width: columnWidths.title }} />
            <col style={{ width: columnWidths.start_page }} />
            <col style={{ width: columnWidths.end_page }} />
            <col style={{ width: columnWidths.deck_path }} />
            <col style={{ width: columnWidths.source_file }} />
            <col style={{ width: FIXED_ICON_COLUMN_WIDTH }} />
          </colgroup>
          <thead>
            <tr className="border-b border-gray-300 text-left">
              <th className="p-2">
                <input
                  ref={selectAllRef}
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="全選択/全解除"
                  title="全選択/全解除"
                  className={checkboxClasses}
                />
              </th>
              <th className="relative p-2">
                節タイトル
                <ResizeHandle onMouseDown={(e) => startResize('title', e)} />
              </th>
              <th className="relative p-2">
                開始ページ
                <ResizeHandle
                  onMouseDown={(e) => startResize('start_page', e)}
                />
              </th>
              <th className="relative p-2">
                終了ページ
                <ResizeHandle
                  onMouseDown={(e) => startResize('end_page', e)}
                />
              </th>
              <th className="relative p-2">
                出力デッキ名
                <ResizeHandle
                  onMouseDown={(e) => startResize('deck_path', e)}
                />
              </th>
              <th className="relative p-2">
                ソースファイル
                <ResizeHandle
                  onMouseDown={(e) => startResize('source_file', e)}
                />
              </th>
              <th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const titleError = getTitleError(row.title)
              const startPageError = getStartPageError(row.start_page)
              const endPageError = getEndPageError(row.start_page, row.end_page)
              const deckPathError = getDeckPathError(row.deck_path)

              // Only shown once the field has been blurred at least once
              // (Phase5-8: "blur後のみ" -- avoids flashing a warning while
              // the user is still mid-typing, e.g. right after adding a
              // blank row).
              const showTitleError =
                titleError !== null && row.touchedFields?.title
              const showStartPageError =
                startPageError !== null && row.touchedFields?.start_page
              const showEndPageError =
                endPageError !== null && row.touchedFields?.end_page
              const showDeckPathError =
                deckPathError !== null && row.touchedFields?.deck_path

              return (
                <tr key={row.id} className="border-b border-gray-100">
                  <td className="p-2">
                    <label
                      className="sr-only"
                      htmlFor={fieldId(row.id, 'selected')}
                    >
                      この行を選択
                    </label>
                    <input
                      id={fieldId(row.id, 'selected')}
                      type="checkbox"
                      checked={row.selected}
                      onChange={(event) =>
                        updateRow(row.id, { selected: event.target.checked })
                      }
                      className={checkboxClasses}
                    />
                  </td>
                  <td className="p-2">
                    <div className="group relative w-full">
                      <label
                        className="sr-only"
                        htmlFor={fieldId(row.id, 'title')}
                      >
                        節タイトル
                      </label>
                      <input
                        id={fieldId(row.id, 'title')}
                        type="text"
                        value={row.title}
                        onChange={(event) =>
                          updateRow(row.id, { title: event.target.value })
                        }
                        onBlur={() => markTouched(row.id, 'title')}
                        className={`w-full ${tableFieldClasses} ${
                          showTitleError
                            ? fieldBorderErrorClasses
                            : fieldBorderDefaultClasses
                        }`}
                      />
                      {showTitleError && (
                        <div className="absolute left-0 top-full z-10 mt-1 hidden whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white group-hover:block group-focus-within:block">
                          {titleError}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="p-2">
                    <div className="group relative w-full">
                      <label
                        className="sr-only"
                        htmlFor={fieldId(row.id, 'start_page')}
                      >
                        開始ページ
                      </label>
                      <input
                        id={fieldId(row.id, 'start_page')}
                        type="number"
                        min={1}
                        value={row.start_page}
                        onChange={(event) =>
                          updateRow(row.id, {
                            start_page:
                              event.target.value === ''
                                ? ''
                                : Number(event.target.value),
                          })
                        }
                        onBlur={() => markTouched(row.id, 'start_page')}
                        className={`w-full ${tableFieldClasses} ${
                          showStartPageError
                            ? fieldBorderErrorClasses
                            : fieldBorderDefaultClasses
                        }`}
                      />
                      {showStartPageError && (
                        <div className="absolute left-0 top-full z-10 mt-1 hidden whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white group-hover:block group-focus-within:block">
                          {startPageError}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="p-2">
                    <div className="group relative w-full">
                      <label
                        className="sr-only"
                        htmlFor={fieldId(row.id, 'end_page')}
                      >
                        終了ページ
                      </label>
                      <input
                        id={fieldId(row.id, 'end_page')}
                        type="number"
                        min={1}
                        value={row.end_page ?? ''}
                        onChange={(event) =>
                          updateRow(row.id, {
                            end_page:
                              event.target.value === ''
                                ? null
                                : Number(event.target.value),
                          })
                        }
                        onBlur={() => markTouched(row.id, 'end_page')}
                        placeholder="(文末まで)"
                        className={`w-full ${tableFieldClasses} ${
                          showEndPageError
                            ? fieldBorderErrorClasses
                            : fieldBorderDefaultClasses
                        }`}
                      />
                      {showEndPageError && (
                        <div className="absolute left-0 top-full z-10 mt-1 hidden whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white group-hover:block group-focus-within:block">
                          {endPageError}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="p-2">
                    <div className="group relative w-full">
                      <label
                        className="sr-only"
                        htmlFor={fieldId(row.id, 'deck_path')}
                      >
                        出力デッキ名
                      </label>
                      <input
                        id={fieldId(row.id, 'deck_path')}
                        type="text"
                        list={DECK_PATH_DATALIST_ID}
                        value={row.deck_path}
                        onChange={(event) =>
                          updateRow(row.id, { deck_path: event.target.value })
                        }
                        onBlur={() => markTouched(row.id, 'deck_path')}
                        className={`w-full ${tableFieldClasses} ${
                          showDeckPathError
                            ? fieldBorderErrorClasses
                            : fieldBorderDefaultClasses
                        }`}
                      />
                      {showDeckPathError && (
                        <div className="absolute left-0 top-full z-10 mt-1 hidden whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white group-hover:block group-focus-within:block">
                          {deckPathError}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="p-2">
                    <label
                      className="sr-only"
                      htmlFor={fieldId(row.id, 'source_file')}
                    >
                      ソースファイル
                    </label>
                    <select
                      id={fieldId(row.id, 'source_file')}
                      value={row.source_file}
                      onChange={(event) =>
                        updateRow(row.id, { source_file: event.target.value })
                      }
                      className={`w-full ${tableFieldClasses} ${fieldBorderDefaultClasses}`}
                    >
                      <option value="">-- 選択してください --</option>
                      {/* A manually-picked file from a previous session might
                          no longer be in sourceFileOptions after a reload --
                          keep it selectable so the row doesn't silently lose
                          its value. */}
                      {row.source_file &&
                        !sourceFileOptions.includes(row.source_file) && (
                          <option value={row.source_file}>
                            {row.source_file}
                          </option>
                        )}
                      {sourceFileOptions.map((file) => (
                        <option key={file} value={file}>
                          {file}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2">
                    <button
                      type="button"
                      onClick={() => deleteRow(row.id)}
                      aria-label="この行を削除"
                      title="この行を削除"
                      className={`text-red-600 hover:text-red-800 ${iconButtonClasses}`}
                    >
                      <TrashIcon />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <datalist id={DECK_PATH_DATALIST_ID}>
        {deckPathOptions.map((path) => (
          <option key={path} value={path} />
        ))}
      </datalist>

      <button
        type="button"
        onClick={addRow}
        className={`mt-2 flex items-center gap-1 ${secondaryButtonClasses}`}
      >
        <PlusIcon />
        行を追加
      </button>
    </div>
  )
}
