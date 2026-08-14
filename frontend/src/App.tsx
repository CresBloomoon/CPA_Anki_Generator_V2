import { useState } from 'react'
import { UploadPanel } from './components/UploadPanel'
import type { ScanResponse, SectionScanResult } from './api/types'

function App() {
  const [sections, setSections] = useState<SectionScanResult[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [hasScanned, setHasScanned] = useState(false)

  function handleScanComplete(result: ScanResponse) {
    setSections(result.sections)
    setWarnings(result.warnings)
    setHasScanned(true)
  }

  return (
    <div className="min-h-screen bg-white p-8 text-gray-900">
      <h1 className="mb-6 text-2xl font-semibold">CPA Anki Generator V2</h1>

      <UploadPanel onScanComplete={handleScanComplete} />

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
        ではないため、ボタンの無効化などは一切行わない。
      */}
      {hasScanned && sections.length === 0 && (
        <p className="mt-4 text-sm text-gray-500">
          セクションが見つかりませんでした。
        </p>
      )}

      {/* 暫定の簡易プレビュー。Phase5-2で編集可能なセクションテーブルに置き換える。 */}
      {sections.length > 0 && (
        <ul className="mt-4 divide-y divide-gray-200 text-sm">
          {sections.map((section, index) => (
            <li key={`${section.source_file}-${index}`} className="py-2">
              <span className="font-medium">{section.title}</span>
              {' '}
              <span className="text-gray-500">({section.deck_path})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default App
