import { useState } from 'react'
import { UploadPanel } from './components/UploadPanel'
import { SectionTable, type SectionRow } from './components/SectionTable'
import type { ScanResponse, SectionScanResult } from './api/types'
import { createId } from './utils/id'

function toSectionRow(section: SectionScanResult): SectionRow {
  return {
    id: createId(),
    selected: true,
    title: section.title,
    start_page: section.start_page,
    end_page: section.end_page,
    deck_path: section.deck_path,
    source_file: section.source_file,
  }
}

function App() {
  const [rows, setRows] = useState<SectionRow[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [uploadedSourceFiles, setUploadedSourceFiles] = useState<string[]>([])
  const [hasScanned, setHasScanned] = useState(false)

  function handleFilesUploaded(sourceFiles: string[]) {
    setUploadedSourceFiles((prev) =>
      Array.from(new Set([...prev, ...sourceFiles])),
    )
  }

  function handleScanComplete(result: ScanResponse) {
    // 追記方式: 複数回に分けてアップロード・スキャンしても、既に手動編集・
    // 追加した行を消さない(まーくんとの合意事項)。warningsは直近の
    // スキャン結果のみを表示する(過去の警告を蓄積させると、既に対応済みの
    // 警告がいつまでも残ってしまうため)。
    setRows((prev) => [...prev, ...result.sections.map(toSectionRow)])
    setWarnings(result.warnings)
    setHasScanned(true)
  }

  return (
    <div className="min-h-screen bg-white p-8 text-gray-900">
      <h1 className="mb-6 text-2xl font-semibold">CPA Anki Generator V2</h1>

      <UploadPanel
        onFilesUploaded={handleFilesUploaded}
        onScanComplete={handleScanComplete}
      />

      {warnings.length > 0 && (
        <ul className="mt-4 text-sm text-amber-700">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      {/*
        エラー(UploadPanel側のerrorステート)ともwarningsとも別枠の、
        あくまで情報提供のための空状態メッセージ。操作を妨げるもの
        ではないため、ボタンの無効化などは一切行わない。テーブルの
        「行を追加」から手動でセクションを積み上げられることも案内する。
      */}
      {hasScanned && rows.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          セクションが見つかりませんでした。下の「行を追加」から手動で入力できます。
        </p>
      )}

      <SectionTable
        rows={rows}
        onRowsChange={setRows}
        sourceFileOptions={uploadedSourceFiles}
      />
    </div>
  )
}

export default App
