import { useState } from 'react'
import { UploadPanel } from './components/UploadPanel'
import { SectionTable, type SectionRow } from './components/SectionTable'
import { GenerationProgress } from './components/GenerationProgress'
import { DownloadButton } from './components/DownloadButton'
import type {
  GenerationJobStatusResponse,
  ScanResponse,
  SectionScanResult,
} from './api/types'
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

// "生成中" = まだ完了しておらず、かつ1件も失敗していない状態。
// 一部のセクションが失敗すると StartGenerationJobUsecase.run() がそこで
// 処理を打ち切り、残りは永遠にPENDINGのまま止まる(Phase3-3の設計)。
// この状態は「未完了」ではあるが実質的には停止済みなので、生成中とは
// 扱わない(扱うとリセット手段が無くなり、ページリロードしか復帰方法が
// 無くなってしまう)。
function isGenerating(status: GenerationJobStatusResponse | null): boolean {
  if (!status) return false
  if (status.is_complete) return false
  const hasFailure = status.section_jobs.some(
    (sectionJob) => sectionJob.status === 'FAILED',
  )
  return !hasFailure
}

function App() {
  const [rows, setRows] = useState<SectionRow[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [uploadedSourceFiles, setUploadedSourceFiles] = useState<string[]>([])
  const [hasScanned, setHasScanned] = useState(false)
  const [generationStatus, setGenerationStatus] =
    useState<GenerationJobStatusResponse | null>(null)
  // Bumped on reset; used (with a distinct prefix per component -- see
  // below) as `key` for UploadPanel/GenerationProgress so React fully
  // remounts them, clearing their internal state (including
  // GenerationProgress's polling interval, via its effect cleanup) without
  // this component needing to know what's inside either of them. A shared
  // bare `resetKey` here previously caused two *sibling* elements to carry
  // the same key, which React silently mishandled (duplicated DOM instead
  // of cleanly remounting) -- hence the "upload-"/"progress-" prefixes.
  const [resetKey, setResetKey] = useState(0)

  function handleFilesUploaded(sourceFiles: string[]) {
    setUploadedSourceFiles((prev) =>
      Array.from(new Set([...prev, ...sourceFiles])),
    )
  }

  function handleReset() {
    setRows([])
    setWarnings([])
    setUploadedSourceFiles([])
    setHasScanned(false)
    setGenerationStatus(null)
    setResetKey((prev) => prev + 1)
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
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">CPA Anki Generator V2</h1>
        <button
          type="button"
          onClick={handleReset}
          disabled={isGenerating(generationStatus)}
          title={
            isGenerating(generationStatus)
              ? '生成が完了するまでリセットできません'
              : undefined
          }
          className="rounded border border-gray-300 px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          リセット
        </button>
      </div>

      <UploadPanel
        key={`upload-${resetKey}`}
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

      <GenerationProgress
        key={`progress-${resetKey}`}
        rows={rows}
        onStatusChange={setGenerationStatus}
      />

      <DownloadButton status={generationStatus} />
    </div>
  )
}

export default App
