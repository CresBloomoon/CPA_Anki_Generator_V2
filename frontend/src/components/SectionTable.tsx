import { useEffect, useRef } from 'react'
import { PlusIcon, TrashIcon } from './icons'
import { createId } from '../utils/id'

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
        <table className="w-full min-w-max border-collapse text-sm">
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
                />
              </th>
              <th className="p-2">節タイトル</th>
              <th className="p-2">開始ページ</th>
              <th className="p-2">終了ページ</th>
              <th className="p-2">出力デッキ名</th>
              <th className="p-2">ソースファイル</th>
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
                  />
                </td>
                <td className="p-2">
                  <input
                    type="text"
                    value={row.title}
                    onChange={(event) =>
                      updateRow(row.id, { title: event.target.value })
                    }
                    className="w-48 rounded border border-gray-300 px-1 py-0.5"
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
                    className="w-20 rounded border border-gray-300 px-1 py-0.5"
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
                    className="w-24 rounded border border-gray-300 px-1 py-0.5"
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
                    className="w-64 rounded border border-gray-300 px-1 py-0.5"
                  />
                </td>
                <td className="p-2">
                  <select
                    value={row.source_file}
                    onChange={(event) =>
                      updateRow(row.id, { source_file: event.target.value })
                    }
                    className="rounded border border-gray-300 px-1 py-0.5"
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
                    className="text-red-600 hover:text-red-800"
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
        className="mt-2 flex items-center gap-1 rounded border border-gray-300 px-3 py-1 text-sm"
      >
        <PlusIcon />
        行を追加
      </button>
    </div>
  )
}
