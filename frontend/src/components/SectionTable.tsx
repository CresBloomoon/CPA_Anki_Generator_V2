import { useEffect, useRef, useState } from 'react'
import { PlusIcon, TrashIcon } from './icons'
import { createId } from '../utils/id'
import {
  checkboxClasses,
  iconButtonClasses,
  secondaryButtonClasses,
  tableFieldClasses,
} from '../styles'

// This component owns the shape of a row (SectionRow), not just the
// backend's ScanResponse shape: `id` (for stable React keys and immutable
// updates) and `selected` (a UI-only concern -- see CLAUDE.md) exist only
// here, never on the wire.
export interface SectionRow {
  id: string
  selected: boolean
  title: string
  start_page: number
  end_page: number | null
  deck_path: string
  source_file: string
}

interface SectionTableProps {
  rows: SectionRow[]
  onRowsChange: (rows: SectionRow[]) => void
  sourceFileOptions: string[]
}

const DECK_PATH_DATALIST_ID = 'section-table-deck-path-options'

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
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-gray-100">
                <td className="p-2">
                  <input
                    type="checkbox"
                    checked={row.selected}
                    onChange={(event) =>
                      updateRow(row.id, { selected: event.target.checked })
                    }
                    className={checkboxClasses}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="text"
                    value={row.title}
                    onChange={(event) =>
                      updateRow(row.id, { title: event.target.value })
                    }
                    className={`w-full ${tableFieldClasses}`}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="number"
                    min={1}
                    value={row.start_page}
                    onChange={(event) =>
                      updateRow(row.id, {
                        start_page: Number(event.target.value),
                      })
                    }
                    className={`w-full ${tableFieldClasses}`}
                  />
                </td>
                <td className="p-2">
                  <input
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
                    placeholder="(文末まで)"
                    className={`w-full ${tableFieldClasses}`}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="text"
                    list={DECK_PATH_DATALIST_ID}
                    value={row.deck_path}
                    onChange={(event) =>
                      updateRow(row.id, { deck_path: event.target.value })
                    }
                    className={`w-full ${tableFieldClasses}`}
                  />
                </td>
                <td className="p-2">
                  <select
                    value={row.source_file}
                    onChange={(event) =>
                      updateRow(row.id, { source_file: event.target.value })
                    }
                    className={`w-full ${tableFieldClasses}`}
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
            ))}
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
